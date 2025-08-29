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
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
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
import logging
from urllib.parse import quote

#
REFERRAL_IMAGE_URL = "https://files.catbox.moe/nqvowv.jpg"
SHARE_TEXT = "Hello! Experience a bot that offers a vast library of unlimited movies and series. 😃"
#

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


async def create_keyboard_enhanced(files, key, req, offset, n_offset, total, page_size, settings, user_id):
    """Create enhanced keyboard with new features"""
    buttons = []
    
    # Add enhanced action buttons
    buttons.extend(create_action_buttons(key))
    
    # Add file buttons with bookmark indicators if enabled
    if settings.get('button', True):
        file_buttons = create_file_buttons_enhanced(files, key, user_id)
        buttons.extend(file_buttons)
    
    # Add enhanced pagination buttons
    current_page, total_pages, prev_offset = calculate_pagination_info(
        offset, total, page_size
    )
    
    pagination_buttons = create_pagination_buttons_enhanced(
        req, key, offset, n_offset, current_page, total_pages, prev_offset
    )
    buttons.extend(pagination_buttons)
    
    return InlineKeyboardMarkup(buttons)

async def update_message_enhanced(query, settings, files, keyboard, total, search, offset):
    """Update message with enhanced features and statistics"""
    try:
        if settings.get('button', True):
            # Only update keyboard for button mode
            await query.edit_message_reply_markup(reply_markup=keyboard)
        else:
            # Enhanced caption with statistics
            remaining_seconds = calculate_time_difference()
            
            # Add enhanced statistics
            file_stats = await calculate_file_statistics(files)
            user_stats = f"\n📊 <b>Quick Stats:</b>\n{file_stats}"
            
            cap = await get_cap(settings, remaining_seconds, files, query, total, search, offset)
            enhanced_cap = cap + user_stats
            
            await query.message.edit_text(
                text=enhanced_cap,
                reply_markup=keyboard,
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML
            )
    except MessageNotModified:
        # Message content is the same, ignore this error
        pass
    except Exception as e:
        LOGGER.error(f"Failed to update enhanced message: {e}")
        raise

async def calculate_file_statistics(files):
    """Calculate and format file statistics"""
    try:import math
import logging
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified
import pytz
import asyncio
from collections import defaultdict
import json

# Assuming these are imported from your modules
# from your_modules import script, temp, BUTTONS, FRESH, get_search_results, get_settings, save_group_settings, get_cap, silent_size, extract_tag, clean_filename

LOGGER = logging.getLogger(__name__)
TIMEZONE = pytz.timezone('Asia/Kolkata')
DEFAULT_PAGE_SIZE = 10

# New feature: Analytics and rate limiting
PAGINATION_ANALYTICS = defaultdict(lambda: {
    'views': 0, 'last_access': None, 'user_agents': set(),
    'popular_queries': defaultdict(int), 'peak_hours': defaultdict(int)
})
USER_RATE_LIMIT = defaultdict(lambda: {'count': 0, 'reset_time': None})
RATE_LIMIT_MAX = 50  # Max pagination requests per hour per user

# New feature: Bookmarks and favorites
USER_BOOKMARKS = defaultdict(set)
FAVORITE_SEARCHES = defaultdict(list)

class PaginationError(Exception):
    """Custom exception for pagination errors"""
    pass

class RateLimitExceeded(Exception):
    """Exception for rate limit violations"""
    pass

class BookmarkManager:
    """Manage user bookmarks and favorites"""
    
    @staticmethod
    async def add_bookmark(user_id, file_id, file_name):
        """Add file to user bookmarks"""
        USER_BOOKMARKS[user_id].add((file_id, file_name))
        LOGGER.info(f"User {user_id} bookmarked file {file_id}")
    
    @staticmethod
    async def remove_bookmark(user_id, file_id):
        """Remove file from user bookmarks"""
        USER_BOOKMARKS[user_id] = {(fid, fname) for fid, fname in USER_BOOKMARKS[user_id] if fid != file_id}
    
    @staticmethod
    async def get_bookmarks(user_id):
        """Get user bookmarks"""
        return list(USER_BOOKMARKS[user_id])
    
    @staticmethod
    async def is_bookmarked(user_id, file_id):
        """Check if file is bookmarked"""
        return any(fid == file_id for fid, _ in USER_BOOKMARKS[user_id])

class AdvancedFilter:
    """Advanced filtering options"""
    
    @staticmethod
    async def filter_by_quality(files, quality):
        """Filter files by quality (720p, 1080p, etc.)"""
        quality_keywords = {
            '720p': ['720p', 'hd'],
            '1080p': ['1080p', 'full hd', 'fhd'],
            '4k': ['4k', '2160p', 'uhd'],
            'cam': ['cam', 'camrip', 'ts'],
            'web': ['web-dl', 'webrip', 'web']
        }
        
        if quality.lower() in quality_keywords:
            keywords = quality_keywords[quality.lower()]
            return [f for f in files if any(kw in f.file_name.lower() for kw in keywords)]
        return files
    
    @staticmethod
    async def filter_by_size(files, min_size=None, max_size=None):
        """Filter files by size range"""
        filtered = files
        if min_size:
            filtered = [f for f in filtered if f.file_size >= min_size * 1024 * 1024]  # MB to bytes
        if max_size:
            filtered = [f for f in filtered if f.file_size <= max_size * 1024 * 1024]
        return filtered
    
    @staticmethod
    async def filter_by_format(files, format_type):
        """Filter files by format (video, subtitle, etc.)"""
        format_extensions = {
            'video': ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'],
            'subtitle': ['.srt', '.vtt', '.ass', '.ssa', '.sub'],
            'audio': ['.mp3', '.aac', '.flac', '.wav', '.ogg']
        }
        
        if format_type.lower() in format_extensions:
            extensions = format_extensions[format_type.lower()]
            return [f for f in files if any(f.file_name.lower().endswith(ext) for ext in extensions)]
        return files

class SmartSort:
    """Smart sorting algorithms"""
    
    @staticmethod
    async def sort_by_relevance(files, search_query):
        """Sort files by relevance to search query"""
        def relevance_score(file):
            filename = file.file_name.lower()
            query_words = search_query.lower().split()
            score = 0
            
            # Exact match bonus
            if search_query.lower() in filename:
                score += 10
            
            # Word match scoring
            for word in query_words:
                if word in filename:
                    score += 5
            
            # File size preference (larger files often better quality)
            score += min(file.file_size / (1024 * 1024 * 100), 5)  # Max 5 points for size
            
            return score
        
        return sorted(files, key=relevance_score, reverse=True)
    
    @staticmethod
    async def sort_by_popularity(files, analytics_data=None):
        """Sort files by download/view popularity"""
        # In a real implementation, you'd have download/view stats
        # For now, sort by file size as proxy for popularity
        return sorted(files, key=lambda x: x.file_size, reverse=True)
    
    @staticmethod
    async def sort_by_date(files):
        """Sort files by upload/creation date"""
        # This would require file metadata with dates
        # For now, sort by file_id as proxy (newer files often have higher IDs)
        return sorted(files, key=lambda x: x.file_id, reverse=True)

async def check_rate_limit(user_id):
    """Check and enforce rate limiting"""
    current_time = datetime.now(TIMEZONE)
    user_data = USER_RATE_LIMIT[user_id]
    
    # Reset counter if hour has passed
    if user_data['reset_time'] is None or current_time >= user_data['reset_time']:
        user_data['count'] = 0
        user_data['reset_time'] = current_time + timedelta(hours=1)
    
    # Check if limit exceeded
    if user_data['count'] >= RATE_LIMIT_MAX:
        raise RateLimitExceeded(f"Rate limit exceeded. Try again after {user_data['reset_time'].strftime('%H:%M')}")
    
    user_data['count'] += 1

async def log_analytics(user_id, search_query, action="page_view"):
    """Log analytics data"""
    try:
        current_time = datetime.now(TIMEZONE)
        analytics = PAGINATION_ANALYTICS[user_id]
        
        analytics['views'] += 1
        analytics['last_access'] = current_time
        analytics['popular_queries'][search_query] += 1
        analytics['peak_hours'][current_time.hour] += 1
        
        # Log to file or database in production
        LOGGER.info(f"Analytics: User {user_id}, Action: {action}, Query: {search_query}")
    except Exception as e:
        LOGGER.warning(f"Analytics logging failed: {e}")

def parse_callback_data(callback_data):
    """Parse and validate callback data"""
    try:
        parts = callback_data.split("_")
        if len(parts) != 4:
            raise ValueError("Invalid callback data format")
        
        ident, req, key, offset = parts
        req = int(req)
        offset = int(offset) if offset != 'None' else 0
        
        return ident, req, key, offset
    except (ValueError, IndexError) as e:
        raise PaginationError(f"Invalid callback data: {e}")

def validate_user_permission(query_user_id, required_user_id):
    """Check if user has permission to use pagination"""
    return required_user_id in [query_user_id, 0]

async def get_search_query(key):
    """Get search query from buttons or fresh cache"""
    search = BUTTONS.get(key) or FRESH.get(key)
    if not search:
        raise PaginationError("Search query not found or expired")
    return search

def calculate_pagination_info(offset, total, page_size):
    """Calculate pagination information"""
    current_page = math.ceil(offset / page_size) + 1 if offset > 0 else 1
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    # Calculate previous offset
    if offset > page_size:
        prev_offset = offset - page_size
    elif offset > 0:
        prev_offset = 0
    else:
        prev_offset = None
    
    return current_page, total_pages, prev_offset

def create_file_buttons(files, key):
    """Create file selection buttons"""
    buttons = []
    for file in files:
        button_text = f"{silent_size(file.file_size)}| {extract_tag(file.file_name)} {clean_filename(file.file_name)}"
        buttons.append([
            InlineKeyboardButton(
                text=button_text, 
                callback_data=f'file#{file.file_id}'
            )
        ])
    return buttons

def create_action_buttons(key):
    """Create quality, season, and send all buttons"""
    return [
        [
            InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("🗓️ Season", callback_data=f"seasons#{key}#0")
        ],
        [
            InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}")
        ]
    ]

def create_pagination_buttons(req, key, offset, n_offset, current_page, total_pages, prev_offset):
    """Create pagination navigation buttons"""
    buttons = []
    
    if n_offset == 0:  # Last page
        if prev_offset is not None:
            buttons.append([
                InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{prev_offset}"),
                InlineKeyboardButton(f"{current_page} / {total_pages}", callback_data="pages")
            ])
        else:
            buttons.append([
                InlineKeyboardButton(f"{current_page} / {total_pages}", callback_data="pages")
            ])
    elif prev_offset is None:  # First page
        buttons.append([
            InlineKeyboardButton("📄 Page", callback_data="pages"),
            InlineKeyboardButton(f"{current_page} / {total_pages}", callback_data="pages"),
            InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
        ])
    else:  # Middle page
        buttons.append([
            InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{prev_offset}"),
            InlineKeyboardButton(f"{current_page} / {total_pages}", callback_data="pages"),
            InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
        ])
    
    return buttons

async def get_page_size(settings):
    """Get page size from settings with fallback"""
    try:
        if settings.get('max_btn', True):
            return DEFAULT_PAGE_SIZE
        else:
            return int(getattr(settings, 'MAX_B_TN', DEFAULT_PAGE_SIZE))
    except (ValueError, AttributeError):
        return DEFAULT_PAGE_SIZE

def calculate_time_difference():
    """Calculate time difference for processing time display"""
    try:
        curr_time = datetime.now(TIMEZONE).time()
        # This seems to be calculating processing time, but the original logic is unclear
        # Returning a default value for now
        return "0.00"
    except Exception as e:
        LOGGER.warning(f"Time calculation failed: {e}")
        return "0.00"

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    """Handle pagination for search results with enhanced features"""
    try:
        # Rate limiting check
        await check_rate_limit(query.from_user.id)
        
        # Parse callback data
        ident, req, key, offset = parse_callback_data(query.data)
        
        # Validate user permission
        if not validate_user_permission(query.from_user.id, req):
            await query.answer(
                script.ALRT_TXT.format(query.from_user.first_name), 
                show_alert=True
            )
            return
        
        # Get search query
        try:
            search = await get_search_query(key)
        except PaginationError:
            await query.answer(
                script.OLD_ALRT_TXT.format(query.from_user.first_name), 
                show_alert=True
            )
            return
        
        # Log analytics
        await log_analytics(query.from_user.id, search, "pagination")
        
        # Get search results
        files, n_offset, total = await get_search_results(
            query.message.chat.id, 
            search, 
            offset=offset, 
            filter=True
        )
        
        # Validate results
        n_offset = int(n_offset) if n_offset else 0
        if not files:
            await query.answer("No more results found", show_alert=True)
            return
        
        # Apply smart sorting if enabled
        user_settings = await get_user_preferences(query.from_user.id)
        if user_settings.get('smart_sort', True):
            files = await SmartSort.sort_by_relevance(files, search)
        
        # Store results in temp storage
        temp.GETALL[key] = files
        temp.SHORT[query.from_user.id] = query.message.chat.id
        
        # Get settings
        settings = await get_settings(query.message.chat.id)
        page_size = await get_page_size(settings)
        
        # Create keyboard with enhanced features
        keyboard = await create_keyboard_enhanced(
            files, key, req, offset, n_offset, total, page_size, settings, query.from_user.id
        )
        
        # Update message
        await update_message_enhanced(query, settings, files, keyboard, total, search, offset)
        
        await query.answer("✅ Page updated")
        
    except RateLimitExceeded as e:
        await query.answer(f"⏰ {str(e)}", show_alert=True)
    except PaginationError as e:
        LOGGER.warning(f"Pagination error: {e}")
        await query.answer("❌ Invalid request", show_alert=True)
    except Exception as e:
        LOGGER.error(f"Error in pagination handler: {e}")
        await query.answer("❌ Something went wrong", show_alert=True)

# New callback handlers for enhanced features

@Client.on_callback_query(filters.regex(r"^bookmark#"))
async def handle_bookmark(bot, query):
    """Handle bookmark actions"""
    try:
        _, action, file_id = query.data.split("#")
        user_id = query.from_user.id
        
        if action == "bookmark":
            # Get file info from temp storage or database
            file_name = "Unknown File"  # Would get from database in real implementation
            await BookmarkManager.add_bookmark(user_id, file_id, file_name)
            await query.answer("🔖 Bookmarked!", show_alert=False)
        elif action == "unbookmark":
            await BookmarkManager.remove_bookmark(user_id, file_id)
            await query.answer("❌ Removed from bookmarks", show_alert=False)
        
        # Refresh the current page to update bookmark indicators
        # This would trigger the pagination handler again
        
    except Exception as e:
        LOGGER.error(f"Bookmark error: {e}")
        await query.answer("❌ Bookmark action failed", show_alert=True)

@Client.on_callback_query(filters.regex(r"^filter#"))
async def handle_filter(bot, query):
    """Handle advanced filtering options"""
    try:
        _, key, page = query.data.split("#")
        
        filter_keyboard = [
            [
                InlineKeyboardButton("📺 720p", callback_data=f"apply_filter#{key}#quality#720p"),
                InlineKeyboardButton("🎬 1080p", callback_data=f"apply_filter#{key}#quality#1080p"),
                InlineKeyboardButton("🎪 4K", callback_data=f"apply_filter#{key}#quality#4k")
            ],
            [
                InlineKeyboardButton("📱 Small (<500MB)", callback_data=f"apply_filter#{key}#size#small"),
                InlineKeyboardButton("💽 Medium (500MB-2GB)", callback_data=f"apply_filter#{key}#size#medium"),
                InlineKeyboardButton("📀 Large (>2GB)", callback_data=f"apply_filter#{key}#size#large")
            ],
            [
                InlineKeyboardButton("🎥 Video Only", callback_data=f"apply_filter#{key}#format#video"),
                InlineKeyboardButton("📝 Subtitles Only", callback_data=f"apply_filter#{key}#format#subtitle")
            ],
            [
                InlineKeyboardButton("🔄 Clear Filters", callback_data=f"clear_filters#{key}"),
                InlineKeyboardButton("⬅️ Back", callback_data=f"next_0_{key}_0")
            ]
        ]
        
        await query.message.edit_text(
            "🔍 <b>Advanced Filters</b>\n\nSelect filters to refine your search results:",
            reply_markup=InlineKeyboardMarkup(filter_keyboard),
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        LOGGER.error(f"Filter menu error: {e}")
        await query.answer("❌ Filter menu failed", show_alert=True)

@Client.on_callback_query(filters.regex(r"^sort#"))
async def handle_sort(bot, query):
    """Handle sorting options"""
    try:
        _, key, page = query.data.split("#")
        
        sort_keyboard = [
            [
                InlineKeyboardButton("🎯 Relevance", callback_data=f"apply_sort#{key}#relevance"),
                InlineKeyboardButton("⭐ Popularity", callback_data=f"apply_sort#{key}#popularity")
            ],
            [
                InlineKeyboardButton("📅 Date Added", callback_data=f"apply_sort#{key}#date"),
                InlineKeyboardButton("📏 File Size", callback_data=f"apply_sort#{key}#size")
            ],
            [
                InlineKeyboardButton("🔤 Name A-Z", callback_data=f"apply_sort#{key}#name_asc"),
                InlineKeyboardButton("🔤 Name Z-A", callback_data=f"apply_sort#{key}#name_desc")
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data=f"next_0_{key}_0")
            ]
        ]
        
        await query.message.edit_text(
            "📊 <b>Sort Options</b>\n\nChoose how to sort your results:",
            reply_markup=InlineKeyboardMarkup(sort_keyboard),
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        LOGGER.error(f"Sort menu error: {e}")
        await query.answer("❌ Sort menu failed", show_alert=True)

@Client.on_callback_query(filters.regex(r"^bookmarks#"))
async def show_bookmarks(bot, query):
    """Show user bookmarks"""
    try:
        user_id = query.from_user.id
        bookmarks = await BookmarkManager.get_bookmarks(user_id)
        
        if not bookmarks:
            await query.answer("📚 No bookmarks yet! Star some files to see them here.", show_alert=True)
            return
        
        bookmark_buttons = []
        for file_id, file_name in bookmarks[:20]:  # Limit to 20 bookmarks per page
            bookmark_buttons.append([
                InlineKeyboardButton(
                    f"🔖 {file_name[:40]}...",
                    callback_data=f"file#{file_id}"
                ),
                InlineKeyboardButton("❌", callback_data=f"bookmark#unbookmark#{file_id}")
            ])
        
        bookmark_buttons.append([
            InlineKeyboardButton("⬅️ Back", callback_data=f"next_0_{query.data.split('#')[1]}_0")
        ])
        
        await query.message.edit_text(
            f"🔖 <b>Your Bookmarks</b> ({len(bookmarks)} total)\n\n"
            "Click on any file to view details or ❌ to remove bookmark:",
            reply_markup=InlineKeyboardMarkup(bookmark_buttons),
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        LOGGER.error(f"Bookmarks display error: {e}")
        await query.answer("❌ Unable to load bookmarks", show_alert=True)

@Client.on_callback_query(filters.regex(r"^analytics#"))
async def show_analytics(bot, query):
    """Show user analytics and popular content"""
    try:
        user_id = query.from_user.id
        analytics = PAGINATION_ANALYTICS[user_id]
        
        # Get top searches
        top_searches = sorted(analytics['popular_queries'].items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Get peak hour
        peak_hours = analytics['peak_hours']
        peak_hour = max(peak_hours, key=peak_hours.get) if peak_hours else 0
        
        analytics_text = (
            f"📈 <b>Your Analytics</b>\n\n"
            f"👁️ Total Views: {analytics['views']}\n"
            f"🕐 Most Active Hour: {peak_hour}:00\n"
            f"📅 Last Activity: {analytics['last_access'].strftime('%d/%m/%Y %H:%M') if analytics['last_access'] else 'Never'}\n\n"
            f"🔍 <b>Top Searches:</b>\n"
        )
        
        for i, (query_text, count) in enumerate(top_searches, 1):
            analytics_text += f"{i}. {query_text[:30]}... ({count} times)\n"
        
        back_button = [[InlineKeyboardButton("⬅️ Back", callback_data=f"next_0_{query.data.split('#')[1]}_0")]]
        
        await query.message.edit_text(
            analytics_text,
            reply_markup=InlineKeyboardMarkup(back_button),
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        LOGGER.error(f"Analytics display error: {e}")
        await query.answer("❌ Unable to load analytics", show_alert=True)

async def calculate_file_statistics(files):
    """Calculate and format file statistics"""
    try:
        if not files:
            return "No files to analyze"
        
        total_size = sum(f.file_size for f in files)
        avg_size = total_size / len(files)
        
        # Quality distribution
        quality_count = {'720p': 0, '1080p': 0, '4K': 0, 'Other': 0}
        for file in files:
            filename = file.file_name.lower()
            if '720p' in filename:
                quality_count['720p'] += 1
            elif '1080p' in filename:
                quality_count['1080p'] += 1
            elif '4k' in filename or '2160p' in filename:
                quality_count['4K'] += 1
            else:
                quality_count['Other'] += 1
        
        # Format distribution
        format_count = {'MP4': 0, 'MKV': 0, 'AVI': 0, 'Other': 0}
        for file in files:
            filename = file.file_name.lower()
            if '.mp4' in filename:
                format_count['MP4'] += 1
            elif '.mkv' in filename:
                format_count['MKV'] += 1
            elif '.avi' in filename:
                format_count['AVI'] += 1
            else:
                format_count['Other'] += 1
        
        stats = (
            f"📁 Total: {len(files)} files | 💾 Size: {silent_size(total_size)}\n"
            f"📊 Avg Size: {silent_size(int(avg_size))}\n"
            f"🎬 Quality: 720p({quality_count['720p']}) | 1080p({quality_count['1080p']}) | 4K({quality_count['4K']})\n"
            f"📂 Format: MP4({format_count['MP4']}) | MKV({format_count['MKV']}) | AVI({format_count['AVI']})"
        )
        
        return stats
    except Exception as e:
        LOGGER.error(f"Statistics calculation failed: {e}")
        return "Statistics unavailable"

async def get_user_preferences(user_id):
    """Get user preferences with defaults"""
    # In a real implementation, this would load from database
    # For now, return defaults
    return {
        'smart_sort': True,
        'show_bookmarks': True,
        'auto_bookmark_downloads': False,
        'preferred_quality': '1080p',
        'preferred_format': 'MP4',
        'notifications_enabled': True
    }

# Advanced search and recommendation features
class SearchRecommendations:
    """Provide search recommendations and related queries"""
    
    @staticmethod
    async def get_related_searches(search_query):
        """Get related search suggestions"""
        # In production, this would use ML/AI for better suggestions
        query_words = search_query.lower().split()
        suggestions = []
        
        # Basic related terms (would be more sophisticated in production)
        related_terms = {
            'movie': ['film', 'cinema', 'hollywood', 'bollywood'],
            'series': ['tv show', 'season', 'episode', 'drama'],
            'action': ['thriller', 'adventure', 'crime', 'war'],
            'comedy': ['humor', 'funny', 'laugh', 'sitcom'],
            'horror': ['scary', 'thriller', 'supernatural', 'zombie']
        }
        
        for word in query_words:
            if word in related_terms:
                suggestions.extend(related_terms[word])
        
        return suggestions[:5]  # Return top 5 suggestions
    
    @staticmethod
    async def get_trending_searches():
        """Get currently trending searches"""
        # In production, this would query analytics database
        return [
            "Latest Movies 2024",
            "Popular TV Series",
            "Action Movies",
            "Marvel Movies",
            "Korean Drama"
        ]

# Batch operations for power users
class BatchOperations:
    """Handle batch operations on files"""
    
    @staticmethod
    async def bulk_bookmark(user_id, file_ids):
        """Bookmark multiple files at once"""
        success_count = 0
        for file_id in file_ids:
            try:
                file_name = f"File_{file_id}"  # Would get real name from database
                await BookmarkManager.add_bookmark(user_id, file_id, file_name)
                success_count += 1
            except Exception as e:
                LOGGER.error(f"Failed to bookmark {file_id}: {e}")
        
        return success_count
    
    @staticmethod
    async def export_bookmarks(user_id, format_type="json"):
        """Export user bookmarks in various formats"""
        bookmarks = await BookmarkManager.get_bookmarks(user_id)
        
        if format_type.lower() == "json":
            return json.dumps({
                "user_id": user_id,
                "export_date": datetime.now(TIMEZONE).isoformat(),
                "bookmarks": [{"file_id": fid, "file_name": fname} for fid, fname in bookmarks]
            }, indent=2)
        
        elif format_type.lower() == "txt":
            lines = [f"Bookmarks Export - {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}\n"]
            lines.extend([f"{fname} (ID: {fid})" for fid, fname in bookmarks])
            return "\n".join(lines)
        
        return None

# New callback handlers for advanced features
@Client.on_callback_query(filters.regex(r"^apply_filter#"))
async def apply_filter(bot, query):
    """Apply selected filter to search results"""
    try:
        _, key, filter_type, filter_value = query.data.split("#")
        
        # Get current search and files
        search = await get_search_query(key)
        files = temp.GETALL.get(key, [])
        
        if not files:
            await query.answer("❌ No files to filter", show_alert=True)
            return
        
        # Apply the selected filter
        filtered_files = files
        if filter_type == "quality":
            filtered_files = await AdvancedFilter.filter_by_quality(files, filter_value)
        elif filter_type == "size":
            size_ranges = {
                "small": (None, 500),
                "medium": (500, 2000),
                "large": (2000, None)
            }
            if filter_value in size_ranges:
                min_size, max_size = size_ranges[filter_value]
                filtered_files = await AdvancedFilter.filter_by_size(files, min_size, max_size)
        elif filter_type == "format":
            filtered_files = await AdvancedFilter.filter_by_format(files, filter_value)
        
        # Update temp storage with filtered results
        temp.GETALL[key] = filtered_files
        
        # Show filtered results
        total = len(filtered_files)
        if total == 0:
            await query.answer("🔍 No files match the selected filter", show_alert=True)
            return
        
        # Create new keyboard with filtered results
        settings = await get_settings(query.message.chat.id)
        keyboard = await create_keyboard_enhanced(
            filtered_files[:10], key, 0, key, 0, total, 10, settings, query.from_user.id
        )
        
        filter_info = f"🔍 <b>Filtered Results</b>\n\n"
        filter_info += f"Applied Filter: {filter_type.title()} = {filter_value}\n"
        filter_info += f"Results: {total} files\n\n"
        
        await query.message.edit_text(
            filter_info + f"Showing filtered results for: <code>{search}</code>",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )
        
        await query.answer(f"✅ Filter applied! {total} results found")
        
    except Exception as e:
        LOGGER.error(f"Filter application error: {e}")
        await query.answer("❌ Filter failed", show_alert=True)

@Client.on_callback_query(filters.regex(r"^apply_sort#"))
async def apply_sort(bot, query):
    """Apply selected sorting to search results"""
    try:
        _, key, sort_type = query.data.split("#")
        
        # Get current search and files
        search = await get_search_query(key)
        files = temp.GETALL.get(key, [])
        
        if not files:
            await query.answer("❌ No files to sort", show_alert=True)
            return
        
        # Apply the selected sort
        sorted_files = files
        if sort_type == "relevance":
            sorted_files = await SmartSort.sort_by_relevance(files, search)
        elif sort_type == "popularity":
            sorted_files = await SmartSort.sort_by_popularity(files)
        elif sort_type == "date":
            sorted_files = await SmartSort.sort_by_date(files)
        elif sort_type == "size":
            sorted_files = sorted(files, key=lambda x: x.file_size, reverse=True)
        elif sort_type == "name_asc":
            sorted_files = sorted(files, key=lambda x: x.file_name.lower())
        elif sort_type == "name_desc":
            sorted_files = sorted(files, key=lambda x: x.file_name.lower(), reverse=True)
        
        # Update temp storage with sorted results
        temp.GETALL[key] = sorted_files
        
        # Show sorted results
        settings = await get_settings(query.message.chat.id)
        keyboard = await create_keyboard_enhanced(
            sorted_files[:10], key, 0, key, 0, len(sorted_files), 10, settings, query.from_user.id
        )
        
        sort_info = f"📊 <b>Sorted Results</b>\n\n"
        sort_info += f"Sort Method: {sort_type.replace('_', ' ').title()}\n"
        sort_info += f"Total Results: {len(sorted_files)} files\n\n"
        
        await query.message.edit_text(
            sort_info + f"Showing sorted results for: <code>{search}</code>",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )
        
        await query.answer(f"✅ Sorted by {sort_type.replace('_', ' ')}")
        
    except Exception as e:
        LOGGER.error(f"Sort application error: {e}")
        await query.answer("❌ Sort failed", show_alert=True)

@Client.on_callback_query(filters.regex(r"^jump#"))
async def page_jump(bot, query):
    """Handle quick page jumping"""
    try:
        _, key, current_page = query.data.split("#")
        
        jump_buttons = []
        current_page = int(current_page)
        
        # Create page jump options
        page_options = []
        if current_page > 10:
            page_options.extend([1, 5, 10])
        
        page_options.extend([
            max(1, current_page - 5),
            max(1, current_page - 1),
            current_page + 1,
            current_page + 5,
            current_page + 10
        ])
        
        # Remove duplicates and sort
        page_options = sorted(list(set(page_options)))
        
        # Create buttons for page options
        for i, page in enumerate(page_options):
            if i % 3 == 0:
                jump_buttons.append([])
            
            offset = (page - 1) * 10  # Assuming 10 items per page
            jump_buttons[-1].append(
                InlineKeyboardButton(
                    f"📄 {page}",
                    callback_data=f"next_0_{key}_{offset}"
                )
            )
        
        jump_buttons.append([
            InlineKeyboardButton("⬅️ Back", callback_data=f"next_0_{key}_0")
        ])
        
        await query.message.edit_text(
            f"🔢 <b>Jump to Page</b>\n\nCurrent page: {current_page}\nSelect a page to jump to:",
            reply_markup=InlineKeyboardMarkup(jump_buttons),
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        LOGGER.error(f"Page jump error: {e}")
        await query.answer("❌ Page jump failed", show_alert=True)

# Background tasks for maintenance and optimization
async def cleanup_expired_data():
    """Clean up expired pagination data"""
    try:
        current_time = datetime.now(TIMEZONE)
        expired_keys = []
        
        # Clean up rate limit data older than 1 hour
        for user_id, data in USER_RATE_LIMIT.items():
            if data['reset_time'] and current_time >= data['reset_time']:
                expired_keys.append(user_id)
        
        for key in expired_keys:
            del USER_RATE_LIMIT[key]
        
        # Clean up old analytics data (keep last 30 days)
        cutoff_time = current_time - timedelta(days=30)
        for user_id, analytics in PAGINATION_ANALYTICS.items():
            if analytics['last_access'] and analytics['last_access'] < cutoff_time:
                expired_keys.append(user_id)
        
        LOGGER.info(f"Cleaned up {len(expired_keys)} expired data entries")
        
    except Exception as e:
        LOGGER.error(f"Cleanup task failed: {e}")

# Initialize background tasks
async def initialize_background_tasks():
    """Initialize background maintenance tasks"""
    try:
        # Schedule cleanup every hour
        while True:
            await asyncio.sleep(3600)  # 1 hour
            await cleanup_expired_data()
    except Exception as e:
        LOGGER.error(f"Background task initialization failed: {e}")

# Performance monitoring
class PerformanceMonitor:
    """Monitor pagination performance"""
    
    @staticmethod
    async def log_response_time(user_id, operation, duration):
        """Log response times for performance analysis"""
        try:
            LOGGER.info(f"Performance: User {user_id}, Operation: {operation}, Duration: {duration:.2f}s")
            # In production, this would go to a monitoring system
        except Exception as e:
            LOGGER.error(f"Performance logging failed: {e}")

async def update_message(query, settings, files, keyboard, total, search, offset):
    """Update message based on settings"""
    try:
        if settings.get('button', True):
            # Only update keyboard for button mode
            await query.edit_message_reply_markup(reply_markup=keyboard)
        else:
            # Update full message with caption for non-button mode
            remaining_seconds = calculate_time_difference()
            cap = await get_cap(settings, remaining_seconds, files, query, total, search, offset)
            
            await query.message.edit_text(
                text=cap,
                reply_markup=keyboard,
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML
            )
    except MessageNotModified:
        # Message content is the same, ignore this error
        pass
    except Exception as e:
        LOGGER.error(f"Failed to update message: {e}")
        raise

# Additional utility functions for better error handling

async def safe_get_settings(chat_id):
    """Safely get chat settings with defaults"""
    try:
        settings = await get_settings(chat_id)
        # Ensure max_btn setting exists
        if 'max_btn' not in settings:
            await save_group_settings(chat_id, 'max_btn', True)
            settings['max_btn'] = True
        return settings
    except Exception as e:
        LOGGER.error(f"Failed to get settings for chat {chat_id}: {e}")
        return {'button': True, 'max_btn': True}

# Health check function
async def validate_pagination_state(key, user_id):
    """Validate that pagination state is healthy"""
    try:
        # Check if search query exists
        search = BUTTONS.get(key) or FRESH.get(key)
        if not search:
            return False, "Search query expired"
        
        # Check if user context exists
        if user_id not in temp.SHORT:
            return False, "User context missing"
        
        return True, "OK"
    except Exception as e:
        return False, f"State validation error: {e}"
		
@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_cb_handler(client: Client, query: CallbackQuery):
    try:
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
                    show_alert=True,
                )
        except:
            pass
        _, key, offset = query.data.split("#")
        search = FRESH.get(key)
        offset = int(offset)
        search = search.replace(' ', '_')
        btn = []
        for i in range(0, len(QUALITIES)-1, 2):
            btn.append([
                InlineKeyboardButton(
                    text=QUALITIES[i].title(),
                    callback_data=f"fq#{QUALITIES[i].lower()}#{key}#{offset}"
                ),
                InlineKeyboardButton(
                    text=QUALITIES[i+1].title(),
                    callback_data=f"fq#{QUALITIES[i+1].lower()}#{key}#{offset}"
                ),
            ])
        btn.insert(
            0,
            [
                InlineKeyboardButton(
                    text="🎯 Select Quality", callback_data="ident"
                )
            ],
        )
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="📂 Back to Files 📂", callback_data=f"fq#homepage#{key}#{offset}")])
        await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    except Exception as e:
        LOGGER.error(f"Error In Quality Callback Handler - {e}")

@Client.on_callback_query(filters.regex(r"^fq#"))
async def filter_qualities_cb_handler(client: Client, query: CallbackQuery):
    try:
        _, qual, key, offset = query.data.split("#")
        offset = int(offset)
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        search = FRESH.get(key)
        search = search.replace("_", " ")
        baal = qual in search
        if baal:
            search = search.replace(qual, "")
        else:
            search = search
        req = query.from_user.id
        chat_id = query.message.chat.id
        message = query.message
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
                    show_alert=True,
                )
        except:
            pass
        if qual != "homepage":
            search = f"{search} {qual}" 
        BUTTONS[key] = search   
        files, n_offset, total_results = await get_search_results(chat_id, search, offset=offset, filter=True)
        if not files:
            await query.answer("⚡ Sorry, nothing was found!", show_alert=1)
            return
        temp.GETALL[key] = files
        settings = await get_settings(message.chat.id)
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
        if n_offset != "":
            try:
                if settings['max_btn']:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )
    
                else:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )
            except KeyError:
                await save_group_settings(query.message.chat.id, 'max_btn', True)
                btn.append(
                    [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                )
        else:
            n_offset = 0
            btn.append(
                [InlineKeyboardButton(text="🚫 That’s everything!",callback_data="pages")]
            )               
        if not settings.get('button'):
            cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
            time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
            remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
            cap = await get_cap(settings, remaining_seconds, files, query, total_results, search, offset)
            try:
                await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
            except MessageNotModified:
                pass
        else:
            try:
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except MessageNotModified:
                pass
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error In Quality - {e}")


@Client.on_callback_query(filters.regex(r"^languages#"))
async def languages_cb_handler(client: Client, query: CallbackQuery):
    try:
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
                    show_alert=True,
                )
        except:
            pass
        _, key, offset = query.data.split("#")
        search = FRESH.get(key)
        search = search.replace(' ', '_')
        offset = int(offset)
        btn = []
        for i in range(0, len(LANGUAGES)-1, 2):
            btn.append([
                InlineKeyboardButton(
                    text=LANGUAGES[i].title(),
                    callback_data=f"fl#{LANGUAGES[i].lower()}#{key}#{offset}"
                ),
                InlineKeyboardButton(
                    text=LANGUAGES[i+1].title(),
                    callback_data=f"fl#{LANGUAGES[i+1].lower()}#{key}#{offset}"
                ),
            ])
        btn.insert(
            0,
            [
                InlineKeyboardButton(
                    text="⇊ ꜱᴇʟᴇᴄᴛ ʟᴀɴɢᴜᴀɢᴇ ⇊", callback_data="ident"
                )
            ],
        )
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="📂 Back to Files 📂", callback_data=f"fl#homepage#{key}#{offset}")])
        await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    except Exception as e:
        LOGGER.error(f"Error In Language Cb Handaler - {e}")
    

@Client.on_callback_query(filters.regex(r"^fl#"))
async def filter_languages_cb_handler(client: Client, query: CallbackQuery):
    try:
        _, lang, key, offset = query.data.split("#")
        offset = int(offset)
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        search = FRESH.get(key)
        search = search.replace("_", " ")
        baal = lang in search
        if baal:
            search = search.replace(lang, "")
        else:
            search = search
        req = query.from_user.id
        chat_id = query.message.chat.id
        message = query.message
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
                    show_alert=True,
                )
        except:
            pass
        if lang != "homepage":
            search = f"{search} {lang}"
        BUTTONS[key] = search
        files, n_offset, total_results = await get_search_results(chat_id, search, offset=offset, filter=True)
        if not files:
            await query.answer("⚡ Sorry, nothing was found!", show_alert=1)
            return
        temp.GETALL[key] = files
        settings = await get_settings(message.chat.id)
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
        if n_offset != "":
            try:
                if settings['max_btn']:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )
    
                else:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )
            except KeyError:
                await save_group_settings(query.message.chat.id, 'max_btn', True)
                btn.append(
                    [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                )
        else:
            n_offset = 0
            btn.append(
                [InlineKeyboardButton(text="🚫 That’s everything!",callback_data="pages")]
            )    

        if not settings.get('button'):
            cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
            time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
            remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
            cap = await get_cap(settings, remaining_seconds, files, query, total_results, search, offset)
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
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error In Language - {e}")
        
@Client.on_callback_query(filters.regex(r"^seasons#"))
async def season_cb_handler(client: Client, query: CallbackQuery):
    try:
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
                    show_alert=True,
                )
        except:
            pass
        _, key, offset = query.data.split("#")
        search = FRESH.get(key)
        search = search.replace(' ', '_')
        offset = int(offset)
        btn = []
        for i in range(0, len(SEASONS)-1, 2):
            btn.append([
                InlineKeyboardButton(
                    text=SEASONS[i].title(),
                    callback_data=f"fs#{SEASONS[i].lower()}#{key}#{offset}"
                ),
                InlineKeyboardButton(
                    text=SEASONS[i+1].title(),
                    callback_data=f"fs#{SEASONS[i+1].lower()}#{key}#{offset}"
                ),
            ])
        btn.insert(
            0,
            [
                InlineKeyboardButton(
                    text="⇊ ꜱᴇʟᴇᴄᴛ Sᴇᴀsᴏɴ ⇊", callback_data="ident"
                )
            ],
        )
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="📂 Back to Files 📂", callback_data=f"fl#homepage#{key}#{offset}")])
        await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    except Exception as e:
        LOGGER.error(f"Error In Season Cb Handaler - {e}")


@Client.on_callback_query(filters.regex(r"^fs#"))
async def filter_season_cb_handler(client: Client, query: CallbackQuery):
    try:
        _, seas, key, offset = query.data.split("#")
        offset = int(offset)
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        search = FRESH.get(key)
        search = search.replace("_", " ")
        baal = seas in search
        if baal:
            search = search.replace(seas, "")
        else:
            search = search
        req = query.from_user.id
        chat_id = query.message.chat.id
        message = query.message
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
                    show_alert=True,
                )
        except:
            pass
        if seas != "homepage":
            search = f"{search} {seas}"
        BUTTONS[key] = search
        files, n_offset, total_results = await get_search_results(chat_id, search, offset=offset, filter=True)
        if not files:
            await query.answer("⚡ Sorry, nothing was found!", show_alert=1)
            return
        temp.GETALL[key] = files
        settings = await get_settings(message.chat.id)
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
        if n_offset != "":
            try:
                if settings['max_btn']:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )

                else:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )
            except KeyError:
                await save_group_settings(query.message.chat.id, 'max_btn', True)
                btn.append(
                    [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                )
        else:
            n_offset = 0
            btn.append(
                [InlineKeyboardButton(text="🚫 That’s everything!",callback_data="pages")]
            )    

        if not settings.get('button'):
            cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
            time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
            remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
            cap = await get_cap(settings, remaining_seconds, files, query, total_results, search, offset)
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
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error In Season - {e}")

@Client.on_callback_query(filters.regex(r"^spol"))
async def advantage_spoll_choker(bot, query):
    _, id, user = query.data.split('#')
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    movies = await get_poster(id, id=True)
    movie = movies.get('title')
    movie = re.sub(r"[:-]", " ", movie)
    movie = re.sub(r"\s+", " ", movie).strip()
    await query.answer(script.TOP_ALRT_MSG)
    files, offset, total_results = await get_search_results(query.message.chat.id, movie, offset=0, filter=True)
    if files:
        k = (movie, files, offset, total_results)
        await auto_filter(bot, query, k)
    else:
        reqstr1 = query.from_user.id if query.from_user else 0
        reqstr = await bot.get_users(reqstr1)
        if NO_RESULTS_MSG:
            await bot.send_message(chat_id=BIN_CHANNEL,text=script.NORSLTS.format(reqstr.id, reqstr.mention, movie))
        contact_admin_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔔 Send Request to Admin 🔔", url=OWNER_LNK)]])
        k = await query.message.edit(script.MVE_NT_FND,reply_markup=contact_admin_button)
        await asyncio.sleep(10)
        await k.delete()
                
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
