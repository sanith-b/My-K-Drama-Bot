import asyncio
import re
import ast
import math
import random
import pytz
from datetime import datetime, timedelta, date, time
from collections import defaultdict
import json
import hashlib
from typing import Dict, List, Optional, Tuple
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
SEARCH_HISTORY = defaultdict(list)  # New: Store search history per user
FAVORITES = defaultdict(set)  # New: Store user favorites
RECENT_SEARCHES = defaultdict(list)  # New: Store recent searches for quick access
ADVANCED_FILTERS = {}  # New: Store advanced filter preferences
USER_PREFERENCES = defaultdict(dict)  # New: Store user preferences

# New: Enhanced search analytics
SEARCH_ANALYTICS = {
    'popular_searches': defaultdict(int),
    'search_trends': defaultdict(list),
    'user_activity': defaultdict(int)
}

# New: Cache for frequent searches
SEARCH_CACHE = {}
CACHE_EXPIRY = 3600  # 1 hour

# New: Enhanced filter options
LANGUAGES = ['english', 'hindi', 'tamil', 'telugu', 'malayalam', 'kannada', 'bengali', 'marathi', 'gujarati', 'punjabi']
GENRES = ['action', 'comedy', 'drama', 'horror', 'thriller', 'romance', 'sci-fi', 'fantasy', 'animation', 'documentary']
YEARS = [str(year) for year in range(2024, 1990, -1)]
RESOLUTIONS = ['4k', '2160p', '1080p', '720p', '480p', '360p']

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
    
    # New: Update search analytics
    await update_search_analytics(message.from_user.id, message.text)
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
            return await message.reply_text(f"<b>✨ Hello {message.from_user.mention}! \n\n✅ Your request is already available. \n📂 Files found: {str(total_results)} \n🔍 Search: <code>{search}</code> \n‼️ This is a <u>support group</u>, so you can't get files from here. \n\n📝 Search Here 👇</b>",   
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
    
    # New: Handle special commands
    if content.lower().startswith('!history'):
        await show_search_history(bot, message)
        return
    elif content.lower().startswith('!favorites'):
        await show_favorites(bot, message)
        return
    elif content.lower().startswith('!trending'):
        await show_trending_searches(bot, message)
        return
    elif content.lower().startswith('!clear history'):
        await clear_search_history(user_id, bot, message)
        return
    
    try:
        await silentdb.update_top_messages(user_id, content)
        await update_search_analytics(user_id, content)
        pm_search = await db.pm_search_status(bot_id)
        if pm_search:
            await auto_filter(bot, message)
        else:
            # New: Show recent searches and trending
            recent_btn = await get_recent_searches_buttons(user_id)
            await message.reply_text(
             text=f"<b><i>⚠️ Not available here! Join & search below 👇</i></b>",   
             reply_markup=InlineKeyboardMarkup(recent_btn + [[InlineKeyboardButton("🔍 Start Search", url=GRP_LNK)]])
            )
    except Exception as e:
        LOGGER.error(f"An error occurred: {str(e)}")

# New: Enhanced callback query handlers
@Client.on_callback_query(filters.regex(r"^advanced_search"))
async def advanced_search_handler(bot, query):
    """Handle advanced search options"""
    user_id = query.from_user.id
    
    btn = [
        [InlineKeyboardButton("🎭 Genre", callback_data=f"filter_genre#{user_id}"),
         InlineKeyboardButton("🌍 Language", callback_data=f"filter_language#{user_id}")],
        [InlineKeyboardButton("📅 Year", callback_data=f"filter_year#{user_id}"),
         InlineKeyboardButton("📺 Resolution", callback_data=f"filter_resolution#{user_id}")],
        [InlineKeyboardButton("⭐ IMDb Rating", callback_data=f"filter_rating#{user_id}"),
         InlineKeyboardButton("💾 File Size", callback_data=f"filter_size#{user_id}")],
        [InlineKeyboardButton("🔄 Reset Filters", callback_data=f"reset_filters#{user_id}"),
         InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ]
    
    current_filters = ADVANCED_FILTERS.get(user_id, {})
    filter_text = "🔍 Advanced Search Options\n\n"
    
    if current_filters:
        filter_text += "📋 Active Filters:\n"
        for key, value in current_filters.items():
            filter_text += f"• {key.title()}: {value}\n"
        filter_text += "\n"
    
    filter_text += "Select a filter category to refine your search:"
    
    await query.message.edit_text(filter_text, reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^filter_"))
async def filter_handler(bot, query):
    """Handle individual filter selections"""
    filter_type, user_id = query.data.split("#")
    filter_type = filter_type.replace("filter_", "")
    user_id = int(user_id)
    
    if query.from_user.id != user_id:
        await query.answer("❌ Not your search session", show_alert=True)
        return
    
    btn = []
    
    if filter_type == "genre":
        btn = [[InlineKeyboardButton(genre.title(), callback_data=f"set_filter#genre#{genre}#{user_id}")] for genre in GENRES]
    elif filter_type == "language":
        btn = [[InlineKeyboardButton(lang.title(), callback_data=f"set_filter#language#{lang}#{user_id}")] for lang in LANGUAGES]
    elif filter_type == "year":
        # Show years in rows of 3
        for i in range(0, len(YEARS), 3):
            row = [InlineKeyboardButton(year, callback_data=f"set_filter#year#{year}#{user_id}") for year in YEARS[i:i+3]]
            btn.append(row)
    elif filter_type == "resolution":
        btn = [[InlineKeyboardButton(res, callback_data=f"set_filter#resolution#{res}#{user_id}")] for res in RESOLUTIONS]
    
    btn.append([InlineKeyboardButton("⬅️ Back", callback_data="advanced_search")])
    
    await query.message.edit_text(
        f"🔍 Select {filter_type.title()}:",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@Client.on_callback_query(filters.regex(r"^set_filter#"))
async def set_filter_handler(bot, query):
    """Set a specific filter value"""
    _, filter_type, value, user_id = query.data.split("#")
    user_id = int(user_id)
    
    if query.from_user.id != user_id:
        await query.answer("❌ Not your search session", show_alert=True)
        return
    
    if user_id not in ADVANCED_FILTERS:
        ADVANCED_FILTERS[user_id] = {}
    
    ADVANCED_FILTERS[user_id][filter_type] = value
    
    await query.answer(f"✅ {filter_type.title()} set to: {value}", show_alert=True)
    await advanced_search_handler(bot, query)

@Client.on_callback_query(filters.regex(r"^episodes#"))
async def episodes_cb_handler(client: Client, query: CallbackQuery):
    """New: Handle episode filtering"""
    try:
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn't your movie request. \n📝 Please send your own request.",
                    show_alert=True,
                )
        except:
            pass
        
        _, key, offset = query.data.split("#")
        search = FRESH.get(key)
        offset = int(offset)
        
        # Extract episode numbers from search results
        files, _, _ = await get_search_results(query.message.chat.id, search, offset=0, filter=True)
        episodes = set()
        
        for file in files:
            # Extract episode numbers using regex
            episode_match = re.search(r'[eE](\d+)', file.file_name)
            if episode_match:
                episodes.add(int(episode_match.group(1)))
        
        episodes = sorted(list(episodes))[:20]  # Limit to first 20 episodes
        
        btn = []
        for i in range(0, len(episodes), 3):
            row = [InlineKeyboardButton(f"EP {ep}", callback_data=f"fe#e{ep:02d}#{key}#{offset}") for ep in episodes[i:i+3]]
            btn.append(row)
        
        btn.insert(0, [InlineKeyboardButton("📺 Select Episode", callback_data="ident")])
        btn.append([InlineKeyboardButton("📂 Back to Files", callback_data=f"fe#homepage#{key}#{offset}")])
        
        await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
        
    except Exception as e:
        LOGGER.error(f"Error In Episode Handler - {e}")

@Client.on_callback_query(filters.regex(r"^fe#"))
async def filter_episode_handler(client: Client, query: CallbackQuery):
    """New: Filter by episode number"""
    try:
        _, episode, key, offset = query.data.split("#")
        offset = int(offset)
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        search = FRESH.get(key)
        
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn't your movie request. \n📝 Please send your own request.",
                    show_alert=True,
                )
        except:
            pass
        
        if episode != "homepage":
            search = f"{search} {episode}"
        
        BUTTONS[key] = search
        files, n_offset, total_results = await get_search_results(query.message.chat.id, search, offset=offset, filter=True)
        
        if not files:
            await query.answer("⚡ Sorry, nothing was found!", show_alert=1)
            return
        
        await update_search_results_ui(client, query, files, n_offset, total_results, search, key, offset)
        await query.answer()
        
    except Exception as e:
        LOGGER.error(f"Error In Episode Filter - {e}")

@Client.on_callback_query(filters.regex(r"^favorite#"))
async def favorite_handler(bot, query):
    """New: Handle favorites"""
    try:
        _, action, file_id = query.data.split("#")
        user_id = query.from_user.id
        
        if action == "add":
            FAVORITES[user_id].add(file_id)
            await query.answer("💖 Added to favorites!", show_alert=True)
        elif action == "remove":
            FAVORITES[user_id].discard(file_id)
            await query.answer("💔 Removed from favorites!", show_alert=True)
            
    except Exception as e:
        LOGGER.error(f"Error in favorite handler: {e}")

@Client.on_callback_query(filters.regex(r"^download_all#"))
async def download_all_handler(bot, query):
    """New: Handle bulk download requests"""
    try:
        _, key = query.data.split("#")
        user_id = query.from_user.id
        
        files = temp.GETALL.get(key, [])
        if not files:
            await query.answer("❌ No files found!", show_alert=True)
            return
        
        # Create download links for all files
        download_links = []
        for file in files[:10]:  # Limit to 10 files
            link = f"https://telegram.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file.file_id}"
            download_links.append(f"📁 {clean_filename(file.file_name)}\n🔗 {link}")
        
        message_text = f"📦 Bulk Download Links:\n\n" + "\n\n".join(download_links)
        
        await bot.send_message(
            chat_id=user_id,
            text=message_text,
            disable_web_page_preview=True
        )
        
        await query.answer("📨 Download links sent to your PM!", show_alert=True)
        
    except Exception as e:
        LOGGER.error(f"Error in download all handler: {e}")

@Client.on_callback_query(filters.regex(r"^smart_search"))
async def smart_search_handler(bot, query):
    """New: AI-powered smart search suggestions"""
    try:
        user_id = query.from_user.id
        
        # Get user's search history
        history = SEARCH_HISTORY.get(user_id, [])
        if not history:
            await query.answer("❌ No search history found!", show_alert=True)
            return
        
        # Generate smart suggestions based on history
        suggestions = await generate_smart_suggestions(history)
        
        btn = []
        for suggestion in suggestions[:6]:  # Limit to 6 suggestions
            btn.append([InlineKeyboardButton(f"🎯 {suggestion}", callback_data=f"search#{suggestion}")])
        
        btn.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
        
        await query.message.edit_text(
            "🤖 Smart Search Suggestions:\nBased on your search history:",
            reply_markup=InlineKeyboardMarkup(btn)
        )
        
    except Exception as e:
        LOGGER.error(f"Error in smart search: {e}")

# New: Helper functions
async def update_search_analytics(user_id: int, search_text: str):
    """Update search analytics and history"""
    try:
        # Update search history
        SEARCH_HISTORY[user_id].append({
            'query': search_text,
            'timestamp': datetime.now(),
            'chat_id': user_id
        })
        
        # Keep only last 50 searches
        SEARCH_HISTORY[user_id] = SEARCH_HISTORY[user_id][-50:]
        
        # Update popular searches
        SEARCH_ANALYTICS['popular_searches'][search_text.lower()] += 1
        SEARCH_ANALYTICS['user_activity'][user_id] += 1
        
        # Update recent searches for quick access
        if search_text not in RECENT_SEARCHES[user_id]:
            RECENT_SEARCHES[user_id].insert(0, search_text)
            RECENT_SEARCHES[user_id] = RECENT_SEARCHES[user_id][:10]  # Keep only 10 recent
            
    except Exception as e:
        LOGGER.error(f"Error updating search analytics: {e}")

async def get_recent_searches_buttons(user_id: int) -> List[List[InlineKeyboardButton]]:
    """Get recent searches as buttons"""
    recent = RECENT_SEARCHES.get(user_id, [])[:5]  # Show only 5 most recent
    buttons = []
    
    if recent:
        buttons.append([InlineKeyboardButton("🕒 Recent Searches:", callback_data="ident")])
        for search in recent:
            buttons.append([InlineKeyboardButton(f"🔍 {search[:30]}...", callback_data=f"search#{search}")])
    
    return buttons

async def show_search_history(bot, message):
    """Show user's search history"""
    user_id = message.from_user.id
    history = SEARCH_HISTORY.get(user_id, [])[-20:]  # Show last 20 searches
    
    if not history:
        await message.reply("📭 Your search history is empty!")
        return
    
    text = "📊 Your Search History (Last 20):\n\n"
    for i, search in enumerate(reversed(history), 1):
        timestamp = search['timestamp'].strftime("%d/%m %H:%M")
        text += f"{i}. {search['query']} - {timestamp}\n"
    
    btn = [[InlineKeyboardButton("🗑️ Clear History", callback_data=f"clear_history#{user_id}")]]
    
    await message.reply(text, reply_markup=InlineKeyboardMarkup(btn))

async def show_favorites(bot, message):
    """Show user's favorite files"""
    user_id = message.from_user.id
    favorites = FAVORITES.get(user_id, set())
    
    if not favorites:
        await message.reply("💔 You have no favorites yet!")
        return
    
    # Here you would typically fetch file details for each favorite
    # For now, just show count
    await message.reply(f"💖 You have {len(favorites)} favorite files!")

async def show_trending_searches(bot, message):
    """Show trending searches"""
    popular = dict(sorted(SEARCH_ANALYTICS['popular_searches'].items(), 
                         key=lambda x: x[1], reverse=True)[:10])
    
    if not popular:
        await message.reply("📈 No trending searches yet!")
        return
    
    text = "🔥 Trending Searches:\n\n"
    for i, (search, count) in enumerate(popular.items(), 1):
        text += f"{i}. {search.title()} ({count} searches)\n"
    
    await message.reply(text)

async def clear_search_history(user_id: int, bot, message):
    """Clear user's search history"""
    SEARCH_HISTORY[user_id] = []
    RECENT_SEARCHES[user_id] = []
    await message.reply("🗑️ Search history cleared!")

async def generate_smart_suggestions(history: List[dict]) -> List[str]:
    """Generate smart search suggestions based on history"""
    # Simple implementation - in production, you might use ML
    suggestions = []
    recent_searches = [h['query'].lower() for h in history[-10:]]
    
    # Find common keywords
    keywords = []
    for search in recent_searches:
        keywords.extend(search.split())
    
    # Get most common keywords
    from collections import Counter
    common_keywords = Counter(keywords).most_common(10)
    
    # Generate suggestions by combining keywords
    for keyword, count in common_keywords:
        if len(keyword) > 3:  # Skip short words
            suggestions.append(f"{keyword} movie")
            suggestions.append(f"{keyword} series")
    
    return suggestions[:6]

async def update_search_results_ui(client, query, files, n_offset, total_results, search, key, offset):
    """Update search results UI - refactored for reuse"""
    settings = await get_settings(query.message.chat.id)
    temp.GETALL[key] = files
    
    if settings.get('button'):
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{silent_size(file.file_size)}| {extract_tag(file.file_name)} {clean_filename(file.file_name)}", 
                    callback_data=f'file#{file.file_id}'
                ),
            ]
            for file in files
        ]
        btn.insert(0, [
            InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("🗓️ Season", callback_data=f"seasons#{key}#0"),
            InlineKeyboardButton("📺 Episodes", callback_data=f"episodes#{key}#0")
        ])
        btn.insert(1, [
            InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("📦 Bulk Download", callback_data=f"download_all#{key}")
        ])
    else:
        btn = []
        btn.insert(0, [
            InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("🗓️ Season", callback_data=f"seasons#{key}#0"),
            InlineKeyboardButton("📺 Episodes", callback_data=f"episodes#{key}#0")
        ])
        btn.insert(1, [
            InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("📦 Bulk Download", callback_data=f"download_all#{key}")
        ])
    
    # Enhanced navigation with new features
    req = query.from_user.id
    nav_buttons = await build_enhanced_navigation(req, key, offset, n_offset, total_results, settings)
    btn.extend(nav_buttons)
    
    # Update message
    if not settings.get('button'):
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        cap = await get_enhanced_caption(settings, files, query, total_results, search, offset)
        try:
            await query.message.edit_text(
                text=cap, 
                reply_markup=InlineKeyboardMarkup(btn), 
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML
            )
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass

async def build_enhanced_navigation(req, key, offset, n_offset, total, settings):
    """Build enhanced navigation buttons"""
    try:
        max_btn_setting = settings.get('max_btn', True)
        items_per_page = 10 if max_btn_setting else int(MAX_B_TN)
        
        current_page = math.ceil(int(offset) / items_per_page) + 1
        total_pages = math.ceil(total / items_per_page)
        
        # Calculate previous offset
        if 0 < offset <= items_per_page:
            prev_offset = 0
        elif offset == 0:
            prev_offset = None
        else:
            prev_offset = offset - items_per_page
        
        buttons = []
        
        # Main navigation row
        nav_row = []
        if prev_offset is not None:
            nav_row.append(InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{prev_offset}"))
        
        nav_row.append(InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="pages"))
        
        if n_offset != 0:
            nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}"))
        
        buttons.append(nav_row)
        
        # Quick navigation for large datasets
        if total_pages > 5:
            quick_nav = []
            if current_page > 3:
                quick_nav.append(InlineKeyboardButton("⏮️ First", callback_data=f"next_{req}_{key}_0"))
            
            # Jump buttons
            if current_page > 5:
                jump_back = max(0, (current_page - 6) * items_per_page)
                quick_nav.append(InlineKeyboardButton("↩️ -5", callback_data=f"next_{req}_{key}_{jump_back}"))
            
            if current_page + 5 <= total_pages:
                jump_forward = (current_page + 4) * items_per_page
                quick_nav.append(InlineKeyboardButton("↪️ +5", callback_data=f"next_{req}_{key}_{jump_forward}"))
            
            if current_page < total_pages - 2:
                last_offset = (total_pages - 1) * items_per_page
                quick_nav.append(InlineKeyboardButton("⏭️ Last", callback_data=f"next_{req}_{key}_{last_offset}"))
            
            if quick_nav:
                buttons.append(quick_nav)
        
        return buttons
        
    except Exception as e:
        LOGGER.error(f"Error building navigation: {e}")
        return [[InlineKeyboardButton(f"📄 Page", callback_data="pages")]]

async def get_enhanced_caption(settings, files, query, total_results, search, offset):
    """Get enhanced caption with more information"""
    cap = f"<b><blockquote>✨ Hello!,{query.from_user.mention}</blockquote>\n\n"
    cap += f"📂 Results for: <code>{search}</code>\n"
    cap += f"📊 Found: {total_results} files\n"
    cap += f"📄 Showing: {offset + 1}-{min(offset + len(files), total_results)}\n\n</b>"
    
    for file_num, file in enumerate(files, start=offset + 1):
        cap += f"<b>{file_num}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file.file_id}'>{get_size(file.file_size)} | {clean_filename(file.file_name)}</a></b>\n"
    
    return cap

# Continue with existing handlers (next_page, qualities, seasons, etc.)
# The existing handlers remain largely the same but can be enhanced with the new features

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    try:
        ident, req, key, offset = query.data.split("_")
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        
        if int(req) not in [query.from_user.id, 0]:
            return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        
        try:
            offset = int(offset)
        except:
            offset = 0
            
        if BUTTONS.get(key) != None:
            search = BUTTONS.get(key)
        else:
            search = FRESH.get(key)
            
        if not search:
            await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name), show_alert=True)
            return
            
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=offset, filter=True)
        
        try:
            n_offset = int(n_offset)
        except:
            n_offset = 0
            
        if not files:
            return
        
        # Update with enhanced UI
        await update_search_results_ui(bot, query, files, n_offset, total, search, key, offset)
        await query.answer()
        
    except Exception as e:
        LOGGER.error(f"Error In Next Function - {e}")

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

@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_cb_handler(client: Client, query: CallbackQuery):
    try:
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn't your movie request. \n📝 Please send your own request.",
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
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn't your movie request. \n📝 Please send your own request.",
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
        
        await update_search_results_ui(client, query, files, n_offset, total_results, search, key, offset)
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error In Quality - {e}")

@Client.on_callback_query(filters.regex(r"^seasons#"))
async def season_cb_handler(client: Client, query: CallbackQuery):
    try:
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn't your movie request. \n📝 Please send your own request.",
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
                    text="🗓️ Select Season", callback_data="ident"
                )
            ],
        )
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="📂 Back to Files 📂", callback_data=f"fs#homepage#{key}#{offset}")])
        await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    except Exception as e:
        LOGGER.error(f"Error In Season Cb Handler - {e}")

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
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn't your movie request. \n📝 Please send your own request.",
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
        
        await update_search_results_ui(client, query, files, n_offset, total_results, search, key, offset)
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
        # Removed user ID verification - anyone can access files
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
            await query.answer("❌ You don't have enough rights to do this!", show_alert=True)
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
            await query.answer("❌ You don't have enough rights to do this!", show_alert=True)
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
                chat_id=LOG_CHANNEL,
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
        await query.message.edit("<b>🛠️ Advanced Settings Mode\n\nCustomize your Log Channel value here\n👇 Select an option below<\b>", reply_markup=InlineKeyboardMarkup(btn))

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
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'log_setgs#{grp_id}')]
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
            [InlineKeyboardButton('⬅️ Back', callback_data=f'log_setgs#{grp_id}')]
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
                InlineKeyboardButton('⬅️ Back', callback_data=f'caption_setgs#{grp_id}')]
            ]	
            await query.message.edit("<b>🎨 Customize caption & change values</b>", reply_markup=InlineKeyboardMarkup(btn))
            await m.delete()
            return
        await m.delete()	
        await save_group_settings(int(grp_id), f'caption', caption_msg.text)
        await client.send_message(LOG_API_CHANNEL, f"#Set_Caption\n\nGroup Title : {silentx.title}\n\nɢʀᴏᴜᴘ ɪᴅ: {grp_id}\nɪɴᴠɪᴛᴇ ʟɪɴᴋ : {invite_link}\n\nᴜᴘᴅᴀᴛᴇᴅ ʙʏ : {query.from_user.username}")	    
        btn = [            
            [InlineKeyboardButton('⬅️ Back', callback_data=f'caption_setgs#{grp_id}')]
        ]    
        await query.message.reply(f"<b>✅ Custom caption values updated!\n\n🎨 Caption Here: <code>{caption_msg.text}</code></b>", reply_markup=InlineKeyboardMarkup(btn))

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
# New: Watchlist functionality
@Client.on_callback_query(filters.regex(r"^watchlist#"))
async def watchlist_handler(bot, query):
    """Handle watchlist operations"""
    try:
        _, action, data = query.data.split("#", 2)
        user_id = query.from_user.id
        
        if user_id not in USER_PREFERENCES:
            USER_PREFERENCES[user_id] = {'watchlist': []}
        
        if action == "add":
            # Add to watchlist
            watchlist_item = {
                'title': data,
                'added_date': datetime.now().isoformat(),
                'status': 'pending'
            }
            USER_PREFERENCES[user_id]['watchlist'].append(watchlist_item)
            await query.answer("📝 Added to your watchlist!", show_alert=True)
            
        elif action == "show":
            # Show watchlist
            watchlist = USER_PREFERENCES[user_id].get('watchlist', [])
            if not watchlist:
                await query.answer("📭 Your watchlist is empty!", show_alert=True)
                return
            
            text = "📝 Your Watchlist:\n\n"
            buttons = []
            for i, item in enumerate(watchlist[-10:], 1):  # Show last 10 items
                text += f"{i}. {item['title']} - {item['status']}\n"
                buttons.append([InlineKeyboardButton(
                    f"🔍 Search: {item['title'][:20]}...",
                    callback_data=f"search#{item['title']}"
                )])
            
            buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
            
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            
        elif action == "clear":
            # Clear watchlist
            USER_PREFERENCES[user_id]['watchlist'] = []
            await query.answer("🗑️ Watchlist cleared!", show_alert=True)
            
    except Exception as e:
        LOGGER.error(f"Error in watchlist handler: {e}")

# New: Enhanced auto filter with caching and analytics
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
            
            # Check cache first
            cache_key = f"{message.chat.id}_{search}"
            cached_result = SEARCH_CACHE.get(cache_key)
            
            if cached_result and (datetime.now().timestamp() - cached_result['timestamp']) < CACHE_EXPIRY:
                files, offset, total_results = cached_result['data']
                m = await message.reply_text(f'<b>⚡ Quick results for: <i>{search}...</i></b>', reply_to_message_id=message.id)
            else:
                m = await message.reply_text(f'<b>🕐 Hold on... {message.from_user.mention} Searching for your query: <i>{search}...</i></b>', reply_to_message_id=message.id)
                files, offset, total_results = await get_search_results(message.chat.id, search, offset=0, filter=True)
                
                # Cache the result
                SEARCH_CACHE[cache_key] = {
                    'data': (files, offset, total_results),
                    'timestamp': datetime.now().timestamp()
                }
            
            settings = await get_settings(message.chat.id)
            if not files:
                if settings.get("spell_check", True):
                    ai_sts = await m.edit('🤖 Hang tight… AI is checking your spelling!')
                    is_misspelled = await ai_spell_check(chat_id=message.chat.id, wrong_name=search)
                    if is_misspelled:
                        await ai_sts.edit(f'<b>🔹 My pick: <code>{is_misspelled}</code> \nSearching for <code>{is_misspelled}</code></b>')
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
        m = await message.reply_text(f'<b>🕐 Hold on... {message.from_user.mention} Searching for your query: <i>{search}...</i></b>', reply_to_message_id=message.id)
        settings = await get_settings(message.chat.id)
        await msg.message.delete()
    
    key = f"{message.chat.id}-{message.id}"
    FRESH[key] = search
    temp.GETALL[key] = files
    temp.SHORT[message.from_user.id] = message.chat.id
    
    # Enhanced buttons with new features
    if settings.get('button'):
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{silent_size(file.file_size)}| {extract_tag(file.file_name)} {clean_filename(file.file_name)}", 
                    callback_data=f'file#{file.file_id}'
                ),
            ]
            for file in files
        ]
        btn.insert(0, [
            InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("🗓️ Season", callback_data=f"seasons#{key}#0"),
            InlineKeyboardButton("📺 Episodes", callback_data=f"episodes#{key}#0")
        ])
        btn.insert(1, [
            InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("📦 Bulk Download", callback_data=f"download_all#{key}")
        ])
        btn.insert(2, [
            InlineKeyboardButton("📝 Add to Watchlist", callback_data=f"watchlist#add#{search}"),
            InlineKeyboardButton("🤖 Smart Search", callback_data="smart_search")
        ])
    else:
        btn = []
        btn.insert(0, [
            InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("🗓️ Season", callback_data=f"seasons#{key}#0"),
            InlineKeyboardButton("📺 Episodes", callback_data=f"episodes#{key}#0")
        ])
        btn.insert(1, [
            InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("📦 Bulk Download", callback_data=f"download_all#{key}")
        ])
        btn.insert(2, [
            InlineKeyboardButton("📝 Watchlist", callback_data=f"watchlist#add#{search}"),
            InlineKeyboardButton("🔍 Advanced Search", callback_data="advanced_search")
        ])
    
    if offset != "":
        req = message.from_user.id if message.from_user else 0
        try:
            if settings.get('max_btn', True):
                nav_buttons = await build_enhanced_navigation(req, key, 0, offset, total_results, settings)
                btn.extend(nav_buttons)
        except KeyError:
            await save_group_settings(message.chat.id, 'max_btn', True)
            btn.append([
                InlineKeyboardButton("📄 Page", callback_data="pages"), 
                InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}", callback_data="pages"), 
                InlineKeyboardButton(text="➡️ Next", callback_data=f"next_{req}_{key}_{offset}")
            ])
    else:
        btn.append([InlineKeyboardButton(text="🚫 That's everything!", callback_data="pages")])
    
    # Enhanced IMDB integration and caption
    imdb = await get_poster(search, file=(files[0]).file_name) if settings.get("imdb", True) else None
    cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    time_difference = timedelta(
        hours=cur_time.hour, 
        minutes=cur_time.minute, 
        seconds=(cur_time.second + (cur_time.microsecond/1000000))
    ) - timedelta(
        hours=curr_time.hour, 
        minutes=curr_time.minute, 
        seconds=(curr_time.second + (curr_time.microsecond/1000000))
    )
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
        cap = await get_enhanced_caption(settings, files, message, total_results, search, 0)
    
    # Send results with enhanced UI
    if imdb and imdb.get('poster'):
        try:
            hehe = await m.edit_photo(photo=imdb.get('poster'), caption=cap, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
            await handle_auto_delete(settings, hehe, message)
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg") 
            hmm = await m.edit_photo(photo=poster, caption=cap, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
            await handle_auto_delete(settings, hmm, message)
        except Exception as e:
            LOGGER.error(e)
            fek = await m.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
            await handle_auto_delete(settings, fek, message)
    else:
        fuk = await m.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
        await handle_auto_delete(settings, fuk, message)

async def handle_auto_delete(settings, response_msg, original_msg):
    """Handle auto-delete functionality"""
    try:
        if settings.get('auto_delete', True):
            await asyncio.sleep(DELETE_TIME)
            await response_msg.delete()
            await original_msg.delete()
    except KeyError:
        await save_group_settings(original_msg.chat.id, 'auto_delete', True)
        await asyncio.sleep(DELETE_TIME)
        await response_msg.delete()
        await original_msg.delete()
    except Exception as e:
        LOGGER.error(f"Error in auto delete: {e}")

# Enhanced spell check with AI
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
    ] for movie in movies]
    
    buttons.append([InlineKeyboardButton(text="❌ Close", callback_data='close_data')])
    
    d = await message.reply_text(
        text=script.CUDNT_FND.format(message.from_user.mention), 
        reply_markup=InlineKeyboardMarkup(buttons), 
        reply_to_message_id=message.id
    )
    await asyncio.sleep(60)
    await d.delete()
    try:
        await message.delete()
    except:
        pass

# New: Background tasks for analytics and cleanup
async def cleanup_cache():
    """Clean up expired cache entries"""
    current_time = datetime.now().timestamp()
    expired_keys = [
        key for key, value in SEARCH_CACHE.items() 
        if (current_time - value['timestamp']) > CACHE_EXPIRY
    ]
    for key in expired_keys:
        del SEARCH_CACHE[key]

async def update_trending():
    """Update trending searches periodically"""
    # This would typically save to database
    pass

# New: User activity tracking
async def track_user_activity(user_id: int, activity: str, data: dict = None):
    """Track user activities for analytics"""
    activity_data = {
        'user_id': user_id,
        'activity': activity,
        'timestamp': datetime.now().isoformat(),
        'data': data or {}
    }
    # In production, save to database
    pass
