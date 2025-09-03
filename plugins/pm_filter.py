import asyncio
import re
import ast
import math
import random
import pytz
import json
import weakref
from datetime import datetime, timedelta, date, time
from contextlib import asynccontextmanager
from collections import defaultdict
from functools import wraps
import speech_recognition as sr
import io
import tempfile
import os

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

# Enhanced Cache Management
class TimedCache:
    def __init__(self, ttl=3600):
        self.cache = {}
        self.timestamps = {}
        self.ttl = ttl
    
    def get(self, key):
        self.cleanup_expired()
        return self.cache.get(key)
    
    def set(self, key, value):
        self.cleanup_expired()
        self.cache[key] = value
        self.timestamps[key] = datetime.now().timestamp()
    
    def cleanup_expired(self):
        now = datetime.now().timestamp()
        expired = [k for k, t in self.timestamps.items() if now - t > self.ttl]
        for key in expired:
            self.cache.pop(key, None)
            self.timestamps.pop(key, None)

# Replace global dictionaries with timed caches
BUTTON_CACHE = TimedCache(1800)  # 30 minutes
FRESH_CACHE = TimedCache(1800)
SPELL_CHECK_CACHE = TimedCache(900)  # 15 minutes

# Voice Recognition Setup
recognizer = sr.Recognizer()

# Retry decorator
def retry_on_error(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        LOGGER.error(f"Function {func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    await asyncio.sleep(delay * (2 ** attempt))
            return None
        return wrapper
    return decorator

# Database transaction manager
@asynccontextmanager
async def db_transaction():
    try:
        yield
    except Exception:
        raise

# Voice Search Handler
@Client.on_message(filters.private & filters.voice)
async def voice_search(client, message):
    """Handle voice messages for search queries"""
    user_id = message.from_user.id
    
    # Check maintenance mode
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and user_id not in ADMINS:
        await message.reply_text("🚧 Currently upgrading… Will return soon 🔜")
        return
    
    # Check premium for voice search if required
    is_premium = await db.has_premium_access(user_id)
    if VOICE_SEARCH_PREMIUM_ONLY and not is_premium:
        btn = [[InlineKeyboardButton("💰 Get Premium", callback_data='buy')]]
        await message.reply_text(
            "🎤 Voice search is a premium feature. Upgrade to access it!",
            reply_markup=InlineKeyboardMarkup(btn)
        )
        return
    
    processing_msg = await message.reply_text("🎤 Processing voice message...")
    
    try:
        # Download voice file
        voice_file = await message.download()
        
        # Convert to text using speech recognition
        search_text = await convert_voice_to_text(voice_file)
        
        if not search_text:
            await processing_msg.edit_text(
                "❌ Could not understand the voice message. Please try again or type your search."
            )
            return
        
        await processing_msg.edit_text(f"🎤 Heard: \"{search_text}\"\n🔍 Searching...")
        
        # Clean up the voice file
        try:
            os.remove(voice_file)
        except:
            pass
        
        # Process the search
        message.text = search_text
        await processing_msg.delete()
        await auto_filter(client, message)
        
    except Exception as e:
        LOGGER.error(f"Voice search error: {e}")
        await processing_msg.edit_text(
            "❌ Error processing voice message. Please try again."
        )

async def convert_voice_to_text(voice_file_path):
    """Convert voice file to text using speech recognition"""
    try:
        with sr.AudioFile(voice_file_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language='en-US')
            return text.strip()
    except sr.UnknownValueError:
        # Try with different languages
        languages = ['hi-IN', 'ta-IN', 'te-IN']  # Hindi, Tamil, Telugu
        for lang in languages:
            try:
                with sr.AudioFile(voice_file_path) as source:
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data, language=lang)
                    return text.strip()
            except:
                continue
        return None
    except Exception as e:
        LOGGER.error(f"Speech recognition error: {e}")
        return None

# Enhanced search suggestions
async def get_search_suggestions(search_text, limit=5):
    """Get search suggestions based on partial input"""
    suggestions = []
    
    # Get from database - popular searches
    try:
        popular = await get_trending_searches(days=30)
        for term, count in popular:
            if search_text.lower() in term.lower():
                suggestions.append(term)
                if len(suggestions) >= limit:
                    break
    except:
        pass
    
    # Add some common completions
    common_suffixes = ['movie', 'series', '2024', '2023', 'hindi', 'english']
    for suffix in common_suffixes:
        candidate = f"{search_text} {suffix}"
        if candidate not in suggestions:
            suggestions.append(candidate)
            if len(suggestions) >= limit:
                break
    
    return suggestions[:limit]

# Smart auto-complete for text messages
@Client.on_message(filters.private & filters.text & ~filters.command)
async def enhanced_search_with_suggestions(client, message):
    search_text = message.text.strip()
    user_id = message.from_user.id
    
    # Check maintenance
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and user_id not in ADMINS:
        await message.reply_text("🚧 Currently upgrading… Will return soon 🔜")
        return
    
    # Auto-suggestions for short queries
    if 3 <= len(search_text) <= 15:
        suggestions = await get_search_suggestions(search_text)
        if len(suggestions) > 1:
            btn = []
            for sugg in suggestions[:5]:
                btn.append([InlineKeyboardButton(
                    f"🔍 {sugg}", 
                    callback_data=f"search_suggestion:{sugg}"
                )])
            btn.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")])
            btn.append([InlineKeyboardButton("🎤 Voice Search", callback_data="voice_search_help")])
            
            await message.reply_text(
                f"💡 Search suggestions for: <code>{search_text}</code>",
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
            return
    
    await auto_filter(client, message)

# Handle search suggestions callback
@Client.on_callback_query(filters.regex(r"^search_suggestion:"))
async def handle_search_suggestion(client, query):
    search_term = query.data.split(":", 1)[1]
    
    # Create a fake message object for auto_filter
    message = query.message.reply_to_message
    message.text = search_term
    
    await query.message.delete()
    await auto_filter(client, message)

@Client.on_callback_query(filters.regex(r"^voice_search_help"))
async def voice_search_help(client, query):
    await query.answer(
        "🎤 Send a voice message to search! Just record your movie/series name and send it.",
        show_alert=True
    )

@Client.on_callback_query(filters.regex(r"^cancel_search"))
async def cancel_search(client, query):
    await query.message.delete()

# Enhanced file information
async def get_enhanced_file_info(file):
    """Extract detailed file information"""
    filename = file.file_name.lower()
    
    # Extract quality
    quality_patterns = [
        (r'2160p|4k', '4K UHD'),
        (r'1440p', '2K QHD'),
        (r'1080p', 'Full HD'),
        (r'720p', 'HD'),
        (r'480p', 'SD'),
        (r'360p', 'Low Quality')
    ]
    
    quality = 'Unknown'
    for pattern, label in quality_patterns:
        if re.search(pattern, filename):
            quality = label
            break
    
    # Extract audio info
    audio_patterns = [
        (r'atmos', 'Dolby Atmos'),
        (r'dts', 'DTS'),
        (r'aac', 'AAC'),
        (r'ac3', 'AC3'),
        (r'mp3', 'MP3')
    ]
    
    audio = 'Unknown'
    for pattern, label in audio_patterns:
        if re.search(pattern, filename):
            audio = label
            break
    
    # Check for subtitles
    has_subtitles = bool(re.search(r'sub|srt', filename))
    
    # Get file format
    file_format = filename.split('.')[-1].upper() if '.' in filename else 'Unknown'
    
    return {
        'quality': quality,
        'audio': audio,
        'subtitles': 'Yes' if has_subtitles else 'No',
        'format': file_format,
        'size': get_size(file.file_size)
    }

# User preferences management
async def save_user_preference(user_id, pref_type, value):
    """Save user preference to database"""
    try:
        await db.upsert_user_preference(user_id, pref_type, value)
    except Exception as e:
        LOGGER.error(f"Error saving preference: {e}")

async def get_user_preferences(user_id):
    """Get user preferences from database"""
    try:
        return await db.get_user_preferences(user_id) or {}
    except Exception as e:
        LOGGER.error(f"Error getting preferences: {e}")
        return {}

async def get_personalized_results(user_id, files):
    """Sort files based on user preferences"""
    prefs = await get_user_preferences(user_id)
    preferred_quality = prefs.get('quality', '1080p').lower()
    preferred_lang = prefs.get('language', 'english').lower()
    
    def sort_key(file):
        score = 0
        filename = file.file_name.lower()
        
        if preferred_quality in filename:
            score += 10
        if preferred_lang in filename:
            score += 5
        if 'x265' in filename or 'hevc' in filename:
            score += 3  # Prefer smaller file sizes
        
        return score
    
    return sorted(files, key=sort_key, reverse=True)

# Analytics functions
async def log_search_analytics(user_id, search_term, results_count):
    """Log search for analytics"""
    try:
        await db.log_search(user_id, search_term, results_count, datetime.now())
    except Exception as e:
        LOGGER.error(f"Error logging search: {e}")

async def get_trending_searches(days=7):
    """Get trending searches from the past N days"""
    try:
        return await db.get_popular_searches(days)
    except Exception as e:
        LOGGER.error(f"Error getting trending searches: {e}")
        return []

# Enhanced group message handler
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
        await message.reply_text("🚧 Currently upgrading… Will return soon 🔜")
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
        temp_files, temp_offset, total_results = await get_search_results(
            chat_id=message.chat.id, query=search.lower(), offset=0, filter=True
        )
        if total_results == 0:
            return
        else:
            return await message.reply_text(
                f"<b>✨ Hello {message.from_user.mention}! \n\n✅ Your request is already available. \n📂 Files found: {str(total_results)} \n🔍 Search: <code>{search}</code> \n‼️ This is a <u>support group</u>, so you can't get files from here. \n\n📝 Search Here 👇</b>",   
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Join & Explore 🔍", url=GRP_LNK)]])
            )

# Enhanced private message handler
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
    if maintenance_mode and user_id not in ADMINS:
        await message.reply_text("🚧 Currently upgrading… Will return soon 🔜")
        return
    
    if content.startswith(("/", "#")):
        return  
    
    try:
        await silentdb.update_top_messages(user_id, content)
        pm_search = await db.pm_search_status(bot_id)
        if pm_search:
            await auto_filter(bot, message)
        else:
            btn = [[InlineKeyboardButton("🔍 Start Search", url=GRP_LNK)]]
            await message.reply_text(
                "<b><i>⚠️ Not available here! Join & search below 👇</i></b>",   
                reply_markup=InlineKeyboardMarkup(btn)
            )
    except Exception as e:
        LOGGER.error(f"An error occurred: {str(e)}")

# Enhanced callback query handler for pagination
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
        
        search = BUTTON_CACHE.get(key) or FRESH_CACHE.get(key)
        if not search:
            await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name), show_alert=True)
            return
        
        files, n_offset, total = await get_search_results(
            query.message.chat.id, search, offset=offset, filter=True
        )
        
        # Personalize results
        files = await get_personalized_results(query.from_user.id, files)
        
        try:
            n_offset = int(n_offset)
        except:
            n_offset = 0
        
        if not files:
            return
        
        temp.GETALL[key] = files
        temp.SHORT[query.from_user.id] = query.message.chat.id
        settings = await get_settings(query.message.chat.id)
        
        btn = await create_file_buttons(files, key, settings)
        
        # Add pagination
        btn = await add_pagination_buttons(btn, req, key, offset, n_offset, total, settings)
        
        if not settings.get('button'):
            cap = await get_results_caption(settings, files, query, total, search, offset)
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
        
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error in next_page: {e}")

async def create_file_buttons(files, key, settings):
    """Create file buttons with enhanced information"""
    btn = []
    
    if settings.get('button'):
        for file in files:
            file_info = await get_enhanced_file_info(file)
            btn.append([
                InlineKeyboardButton(
                    text=f"{file_info['size']} | {file_info['quality']} | {clean_filename(file.file_name)}", 
                    callback_data=f'file#{file.file_id}'
                )
            ])
    
    # Add filter buttons
    btn.insert(0, [
        InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
        InlineKeyboardButton("🗓️ Season", callback_data=f"seasons#{key}#0")
    ])
    
    btn.insert(1, [
        InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}"),
        InlineKeyboardButton("📊 File Details", callback_data=f"file_details#{key}")
    ])
    
    return btn

async def add_pagination_buttons(btn, req, key, offset, n_offset, total, settings):
    """Add pagination buttons"""
    try:
        max_btn = 10 if settings.get('max_btn', True) else int(MAX_B_TN)
        
        if 0 < offset <= max_btn:
            off_set = 0
        elif offset == 0:
            off_set = None
        else:
            off_set = offset - max_btn
        
        if n_offset == 0:
            btn.append([
                InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"), 
                InlineKeyboardButton(f"{math.ceil(int(offset)/max_btn)+1} / {math.ceil(total/max_btn)}", callback_data="pages")
            ])
        elif off_set is None:
            btn.append([
                InlineKeyboardButton("📄 Page", callback_data="pages"), 
                InlineKeyboardButton(f"{math.ceil(int(offset)/max_btn)+1} / {math.ceil(total/max_btn)}", callback_data="pages"), 
                InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
            ])
        else:
            btn.append([
                InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"{math.ceil(int(offset)/max_btn)+1} / {math.ceil(total/max_btn)}", callback_data="pages"),
                InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
            ])
    except Exception as e:
        LOGGER.error(f"Error in pagination: {e}")
    
    return btn

async def get_results_caption(settings, files, query, total, search, offset):
    """Generate results caption"""
    remaining_seconds = "0.50"  # Simplified for now
    
    if not settings.get('button'):
        cap = f"<b>✨ Hello {query.from_user.mention}!\n\n📂 Results for: <code>{search}</code>\n📊 Total: {total} files</b>\n\n"
        
        for file_num, file in enumerate(files, start=offset+1):
            file_info = await get_enhanced_file_info(file)
            cap += f"<b>{file_num}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file.file_id}'>"
            cap += f"{file_info['size']} | {file_info['quality']} | {clean_filename(file.file_name)}</a></b>\n\n"
    else:
        cap = f"<b>✨ Hello {query.from_user.mention}!\n\n📂 Results for: <code>{search}</code>\n📊 Found {total} files</b>"
    
    return cap

# Enhanced quality filter
@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_cb_handler(client: Client, query: CallbackQuery):
    try:
        _, key, offset = query.data.split("#")
        search = FRESH_CACHE.get(key)
        offset = int(offset)
        
        # Create quality buttons
        btn = []
        qualities = ['4K', '1080p', '720p', '480p', 'CAM', 'HDRip']
        
        for i in range(0, len(qualities)-1, 2):
            btn.append([
                InlineKeyboardButton(
                    text=qualities[i],
                    callback_data=f"fq#{qualities[i].lower()}#{key}#{offset}"
                ),
                InlineKeyboardButton(
                    text=qualities[i+1] if i+1 < len(qualities) else qualities[i],
                    callback_data=f"fq#{qualities[i+1].lower() if i+1 < len(qualities) else qualities[i].lower()}#{key}#{offset}"
                ),
            ])
        
        btn.insert(0, [InlineKeyboardButton("🎯 Select Quality", callback_data="ident")])
        btn.append([InlineKeyboardButton("📂 Back to Files", callback_data=f"fq#homepage#{key}#{offset}")])
        
        await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    except Exception as e:
        LOGGER.error(f"Error in quality handler: {e}")

# File details handler
@Client.on_callback_query(filters.regex(r"^file_details#"))
async def file_details_handler(client, query):
    try:
        _, key = query.data.split("#")
        files = temp.GETALL.get(key, [])
        
        if not files:
            await query.answer("No files found!", show_alert=True)
            return
        
        details = "📊 **File Statistics:**\n\n"
        
        # Count by quality
        quality_counts = {}
        total_size = 0
        
        for file in files:
            file_info = await get_enhanced_file_info(file)
            quality = file_info['quality']
            quality_counts[quality] = quality_counts.get(quality, 0) + 1
            
            try:
                total_size += file.file_size
            except:
                pass
        
        for quality, count in quality_counts.items():
            details += f"🎯 {quality}: {count} files\n"
        
        details += f"\n📦 Total Size: {get_size(total_size)}\n"
        details += f"📁 Total Files: {len(files)}"
        
        await query.answer(details, show_alert=True)
        
    except Exception as e:
        LOGGER.error(f"Error in file details: {e}")
        await query.answer("Error getting file details", show_alert=True)

# Batch download handler
@Client.on_callback_query(filters.regex(r"^batch_download:"))
async def batch_download(client, query):
    try:
        _, key = query.data.split(":", 1)
        files = temp.GETALL.get(key, [])
        user_id = query.from_user.id
        
        # Check premium for batch download
        is_premium = await db.has_premium_access(user_id)
        if not is_premium:
            await query.answer("🔒 Batch download is a premium feature!", show_alert=True)
            return
        
        if len(files) > 10:
            await query.answer("⚠️ Maximum 10 files at once!", show_alert=True)
            return
        
        progress_msg = await query.message.reply_text("📦 Preparing batch download...")
        
        for i, file in enumerate(files[:10]):
            try:
                await client.send_cached_media(
                    chat_id=user_id,
                    file_id=file.file_id,
                    caption=f"📦 {i+1}/{len(files)} - {file.file_name}"
                )
                await progress_msg.edit_text(f"📦 Sending {i+1}/{len(files)} files...")
                await asyncio.sleep(1)  # Rate limiting
            except Exception as e:
                LOGGER.error(f"Failed to send file {file.file_id}: {e}")
        
        await progress_msg.edit_text("✅ Batch download completed!")
        
    except Exception as e:
        LOGGER.error(f"Error in batch download: {e}")

# Add trending searches command
@Client.on_message(filters.command("trending"))
async def show_trending(client, message):
    try:
        trending = await get_trending_searches(7)
        if not trending:
            await message.reply_text("📊 No trending searches available yet.")
            return
        
        text = "🔥 **Trending Searches (Last 7 Days):**\n\n"
        
        for i, (search, count) in enumerate(trending[:10], 1):
            text += f"{i}. `{search}` ({count} searches)\n"
        
        btn = [[InlineKeyboardButton("🎤 Voice Search", callback_data="voice_search_help")]]
        
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))
        
    except Exception as e:
        LOGGER.error(f"Error showing trending: {e}")

# Enhanced auto filter function with voice search integration
@retry_on_error(max_retries=3)
async def auto_filter(client, msg, spoll=False):
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    
    if not spoll:
        message = msg
        if message.text.startswith("/"):
            return
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        
        if len(message.text) < 100:
            search = await replace_words(message.text)		
            search = search.lower()
            search = search.replace("-", " ")
            search = search.replace(":", "")
            search = re.sub(r'\s+', ' ', search).strip()
            
            m = await message.reply_text(
                f'<b>🕐 Searching for: <code>{search}</code>...</b>', 
                reply_to_message_id=message.id
            )
            
            # Log search analytics
            files, offset, total_results = await get_search_results(
                message.chat.id, search, offset=0, filter=True
            )
            await log_search_analytics(message.from_user.id, search, total_results)
            
            # Personalize results
            files = await get_personalized_results(message.from_user.id, files)
            
            settings = await get_settings(message.chat.id)
            
            if not files:
                if settings["spell_check"]:
                    ai_sts = await m.edit('🤖 Checking spelling with AI...')
                    is_misspelled = await ai_spell_check(chat_id=message.chat.id, wrong_name=search)
                    if is_misspelled:
                        await ai_sts.edit(f'<b>🔹 Suggestion: <code>{is_misspelled}</code></b>')
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
        m = await message.reply_text(
            f'<b>🕐 Searching for: <code>{search}</code>...</b>', 
            reply_to_message_id=message.id
        )
        settings = await get_settings(message.chat.id)
        await msg.message.delete()

    key = f"{message.chat.id}-{message.id}"
    FRESH_CACHE.set(key, search)
    temp.GETALL[key] = files
    temp.SHORT[message.from_user.id] = message.chat.id
    
    btn = await create_file_buttons(files, key, settings)
    
    if offset != "":
        req = message.from_user.id if message.from_user else 0
        btn = await add_pagination_buttons(btn, req, key, 0, offset, total_results, settings)
    else:
        btn.append([InlineKeyboardButton("🚫 That's everything!", callback_data="pages")])
    
    # Get IMDB info if enabled
    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    
    # Create caption
    if imdb:
        cap = await create_imdb_caption(search, imdb, files, message, settings)
        temp.IMDB_CAP[message.from_user.id] = cap
    else:
        cap = await create_simple_caption(search, files, message, settings)
    
    # Send response with poster if available
    try:
        if imdb and imdb.get('poster'):
            try:
                response_msg = await m.edit_photo(
                    photo=imdb.get('poster'), 
                    caption=cap, 
                    reply_markup=InlineKeyboardMarkup(btn), 
                    parse_mode=enums.ParseMode.HTML
                )
            except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
                poster = imdb.get('poster', '').replace('.jpg', "._V1_UX360.jpg") 
                response_msg = await m.edit_photo(
                    photo=poster, 
                    caption=cap, 
                    reply_markup=InlineKeyboardMarkup(btn), 
                    parse_mode=enums.ParseMode.HTML
                )
        else:
            response_msg = await m.edit_text(
                text=cap, 
                reply_markup=InlineKeyboardMarkup(btn), 
                disable_web_page_preview=True, 
                parse_mode=enums.ParseMode.HTML
            )
        
        # Auto-delete if enabled
        if settings.get('auto_delete', False):
            await asyncio.sleep(DELETE_TIME)
            try:
                await response_msg.delete()
                await message.delete()
            except:
                pass
                
    except Exception as e:
        LOGGER.error(f"Error in auto_filter: {e}")

async def create_imdb_caption(search, imdb, files, message, settings):
    """Create IMDB-enhanced caption"""
    TEMPLATE = script.IMDB_TEMPLATE_TXT
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
        url=imdb['url']
    )
    
    if not settings.get('button'):
        for file_num, file in enumerate(files, start=1):
            file_info = await get_enhanced_file_info(file)
            cap += f"\n\n<b>{file_num}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>"
            cap += f"{file_info['size']} | {file_info['quality']} | {clean_filename(file.file_name)}</a></b>"
    
    return cap

async def create_simple_caption(search, files, message, settings):
    """Create simple caption without IMDB"""
    cap = f"<b>✨ Hello {message.from_user.mention}!\n\n📂 Results for: <code>{search}</code>\n📊 Found {len(files)} files</b>\n\n"
    
    if not settings.get('button'):
        for file_num, file in enumerate(files, start=1):
            file_info = await get_enhanced_file_info(file)
            cap += f"<b>{file_num}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>"
            cap += f"{file_info['size']} | {file_info['quality']} | {clean_filename(file.file_name)}</a></b>\n\n"
    
    return cap

# AI spell check with voice search integration
async def ai_spell_check(chat_id, wrong_name):
    """Enhanced spell check with voice search suggestions"""
    # Check cache first
    cached_result = SPELL_CHECK_CACHE.get(wrong_name)
    if cached_result:
        return cached_result
    
    async def search_movie(wrong_name):
        try:
            search_results = imdb.search_movie(wrong_name)
            movie_list = [movie['title'] for movie in search_results]
            return movie_list
        except:
            return []
    
    movie_list = await search_movie(wrong_name)
    if not movie_list:
        return None
    
    for _ in range(5):
        closest_match = process.extractOne(wrong_name, movie_list)
        if not closest_match or closest_match[1] <= 80:
            return None
        
        movie = closest_match[0]
        files, offset, total_results = await get_search_results(chat_id=chat_id, query=movie)
        if files:
            # Cache the result
            SPELL_CHECK_CACHE.set(wrong_name, movie)
            return movie
        movie_list.remove(movie)
    
    return None

# Enhanced advantage spell check
async def advantage_spell_chok(client, message):
    """Enhanced spell check with voice search option"""
    search = message.text
    chat_id = message.chat.id
    
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", message.text, flags=re.IGNORECASE
    )
    query = query.strip() + " movie"
    
    try:
        movies = await get_poster(search, bulk=True)
    except Exception as e:
        LOGGER.error(f"Error getting movie suggestions: {e}")
        google = search.replace(" ", "+")
        button = [[
            InlineKeyboardButton("💡 Google Search", url=f"https://www.google.com/search?q={google}"),
            InlineKeyboardButton("🎤 Try Voice Search", callback_data="voice_search_help")
        ]]
        k = await message.reply_text(
            text=script.I_CUDNT.format(search), 
            reply_markup=InlineKeyboardMarkup(button)
        )
        await asyncio.sleep(60)
        await k.delete()
        return
    
    if not movies:
        google = search.replace(" ", "+")
        button = [[
            InlineKeyboardButton("💡 Google Search", url=f"https://www.google.com/search?q={google}"),
            InlineKeyboardButton("🎤 Try Voice Search", callback_data="voice_search_help")
        ]]
        k = await message.reply_text(
            text=script.I_CUDNT.format(search), 
            reply_markup=InlineKeyboardMarkup(button)
        )
        await asyncio.sleep(60)
        await k.delete()
        return
    
    user = message.from_user.id if message.from_user else 0
    buttons = []
    
    for movie in movies:
        buttons.append([InlineKeyboardButton(
            text=movie.get('title'), 
            callback_data=f"spol#{movie.movieID}#{user}"
        )])
    
    buttons.append([
        InlineKeyboardButton("🎤 Try Voice Search", callback_data="voice_search_help"),
        InlineKeyboardButton("❌ Close", callback_data='close_data')
    ])
    
    d = await message.reply_text(
        text=script.CUDNT_FND.format(message.from_user.mention), 
        reply_markup=InlineKeyboardMarkup(buttons), 
        reply_to_message_id=message.id
    )
    await asyncio.sleep(60)
    await d.delete()

# Enhanced callback query handler for spell check
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
    
    files, offset, total_results = await get_search_results(
        query.message.chat.id, movie, offset=0, filter=True
    )
    
    if files:
        k = (movie, files, offset, total_results)
        await auto_filter(bot, query, k)
    else:
        reqstr1 = query.from_user.id if query.from_user else 0
        reqstr = await bot.get_users(reqstr1)
        if NO_RESULTS_MSG:
            await bot.send_message(
                chat_id=BIN_CHANNEL,
                text=script.NORSLTS.format(reqstr.id, reqstr.mention, movie)
            )
        
        contact_buttons = [[
            InlineKeyboardButton("🔔 Request to Admin", url=OWNER_LNK),
            InlineKeyboardButton("🎤 Try Voice Search", callback_data="voice_search_help")
        ]]
        
        k = await query.message.edit(
            script.MVE_NT_FND,
            reply_markup=InlineKeyboardMarkup(contact_buttons)
        )
        await asyncio.sleep(10)
        await k.delete()

# Enhanced quality filter handler
@Client.on_callback_query(filters.regex(r"^fq#"))
async def filter_qualities_cb_handler(client: Client, query: CallbackQuery):
    try:
        _, qual, key, offset = query.data.split("#")
        offset = int(offset)
        search = FRESH_CACHE.get(key)
        
        if not search:
            await query.answer("Session expired. Please search again.", show_alert=True)
            return
        
        search = search.replace("_", " ")
        
        # Remove existing quality from search if present
        for q in ['4k', '1080p', '720p', '480p', 'cam', 'hdrip']:
            search = re.sub(rf'\b{q}\b', '', search, flags=re.IGNORECASE)
        
        if qual != "homepage":
            search = f"{search} {qual}".strip()
        
        BUTTON_CACHE.set(key, search)
        
        files, n_offset, total_results = await get_search_results(
            query.message.chat.id, search, offset=offset, filter=True
        )
        
        if not files:
            await query.answer("⚡ No files found for this quality!", show_alert=True)
            return
        
        # Personalize results
        files = await get_personalized_results(query.from_user.id, files)
        
        temp.GETALL[key] = files
        settings = await get_settings(query.message.chat.id)
        
        btn = await create_file_buttons(files, key, settings)
        
        if n_offset != "":
            req = query.from_user.id
            btn = await add_pagination_buttons(btn, req, key, offset, n_offset, total_results, settings)
        else:
            btn.append([InlineKeyboardButton("🚫 That's everything!", callback_data="pages")])
        
        if not settings.get('button'):
            cap = await create_simple_caption(search, files, query.message, settings)
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
        
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error in quality filter: {e}")

# Enhanced seasons handler
@Client.on_callback_query(filters.regex(r"^seasons#"))
async def season_cb_handler(client: Client, query: CallbackQuery):
    try:
        _, key, offset = query.data.split("#")
        search = FRESH_CACHE.get(key)
        offset = int(offset)
        
        btn = []
        seasons = ['Season 1', 'Season 2', 'Season 3', 'Season 4', 'Season 5', 'Season 6']
        
        for i in range(0, len(seasons)-1, 2):
            btn.append([
                InlineKeyboardButton(
                    text=seasons[i],
                    callback_data=f"fs#{seasons[i].lower().replace(' ', '')}#{key}#{offset}"
                ),
                InlineKeyboardButton(
                    text=seasons[i+1] if i+1 < len(seasons) else seasons[i],
                    callback_data=f"fs#{seasons[i+1].lower().replace(' ', '') if i+1 < len(seasons) else seasons[i].lower().replace(' ', '')}#{key}#{offset}"
                ),
            ])
        
        btn.insert(0, [InlineKeyboardButton("🗓️ Select Season", callback_data="ident")])
        btn.append([InlineKeyboardButton("📂 Back to Files", callback_data=f"fs#homepage#{key}#{offset}")])
        
        await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    except Exception as e:
        LOGGER.error(f"Error in season handler: {e}")

# Enhanced season filter
@Client.on_callback_query(filters.regex(r"^fs#"))
async def filter_season_cb_handler(client: Client, query: CallbackQuery):
    try:
        _, seas, key, offset = query.data.split("#")
        offset = int(offset)
        search = FRESH_CACHE.get(key)
        
        if not search:
            await query.answer("Session expired. Please search again.", show_alert=True)
            return
        
        search = search.replace("_", " ")
        
        # Remove existing season from search
        search = re.sub(r'\bseason\s*\d+\b', '', search, flags=re.IGNORECASE)
        
        if seas != "homepage":
            search = f"{search} {seas.replace('season', 'season ')}".strip()
        
        BUTTON_CACHE.set(key, search)
        
        files, n_offset, total_results = await get_search_results(
            query.message.chat.id, search, offset=offset, filter=True
        )
        
        if not files:
            await query.answer("⚡ No files found for this season!", show_alert=True)
            return
        
        # Personalize results
        files = await get_personalized_results(query.from_user.id, files)
        
        temp.GETALL[key] = files
        settings = await get_settings(query.message.chat.id)
        
        btn = await create_file_buttons(files, key, settings)
        
        if n_offset != "":
            req = query.from_user.id
            btn = await add_pagination_buttons(btn, req, key, offset, n_offset, total_results, settings)
        else:
            btn.append([InlineKeyboardButton("🚫 That's everything!", callback_data="pages")])
        
        if not settings.get('button'):
            cap = await create_simple_caption(search, files, query.message, settings)
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
        
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error in season filter: {e}")

# Main callback query handler
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    try:
        data = query.data
        
        if data == "close_data":
            await query.message.delete()
            return
        
        # Voice search help
        if data == "voice_search_help":
            help_text = """🎤 **Voice Search Guide:**

1. Record a voice message with your search query
2. Say the movie/series name clearly
3. Supported languages: English, Hindi, Tamil, Telugu
4. Example: "Avengers Endgame" or "KGF Chapter 2"

**Tips:**
• Speak clearly and slowly
• Use popular names/titles
• Avoid background noise"""
            
            await query.answer(help_text, show_alert=True)
            return
        
        # Handle file requests
        if data.startswith("file"):
            ident, file_id = data.split("#")
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}")
            return
        
        # Handle send all files
        if data.startswith("sendfiles"):
            ident, key = data.split("#")
            try:
                await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=allfiles_{query.message.chat.id}_{key}")
                return
            except UserIsBlocked:
                await query.answer('🔓 Unblock the Bot!', show_alert=True)
            except PeerIdInvalid:
                await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles3_{key}")
            except Exception as e:
                LOGGER.error(f"Error in sendfiles: {e}")
                await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles4_{key}")
            return
        
        # Handle premium and other callbacks (keeping original logic)
        if data == "premium":
            btn = [[
                InlineKeyboardButton('💰 Contribute', callback_data='buy'),
            ],[
                InlineKeyboardButton('👥 Invite Friends', callback_data='reffff'),
                InlineKeyboardButton('🎤 Voice Search', callback_data='voice_search_help')
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
            return
        
        # Start menu
        if data == "start":
            buttons = [[
                InlineKeyboardButton('🚀 Add Me Now!', url=f'http://telegram.me/{temp.U_NAME}?startgroup=true')
            ],[
                InlineKeyboardButton('🔥 Trending', callback_data="topsearch"),
                InlineKeyboardButton('💖 Support Us', callback_data="premium"),
            ],[
                InlineKeyboardButton('🆘 Help', callback_data='disclaimer'),
                InlineKeyboardButton('ℹ️ About', callback_data='me')
            ],[
                InlineKeyboardButton('🎤 Voice Search Guide', callback_data='voice_search_help'),
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
            return
        
        await query.answer("🔄 Processing...", show_alert=False)
        
    except Exception as e:
        LOGGER.error(f"Error in callback handler: {e}")
        await query.answer("❌ Something went wrong!", show_alert=True)
