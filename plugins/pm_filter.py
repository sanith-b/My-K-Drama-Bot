import asyncio
import re
import ast
import math
import random
import pytz
from datetime import datetime, timedelta, date, time
lock = asyncio.Lock()
from database.users_chats_db import db
from database.refer import referdb
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
import pyrogram
from info import *
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, WebAppInfo
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid, MessageNotModified
from utils import *
from fuzzywuzzy import process
from database.users_chats_db import db
from database.ia_filterdb import Media, Media2, get_file_details, get_search_results, get_bad_files
from logging_helper import LOGGER
from urllib.parse import quote_plus
from Lucia.util.file_properties import get_name, get_hash, get_media_file_size
from database.topdb import silentdb
import requests
import string
import tracemalloc
import random
import logging
from urllib.parse import quote
import json
from collections import defaultdict
from typing import List, Tuple, Optional
#
REFERRAL_IMAGE_URL = "https://files.catbox.moe/nqvowv.jpg"
SHARE_TEXT = "Hello! Experience a bot that offers a vast library of unlimited movies and series. 😃"
FEATURE_FLAGS = {
    "smart_search": True,
    "bookmarks": True, 
    "search_history": True,
    "auto_refresh": True,
    "bulk_operations": True,
    "advanced_filters": True,
    "user_preferences": True,
    "analytics": True
}
ENHANCED_QUALITIES = [
    "4K", "2160p", "1080p", "720p", "480p", "360p",
    "HDR", "BluRay", "WEBRip", "HDTV", "DVDRip", "CAM"
]

# Season patterns for better detection
SEASON_PATTERNS = [
    r"S(\d{1,2})", r"Season\s*(\d{1,2})", r"series\s*(\d{1,2})",
    r"S(\d{1,2})E(\d{1,2})", r"(\d{1,2})x(\d{1,2})"
]

# File type categories
FILE_CATEGORIES = {
    "movies": ["movie", "film", "cinema"],
    "tv_shows": ["episode", "series", "season", "tv"],
    "documentaries": ["documentary", "docs", "national geographic"],
    "anime": ["anime", "manga", "japanese"]
}
#
user_sessions = defaultdict(dict)
search_analytics = defaultdict(list)
user_bookmarks = defaultdict(set)
search_history = defaultdict(list)

tracemalloc.start()

TIMEZONE = "Asia/Kolkata"
BUTTON = {}
BUTTONS = {}
FRESH = {}
SPELL_CHECK = {}

LOGGER = logging.getLogger(__name__)

async def handle_emoji_reaction(message):
    """Handle emoji reactions if enabled"""
    if EMOJI_MODE:
        try:
            await message.react(emoji=random.choice(REACTIONS))
        except Exception as e:
            LOGGER.debug(f"Failed to react with emoji: {e}")

async def check_maintenance_mode(client, message, user_id):
    """Check if bot is in maintenance mode and handle accordingly"""
    maintenance_mode = await db.get_maintenance_status(client.me.id)
    if maintenance_mode and user_id not in ADMINS:
        await message.reply_text(
            "🚧 Currently upgrading… Will return soon 🔜", 
            disable_web_page_preview=True
        )
        return True
    return False

async def has_links(text):
    """Check if message contains links"""
    return bool(re.search(r'https?://\S+|www\.\S+|t\.me/\S+', text))

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    """Handle group messages with filtering functionality"""
    try:
        # Handle emoji reactions
        await handle_emoji_reaction(message)
        
        # Check maintenance mode
        if await check_maintenance_mode(client, message, message.from_user.id):
            return
        
        # Update message statistics
        await silentdb.update_top_messages(message.from_user.id, message.text)
        
        # Handle support chat differently
        if message.chat.id == SUPPORT_CHAT_ID:
            await handle_support_chat_message(client, message)
        else:
            await handle_regular_group_message(client, message)
            
    except Exception as e:
        LOGGER.error(f"Error in give_filter: {e}")

async def handle_support_chat_message(client, message):
    """Handle messages in support chat"""
    search = message.text
    temp_files, temp_offset, total_results = await get_search_results(
        chat_id=message.chat.id, 
        query=search.lower(), 
        offset=0, 
        filter=True
    )
    
    if total_results > 0:
        response_text = (
            f"<b>✨ Hello {message.from_user.mention}!\n\n"
            f"✅ Your request is already available.\n"
            f"📂 Files found: {total_results}\n"
            f"🔍 Search: <code>{search}</code>\n"
            f"‼️ This is a <u>support group</u>, so you can't get files from here.\n\n"
            f"📝 Search Here 👇</b>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Join & Explore 🔍", url=GRP_LNK)]
        ])
        await message.reply_text(response_text, reply_markup=keyboard)

async def handle_regular_group_message(client, message):
    """Handle messages in regular groups"""
    settings = await get_settings(message.chat.id)
    
    if settings['auto_ffilter']:
        # Check for links and delete if not from admin
        if await has_links(message.text):
            if not await is_check_admin(client, message.chat.id, message.from_user.id):
                await message.delete()
                return
        
        # Run auto filter
        await auto_filter(client, message)

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_text(client, message):
    """Handle private messages"""
    try:
        user_id = message.from_user.id
        content = message.text
        
        # Skip commands
        if content.startswith(("/", "#")):
            return
        
        # Handle emoji reactions
        await handle_emoji_reaction(message)
        
        # Check maintenance mode
        if await check_maintenance_mode(client, message, user_id):
            return
        
        # Update message statistics
        await silentdb.update_top_messages(user_id, content)
        
        # Handle PM search based on settings
        pm_search = await db.pm_search_status(client.me.id)
        
        if pm_search:
            await auto_filter(client, message)
        else:
            await send_redirect_message(message)
            
    except Exception as e:
        LOGGER.error(f"Error in pm_text: {e}")

async def send_redirect_message(message):
    """Send redirect message for PM users"""
    response_text = "<b><i>⚠️ Not available here! Join & search below 👇</i></b>"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Start Search", url=GRP_LNK)]
    ])
    await message.reply_text(text=response_text, reply_markup=keyboard)

# Additional utility functions for better error handling and logging
async def safe_delete_message(message):
    """Safely delete a message with error handling"""
    try:
        await message.delete()
    except Exception as e:
        LOGGER.warning(f"Failed to delete message: {e}")

async def safe_reply(message, text, **kwargs):
    """Safely reply to a message with error handling"""
    try:
        return await message.reply_text(text, **kwargs)
    except Exception as e:
        LOGGER.error(f"Failed to send reply: {e}")
        return None
		
async def get_user_refer_points(user_id):
    """Get user referral points with error handling"""
    try:
        return await referdb.get_refer_points(user_id) if hasattr(referdb, 'get_refer_points') else referdb.get_refer_points(user_id)
    except Exception as e:
        LOGGER.error(f"Failed to get referral points for user {user_id}: {e}")
        return 0

def create_referral_link(bot_username, user_id):
    """Create referral link for sharing"""
    return f"https://t.me/{bot_username}?start=reff_{user_id}"

def create_share_link(bot_username, user_id, share_text):
    """Create Telegram share link with pre-filled text"""
    encoded_text = quote(share_text)
    referral_url = quote(create_referral_link(bot_username, user_id))
    return f"https://telegram.me/share/url?url={referral_url}&text={encoded_text}"

async def create_referral_keyboard(bot_username, user_id):
    """Create inline keyboard for referral interface"""
    try:
        refer_points = await get_user_refer_points(user_id)
        share_link = create_share_link(bot_username, user_id, SHARE_TEXT)
        
        keyboard = [
            [
                InlineKeyboardButton('🔗 Invite Link', url=share_link),
                InlineKeyboardButton(f'⏳ {refer_points}', callback_data='ref_point')
            ],
            [
                InlineKeyboardButton('⬅️ Back', callback_data='premium')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    except Exception as e:
        LOGGER.error(f"Failed to create referral keyboard: {e}")
        # Return basic keyboard on error
        return InlineKeyboardMarkup([
            [InlineKeyboardButton('⬅️ Back', callback_data='premium')]
        ])

@Client.on_callback_query(filters.regex(r"^reffff"))
async def refercall(bot, query):
    """Handle referral callback queries"""
    try:
        user_id = query.from_user.id
        bot_username = bot.me.username
        
        # Create referral link and keyboard
        referral_link = create_referral_link(bot_username, user_id)
        reply_markup = await create_referral_keyboard(bot_username, user_id)
        
        # Prepare message content
        message_text = (
            f"🎉 <b>Your Referral Link:</b>\n"
            f"🔗 <code>{referral_link}</code>\n\n"
            f"👥 <i>Share with friends to earn rewards!</i>"
        )
        
        # Check if message has media to decide edit method
        if query.message.photo or query.message.video or query.message.document:
            # Edit media message
            await edit_media_message(bot, query, message_text, reply_markup)
        else:
            # Edit text message
            await edit_text_message(query, message_text, reply_markup)
            
        await query.answer("🎉 Referral link ready!")
        
    except Exception as e:
        LOGGER.error(f"Error in refercall handler: {e}")
        await query.answer("❌ Something went wrong. Please try again.", show_alert=True)

async def edit_media_message(bot, query, text, reply_markup):
    """Edit message with media content"""
    try:
        # First edit the media
        await bot.edit_message_media(
            chat_id=query.message.chat.id,
            message_id=query.message.id,
            media=InputMediaPhoto(
                media=REFERRAL_IMAGE_URL,
                caption=text,
                parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=reply_markup
        )
    except Exception as e:
        LOGGER.error(f"Failed to edit media message: {e}")
        # Fallback to editing caption only
        try:
            await query.message.edit_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as fallback_error:
            LOGGER.error(f"Fallback caption edit failed: {fallback_error}")
            raise

async def edit_text_message(query, text, reply_markup):
    """Edit text-only message"""
    try:
        await query.message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        LOGGER.error(f"Failed to edit text message: {e}")
        raise

# Additional callback handler for referral points display
@Client.on_callback_query(filters.regex(r"^ref_point$"))
async def show_referral_stats(bot, query):
    """Show detailed referral statistics"""
    try:
        user_id = query.from_user.id
        refer_points = await get_user_refer_points(user_id)
        
        stats_text = (
            f"📊 <b>Your Referral Stats:</b>\n\n"
            f"⏳ <b>Current Points:</b> {refer_points}\n"
            f"🎯 <b>How to earn more:</b>\n"
            f"• Share your referral link\n"
            f"• Get friends to join using your link\n"
            f"• Earn rewards for each successful referral!"
        )
        
        await query.answer(stats_text, show_alert=True)
        
    except Exception as e:
        LOGGER.error(f"Error showing referral stats: {e}")
        await query.answer("❌ Unable to load stats", show_alert=True)

# Utility function for referral tracking (bonus feature)
async def track_referral_usage(user_id, action="view"):
    """Track referral link usage for analytics"""
    try:
        # This would log to your analytics system
        LOGGER.info(f"Referral {action} by user {user_id}")
        # You could extend this to save to database for analytics
    except Exception as e:
        LOGGER.error(f"Failed to track referral {action}: {e}")


@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    try:
        ident, req, key, offset = query.data.split("_")
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        
        # Feature 1: Rate limiting check
        user_id = query.from_user.id
        current_time = time.time()
        if hasattr(temp, 'USER_LAST_REQUEST'):
            if user_id in temp.USER_LAST_REQUEST:
                if current_time - temp.USER_LAST_REQUEST[user_id] < 1:  # 1 second cooldown
                    return await query.answer("⏰ Please wait a moment before navigating!", show_alert=True)
        else:
            temp.USER_LAST_REQUEST = {}
        temp.USER_LAST_REQUEST[user_id] = current_time
        
        if int(req) not in [query.from_user.id, 0]:
            return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        
        try:
            offset = int(offset)
        except:
            offset = 0
            
        if BUTTONS.get(key)!=None:
            search = BUTTONS.get(key)
        else:
            search = FRESH.get(key)
            
        if not search:
            await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
            return
            
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=offset, filter=True)
        
        try:
            n_offset = int(n_offset)
        except:
            n_offset = 0
            
        if not files:
            return
            
        temp.GETALL[key] = files
        temp.SHORT[query.from_user.id] = query.message.chat.id
        settings = await get_settings(query.message.chat.id)
        
        # Feature 2: Sort options
        sort_option = settings.get('sort', 'name')  # default sort by name
        if sort_option == 'size':
            files.sort(key=lambda x: x.file_size, reverse=True)
        elif sort_option == 'date':
            files.sort(key=lambda x: getattr(x, 'date', 0), reverse=True)
        else:  # name
            files.sort(key=lambda x: x.file_name.lower())
        
        if settings.get('button'):
            btn = []
            
            # Feature 3: Enhanced file buttons with emojis
            for file in files:
                file_ext = file.file_name.split('.')[-1].lower()
                emoji = get_file_emoji(file_ext)
                size_text = silent_size(file.file_size)
                
                # Feature 4: Truncate long filenames
                display_name = clean_filename(file.file_name)
                if len(display_name) > 35:
                    display_name = display_name[:32] + "..."
                
                btn.append([
                    InlineKeyboardButton(
                        text=f"{emoji} {size_text} | {extract_tag(file.file_name)} {display_name}", 
                        callback_data=f'file#{file.file_id}'
                    )
                ])
            
            # Feature 5: Enhanced action buttons
            btn.insert(0, [
                InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                InlineKeyboardButton("🗓️ Season", callback_data=f"seasons#{key}#0"),
                InlineKeyboardButton("🔄 Sort", callback_data=f"sort#{key}#0")  # New sort button
            ])
            
            btn.insert(1, [
                InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}"),
                InlineKeyboardButton("📊 Stats", callback_data=f"stats#{key}")  # New stats button
            ])
            
            # Feature 6: Quick navigation for large result sets
            if total > 50:
                btn.insert(2, [
                    InlineKeyboardButton("⏮️ First", callback_data=f"next_{req}_{key}_0"),
                    InlineKeyboardButton("⏭️ Last", callback_data=f"next_{req}_{key}_{((total-1)//10)*10}")
                ])
        else:
            btn = []
            btn.insert(0, [
                InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                InlineKeyboardButton("🗓️ Season", callback_data=f"seasons#{key}#0"),
                InlineKeyboardButton("🔄 Sort", callback_data=f"sort#{key}#0")
            ])
            btn.insert(1, [
                InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}"),
                InlineKeyboardButton("📊 Stats", callback_data=f"stats#{key}")
            ])
            
            # Quick navigation for non-button mode too
            if total > 50:
                btn.insert(2, [
                    InlineKeyboardButton("⏮️ First", callback_data=f"next_{req}_{key}_0"),
                    InlineKeyboardButton("⏭️ Last", callback_data=f"next_{req}_{key}_{((total-1)//10)*10}")
                ])
        
        # Existing pagination logic with enhancements
        try:
            if settings['max_btn']:
                if 0 < offset <= 10:
                    off_set = 0
                elif offset == 0:
                    off_set = None
                else:
                    off_set = offset - 10
                    
                current_page = math.ceil(int(offset)/10)+1
                total_pages = math.ceil(total/10)
                
                if n_offset == 0:
                    btn.append([
                        InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"), 
                        InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="pages")
                    ])
                elif off_set is None:
                    btn.append([
                        InlineKeyboardButton("📄 Page", callback_data="pages"), 
                        InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="pages"), 
                        InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
                    ])
                else:
                    btn.append([
                        InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"),
                        InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="pages"),
                        InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
                    ])
            else:
                if 0 < offset <= int(MAX_B_TN):
                    off_set = 0
                elif offset == 0:
                    off_set = None
                else:
                    off_set = offset - int(MAX_B_TN)
                    
                current_page = math.ceil(int(offset)/int(MAX_B_TN))+1
                total_pages = math.ceil(total/int(MAX_B_TN))
                
                if n_offset == 0:
                    btn.append([
                        InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"), 
                        InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="pages")
                    ])
                elif off_set is None:
                    btn.append([
                        InlineKeyboardButton("📄 Page", callback_data="pages"), 
                        InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="pages"), 
                        InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
                    ])
                else:
                    btn.append([
                        InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"),
                        InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="pages"),
                        InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
                    ])
        except KeyError:
            await save_group_settings(query.message.chat.id, 'max_btn', True)
            # Default pagination logic here (same as above with max_btn=True)
            if 0 < offset <= 10:
                off_set = 0
            elif offset == 0:
                off_set = None
            else:
                off_set = offset - 10
                
            current_page = math.ceil(int(offset)/10)+1
            total_pages = math.ceil(total/10)
            
            if n_offset == 0:
                btn.append([
                    InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"), 
                    InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="pages")
                ])
            elif off_set is None:
                btn.append([
                    InlineKeyboardButton("📄 Page", callback_data="pages"), 
                    InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="pages"), 
                    InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
                ])
            else:
                btn.append([
                    InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"),
                    InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="pages"),
                    InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
                ])
        
        # Feature 7: Loading indicator
        await query.answer("🔄 Loading...", show_alert=False)
        
        if not settings.get('button'):
            cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
            time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
            remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
            
            # Feature 8: Enhanced caption with more info
            cap = await get_enhanced_cap(settings, remaining_seconds, files, query, total, search, offset, sort_option)
            
            try:
                await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
        else:
            try:
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except MessageNotModified:
                pass
                
    except Exception as e:
        LOGGER.error(f"Error In Next Function - {e}")
        await query.answer("❌ Something went wrong! Please try again.", show_alert=True)


# Feature 2: Helper function for file emojis
def get_file_emoji(file_ext):
    """Return appropriate emoji for file type"""
    emoji_map = {
        'mp4': '🎬', 'avi': '🎬', 'mkv': '🎬', 'mov': '🎬', 'wmv': '🎬',
        'mp3': '🎵', 'flac': '🎵', 'wav': '🎵', 'aac': '🎵',
        'pdf': '📄', 'doc': '📄', 'docx': '📄', 'txt': '📄',
        'zip': '📦', 'rar': '📦', '7z': '📦', 'tar': '📦',
        'jpg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'jpeg': '🖼️',
        'apk': '📱', 'exe': '💻', 'dmg': '💻'
    }
    return emoji_map.get(file_ext, '📁')


# Feature 8: Enhanced caption function
async def get_enhanced_cap(settings, remaining_seconds, files, query, total, search, offset, sort_option):
    """Generate enhanced caption with additional information"""
    cap = await get_cap(settings, remaining_seconds, files, query, total, search, offset)
    
    # Add sorting info
    sort_text = {
        'name': '📝 Name',
        'size': '📊 Size', 
        'date': '📅 Date'
    }
    
    # Add additional stats
    total_size = sum(file.file_size for file in files if hasattr(file, 'file_size'))
    avg_size = total_size / len(files) if files else 0
    
    enhanced_info = f"\n\n📈 <b>Stats:</b>\n"
    enhanced_info += f"🔍 Sorted by: {sort_text.get(sort_option, '📝 Name')}\n"
    enhanced_info += f"📦 Total Size: {silent_size(total_size)}\n"
    enhanced_info += f"📊 Avg Size: {silent_size(avg_size)}\n"
    enhanced_info += f"⏱️ Response Time: {remaining_seconds}s"
    
    return cap + enhanced_info

@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_cb_handler(client: Client, query: CallbackQuery):
    """Handle quality selection callback"""
    try:
        # Validate user permission
        if not await handler.validate_user_permission(query):
            return
        
        # Parse callback data
        _, key, offset = query.data.split("#")
        offset = int(offset)
        
        # Get search term and prepare for display
        search = FRESH.get(key, "").replace(' ', '_')
        
        # Create quality buttons
        buttons = handler.create_quality_buttons(QUALITIES, key, offset)
        
        # Update message with new buttons
        await query.edit_message_reply_markup(InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        LOGGER.error(f"Error in quality callback handler: {e}")
        await query.answer("An error occurred. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^fq#"))
async def filter_qualities_cb_handler(client: Client, query: CallbackQuery):
    """Handle quality filter callback"""
    try:
        # Validate user permission
        if not await handler.validate_user_permission(query):
            return
        
        # Parse callback data
        _, qual, key, offset = query.data.split("#")
        offset = int(offset)
        curr_time = datetime.now(handler.timezone).time()
        
        # Process search term
        search = FRESH.get(key, "")
        search = handler.process_search_term(search, qual, homepage=(qual == "homepage"))
        
        # Update search cache
        BUTTONS[key] = search
        
        # Get search results
        chat_id = query.message.chat.id
        files, n_offset, total_results = await get_search_results(
            chat_id, search, offset=offset, filter=True
        )
        
        if not files:
            await query.answer("⚡ Sorry, nothing was found!", show_alert=True)
            return
        
        # Cache results
        temp.GETALL[key] = files
        
        # Get settings and create buttons
        settings = await get_settings(query.message.chat.id)
        req = query.from_user.id
        buttons = handler.create_file_buttons(files, key, settings, total_results, req, n_offset)
        
        # Update message
        if settings.get('button'):
            try:
                await query.edit_message_reply_markup(InlineKeyboardMarkup(buttons))
            except MessageNotModified:
                pass
        else:
            # Calculate time difference and get caption
            remaining_seconds = handler.calculate_time_difference(curr_time)
            cap = await get_cap(settings, remaining_seconds, files, query, total_results, search, offset)
            
            try:
                await query.message.edit_text(
                    text=cap,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True
                )
            except MessageNotModified:
                pass
        
        await query.answer()
        
    except Exception as e:
        LOGGER.error(f"Error in quality filter handler: {e}")
        await query.answer("An error occurred. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^seasons#"))
async def season_cb_handler(client: Client, query: CallbackQuery):
    """Handle season selection callback"""
    try:
        # Validate user permission
        if not await handler.validate_user_permission(query):
            return
        
        # Parse callback data
        _, key, offset = query.data.split("#")
        offset = int(offset)
        
        # Get search term and prepare for display
        search = FRESH.get(key, "").replace(' ', '_')
        
        # Create season buttons
        buttons = handler.create_season_buttons(SEASONS, key, offset)
        
        # Update message with new buttons
        await query.edit_message_reply_markup(InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        LOGGER.error(f"Error in season callback handler: {e}")
        await query.answer("An error occurred. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^fs#"))
async def filter_season_cb_handler(client: Client, query: CallbackQuery):
    """Handle season filter callback"""
    try:
        # Validate user permission
        if not await handler.validate_user_permission(query):
            return
        
        # Parse callback data
        _, seas, key, offset = query.data.split("#")
        offset = int(offset)
        curr_time = datetime.now(handler.timezone).time()
        
        # Process search term
        search = FRESH.get(key, "")
        search = handler.process_search_term(search, seas, homepage=(seas == "homepage"))
        
        # Update search cache
        BUTTONS[key] = search
        
        # Get search results
        chat_id = query.message.chat.id
        files, n_offset, total_results = await get_search_results(
            chat_id, search, offset=offset, filter=True
        )
        
        if not files:
            await query.answer("⚡ Sorry, nothing was found!", show_alert=True)
            return
        
        # Cache results
        temp.GETALL[key] = files
        
        # Get settings and create buttons
        settings = await get_settings(query.message.chat.id)
        req = query.from_user.id
        buttons = handler.create_file_buttons(files, key, settings, total_results, req, n_offset)
        
        # Update message
        if settings.get('button'):
            try:
                await query.edit_message_reply_markup(InlineKeyboardMarkup(buttons))
            except MessageNotModified:
                pass
        else:
            # Calculate time difference and get caption
            remaining_seconds = handler.calculate_time_difference(curr_time)
            cap = await get_cap(settings, remaining_seconds, files, query, total_results, search, offset)
            
            try:
                await query.message.edit_text(
                    text=cap,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.HTML
                )
            except MessageNotModified:
                pass
        
        await query.answer()
        
    except Exception as e:
        LOGGER.error(f"Error in season filter handler: {e}")
        await query.answer("An error occurred. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^spol"))
async def advantage_spoll_choker(bot, query):
    try:
        _, id, user = query.data.split('#')
        
        # Feature 1: Rate limiting for poll searches
        user_id = query.from_user.id
        current_time = time.time()
        if not hasattr(temp, 'SPOLL_COOLDOWN'):
            temp.SPOLL_COOLDOWN = {}
        
        if user_id in temp.SPOLL_COOLDOWN:
            if current_time - temp.SPOLL_COOLDOWN[user_id] < 3:  # 3 second cooldown
                return await query.answer("⏰ Please wait a moment before searching again!", show_alert=True)
        temp.SPOLL_COOLDOWN[user_id] = current_time
        
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        
        # Feature 2: Loading indicator with movie fetching
        await query.answer("🎬 Fetching movie details...", show_alert=False)
        
        movies = await get_poster(id, id=True)
        if not movies:
            return await query.answer("❌ Movie details not found!", show_alert=True)
        
        movie = movies.get('title')
        original_title = movie  # Store original for logging
        
        # Feature 3: Enhanced title cleaning with better regex
        movie = re.sub(r"[:\-\.\(\)\[\]{}]", " ", movie)  # Remove more special characters
        movie = re.sub(r"\b(19|20)\d{2}\b", "", movie)    # Remove years
        movie = re.sub(r"\b(hindi|english|tamil|telugu|malayalam|kannada|bengali|punjabi|marathi|gujarati)\b", "", movie, flags=re.IGNORECASE)  # Remove language names
        movie = re.sub(r"\b(dvdrip|brrip|webrip|hdtv|720p|1080p|480p|4k|hd|hdrip|cam|ts|tc)\b", "", movie, flags=re.IGNORECASE)  # Remove quality terms
        movie = re.sub(r"\s+", " ", movie).strip()
        
        # Feature 4: Alternative search terms
        search_terms = [
            movie,  # Cleaned title
            original_title,  # Original title as backup
        ]
        
        # Add partial searches for longer titles
        if len(movie.split()) > 3:
            words = movie.split()
            search_terms.append(" ".join(words[:3]))  # First 3 words
            search_terms.append(" ".join(words[-3:]))  # Last 3 words
        
        await query.answer(script.TOP_ALRT_MSG)
        
        # Feature 5: Try multiple search attempts
        files = None
        successful_search = None
        
        for search_term in search_terms:
            if len(search_term.strip()) < 2:  # Skip too short terms
                continue
                
            files, offset, total_results = await get_search_results(
                query.message.chat.id, 
                search_term, 
                offset=0, 
                filter=True
            )
            
            if files:
                successful_search = search_term
                break
        
        if files:
            # Feature 6: Add search context to results
            search_info = {
                'original_title': original_title,
                'search_term': successful_search,
                'movie_id': id,
                'poster_data': movies
            }
            
            k = (successful_search, files, offset, total_results, search_info)
            await auto_filter(bot, query, k)
            
            # Feature 7: Log successful searches for analytics
            if hasattr(temp, 'SEARCH_ANALYTICS'):
                temp.SEARCH_ANALYTICS[id] = {
                    'title': original_title,
                    'search_term': successful_search,
                    'results_count': total_results,
                    'timestamp': current_time,
                    'user_id': user_id
                }
            
        else:
            # Enhanced no results handling
            reqstr1 = query.from_user.id if query.from_user else 0
            reqstr = await bot.get_users(reqstr1)
            
            # Feature 8: Enhanced no results message with movie info
            movie_info = f"🎬 <b>{original_title}</b>\n"
            if movies.get('year'):
                movie_info += f"📅 Year: {movies.get('year')}\n"
            if movies.get('genre'):
                movie_info += f"🎭 Genre: {', '.join(movies.get('genre', [])[:3])}\n"  # Show first 3 genres
            if movies.get('rating'):
                movie_info += f"⭐ Rating: {movies.get('rating')}\n"
            
            no_results_msg = f"{movie_info}\n❌ Sorry, this movie is not available right now.\n\n🔍 <b>Search attempts:</b>\n"
            for i, term in enumerate(search_terms[:3], 1):  # Show first 3 attempts
                if term.strip():
                    no_results_msg += f"{i}. '{term}'\n"
            
            if NO_RESULTS_MSG:
                # Feature 9: Enhanced logging with movie details
                log_msg = script.NORSLTS.format(reqstr.id, reqstr.mention, original_title)
                log_msg += f"\n\n📊 <b>Search Details:</b>"
                log_msg += f"\n🆔 Movie ID: {id}"
                log_msg += f"\n🎬 Original Title: {original_title}"
                log_msg += f"\n🔍 Cleaned Title: {movie}"
                log_msg += f"\n📅 Search Time: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')}"
                
                await bot.send_message(chat_id=BIN_CHANNEL, text=log_msg)
            
            # Feature 10: Enhanced action buttons
            action_buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 Request to Admin", url=OWNER_LNK)],
                [InlineKeyboardButton("🔍 Try Manual Search", callback_data=f"manual_search#{id}#{user}")],
                [InlineKeyboardButton("📝 Suggest Alternative", callback_data=f"suggest#{id}#{user}")]
            ])
            
            k = await query.message.edit(
                text=no_results_msg,
                reply_markup=action_buttons,
                parse_mode=enums.ParseMode.HTML
            )
            
            # Feature 11: Auto-cleanup with longer delay for better UX
            await asyncio.sleep(15)  # Increased from 10 to 15 seconds
            try:
                await k.delete()
            except Exception:
                pass  # Message might already be deleted
                
    except ValueError:
        await query.answer("❌ Invalid request format!", show_alert=True)
    except Exception as e:
        LOGGER.error(f"Error in spoll handler - {e}")
        await query.answer("❌ Something went wrong! Please try again later.", show_alert=True)


# Feature 12: Helper function for manual search
@Client.on_callback_query(filters.regex(r"^manual_search"))
async def manual_search_handler(bot, query):
    try:
        _, movie_id, user = query.data.split('#')
        
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        
        movies = await get_poster(movie_id, id=True)
        title = movies.get('title', 'Unknown Movie')
        
        manual_search_msg = f"🔍 <b>Manual Search</b>\n\n"
        manual_search_msg += f"🎬 Movie: <code>{title}</code>\n\n"
        manual_search_msg += f"💡 <b>Tips for better results:</b>\n"
        manual_search_msg += f"• Try searching with just the movie name\n"
        manual_search_msg += f"• Remove year and language\n"
        manual_search_msg += f"• Try alternative spellings\n"
        manual_search_msg += f"• Search for actor/director names\n\n"
        manual_search_msg += f"👆 Just type your search query in the chat!"
        
        back_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data=f"spol#{movie_id}#{user}")]
        ])
        
        await query.message.edit(
            text=manual_search_msg,
            reply_markup=back_button,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        LOGGER.error(f"Error in manual search handler - {e}")
        await query.answer("❌ Something went wrong!", show_alert=True)


# Feature 13: Suggestion handler
@Client.on_callback_query(filters.regex(r"^suggest"))
async def suggest_handler(bot, query):
    try:
        _, movie_id, user = query.data.split('#')
        
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        
        movies = await get_poster(movie_id, id=True)
        title = movies.get('title', 'Unknown Movie')
        
        suggest_msg = f"📝 <b>Suggest Alternative</b>\n\n"
        suggest_msg += f"🎬 Original: <code>{title}</code>\n\n"
        suggest_msg += f"💡 You can suggest:\n"
        suggest_msg += f"• Alternative movie titles\n"
        suggest_msg += f"• Similar movies\n"
        suggest_msg += f"• Different language versions\n\n"
        suggest_msg += f"📩 Send your suggestion to: {OWNER_LNK}"
        
        back_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data=f"spol#{movie_id}#{user}")]
        ])
        
        await query.message.edit(
            text=suggest_msg,
            reply_markup=back_button,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        LOGGER.error(f"Error in suggest handler - {e}")
        await query.answer("❌ Something went wrong!", show_alert=True)
                
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    lazyData = query.data
    try:
        link = await client.create_chat_invite_link(int(REQST_CHANNEL))
    except:
        pass
    if query.data == "close_data":
        await query.message.delete()     
        
    if query.data.startswith("file"):
        ident, file_id = query.data.split("#")
        user = query.message.reply_to_message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}")          
                            
    elif query.data.startswith("sendfiles"):
        clicked = query.from_user.id
        ident, key = query.data.split("#") 
        settings = await get_settings(query.message.chat.id)
        try:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=allfiles_{query.message.chat.id}_{key}")
            return
        except UserIsBlocked:
            await query.answer('🔓 Unblock the Bot!', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles3_{key}")
        except Exception as e:
            logger.exception(e)
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles4_{key}")
            
    elif query.data.startswith("del"):
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('📂 File Not Exist!')
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        settings = await get_settings(query.message.chat.id)
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                LOGGER.error(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = f"{files.file_name}"
        await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=file_{file_id}")

    elif query.data == "pages":
        await query.answer()    
    
    elif query.data.startswith("killfilesdq"):
        ident, keyword = query.data.split("#")
        await query.message.edit_text(f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
        files, total = await get_bad_files(keyword)
        await query.message.edit_text("<b>ꜰɪʟᴇ ᴅᴇʟᴇᴛɪᴏɴ ᴘʀᴏᴄᴇꜱꜱ ᴡɪʟʟ ꜱᴛᴀʀᴛ ɪɴ 5 ꜱᴇᴄᴏɴᴅꜱ !</b>")
        await asyncio.sleep(5)
        deleted = 0
        async with lock:
            try:
                for file in files:
                    file_ids = file.file_id
                    file_name = file.file_name
                    result = await Media.collection.delete_one({
                        '_id': file_ids,
                    })
                    if not result.deleted_count and MULTIPLE_DB:
                        result = await Media2.collection.delete_one({
                            '_id': file_ids,
                        })
                    if result.deleted_count:
                        logger.info(f'ꜰɪʟᴇ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ {keyword}! ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ {file_name} ꜰʀᴏᴍ ᴅᴀᴛᴀʙᴀꜱᴇ.')
                    deleted += 1
                    if deleted % 20 == 0:
                        await query.message.edit_text(f"<b>ᴘʀᴏᴄᴇꜱꜱ ꜱᴛᴀʀᴛᴇᴅ ꜰᴏʀ ᴅᴇʟᴇᴛɪɴɢ ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ. ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ {str(deleted)} ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ ꜰᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ {keyword} !\n\nᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ...</b>")
            except Exception as e:
                LOGGER.error(f"Error In killfiledq -{e}")
                await query.message.edit_text(f'Error: {e}')
            else:
                await query.message.edit_text(f"<b>ᴘʀᴏᴄᴇꜱꜱ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ꜰᴏʀ ꜰɪʟᴇ ᴅᴇʟᴇᴛᴀᴛɪᴏɴ !\n\nꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ {str(deleted)} ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ ꜰᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ {keyword}.</b>")
				
    elif query.data.startswith("opnsetgrp"):
        ident, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in ADMINS
        ):
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)
            return
        title = query.message.chat.title
        settings = await get_settings(grp_id)
        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('📄 Result Page',
                                         callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}'),
                    InlineKeyboardButton('Button' if settings.get("button") else 'Text',
                                         callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('🛡️ Protected File',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["file_secure"] else '❌ Disable',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('🎬 IMDb Poster', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["imdb"] else '❌ Disable',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('👋 Welcome Message', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["welcome"] else '❌ Disable',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('🗑️ Auto Delete',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["auto_delete"] else '❌ Disable',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],		    
                [
                    InlineKeyboardButton('🔘 Max Buttons',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
                ],[
                    InlineKeyboardButton('📜 Log Channel', callback_data=f'log_setgs#{grp_id}',),
                    InlineKeyboardButton('📝 Add Caption', callback_data=f'caption_setgs#{grp_id}',),
                ],
                [
                    InlineKeyboardButton('🔒 Exit Settings', callback_data='close_data', )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_text(
                text=f"<b>⚙ Customize your {title} settings as you like!</b>",
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML
            )
            await query.message.edit_reply_markup(reply_markup)
        
    elif query.data.startswith("opnsetpm"):
        ident, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in ADMINS
        ):
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)
            return
        title = query.message.chat.title
        settings = await get_settings(grp_id)
        btn2 = [[
                 InlineKeyboardButton("📩 Check My DM!", url=f"telegram.me/{temp.U_NAME}")
               ]]
        reply_markup = InlineKeyboardMarkup(btn2)
        await query.message.edit_text(f"<b>Your settings menu for {title} has been sent to your DM!</b>")
        await query.message.edit_reply_markup(reply_markup)
        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('📄 Result Page',
                                         callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}'),
                    InlineKeyboardButton('Button' if settings.get("button") else 'Text',
                                         callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('🛡️ Protected File',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["file_secure"] else '❌ Disable',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('🎬 IMDb Poster', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["imdb"] else '❌ Disable',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('👋 Welcome Message', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["welcome"] else '❌ Disable',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('🗑️ Auto Delete',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["auto_delete"] else '❌ Disable',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('🔘 Max Buttons',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
				],
				[
                    InlineKeyboardButton('📜 Log Channel', callback_data=f'log_setgs#{grp_id}',),		
                    InlineKeyboardButton('📝 Add Caption', callback_data=f'caption_setgs#{grp_id}',),
                ],
                [
                    InlineKeyboardButton('🔒 Exit Settings', 
                                         callback_data='close_data'
                                         )
                ]
        ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await client.send_message(
                chat_id=userid,
                text=f"<b>⚙ Customize your {title} settings as you like!</b>",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=query.message.id
            )

    elif query.data.startswith("show_option"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("• ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"unavailable#{from_user}"),
                InlineKeyboardButton("• ᴜᴘʟᴏᴀᴅᴇᴅ •", callback_data=f"uploaded#{from_user}")
             ],[
                InlineKeyboardButton("• ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"already_available#{from_user}")
             ],[
                InlineKeyboardButton("• ɴᴏᴛ ʀᴇʟᴇᴀꜱᴇᴅ •", callback_data=f"Not_Released#{from_user}"),
                InlineKeyboardButton("• Type Correct Spelling •", callback_data=f"Type_Correct_Spelling#{from_user}")
             ],[
                InlineKeyboardButton("• Not Available In The Hindi •", callback_data=f"Not_Available_In_The_Hindi#{from_user}")
             ]]
        btn2 = [[
                 InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Hᴇʀᴇ ᴀʀᴇ ᴛʜᴇ ᴏᴘᴛɪᴏɴs !")
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)
        
    elif query.data.startswith("unavailable"):
        ident, from_user = query.data.split("#")
        btn = [
            [InlineKeyboardButton("• ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"unalert#{from_user}")]
        ]
        btn2 = [
            [InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
            InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")]
        ]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Uɴᴀᴠᴀɪʟᴀʙʟᴇ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=f"<b>✨ Hello! {user.mention},</b>\n\n<u>{content}</u> Hᴀs Bᴇᴇɴ Mᴀʀᴋᴇᴅ Aᴅ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ...💔\n\n#Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️",
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=f"<b>✨ Hello! {user.mention},</b>\n\n<u>{content}</u> Hᴀs Bᴇᴇɴ Mᴀʀᴋᴇᴅ Aᴅ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ...💔\n\n#Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️\n\n<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small></b>",
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
   
    elif query.data.startswith("Not_Released"):
        ident, from_user = query.data.split("#")
        btn = [[InlineKeyboardButton("📌 Not Released 📌", callback_data=f"nralert#{from_user}")]]
        btn2 = [[
            InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
            InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
        ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Nᴏᴛ Rᴇʟᴇᴀꜱᴇᴅ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>✨ Hello! {user.mention}\n\n"
                        f"<code>{content}</code>, Oops! Your request is still pending 🕊️\n\n"
                        f"Stay tuned… #ComingSoon ✨</b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>✨ Hello! {user.mention}</u>\n\n"
                        f"<b><code>{content}</code>, Oops! Your request is still pending 🕊️\n\n"
                        f"Stay tuned… #ComingSoon ✨\n\n"
                        f"<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small></b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)

    elif query.data.startswith("Type_Correct_Spelling"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("✏️ Enter Correct Spelling", callback_data=f"wsalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
                 InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("✅ Spellcheck Enabled!")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>✨ Hello! {user.mention}\n\n"
                        f"❌ Request Declined: <code>{content}</code> \n📝 Reason: Spelling error 😢✍️\n\n"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>✨ Hello! {user.mention}</u>\n\n"
                        f"<b><code>{content}</code>, Wrong spelling detected!😢\n\n"
                        f"⚠️ #Wrong_Spelling\n\n"
                        f"<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small></b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)

    elif query.data.startswith("Not_Available_In_The_Hindi"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton(" Not Available In The Hindi ", callback_data=f"hnalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
                 InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ Iɴ Hɪɴᴅɪ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>✨ Hello! {user.mention}\n\n"
                        f"Yᴏᴜʀ Rᴇǫᴜᴇsᴛ <code>{content}</code> ɪs Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ ɪɴ Hɪɴᴅɪ ʀɪɢʜᴛ ɴᴏᴡ. Sᴏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ɪᴛ\n\n"
                        f"#Hɪɴᴅɪ_ɴᴏᴛ_ᴀᴠᴀɪʟᴀʙʟᴇ ❌</b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>✨ Hello! {user.mention}</u>\n\n"
                        f"<b><code>{content}</code> ɪs Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ ɪɴ Hɪɴᴅɪ ʀɪɢʜᴛ ɴᴏᴡ. Sᴏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ɪᴛ\n\n"
                        f"#Hɪɴᴅɪ_ɴᴏᴛ_ᴀᴠᴀɪʟᴀʙʟᴇ ❌\n\n"
                        f"<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small></b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)

    elif query.data.startswith("uploaded"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("• ᴜᴘʟᴏᴀᴅᴇᴅ •", callback_data=f"upalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
                 InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
               ],[
                 InlineKeyboardButton("Search Here 🔎", url=GRP_LNK)
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Uᴘʟᴏᴀᴅᴇᴅ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>✨ Hello! {user.mention},\n\n"
                        f"<u>{content}</u> ✅ Your request has been uploaded by our moderators!\n"
                        f"💡 Kindly look in the group first.</b>\n\n"
                        f"#Uploaded ✅"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>{content}</u>\n\n"
                        f"<b>✨ Hello! {user.mention}, ✅ Your request has been uploaded by our moderators!"
                        f"💡 Kindly look in the group first.</b>\n\n"
                        f"#Uploaded ✅\n\n"
                        f"<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)

    elif query.data.startswith("already_available"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("• ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"alalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
                 InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
               ],[
                 InlineKeyboardButton("Search Here 🔎", url=GRP_LNK)
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Set successfully to Available!")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>✨ Hello! {user.mention},\n\n"
                        f"<u>{content}</u> ✅ This request is already in our bot’s database!\n"
                        f"💡 Kindly look in the group first.</b>\n\n"
                        f"🚀 Available Now!"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<b>✨ Hello! {user.mention},\n\n"
                        f"<u>{content}</u> ✅ This request is already in our bot’s database!\n"
                        f"💡 Kindly look in the group first.</b>\n\n"
                        f"🚀 Available Now!\n"
                        f"<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small></i>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)
            
    
    elif query.data.startswith("alalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, 🚀 Already uploaded – request exists!",
                show_alert=True
            )
        else:
            await query.answer("❌ Insufficient rights to perform this action!", show_alert=True)

    elif query.data.startswith("upalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, 🔼 Your request has been uploaded!",
                show_alert=True
            )
        else:
            await query.answer("❌ Insufficient rights to perform this action!", show_alert=True)

    elif query.data.startswith("unalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, Oops! This request isn’t available right now.⚠️",
                show_alert=True
            )
        else:
            await query.answer("❌ Insufficient rights to perform this action!", show_alert=True)

    elif query.data.startswith("hnalert"):
        ident, from_user = query.data.split("#")  # Hindi Not Available
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, ❌ Not available",
                show_alert=True
            )
        else:
            await query.answer("🚫 Permission denied – must be original requester", show_alert=True)

    elif query.data.startswith("nralert"):
        ident, from_user = query.data.split("#")  # Not Released
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, 🚫 Not released yet – stay tuned!",
                show_alert=True
            )
        else:
            await query.answer("❌ Action denied – youre not the original requester!", show_alert=True)

    elif query.data.startswith("wsalert"):
        ident, from_user = query.data.split("#")  # Wrong Spelling
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, ❗ Request rejected – check your spelling!",
                show_alert=True
            )
        else:
            await query.answer("❌ You don’t have permission to view this!", show_alert=True)

    
    elif lazyData.startswith("streamfile"):
        _, file_id = lazyData.split(":")
        try:
            user_id = query.from_user.id
            is_premium_user = await db.has_premium_access(user_id)
            if PAID_STREAM and not is_premium_user:
                premiumbtn = [[InlineKeyboardButton("💰 Contribute", callback_data='buy')]]
                await query.answer("<b>📌 ᴛʜɪꜱ ꜰᴇᴀᴛᴜʀᴇ ɪꜱ ᴏɴʟʏ ꜰᴏʀ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀꜱ</b>", show_alert=True)
                await query.message.reply("<b>📌 ᴛʜɪꜱ ꜰᴇᴀᴛᴜʀᴇ ɪꜱ ᴏɴʟʏ ꜰᴏʀ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀꜱ. ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ ᴛᴏ ᴀᴄᴄᴇꜱꜱ ᴛʜɪꜱ ꜰᴇᴀᴛᴜʀᴇ ✅</b>", reply_markup=InlineKeyboardMarkup(premiumbtn))
                return
            username =  query.from_user.mention 
            silent_msg = await client.send_cached_media(
                chat_id=BIN_CHANNEL,
                file_id=file_id,
            )
            fileName = {quote_plus(get_name(silent_msg))}
            silent_stream = f"{URL}watch/{str(silent_msg.id)}/{quote_plus(get_name(silent_msg))}?hash={get_hash(silent_msg)}"
            silent_download = f"{URL}{str(silent_msg.id)}/{quote_plus(get_name(silent_msg))}?hash={get_hash(silent_msg)}"
            btn= [[
                InlineKeyboardButton("𝖲𝗍𝗋𝖾𝖺𝗆", url=silent_stream),
                InlineKeyboardButton("𝖣𝗈𝗐𝗇𝗅𝗈𝖺𝖽", url=silent_download)        
	    ]]
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
	    )
            await silent_msg.reply_text(
                text=f"•• ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇᴅ ꜰᴏʀ ɪᴅ #{user_id} \n•• ᴜꜱᴇʀɴᴀᴍᴇ : {username} \n\n•• ᖴᎥᒪᗴ Nᗩᗰᗴ : {fileName}",
                quote=True,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(btn)
	    )                
        except Exception as e:
            LOGGER.error(e)
            await query.answer(f"⚠️ SOMETHING WENT WRONG \n\n{e}", show_alert=True)
            return
           
    
    elif query.data == "pagesn1":
        await query.answer(text=script.PAGE_TXT, show_alert=True)

    elif query.data == "start":
        buttons = [[
                    InlineKeyboardButton('🚀 Add Me Now!', url=f'http://telegram.me/{temp.U_NAME}?startgroup=true')
                ],[
                    InlineKeyboardButton('🔥 Trending', callback_data="topsearch"),
                    InlineKeyboardButton('💖 Support Us', callback_data="premium"),
                ],[
                    InlineKeyboardButton('🆘 Help', callback_data='disclaimer'),
                    InlineKeyboardButton('ℹ️ About', callback_data='me')
                ],[
                    InlineKeyboardButton('📞 Contact Us', callback_data="earn")
                ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
  
    elif query.data == "give_trial":
        try:
            user_id = query.from_user.id
            has_free_trial = await db.check_trial_status(user_id)
            if has_free_trial:
                await query.answer("🚸 ʏᴏᴜ'ᴠᴇ ᴀʟʀᴇᴀᴅʏ ᴄʟᴀɪᴍᴇᴅ ʏᴏᴜʀ ꜰʀᴇᴇ ᴛʀɪᴀʟ ᴏɴᴄᴇ !\n\n📌 ᴄʜᴇᴄᴋᴏᴜᴛ ᴏᴜʀ ᴘʟᴀɴꜱ ʙʏ : /plan", show_alert=True)
                return
            else:            
                await db.give_free_trial(user_id)
                await query.message.reply_text(
                    text="<b>🥳 ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴꜱ\n\n🎉 ʏᴏᴜ ᴄᴀɴ ᴜsᴇ ꜰʀᴇᴇ ᴛʀᴀɪʟ ꜰᴏʀ <u>5 ᴍɪɴᴜᴛᴇs</u> ꜰʀᴏᴍ ɴᴏᴡ !</b>",
                    quote=False,
                    disable_web_page_preview=True,                  
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💸 ᴄʜᴇᴄᴋᴏᴜᴛ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴꜱ 💸", callback_data='seeplans')]]))
                return    
        except Exception as e:
            LOGGER.error(e)

    elif query.data == "premium":
        try:
            btn = [[
                InlineKeyboardButton('💰 Contribute', callback_data='buy'),
            ],[
                InlineKeyboardButton('👥 Invite Friends', callback_data='reffff')
            ],[            
                InlineKeyboardButton('🏠 Back to Home', callback_data='start')
            ]]
            reply_markup = InlineKeyboardMarkup(btn)                        
            await client.edit_message_media(                
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(random.choice(PICS))                       
            )
            await query.message.edit_text(
                text=script.BPREMIUM_TXT,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            LOGGER.error(e)

    elif query.data == "buy":
        try:
            btn = [[ 
                InlineKeyboardButton('⭐ Star', callback_data='star'),
                InlineKeyboardButton('🚀 CRIPTO', callback_data='upi')
            ],[
                InlineKeyboardButton('⬅️ Back', callback_data='premium')
            ]]
            reply_markup = InlineKeyboardMarkup(btn)
            await client.edit_message_media(
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(SUBSCRIPTION)
	        ) 
            await query.message.edit_text(
                text=script.PREMIUM_TEXT.format(query.from_user.mention),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            ) 
        except Exception as e:
            LOGGER.error(e)

    elif query.data == "upi":
        try:
            btn = [[ 
                InlineKeyboardButton('USDT ₮', callback_data='buy'),
                InlineKeyboardButton('TON ⛛', callback_data='buy'),
                InlineKeyboardButton('BITCOIN ₿', callback_data='buy'),
            ],[
                InlineKeyboardButton('⬅️ Back', callback_data='buy')
            ]]
            reply_markup = InlineKeyboardMarkup(btn)
            await client.edit_message_media(
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(SUBSCRIPTION)
	        ) 
            await query.message.edit_text(
                text=script.PREMIUM_UPI_TEXT.format(query.from_user.mention),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            ) 
        except Exception as e:
            LOGGER.error(e)


    elif query.data == "star":
        try:
            btn = [
                InlineKeyboardButton(f"{stars}⭐", callback_data=f"buy_{stars}")
                for stars, days in STAR_PREMIUM_PLANS.items()
            ]
            buttons = [btn[i:i + 2] for i in range(0, len(btn), 2)]
            buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="buy")])
            reply_markup = InlineKeyboardMarkup(buttons)
            await client.edit_message_media(
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(random.choice(PICS))
	        ) 
            await query.message.edit_text(
                text=script.PREMIUM_STAR_TEXT,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
	    )
        except Exception as e:
            LOGGER.error(e)

    elif query.data == "earn":
        try:
            btn = [[ 
                InlineKeyboardButton('🏠 Back to Home', callback_data='start')
            ]]
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_text(
                text=script.EARN_INFO.format(temp.B_LINK),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            ) 
        except Exception as e:
            LOGGER.error(e)
                    
    elif query.data == "me":
        buttons = [[
            InlineKeyboardButton ('🌟 Features', url='https://featureskbot.vercel.app/'),
        ],[
            InlineKeyboardButton('🏠 Back to Home', callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(temp.U_NAME, temp.B_NAME, OWNER_LNK),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        

    elif query.data == "ref_point":
        await query.answer(f'You Have: {referdb.get_refer_points(query.from_user.id)} Refferal points.', show_alert=True)
    
    

    elif query.data == "disclaimer":
        try:
            btn = [[
                    InlineKeyboardButton("⬅️ Back", callback_data="start"),
                  ]]
            reply_markup = InlineKeyboardMarkup(btn)                        
            await client.edit_message_media(                
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(random.choice(PICS))                       
            )
            await query.message.edit_text(
                text=script.DISCLAIMER_TXT,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            LOGGER.error(e)
	
    elif query.data.startswith("grp_pm"):
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("💡 You must be an admin to use this", show_alert=True)
        btn = await group_setting_buttons(int(grp_id)) 
        silentx = await client.get_chat(int(grp_id))
        await query.message.edit(text=f"🔹 Modify Group Settings\nGroup Title - '{silentx.title}'</b>⚙", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("verification_setgs"):
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)

        settings = await get_settings(int(grp_id))
        verify_status = settings.get('is_verify', IS_VERIFY)
        btn = [[
            InlineKeyboardButton(f'ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ: {"ᴏɴ" if verify_status else "ᴏꜰꜰ"}', callback_data=f'toggleverify#is_verify#{verify_status}#{grp_id}'),
	],[
            InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ', callback_data=f'changeshortner#{grp_id}'),
            InlineKeyboardButton('ᴛɪᴍᴇ', callback_data=f'changetime#{grp_id}')
	],[
            InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ', callback_data=f'changetutorial#{grp_id}')
        ],[
            InlineKeyboardButton('⬅️ Back', callback_data=f'grp_pm#{grp_id}')
	]]    
        await query.message.edit("<b>🛠️ Advanced Settings Mode\n\nCustomize shortener values & verification interval here\n👇 Select an option below</b>", reply_markup=InlineKeyboardMarkup(btn))
	    

    elif query.data.startswith("log_setgs"):
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("💡 You must be an admin to use this", show_alert=True)
        btn = [[
            InlineKeyboardButton('📜 Log Channel', callback_data=f'changelog#{grp_id}'),
        ],[
            InlineKeyboardButton('⬅️ Back', callback_data=f'grp_pm#{grp_id}')
	]]    
        await query.message.edit("<b>🛠️ Advanced Settings Mode\n\nʏCustomize your Log Channel value here\n👇 Select an option below<\b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("changelog"):
        grp_id = query.data.split("#")[1]
        user_id = query.from_user.id if query.from_user else None
        silentx = await client.get_chat(int(grp_id))
        invite_link = await client.export_chat_invite_link(grp_id)
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        settings = await get_settings(int(grp_id))
        log_channel = settings.get(f'log', "⚡ No value set – using default!")    
        await query.message.edit(f'<b>📌 📜 Log Channel Details\n\n📜 Log Channel: <code>{log_channel}</code>.<b>')
        m = await query.message.reply("<b>📜 Send new Log Channel ID (e.g., -100123569303) or type /cancel to stop the process</b>") 
        while True:
            log_msg = await client.listen(chat_id=query.message.chat.id, user_id=user_id)
            if log_msg.text == "/cancel":
                await m.delete()
                btn = [
                    [InlineKeyboardButton('📜 Log Channel', callback_data=f'changelog#{grp_id}')],
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
		]            
                await query.message.edit("<b>✨ Pick a Log Channel & customize values</b>", reply_markup=InlineKeyboardMarkup(btn))
                return        
            if log_msg.text.startswith("-100") and log_msg.text[4:].isdigit() and len(log_msg.text) >= 10:
                try:
                    int(log_msg.text)
                    break 
                except ValueError:
                    await query.message.reply("<b>⚡ Channel ID not valid! Use a number starting with -100 (like -100123456789)</b>")
            else:       
                await query.message.reply("<b>⚡ Channel ID not valid! Use a number starting with -100 (like -100123456789)</b>")		
        await m.delete()	
        await save_group_settings(int(grp_id), f'log', log_msg.text)
        await client.send_message(LOG_API_CHANNEL, f"#Set_Log_Channel\n\nGroup Title : {silentx.title}\n\nɢʀᴏᴜᴘ ɪᴅ: {grp_id}\nɪɴᴠɪᴛᴇ ʟɪɴᴋ : {invite_link}\n\nᴜᴘᴅᴀᴛᴇᴅ ʙʏ : {query.from_user.username}")	    
        btn = [            
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
        ]    
        await query.message.reply(f"<b>✅ Log Channel value updated!\n📜 Log Channel: <code>{log_msg.text}</code></b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("caption_setgs"):
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        btn = [[
            InlineKeyboardButton('📝 Custom Caption', callback_data=f'changecaption#{grp_id}'),
        ],[
            InlineKeyboardButton('⬅️ Back', callback_data=f'grp_pm#{grp_id}')
	]]    
        await query.message.edit("<b>🛠️ Advanced Settings Mode\n\nYou can customize your caption values here! ✅\n👇 Select an option below</b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("changecaption"):
        grp_id = query.data.split("#")[1]
        user_id = query.from_user.id if query.from_user else None
        silentx = await client.get_chat(int(grp_id))
        invite_link = await client.export_chat_invite_link(grp_id)
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        settings = await get_settings(int(grp_id))
        current_caption = settings.get(f'caption', "No input detected, default used!")    
        await query.message.edit(f'<b>📌 Custom Caption Details\n\n🎨 Caption Here: <code>{current_caption}</code>.</b>')
        m = await query.message.reply("<b>Send New Caption\n\nCaption Format:\nFile Name -<code>{file_name}</code>\nFile Caption - <code>{file_caption}</code>\nFile Size - <code>{file_size}</code>\n\n ❌ /cancel to stop</b>") 
        caption_msg = await client.listen(chat_id=query.message.chat.id, user_id=user_id)
        if caption_msg.text == "/cancel":
            btn = [[
                InlineKeyboardButton('📝 Custom Caption', callback_data=f'changecaption#{grp_id}'),
	    ],[
                InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
            ]	
            await query.message.edit("<b>🎨 Customize caption & change values</b>", reply_markup=InlineKeyboardMarkup(btn))
            await m.delete()
            return
        await m.delete()	
        await save_group_settings(int(grp_id), f'caption', caption_msg.text)
        await client.send_message(LOG_API_CHANNEL, f"#Set_Caption\n\nGroup Title : {title}\n\nɢʀᴏᴜᴘ ɪᴅ: {grp_id}\nɪɴᴠɪᴛᴇ ʟɪɴᴋ : {invite_link}\n\nᴜᴘᴅᴀᴛᴇᴅ ʙʏ : {query.from_user.username}")	    
        btn = [            
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
        ]    
        await query.message.reply(f"<b>✅ Custom caption values updated!\n\n🎨 Caption Here: <code>{caption_msg.text}</code></b>", reply_markup=InlineKeyboardMarkup(btn))

	
    elif query.data.startswith("toggleverify"):
        _, set_type, status, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)    
        new_status = not (status == "True")
        await save_group_settings(int(grp_id), set_type, new_status)
        settings = await get_settings(int(grp_id))
        verify_status = settings.get('is_verify', IS_VERIFY)
        btn = [[
            InlineKeyboardButton(f'ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ: {"ᴏɴ" if verify_status else "ᴏꜰꜰ"}', callback_data=f'toggleverify#is_verify#{verify_status}#{grp_id}'),
	],[
            InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ', callback_data=f'changeshortner#{grp_id}'),
            InlineKeyboardButton('ᴛɪᴍᴇ', callback_data=f'changetime#{grp_id}')
	],[
            InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ', callback_data=f'changetutorial#{grp_id}')
        ],[
            InlineKeyboardButton('⬅️ Back', callback_data=f'grp_pm#{grp_id}')
	]]    
        await query.message.edit("<b>🛠️ Advanced Settings Mode\n\nCustomize shortener values & verification interval here\n👇 Select an option below</b>", reply_markup=InlineKeyboardMarkup(btn))


    elif query.data.startswith("changeshortner"):
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        btn = [
            [
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 1', callback_data=f'set_verify1#{grp_id}'),
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 2', callback_data=f'set_verify2#{grp_id}')
            ],
            [InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 3', callback_data=f'set_verify3#{grp_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
		]
        await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ꜱʜᴏʀᴛɴᴇʀ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("set_verify"):
        shortner_num = query.data.split("#")[0][-1]
        grp_id = query.data.split("#")[1]
        user_id = query.from_user.id if query.from_user else None
        silentx = await client.get_chat(int(grp_id))
        invite_link = await client.export_chat_invite_link(grp_id)
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        settings = await get_settings(int(grp_id))
        suffix = "" if shortner_num == "1" else f"_{'two' if shortner_num == '2' else 'three'}"
        current_url = settings.get(f'shortner{suffix}', "⚡ No value set – using default!")
        current_api = settings.get(f'api{suffix}', "⚡ No value set – using default!")    
        await query.message.edit(f"<b>📌 ᴅᴇᴛᴀɪʟꜱ ᴏꜰ ꜱʜᴏʀᴛɴᴇʀ {shortner_num}:\nᴡᴇʙꜱɪᴛᴇ: <code>{current_url}</code>\nᴀᴘɪ: <code>{current_api}</code></b>")
        m = await query.message.reply("<b>ꜱᴇɴᴅ ɴᴇᴡ ꜱʜᴏʀᴛɴᴇʀ ᴡᴇʙꜱɪᴛᴇ ᴏʀ ᴜꜱᴇ /cancel ᴛᴏ ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇꜱꜱ</b>") 
        url_msg = await client.listen(chat_id=query.message.chat.id, user_id=user_id)
        if url_msg.text == "/cancel":
            btn = [[
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 1', callback_data=f'set_verify1#{grp_id}'),
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 2', callback_data=f'set_verify2#{grp_id}')
            ],
            [InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 3', callback_data=f'set_verify3#{grp_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
            ]	
            await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ꜱʜᴏʀᴛɴᴇʀ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))
            await m.delete()
            return
        await m.delete()
        n = await query.message.reply("<b>ɴᴏᴡ ꜱᴇɴᴅ ꜱʜᴏʀᴛɴᴇʀ ᴀᴘɪ ᴏʀ ᴜꜱᴇ /cancel ᴛᴏ ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇꜱꜱ</b>")
        key_msg = await client.listen(chat_id=query.message.chat.id, user_id=user_id)
        if key_msg.text == "/cancel":
            btn = [[
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 1', callback_data=f'set_verify1#{grp_id}'),
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 2', callback_data=f'set_verify2#{grp_id}')
            ],
            [InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 3', callback_data=f'set_verify3#{grp_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
            ]	
            await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ꜱʜᴏʀᴛɴᴇʀ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))
            await n.delete()
            return
        await n.delete()    		
        await save_group_settings(int(grp_id), f'shortner{suffix}', url_msg.text)
        await save_group_settings(int(grp_id), f'api{suffix}', key_msg.text)
        log_message = f"#New_Shortner_Set\n\n ꜱʜᴏʀᴛɴᴇʀ ɴᴏ - {shortner_num}\nɢʀᴏᴜᴘ ʟɪɴᴋ - `{invite_link}`\n\nɢʀᴏᴜᴘ ɪᴅ : `{grp_id}`\nᴀᴅᴅᴇᴅ ʙʏ - `{user_id}`\nꜱʜᴏʀᴛɴᴇʀ ꜱɪᴛᴇ - {url_msg.text}\nꜱʜᴏʀᴛɴᴇʀ ᴀᴘɪ - `{key_msg.text}`"
        await client.send_message(LOG_API_CHANNEL, log_message, disable_web_page_preview=True)
        next_shortner = int(shortner_num) + 1 if shortner_num in ["1", "2"] else None
        btn = [
            [InlineKeyboardButton(f'ꜱʜᴏʀᴛɴᴇʀ {next_shortner}', callback_data=f'set_verify{next_shortner}#{grp_id}')] if next_shortner else [],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
        ]    
        await query.message.reply(f"<b>ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴜᴘᴅᴀᴛᴇᴅ ꜱʜᴏʀᴛɴᴇʀ {shortner_num} ᴠᴀʟᴜᴇꜱ ✅\n\nᴡᴇʙꜱɪᴛᴇ: <code>{url_msg.text}</code>\nᴀᴘɪ: <code>{key_msg.text}</code></b>", reply_markup=InlineKeyboardMarkup(btn))

    
    elif query.data.startswith("changetime"):
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        btn = [
            [
                InlineKeyboardButton('2ɴᴅ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ', callback_data=f'set_time2#{grp_id}'),
	    ],[
                InlineKeyboardButton('3ʀᴅ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ', callback_data=f'set_time3#{grp_id}')
            ],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
		]
        await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ ɢᴀᴘ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("set_time"):
        time_num = query.data.split("#")[0][-1]
        grp_id = query.data.split("#")[1]
        user_id = query.from_user.id if query.from_user else None
        silentx = await client.get_chat(int(grp_id))
        invite_link = await client.export_chat_invite_link(grp_id)
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        settings = await get_settings(int(grp_id))
        suffix = "" if time_num == "2" else "third_" if time_num == "3" else ""
        current_time = settings.get(f'{suffix}verify_time', 'Not set')
        await query.message.edit(f"<b>📌 ᴅᴇᴛᴀɪʟꜱ ᴏꜰ {time_num} ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ:\n\nᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ: {current_time}</b>")
        m = await query.message.reply("<b>ꜱᴇɴᴅ ɴᴇᴡ ᴛᴜᴛᴏʀɪᴀʟ ᴜʀʟ ᴏʀ ᴜꜱᴇ /cancel ᴛᴏ ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇꜱꜱ.</b>")        
        while True:
            time_msg = await client.listen(chat_id=query.message.chat.id, user_id=user_id)
            if time_msg.text == "/cancel":
                await m.delete()
                btn = [
                    [InlineKeyboardButton('2ɴᴅ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ', callback_data=f'set_time2#{grp_id}')],
                    [InlineKeyboardButton('3ʀᴅ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ', callback_data=f'set_time3#{grp_id}')],
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
		]   
                await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))
                return        
            if time_msg.text.isdigit() and int(time_msg.text) > 0:
                break
            else:
                await query.message.reply("<b>ɪɴᴠᴀʟɪᴅ ᴛɪᴍᴇ! ᴍᴜꜱᴛ ʙᴇ ᴀ ᴘᴏꜱɪᴛɪᴠᴇ ɴᴜᴍʙᴇʀ (ᴇxᴀᴍᴘʟᴇ: 60)</b>")
        await m.delete()
        await save_group_settings(int(grp_id), f'{suffix}verify_time', time_msg.text)
        log_message = f"#New_Time_Set\n\n ᴛɪᴍᴇ ɴᴏ - {time_num}\nɢʀᴏᴜᴘ ʟɪɴᴋ - `{invite_link}`\n\nɢʀᴏᴜᴘ ɪᴅ : `{grp_id}`\nᴀᴅᴅᴇᴅ ʙʏ - `{user_id}`\nᴛɪᴍᴇ - {time_msg.text}"
        await client.send_message(LOG_API_CHANNEL, log_message, disable_web_page_preview=True)
        next_time = int(time_num) + 1 if time_num in ["2"] else None
        btn = [
            [InlineKeyboardButton(f'{next_time} ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ', callback_data=f'set_time{next_time}#{grp_id}')] if next_time else [],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
        ]    
        await query.message.reply(f"<b>{time_num} ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ ᴜᴘᴅᴀᴛᴇ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ✅\n\nᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ: {time_msg.text}</b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("changetutorial"):
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        btn = [
            [
                InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 1', callback_data=f'set_tutorial1#{grp_id}'),
                InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 2', callback_data=f'set_tutorial2#{grp_id}')
            ],
            [InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 3', callback_data=f'set_tutorial3#{grp_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
		]
        await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ᴛᴜᴛᴏʀɪᴀʟ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("set_tutorial"):
        tutorial_num = query.data.split("#")[0][-1]
        grp_id = query.data.split("#")[1]
        user_id = query.from_user.id if query.from_user else None
        silentx = await client.get_chat(int(grp_id))
        invite_link = await client.export_chat_invite_link(grp_id)
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        settings = await get_settings(int(grp_id))
        suffix = "" if tutorial_num == "1" else f"_{'2' if tutorial_num == '2' else '3'}"
        tutorial_url = settings.get(f'tutorial{suffix}', "⚡ No value set – using default!")    
        await query.message.edit(f"<b>📌 ᴅᴇᴛᴀɪʟꜱ ᴏꜰ ᴛᴜᴛᴏʀɪᴀʟ {tutorial_num}:\n\nᴛᴜᴛᴏʀɪᴀʟ ᴜʀʟ: {tutorial_url}.</b>")
        m = await query.message.reply("<b>ꜱᴇɴᴅ ɴᴇᴡ ᴛᴜᴛᴏʀɪᴀʟ ᴜʀʟ ᴏʀ ᴜꜱᴇ /cancel ᴛᴏ ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇꜱꜱ</b>") 
        tutorial_msg = await client.listen(chat_id=query.message.chat.id, user_id=user_id)
        if tutorial_msg.text == "/cancel":
            btn = [[
                InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 1', callback_data=f'set_tutorial1#{grp_id}'),
                InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 2', callback_data=f'set_tutorial2#{grp_id}')
            ],
            [InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 3', callback_data=f'set_tutorial3#{grp_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
            ]	
            await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ᴛᴜᴛᴏʀɪᴀʟ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))
            await m.delete()
            return
        await m.delete()	
        await save_group_settings(int(grp_id), f'tutorial{suffix}', tutorial_msg.text)
        log_message = f"#New_Tutorial_Set\n\n ᴛᴜᴛᴏʀɪᴀʟ ɴᴏ - {tutorial_num}\nɢʀᴏᴜᴘ ʟɪɴᴋ - `{invite_link}`\n\nɢʀᴏᴜᴘ ɪᴅ : `{grp_id}`\nᴀᴅᴅᴇᴅ ʙʏ - `{user_id}`\nᴛᴜᴛᴏʀɪᴀʟ - {tutorial_msg.text}"
        await client.send_message(LOG_API_CHANNEL, log_message, disable_web_page_preview=True)
        next_tutorial = int(tutorial_num) + 1 if tutorial_num in ["1", "2"] else None
        btn = [
            [InlineKeyboardButton(f'ᴛᴜᴛᴏʀɪᴀʟ {next_tutorial}', callback_data=f'set_tutorial{next_tutorial}#{grp_id}')] if next_tutorial else [],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
        ]    
        await query.message.reply(f"<b>ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴜᴘᴅᴀᴛᴇᴅ ᴛᴜᴛᴏʀɪᴀʟ {tutorial_num} ᴠᴀʟᴜᴇꜱ ✅\n\nᴛᴜᴛᴏʀɪᴀʟ ᴜʀʟ: {tutorial_msg.text}</b>", reply_markup=InlineKeyboardMarkup(btn))
	    
    elif query.data.startswith("setgs"):
        ident, set_type, status, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), userid):
            await query.answer(script.ALRT_TXT, show_alert=True)
            return
        if status == "True":
            await save_group_settings(int(grp_id), set_type, False)
            await query.answer("ᴏꜰꜰ ✗")
        else:
            await save_group_settings(int(grp_id), set_type, True)
            await query.answer("ᴏɴ ✓")
        settings = await get_settings(int(grp_id))
        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('📄 Result Page',
                                         callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}'),
                    InlineKeyboardButton('Button' if settings.get("button") else 'Text',
                                         callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('🛡️ Protected File',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["file_secure"] else '❌ Disable',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('🎬 IMDb Poster', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["imdb"] else '❌ Disable',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('👋 Welcome Message', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["welcome"] else '❌ Disable',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('🗑️ Auto Delete',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Enable' if settings["auto_delete"] else '❌ Disable',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('🔘 Max Buttons',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('📜 Log Channel', callback_data=f'log_setgs#{grp_id}',),
                    InlineKeyboardButton('📝 Add Caption', callback_data=f'caption_setgs#{grp_id}',),
                ],
                [
                    InlineKeyboardButton('🔒 Exit Settings', 
                                         callback_data='close_data'
                                         )
                ]
        ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_reply_markup(reply_markup)
    await query.answer(MSG_ALRT)

    
async def auto_filter(client, msg, spoll=False):
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    if not spoll:
        message = msg
        if message.text.startswith("/"): return
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        if len(message.text) < 100:
            search = await replace_words(message.text)		
            search = search.lower()
            search = search.replace("-", " ")
            search = search.replace(":","")
            search = re.sub(r'\s+', ' ', search).strip()
            m=await message.reply_text(f'<b>🕐 Hold on... {message.from_user.mention} Searching for your query : <i>{search}...</i></b>', reply_to_message_id=message.id)
            files, offset, total_results = await get_search_results(message.chat.id ,search, offset=0, filter=True)
            settings = await get_settings(message.chat.id)
            if not files:
                if settings["spell_check"]:
                    ai_sts = await m.edit('🤖 Hang tight… AI is checking your spelling!')
                    is_misspelled = await ai_spell_check(chat_id = message.chat.id,wrong_name=search)
                    if is_misspelled:
                        await ai_sts.edit(f'<b>🔹 My pick<code> {is_misspelled}</code> \nOn the search for <code>{is_misspelled}</code></b>')
                        await asyncio.sleep(2)
                        message.text = is_misspelled
                        await ai_sts.delete()
                        return await auto_filter(client, message)
                    await ai_sts.delete()
                    return await advantage_spell_chok(client, message)
        else:
            return
    else:
        message = msg.message.reply_to_message
        search, files, offset, total_results = spoll
        m=await message.reply_text(f'<b>🕐 Hold on... {message.from_user.mention} Searching for your query :<i>{search}...</i></b>', reply_to_message_id=message.id)
        settings = await get_settings(message.chat.id)
        await msg.message.delete()
    key = f"{message.chat.id}-{message.id}"
    FRESH[key] = search
    temp.GETALL[key] = files
    temp.SHORT[message.from_user.id] = message.chat.id
    if settings.get('button'):
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{silent_size(file.file_size)}| {extract_tag(file.file_name)} {clean_filename(file.file_name)}", callback_data=f'file#{file.file_id}'
                ),
            ]
            for file in files
        ]
        btn.insert(0, 
            [
                InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                InlineKeyboardButton("🗓️ Season",  callback_data=f"seasons#{key}#0")
            ]
        )
        btn.insert(1, [
            InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}")
            
        ])
    else:
        btn = []
        btn.insert(0, 
            [
                InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                InlineKeyboardButton("🗓️ Season",  callback_data=f"seasons#{key}#0")
            ]
        )
        btn.insert(1, [
            InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}")
            
        ])
    if offset != "":
        req = message.from_user.id if message.from_user else 0
        try:
            if settings['max_btn']:
                btn.append(
                    [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{offset}")]
                )
            else:
                btn.append(
                    [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{offset}")]
                )
        except KeyError:
            await save_group_settings(message.chat.id, 'max_btn', True)
            btn.append(
                [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{offset}")]
            )
    else:
        btn.append(
            [InlineKeyboardButton(text="🚫 That’s everything!",callback_data="pages")]
        )
    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
    remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
    TEMPLATE = script.IMDB_TEMPLATE_TXT
    if imdb:
        cap = TEMPLATE.format(
            qurey=search,
            title=imdb['title'],
            votes=imdb['votes'],
            aka=imdb["aka"],
            seasons=imdb["seasons"],
            box_office=imdb['box_office'],
            localized_title=imdb['localized_title'],
            kind=imdb['kind'],
            imdb_id=imdb["imdb_id"],
            cast=imdb["cast"],
            runtime=imdb["runtime"],
            countries=imdb["countries"],
            certificates=imdb["certificates"],
            languages=imdb["languages"],
            director=imdb["director"],
            writer=imdb["writer"],
            producer=imdb["producer"],
            composer=imdb["composer"],
            cinematographer=imdb["cinematographer"],
            music_team=imdb["music_team"],
            distributors=imdb["distributors"],
            release_date=imdb['release_date'],
            year=imdb['year'],
            genres=imdb['genres'],
            poster=imdb['poster'],
            plot=imdb['plot'],
            rating=imdb['rating'],
            url=imdb['url'],
            **locals()
        )
        temp.IMDB_CAP[message.from_user.id] = cap
        if not settings.get('button'):
            for file_num, file in enumerate(files, start=1):
                cap += f"\n\n<b>{file_num}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>{get_size(file.file_size)} | {clean_filename(file.file_name)}</a></b>"
    else:
        if settings.get('button'):
            cap =f"<b><blockquote>Hey!,{message.from_user.mention}</blockquote>\n\n📂 Voilà! Your result: <code>{search}</code></b>\n\n"
        else:
            cap =f"<b><blockquote>✨ Hello!,{message.from_user.mention}</blockquote>\n\n📂 Voilà! Your result: <code>{search}</code></b>\n\n"            
            for file_num, file in enumerate(files, start=1):
                cap += f"<b>{file_num}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>{get_size(file.file_size)} | {clean_filename(file.file_name)}\n\n</a></b>"                
    if imdb and imdb.get('poster'):
        try:
            hehe = await m.edit_photo(photo=imdb.get('poster'), caption=cap, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
            try:
                if settings['auto_delete']:
                    await asyncio.sleep(DELETE_TIME)
                    await hehe.delete()
                    await message.delete()
            except KeyError:
                await save_group_settings(message.chat.id, 'auto_delete', True)
                await asyncio.sleep(DELETE_TIME)
                await hehe.delete()
                await message.delete()
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg") 
            hmm = await m.edit_photo(photo=poster, caption=cap, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
            try:
               if settings['auto_delete']:
                    await asyncio.sleep(DELETE_TIME)
                    await hmm.delete()
                    await message.delete()
            except KeyError:
                await save_group_settings(message.chat.id, 'auto_delete', True)
                await asyncio.sleep(DELETE_TIME)
                await hmm.delete()
                await message.delete()
        except Exception as e:
            LOGGER.error(e)
            fek = await m.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
            try:
                if settings['auto_delete']:
                    await asyncio.sleep(DELETE_TIME)
                    await fek.delete()
                    await message.delete()
            except KeyError:
                await save_group_settings(message.chat.id, 'auto_delete', True)
                await asyncio.sleep(DELETE_TIME)
                await fek.delete()
                await message.delete()
    else:
        fuk = await m.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
        try:
            if settings['auto_delete']:
                await asyncio.sleep(DELETE_TIME)
                await fuk.delete()
                await message.delete()
        except KeyError:
            await save_group_settings(message.chat.id, 'auto_delete', True)
            await asyncio.sleep(DELETE_TIME)
            await fuk.delete()
            await message.delete()

async def ai_spell_check(chat_id, wrong_name):
    async def search_movie(wrong_name):
        search_results = imdb.search_movie(wrong_name)
        movie_list = [movie['title'] for movie in search_results]
        return movie_list
    movie_list = await search_movie(wrong_name)
    if not movie_list:
        return
    for _ in range(5):
        closest_match = process.extractOne(wrong_name, movie_list)
        if not closest_match or closest_match[1] <= 80:
            return 
        movie = closest_match[0]
        files, offset, total_results = await get_search_results(chat_id=chat_id, query=movie)
        if files:
            return movie
        movie_list.remove(movie)

async def advantage_spell_chok(client, message):
    mv_id = message.id
    search = message.text
    chat_id = message.chat.id
    settings = await get_settings(chat_id)
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", message.text, flags=re.IGNORECASE)
    query = query.strip() + " movie"
    try:
        movies = await get_poster(search, bulk=True)
    except:
        k = await message.reply(script.I_CUDNT.format(message.from_user.mention))
        await asyncio.sleep(60)
        await k.delete()
        try:
            await message.delete()
        except:
            pass
        return
    if not movies:
        google = search.replace(" ", "+")
        button = [[
            InlineKeyboardButton("💡 Spell Check? Google it! 🔎", url=f"https://www.google.com/search?q={google}")
        ]]
        k = await message.reply_text(text=script.I_CUDNT.format(search), reply_markup=InlineKeyboardMarkup(button))
        await asyncio.sleep(60)
        await k.delete()
        try:
            await message.delete()
        except:
            pass
        return
    user = message.from_user.id if message.from_user else 0
    buttons = [[
        InlineKeyboardButton(text=movie.get('title'), callback_data=f"spol#{movie.movieID}#{user}")
    ]
        for movie in movies
    ]
    buttons.append(
        [InlineKeyboardButton(text="❌ Close", callback_data='close_data')]
    )
    d = await message.reply_text(text=script.CUDNT_FND.format(message.from_user.mention), reply_markup=InlineKeyboardMarkup(buttons), reply_to_message_id=message.id)
    await asyncio.sleep(60)
    await d.delete()
    try:
        await message.delete()
    except:
        pass
