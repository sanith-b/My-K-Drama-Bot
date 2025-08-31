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

tracemalloc.start()

TIMEZONE = "Asia/Kolkata"
BUTTON = {}
BUTTONS = {}
FRESH = {}
SPELL_CHECK = {}

class Config:
    DEFAULT_PAGE_SIZE = 10
    MAX_PAGE_SIZE = 50
    TIMEZONE = 'Asia/Kolkata'
    CACHE_EXPIRY_HOURS = 24
    MAX_FILENAME_LENGTH = 40
	
@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    bot_id = client.me.id
    if EMOJI_MODE:
        try:
            await message.react(emoji=random.choice(REACTIONS))
        except Exception:
            pass
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"🚧 Currently upgrading… Will return soon 🔜", disable_web_page_preview=True)
        return
    await silentdb.update_top_messages(message.from_user.id, message.text)
    if message.chat.id != SUPPORT_CHAT_ID:
        settings = await get_settings(message.chat.id)
        if settings['auto_ffilter']:
            if re.search(r'https?://\S+|www\.\S+|t\.me/\S+', message.text):
                if await is_check_admin(client, message.chat.id, message.from_user.id):
                    return
                return await message.delete()   
            await auto_filter(client, message)
    else:
        search = message.text
        temp_files, temp_offset, total_results = await get_search_results(chat_id=message.chat.id, query=search.lower(), offset=0, filter=True)
        if total_results == 0:
            return
        else:
            return await message.reply_text(f"<b>✨ Hello {message.from_user.mention}! \n\n✅ Your request is already available. \n📂 Files found: {str(total_results)} \n🔍 Search: <code>{search}</code> \n‼️ This is a <u>support group</u>, so you can’t get files from here. \n\n📝 Search Hear 👇</b>",   
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Join & Explore 🔍", url=GRP_LNK)]]))


@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_text(bot, message):
    bot_id = bot.me.id
    content = message.text
    user = message.from_user.first_name
    user_id = message.from_user.id
    if EMOJI_MODE:
        try:
            await message.react(emoji=random.choice(REACTIONS))
        except Exception:
            pass
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"🚧 Currently upgrading… Will return soon 🔜", disable_web_page_preview=True)
        return
    if content.startswith(("/", "#")):
        return  
    try:
        await silentdb.update_top_messages(user_id, content)
        pm_search = await db.pm_search_status(bot_id)
        if pm_search:
            await auto_filter(bot, message)
        else:
            await message.reply_text(
             text=f"<b><i>⚠️ Not available here! Join & search below 👇</i></b>",   
             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Start Search", url=GRP_LNK)]])
            )
    except Exception as e:
        LOGGER.error(f"An error occurred: {str(e)}")


@Client.on_callback_query(filters.regex(r"^reffff"))
async def refercall(bot, query):
    btn = [[
        InlineKeyboardButton('🔗 Invite Link', url=f'https://telegram.me/share/url?url=https://t.me/{bot.me.username}?start=reff_{query.from_user.id}&text=Hello%21%20Experience%20a%20bot%20that%20offers%20a%20vast%20library%20of%20unlimited%20movies%20and%20series.%20%F0%9F%98%83'),
        InlineKeyboardButton(f'⏳ {referdb.get_refer_points(query.from_user.id)}', callback_data='ref_point'),
        InlineKeyboardButton('⬅️ Back', callback_data='premium')
    ]]
    reply_markup = InlineKeyboardMarkup(btn)
    await bot.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto("https://files.catbox.moe/nqvowv.jpg")
        )
    await query.message.edit_text(
        text=f'🎉 Your Referral Link: \n🔗 https://t.me/{bot.me.username}?start=reff_{query.from_user.id} \n\n👥 Share with friends!',
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
        )
    await query.answer()


class PaginationHandler:
    def __init__(self):
        self.loading_states = {}  # Track loading states per user
        
    async def get_pagination_buttons(self, key: str, offset: int, total: int, req: int, page_size: int = Config.DEFAULT_PAGE_SIZE):
        """Generate smart pagination buttons with improved UX"""
        current_page = (offset // page_size) + 1
        total_pages = math.ceil(total / page_size)
        
        buttons = []
        
        # Quick jump buttons for large result sets
        if total_pages > 10:
            # Show first page, current page context, and last page
            if current_page > 3:
                buttons.append(InlineKeyboardButton("⏮️ First", callback_data=f"next_{req}_{key}_0"))
            
            # Previous page
            if offset > 0:
                prev_offset = max(0, offset - page_size)
                buttons.append(InlineKeyboardButton("⬅️", callback_data=f"next_{req}_{key}_{prev_offset}"))
            
            # Current page indicator with quick jump
            buttons.append(InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data=f"jump_{req}_{key}_{offset}"))
            
            # Next page
            if current_page < total_pages:
                next_offset = offset + page_size
                buttons.append(InlineKeyboardButton("➡️", callback_data=f"next_{req}_{key}_{next_offset}"))
            
            # Last page
            if current_page < total_pages - 2:
                last_offset = (total_pages - 1) * page_size
                buttons.append(InlineKeyboardButton("⏭️ Last", callback_data=f"next_{req}_{key}_{last_offset}"))
        else:
            # Simple pagination for smaller result sets
            if offset > 0:
                prev_offset = max(0, offset - page_size)
                buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{prev_offset}"))
            
            buttons.append(InlineKeyboardButton(f"{current_page} / {total_pages}", callback_data="pages"))
            
            if current_page < total_pages:
                next_offset = offset + page_size
                buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"next_{req}_{key}_{next_offset}"))
        
        return [buttons] if buttons else []

    def create_file_button(self, file, settings):
        """Create enhanced file button with better formatting"""
        # Smart filename truncation
        filename = clean_filename(file.file_name)
        if len(filename) > Config.MAX_FILENAME_LENGTH:
            filename = filename[:Config.MAX_FILENAME_LENGTH-3] + "..."
        
        # Enhanced file info
        size_text = silent_size(file.file_size)
        quality_indicator = extract_tag(file.file_name)
        
        # Add file type emoji
        file_emoji = self.get_file_emoji(file.file_name)
        
        button_text = f"{file_emoji} {size_text} | {quality_indicator} {filename}"
        
        return InlineKeyboardButton(
            text=button_text,
            callback_data=f'file#{file.file_id}'
        )
    
    def get_file_emoji(self, filename):
        """Get appropriate emoji based on file type"""
        filename_lower = filename.lower()
        if any(ext in filename_lower for ext in ['.mp4', '.mkv', '.avi', '.mov']):
            return "🎬"
        elif any(ext in filename_lower for ext in ['.mp3', '.wav', '.flac']):
            return "🎵"
        elif any(ext in filename_lower for ext in ['.zip', '.rar', '.7z']):
            return "📦"
        elif any(ext in filename_lower for ext in ['.pdf', '.doc', '.txt']):
            return "📄"
        return "📁"

    async def create_enhanced_action_buttons(self, key: str, total: int, search_query: str = ""):
        """Create enhanced action buttons with more options"""
        row1 = [
            InlineKeyboardButton("⭐ Filter Quality", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("🗓️ Filter Season", callback_data=f"seasons#{key}#0")
        ]
        
        row2 = [
            InlineKeyboardButton(f"🚀 Send All ({total})", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh#{key}")
        ]
        
        return [row1, row2]

    async def show_loading_state(self, query, message="🔄 Loading..."):
        """Show loading state to improve perceived performance"""
        try:
            await query.answer(message, show_alert=False)
        except:
            pass

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    handler = PaginationHandler()
    
    try:
        # Show immediate feedback
        await handler.show_loading_state(query, "🔄 Loading page...")
        
        # Parse callback data
        try:
            ident, req, key, offset = query.data.split("_")
            req = int(req)
            offset = int(offset) if offset.isdigit() else 0
        except (ValueError, IndexError):
            await query.answer("❌ Invalid request format", show_alert=True)
            return
        
        # Enhanced access control with better error messages
        if req not in [query.from_user.id, 0]:
            await query.answer(
                f"🚫 {query.from_user.first_name}, this search belongs to someone else!",
                show_alert=True
            )
            return
        
        # Get search data with fallback
        search = BUTTONS.get(key) or FRESH.get(key)
        if not search:
            await query.answer(
                f"⏰ {query.from_user.first_name}, this search has expired. Please search again!",
                show_alert=True
            )
            return
        
        # Get settings with caching
        settings = await get_settings(query.message.chat.id)
        page_size = Config.MAX_PAGE_SIZE if settings.get('max_btn') else Config.DEFAULT_PAGE_SIZE
        
        # Fetch results with better error handling
        try:
            files, n_offset, total = await get_search_results(
                query.message.chat.id, 
                search, 
                offset=offset, 
                filter=True
            )
            n_offset = int(n_offset) if str(n_offset).isdigit() else 0
        except Exception as e:
            LOGGER.error(f"Error fetching search results: {e}")
            await query.answer("❌ Error loading results. Please try again.", show_alert=True)
            return
        
        if not files:
            await query.answer("📭 No more results found.", show_alert=True)
            return
        
        # Update cache
        temp.GETALL[key] = files
        temp.SHORT[query.from_user.id] = query.message.chat.id
        
        # Build enhanced button layout
        btn = []
        
        # Action buttons (always visible)
        action_buttons = await handler.create_enhanced_action_buttons(key, total, search)
        btn.extend(action_buttons)
        
        # File buttons (only if button mode is enabled)
        if settings.get('button'):
            file_buttons = [
                [handler.create_file_button(file, settings)]
                for file in files
            ]
            btn.extend(file_buttons)
        
        # Pagination buttons
        pagination_buttons = await handler.get_pagination_buttons(key, offset, total, req, page_size)
        btn.extend(pagination_buttons)
        
        # Add quick actions at bottom
        quick_actions = [
            InlineKeyboardButton("🔍 New Search", callback_data="new_search"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            InlineKeyboardButton("ℹ️ Help", callback_data="help")
        ]
        btn.append(quick_actions)
        
        # Update message with enhanced content
        if not settings.get('button'):
            # Generate enhanced caption with search stats
            current_time = datetime.now(pytz.timezone(Config.TIMEZONE)).time()
            time_diff = timedelta(
                hours=current_time.hour, 
                minutes=current_time.minute, 
                seconds=current_time.second + (current_time.microsecond/1000000)
            ) - timedelta(
                hours=curr_time.hour, 
                minutes=curr_time.minute, 
                seconds=curr_time.second + (curr_time.microsecond/1000000)
            )
            
            processing_time = f"{time_diff.total_seconds():.2f}"
            
            # Enhanced caption with better formatting
            cap = await get_enhanced_cap(
                settings, processing_time, files, query, total, search, offset, page_size
            )
            
            try:
                await query.message.edit_text(
                    text=cap,
                    reply_markup=InlineKeyboardMarkup(btn),
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.HTML
                )
            except MessageNotModified:
                await query.answer("✅ Already showing latest results")
        else:
            try:
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except MessageNotModified:
                await query.answer("✅ Page updated")
        
        # Success feedback
        current_page = (offset // page_size) + 1
        total_pages = math.ceil(total / page_size)
        await query.answer(f"📄 Page {current_page} of {total_pages}", show_alert=False)
        
    except Exception as e:
        LOGGER.error(f"Error in next_page handler: {e}")
        await query.answer("❌ Something went wrong. Please try again.", show_alert=True)

# Additional helper handlers for enhanced features

@Client.on_callback_query(filters.regex(r"^jump"))
async def jump_to_page(bot, query):
    """Allow users to jump to specific pages"""
    try:
        _, req, key, current_offset = query.data.split("_")
        
        # Show page selection interface
        settings = await get_settings(query.message.chat.id)
        page_size = Config.MAX_PAGE_SIZE if settings.get('max_btn') else Config.DEFAULT_PAGE_SIZE
        
        search = BUTTONS.get(key) or FRESH.get(key)
        if not search:
            await query.answer("⏰ Search expired. Please search again!", show_alert=True)
            return
            
        _, _, total = await get_search_results(query.message.chat.id, search, offset=0, filter=True)
        total_pages = math.ceil(total / page_size)
        
        # Create page jump buttons (show up to 20 pages)
        jump_buttons = []
        pages_to_show = min(total_pages, 20)
        
        for i in range(0, pages_to_show, 5):
            row = []
            for j in range(i, min(i + 5, pages_to_show)):
                page_num = j + 1
                page_offset = j * page_size
                row.append(
                    InlineKeyboardButton(
                        f"📄 {page_num}",
                        callback_data=f"next_{req}_{key}_{page_offset}"
                    )
                )
            jump_buttons.append(row)
        
        jump_buttons.append([
            InlineKeyboardButton("🔙 Back to Results", callback_data=f"next_{req}_{key}_{current_offset}")
        ])
        
        await query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(jump_buttons)
        )
        await query.answer("📄 Select a page to jump to")
        
    except Exception as e:
        LOGGER.error(f"Error in jump_to_page: {e}")
        await query.answer("❌ Error loading page selector", show_alert=True)



@Client.on_callback_query(filters.regex(r"^refresh"))
async def refresh_search(bot, query):
    """Refresh search results"""
    try:
        await query.answer("🔄 Refreshing search...", show_alert=False)
        
        _, key = query.data.split("#")
        
        search = BUTTONS.get(key) or FRESH.get(key)
        if not search:
            await query.answer("⏰ Search expired!", show_alert=True)
            return
        
        # Clear old cache and perform fresh search
        if key in temp.GETALL:
            del temp.GETALL[key]
        
        # Redirect to first page with fresh results
        query.data = f"next_{query.from_user.id}_{key}_0"
        await next_page(bot, query)
        
        await query.answer("✅ Search refreshed!")
        
    except Exception as e:
        LOGGER.error(f"Error in refresh_search: {e}")
        await query.answer("❌ Error refreshing search", show_alert=True)

async def get_enhanced_cap(settings, processing_time, files, query, total, search, offset, page_size):
    """Generate enhanced caption with better formatting and information"""
    current_page = (offset // page_size) + 1
    total_pages = math.ceil(total / page_size)
    
    # Search summary
    search_info = f"🔍 <b>Search:</b> <code>{search}</code>\n"
    
    # Results summary with progress bar
    results_info = f"📊 <b>Results:</b> {total} files found\n"
    results_info += f"📄 <b>Page:</b> {current_page} of {total_pages}\n"
    
    # Progress bar
    progress = (current_page / total_pages) * 10
    filled_blocks = int(progress)
    progress_bar = "█" * filled_blocks + "░" * (10 - filled_blocks)
    results_info += f"▫️ <code>[{progress_bar}]</code> {int(progress * 10)}%\n\n"
    
    # Performance info
    perf_info = f"⚡ <b>Loaded in:</b> {processing_time}s\n"
    
    # File list with enhanced formatting
    files_text = "<b>📁 Files in this page:</b>\n"
    for i, file in enumerate(files, 1):
        file_emoji = PaginationHandler().get_file_emoji(file.file_name)
        filename = clean_filename(file.file_name)[:30]
        size = silent_size(file.file_size)
        quality = extract_tag(file.file_name)
        
        files_text += f"{i}. {file_emoji} <code>{filename}</code>\n"
        files_text += f"   📏 {size} | ⭐ {quality}\n"
    
    # Tips for better UX
    tips = "\n💡 <b>Tips:</b>\n"
    tips += "• Use Quality/Season filters to narrow results\n"
    tips += "• Sort by size to find the best quality files\n"
    tips += "• Use 'Send All' to get all files at once"
    
    return search_info + results_info + perf_info + files_text + tips

# Enhanced keyboard layout helper
def create_adaptive_keyboard(buttons, max_width=3):
    """Create adaptive keyboard layout based on content"""
    if not buttons:
        return InlineKeyboardMarkup([])
    
    # Smart button arrangement
    keyboard = []
    
    # Group buttons intelligently
    current_row = []
    for button in buttons:
        if len(current_row) >= max_width:
            keyboard.append(current_row)
            current_row = [button]
        else:
            current_row.append(button)
    
    if current_row:
        keyboard.append(current_row)
    
    return InlineKeyboardMarkup(keyboard)

# Additional feature: Search analytics
class SearchAnalytics:
    @staticmethod
    async def log_search_interaction(user_id, action, search_key=None):
        """Log user interactions for analytics"""
        try:
            timestamp = datetime.now(pytz.timezone(Config.TIMEZONE))
            # Store in database or cache for analytics
            analytics_data = {
                'user_id': user_id,
                'action': action,
                'search_key': search_key,
                'timestamp': timestamp
            }
            # Implementation depends on your storage system
        except Exception as e:
            LOGGER.error(f"Analytics logging error: {e}")

# Feature: Keyboard shortcuts and quick actions
@Client.on_callback_query(filters.regex(r"^quick_"))
async def quick_actions(bot, query):
    """Handle quick action buttons"""
    try:
        action = query.data.replace("quick_", "")
        
        if action == "bookmark":
            # Bookmark current search
            await query.answer("🔖 Search bookmarked!", show_alert=False)
            
        elif action == "share":
            # Generate shareable search link
            await query.answer("🔗 Generating share link...", show_alert=False)
            
        elif action == "export":
            # Export results as text file
            await query.answer("📤 Preparing export...", show_alert=False)
            
    except Exception as e:
        LOGGER.error(f"Error in quick_actions: {e}")

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
