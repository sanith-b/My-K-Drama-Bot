import time
import re
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from info import ADMINS, DATABASE_URI, DATABASE_NAME, INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp, get_readable_time
from math import ceil
from logging_helper import LOGGER
import json
import os
from motor.motor_asyncio import AsyncIOMotorClient

lock = asyncio.Lock()

# MongoDB setup
mongodb_client = AsyncIOMotorClient(DATABASE_URI)
mongodb = mongodb_client[DATABASE_NAME]
auto_index_collection = mongodb['auto_index_config']
private_index_collection = mongodb['private_index_sessions']
forwarded_files_collection = mongodb['forwarded_files_temp']
bulk_queue_collection = mongodb['bulk_queue']

# File extension filters
SUPPORTED_VIDEO_FORMATS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
SUPPORTED_AUDIO_FORMATS = {'.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma'}
SUPPORTED_SUBTITLE_FORMATS = {'.srt', '.vtt', '.ass', '.ssa', '.sub', '.idx'}
SUPPORTED_DOCUMENT_FORMATS = {'.pdf', '.txt', '.doc', '.docx', '.zip', '.rar', '.7z'}

# Load auto-indexing configuration from database
async def load_auto_index_config():
    try:
        config = {}
        async for doc in auto_index_collection.find():
            chat_id = str(doc['chat_id'])
            config[chat_id] = {
                'enabled': doc.get('enabled', False),
                'chat_title': doc.get('chat_title', ''),
                'filters': doc.get('filters', []),
                'private_mode': doc.get('private_mode', False),
                'last_indexed_msg': doc.get('last_indexed_msg', 0)
            }
        return config
    except Exception as e:
        LOGGER.error(f"Error loading auto-index config: {e}")
        return {}

# Save auto-indexing configuration to database
async def save_auto_index_config(chat_id, settings):
    try:
        await auto_index_collection.update_one(
            {'chat_id': int(chat_id)},
            {'$set': settings},
            upsert=True
        )
    except Exception as e:
        LOGGER.error(f"Error saving auto-index config: {e}")

# Delete auto-indexing configuration from database
async def delete_auto_index_config(chat_id):
    try:
        await auto_index_collection.delete_one({'chat_id': int(chat_id)})
    except Exception as e:
        LOGGER.error(f"Error deleting auto-index config: {e}")

# Get file extension from filename
def get_file_extension(filename):
    if not filename:
        return None
    return os.path.splitext(filename.lower())[1]

# Check if file should be indexed based on filters
def should_index_file(media, file_filters):
    if not file_filters:
        return True
    
    filename = getattr(media, 'file_name', '') or ''
    extension = get_file_extension(filename)
    
    return extension in file_filters

# Progress bar for visual feedback
def get_progress_bar(percent, length=10):
    filled = int(length * percent / 100)
    unfilled = length - filled
    return '█' * filled + '▒' * unfilled

# ==================== PRIVATE INDEXING METHODS ====================

@Client.on_message(filters.command('privateindex') & filters.user(ADMINS))
async def start_private_indexing(bot, message):
    """Start private channel indexing session using forward method"""
    if len(message.command) < 2:
        # Show available sessions
        sessions = []
        async for session in private_index_collection.find({'admin_id': message.from_user.id}):
            sessions.append(session)
        
        session_list = ""
        if sessions:
            session_list = "\n\n📋 Your Sessions:\n"
            for session in sessions[-5:]:  # Show last 5
                status_icon = "✅" if session['status'] == 'completed' else "🔄" if session['status'] == 'active' else "⏸️"
                session_list += f"{status_icon} `{session['session_name']}` - {session.get('indexed_count', 0)} files\n"
        
        return await message.reply(
            "🔒 **Private Channel Indexing**\n\n"
            "💡 **Usage:** `/privateindex session_name`\n\n"
            "📋 **Available Methods:**\n"
            "1️⃣ **Forward Method** - Forward messages one by one\n"
            "2️⃣ **Bulk Forward** - Queue multiple messages\n"
            "3️⃣ **JSON Import** - Import from exported data\n"
            "4️⃣ **Media Share** - Share media files directly\n\n"
            "🔧 **Commands:**\n"
            "• `/privateindex session_name` - Start session\n"
            "• `/bulkprivate session_name` - Start bulk mode\n"
            "• `/importjson session_name` - Import JSON\n"
            "• `/mediashare session_name` - Share media mode\n"
            "• `/endprivate session_name` - End session\n"
            "• `/privatestatus [session]` - Check status\n"
            "• `/privatesessions` - List all sessions" + session_list
        )
    
    session_name = " ".join(message.command[1:])
    
    # Check if session already exists and is active
    existing_session = await private_index_collection.find_one({
        'session_name': session_name,
        'admin_id': message.from_user.id,
        'status': 'active'
    })
    
    if existing_session:
        return await message.reply(
            f"⚠️ Session `{session_name}` is already active!\n"
            f"📊 Current count: {existing_session.get('indexed_count', 0)}\n"
            f"Use `/endprivate {session_name}` to end it first."
        )
    
    # Create new indexing session
    session_data = {
        'session_name': session_name,
        'admin_id': message.from_user.id,
        'created_at': time.time(),
        'status': 'active',
        'indexed_count': 0,
        'duplicates': 0,
        'errors': 0,
        'method': 'forward',
        'last_activity': time.time()
    }
    
    await private_index_collection.update_one(
        {'session_name': session_name, 'admin_id': message.from_user.id},
        {'$set': session_data},
        upsert=True
    )
    
    file_filters = getattr(temp, 'FILE_FILTERS', set())
    filter_info = f"🔍 **Active Filters:** {', '.join(file_filters)}" if file_filters else "🔍 **Filters:** None (All supported files)"
    
    await message.reply(
        f"🔒 **Private Indexing Session Started**\n\n"
        f"📝 **Session:** `{session_name}`\n"
        f"🆔 **Admin:** {message.from_user.mention}\n"
        f"{filter_info}\n\n"
        f"📋 **Instructions:**\n"
        f"1. Forward messages from private channels to this chat\n"
        f"2. Files will be automatically indexed\n"
        f"3. Use `/privatestatus {session_name}` to check progress\n"
        f"4. Use `/endprivate {session_name}` when finished\n\n"
        f"⚡ **Ready to receive forwards!**"
    )

@Client.on_message(filters.command('bulkprivate') & filters.user(ADMINS))
async def start_bulk_private_indexing(bot, message):
    """Start bulk private indexing session"""
    if len(message.command) < 2:
        return await message.reply(
            "💡 **Usage:** `/bulkprivate session_name`\n\n"
            "📦 **Bulk Mode Features:**\n"
            "• Forward multiple messages quickly\n"
            "• Files are queued for processing\n"
            "• Process queue with `/processbulk session_name`\n"
            "• Auto-processing every 50 files"
        )
    
    session_name = " ".join(message.command[1:])
    
    # Create bulk session
    session_data = {
        'session_name': session_name,
        'admin_id': message.from_user.id,
        'created_at': time.time(),
        'status': 'bulk_active',
        'indexed_count': 0,
        'queued_count': 0,
        'processed_count': 0,
        'method': 'bulk',
        'last_activity': time.time()
    }
    
    await private_index_collection.update_one(
        {'session_name': session_name, 'admin_id': message.from_user.id},
        {'$set': session_data},
        upsert=True
    )
    
    # Set global bulk session variables
    temp.BULK_PRIVATE_SESSION = session_name
    temp.BULK_PRIVATE_ADMIN = message.from_user.id
    
    await message.reply(
        f"📦 **Bulk Private Indexing Started**\n\n"
        f"📝 **Session:** `{session_name}`\n\n"
        f"📋 **Instructions:**\n"
        f"1. Forward multiple messages from private channels\n"
        f"2. Files will be queued automatically\n"
        f"3. Processing starts every 50 files or use `/processbulk {session_name}`\n"
        f"4. Use `/stopbulk` to stop collecting\n\n"
        f"⚡ **Ready for bulk forwards!**"
    )

@Client.on_message(filters.command('mediashare') & filters.user(ADMINS))
async def start_media_share_indexing(bot, message):
    """Start media share indexing session - for direct file uploads"""
    if len(message.command) < 2:
        return await message.reply(
            "💡 **Usage:** `/mediashare session_name`\n\n"
            "📱 **Media Share Mode:**\n"
            "• Upload files directly to the bot\n"
            "• Share media from private channels\n"
            "• Drag & drop supported\n"
            "• No forwarding required"
        )
    
    session_name = " ".join(message.command[1:])
    
    session_data = {
        'session_name': session_name,
        'admin_id': message.from_user.id,
        'created_at': time.time(),
        'status': 'media_active',
        'indexed_count': 0,
        'method': 'media_share',
        'last_activity': time.time()
    }
    
    await private_index_collection.update_one(
        {'session_name': session_name, 'admin_id': message.from_user.id},
        {'$set': session_data},
        upsert=True
    )
    
    temp.MEDIA_SHARE_SESSION = session_name
    temp.MEDIA_SHARE_ADMIN = message.from_user.id
    
    await message.reply(
        f"📱 **Media Share Indexing Started**\n\n"
        f"📝 **Session:** `{session_name}`\n\n"
        f"📋 **Instructions:**\n"
        f"1. Upload/send media files directly to this chat\n"
        f"2. Files will be indexed immediately\n"
        f"3. Supports: Videos, Audio, Documents, Photos\n"
        f"4. Use `/endmedia {session_name}` when finished\n\n"
        f"⚡ **Ready to receive media!**"
    )

@Client.on_message(filters.command('endprivate') & filters.user(ADMINS))
async def end_private_indexing(bot, message):
    """End private indexing session"""
    if len(message.command) < 2:
        return await message.reply("💡 **Usage:** `/endprivate session_name`")
    
    session_name = " ".join(message.command[1:])
    session = await private_index_collection.find_one({
        'session_name': session_name,
        'admin_id': message.from_user.id
    })
    
    if not session:
        return await message.reply(f"❌ Session `{session_name}` not found or not owned by you.")
    
    # Calculate session duration
    duration = time.time() - session['created_at']
    
    # Update session status
    await private_index_collection.update_one(
        {'session_name': session_name, 'admin_id': message.from_user.id},
        {'$set': {
            'status': 'completed',
            'ended_at': time.time(),
            'duration': duration
        }}
    )
    
    # Clean up temporary data
    if hasattr(temp, 'BULK_PRIVATE_SESSION') and temp.BULK_PRIVATE_SESSION == session_name:
        delattr(temp, 'BULK_PRIVATE_SESSION')
        if hasattr(temp, 'BULK_PRIVATE_ADMIN'):
            delattr(temp, 'BULK_PRIVATE_ADMIN')
    
    if hasattr(temp, 'MEDIA_SHARE_SESSION') and temp.MEDIA_SHARE_SESSION == session_name:
        delattr(temp, 'MEDIA_SHARE_SESSION')
        if hasattr(temp, 'MEDIA_SHARE_ADMIN'):
            delattr(temp, 'MEDIA_SHARE_ADMIN')
    
    await message.reply(
        f"✅ **Private Indexing Session Completed**\n\n"
        f"📝 **Session:** `{session_name}`\n"
        f"📊 **Files Indexed:** {session.get('indexed_count', 0)}\n"
        f"🔄 **Duplicates:** {session.get('duplicates', 0)}\n"
        f"❌ **Errors:** {session.get('errors', 0)}\n"
        f"⏱️ **Duration:** {get_readable_time(duration)}\n"
        f"📈 **Method:** {session.get('method', 'forward').title()}"
    )

@Client.on_message(filters.command('privatestatus') & filters.user(ADMINS))
async def private_indexing_status(bot, message):
    """Check private indexing session status"""
    if len(message.command) < 2:
        # Show all sessions for this admin
        sessions = []
        async for session in private_index_collection.find({'admin_id': message.from_user.id}).sort('created_at', -1):
            sessions.append(session)
        
        if not sessions:
            return await message.reply("📋 No private indexing sessions found.")
        
        text = "🔒 **Your Private Indexing Sessions:**\n\n"
        for session in sessions[:10]:  # Show last 10
            status_icons = {
                'active': '🔄',
                'bulk_active': '📦',
                'media_active': '📱',
                'completed': '✅',
                'stopped': '⏸️',
                'error': '❌'
            }
            
            status_icon = status_icons.get(session['status'], '❓')
            duration = time.time() - session['created_at']
            
            text += f"{status_icon} **{session['session_name']}**\n"
            text += f"   📊 Indexed: {session.get('indexed_count', 0)}\n"
            text += f"   📅 Created: {get_readable_time(duration)} ago\n"
            text += f"   🎯 Status: {session['status'].replace('_', ' ').title()}\n"
            if session.get('duplicates', 0) > 0:
                text += f"   🔄 Duplicates: {session.get('duplicates', 0)}\n"
            text += "\n"
        
        return await message.reply(text)
    
    session_name = " ".join(message.command[1:])
    session = await private_index_collection.find_one({
        'session_name': session_name,
        'admin_id': message.from_user.id
    })
    
    if not session:
        return await message.reply(f"❌ Session `{session_name}` not found.")
    
    status_icons = {
        'active': '🔄 Active',
        'bulk_active': '📦 Bulk Active',
        'media_active': '📱 Media Active',
        'completed': '✅ Completed',
        'stopped': '⏸️ Stopped',
        'error': '❌ Error'
    }
    
    duration = time.time() - session['created_at']
    last_activity = time.time() - session.get('last_activity', session['created_at'])
    
    status_text = f"{status_icons.get(session['status'], '❓ Unknown')}\n\n"
    status_text += f"📝 **Session:** `{session_name}`\n"
    status_text += f"📊 **Files Indexed:** {session.get('indexed_count', 0)}\n"
    status_text += f"🔄 **Duplicates:** {session.get('duplicates', 0)}\n"
    status_text += f"❌ **Errors:** {session.get('errors', 0)}\n"
    status_text += f"📅 **Created:** {get_readable_time(duration)} ago\n"
    status_text += f"⚡ **Last Activity:** {get_readable_time(last_activity)} ago\n"
    status_text += f"📈 **Method:** {session.get('method', 'forward').title()}\n"
    
    if session.get('queued_count'):
        status_text += f"📋 **Queued:** {session.get('queued_count', 0)}\n"
    
    if session.get('status') == 'completed' and session.get('duration'):
        status_text += f"⏱️ **Duration:** {get_readable_time(session['duration'])}"
    
    await message.reply(status_text)

@Client.on_message(filters.command('privatesessions') & filters.user(ADMINS))
async def list_private_sessions(bot, message):
    """List all private indexing sessions"""
    # Get sessions with pagination
    page = 1
    if len(message.command) > 1:
        try:
            page = int(message.command[1])
        except:
            page = 1
    
    per_page = 10
    skip = (page - 1) * per_page
    
    total_sessions = await private_index_collection.count_documents({'admin_id': message.from_user.id})
    
    if total_sessions == 0:
        return await message.reply("📋 No private indexing sessions found.")
    
    sessions = []
    async for session in private_index_collection.find({'admin_id': message.from_user.id}).sort('created_at', -1).skip(skip).limit(per_page):
        sessions.append(session)
    
    text = f"🔒 **Private Sessions** (Page {page}/{ceil(total_sessions/per_page)})\n\n"
    
    for i, session in enumerate(sessions, 1):
        status_icons = {
            'active': '🔄',
            'bulk_active': '📦',
            'media_active': '📱',
            'completed': '✅',
            'stopped': '⏸️'
        }
        
        status_icon = status_icons.get(session['status'], '❓')
        duration = time.time() - session['created_at']
        
        text += f"{status_icon} **{session['session_name']}**\n"
        text += f"   📊 Files: {session.get('indexed_count', 0)}"
        if session.get('duplicates', 0) > 0:
            text += f" | Dupes: {session.get('duplicates', 0)}"
        text += f"\n   📅 {get_readable_time(duration)} ago | {session.get('method', 'forward').title()}\n\n"
    
    # Add pagination buttons if needed
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(f"⬅️ Page {page-1}", callback_data=f"private_sessions_{page-1}"))
    if page < ceil(total_sessions/per_page):
        buttons.append(InlineKeyboardButton(f"Page {page+1} ➡️", callback_data=f"private_sessions_{page+1}"))
    
    if buttons:
        text += f"📄 **Navigation:** Use `/privatesessions {page-1 if page > 1 else page+1}` for other pages"
    
    await message.reply(text)

# ==================== FORWARDED MESSAGE HANDLERS ====================

@Client.on_message(filters.forwarded & filters.private)
async def handle_private_forwarded_files(bot, message):
    """Handle forwarded messages from private channels"""
    # Check for active forward session
    active_session = await private_index_collection.find_one({
        'admin_id': message.from_user.id,
        'status': 'active'
    })
    
    # Check for active bulk session
    bulk_session = None
    if hasattr(temp, 'BULK_PRIVATE_SESSION') and hasattr(temp, 'BULK_PRIVATE_ADMIN'):
        if temp.BULK_PRIVATE_ADMIN == message.from_user.id:
            bulk_session = await private_index_collection.find_one({
                'session_name': temp.BULK_PRIVATE_SESSION,
                'admin_id': message.from_user.id,
                'status': 'bulk_active'
            })
    
    if not active_session and not bulk_session:
        return  # No active sessions
    
    # Check if message has media
    if not message.media or message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT, enums.MessageMediaType.PHOTO]:
        return
    
    media = getattr(message, message.media.value, None)
    if not media:
        return
    
    # Apply file filters
    file_filters = getattr(temp, 'FILE_FILTERS', set())
    if file_filters and not should_index_file(media, file_filters):
        if active_session:  # Only notify in active session, not bulk
            await message.reply("⚠️ File filtered out based on current filters")
        return
    
    # Handle bulk session
    if bulk_session:
        await handle_bulk_forward(message, media, bulk_session)
        return
    
    # Handle regular forward session
    if active_session:
        await handle_forward_indexing(bot, message, media, active_session)

async def handle_forward_indexing(bot, message, media, session):
    """Handle individual forward indexing"""
    # Set media properties
    media.file_type = message.media.value
    media.caption = message.caption
    
    try:
        ok, code = await save_file(media)
        
        # Update session activity
        await private_index_collection.update_one(
            {'session_name': session['session_name'], 'admin_id': message.from_user.id},
            {'$set': {'last_activity': time.time()}}
        )
        
        if ok:
            # Update session count
            await private_index_collection.update_one(
                {'session_name': session['session_name'], 'admin_id': message.from_user.id},
                {'$inc': {'indexed_count': 1}}
            )
            
            file_name = getattr(media, 'file_name', 'Unknown')
            file_size = getattr(media, 'file_size', 0)
            size_text = f" ({get_readable_file_size(file_size)})" if file_size else ""
            
            await message.reply(f"✅ **Indexed:** `{file_name}`{size_text}")
            
            # Log to channel if configured
            if LOG_CHANNEL:
                try:
                    await bot.send_message(
                        LOG_CHANNEL,
                        f"🔒 **Private Index** ({session['session_name']}):\n"
                        f"📁 **File:** `{file_name}`\n"
                        f"👤 **By:** {message.from_user.mention}\n"
                        f"📊 **Session Total:** {session.get('indexed_count', 0) + 1}"
                    )
                except:
                    pass
                    
        elif code == 0:
            await private_index_collection.update_one(
                {'session_name': session['session_name'], 'admin_id': message.from_user.id},
                {'$inc': {'duplicates': 1}}
            )
            await message.reply("🔄 File already exists in database")
        else:
            await private_index_collection.update_one(
                {'session_name': session['session_name'], 'admin_id': message.from_user.id},
                {'$inc': {'errors': 1}}
            )
            await message.reply("❌ Error indexing file")
            
    except Exception as e:
        await private_index_collection.update_one(
            {'session_name': session['session_name'], 'admin_id': message.from_user.id},
            {'$inc': {'errors': 1}}
        )
        await message.reply(f"❌ Error: {e}")

async def handle_bulk_forward(message, media, session):
    """Handle bulk forward queueing"""
    try:
        # Queue the message for processing
        queue_data = {
            'session_name': session['session_name'],
            'admin_id': message.from_user.id,
            'message_data': {
                'media_type': message.media.value,
                'file_name': getattr(media, 'file_name', None),
                'file_id': getattr(media, 'file_id', None),
                'file_size': getattr(media, 'file_size', None),
                'mime_type': getattr(media, 'mime_type', None),
                'caption': message.caption,
                'file_unique_id': getattr(media, 'file_unique_id', None)
            },
            'queued_at': time.time(),
            'processed': False
        }
        
        await bulk_queue_collection.insert_one(queue_data)
        
        # Update session queue count
        await private_index_collection.update_one(
            {'session_name': session['session_name'], 'admin_id': message.from_user.id},
            {'$inc': {'queued_count': 1}, '$set': {'last_activity': time.time()}}
        )
        
        # Get updated queue count
        updated_session = await private_index_collection.find_one({
            'session_name': session['session_name'],
            'admin_id': message.from_user.id
        })
        
        queue_count = updated_session.get('queued_count', 0)
        
        # Auto-process every 50 files or if requested
        if queue_count % 50 == 0:
            await message.reply(f"📦 **Queued:** {queue_count} files\n⚡ **Auto-processing started...**")
            await process_bulk_queue_internal(session['session_name'], message.from_user.id, message)
        else:
            await message.reply(f"📦 **Queued:** {queue_count} files")
            
    except Exception as e:
        LOGGER.error(f"Error queueing bulk file: {e}")

# ==================== MEDIA SHARE HANDLER ====================

@Client.on_message((filters.video | filters.audio | filters.document | filters.photo) & filters.private)
async def handle_media_share(bot, message):
    """Handle direct media uploads for indexing"""
    # Check for active media share session
    if not hasattr(temp, 'MEDIA_SHARE_SESSION') or not hasattr(temp, 'MEDIA_SHARE_ADMIN'):
        return
    
    if temp.MEDIA_SHARE_ADMIN != message.from_user.id:
        return
    
    media_session = await private_index_collection.find_one({
        'session_name': temp.MEDIA_SHARE_SESSION,
        'admin_id': message.from_user.id,
        'status': 'media_active'
    })
    
    if not media_session:
        return
    
    media = getattr(message, message.media.value, None)
    if not media:
        return
    
    # Apply file filters
    file_filters = getattr(temp, 'FILE_FILTERS', set())
    if file_filters and not should_index_file(media, file_filters):
        return await message.reply("⚠️ File filtered out based on current filters")
    
    # Set media properties
    media.file_type = message.media.value
    media.caption = message.caption
    
    try:
        ok, code = await save_file(media)
        
        # Update session activity
        await private_index_collection.update_one(
            {'session_name': media_session['session_name'], 'admin_id': message.from_user.id},
            {'$set': {'last_activity': time.time()}}
        )
        
        if ok:
            await private_index_collection.update_one(
                {'session_name': media_session['session_name'], 'admin_id': message.from_user.id},
                {'$inc': {'indexed_count': 1}}
            )
            
            file_name = getattr(media, 'file_name', 'Media File')
            file_size = getattr(media, 'file_size', 0)
            size_text = f" ({get_readable_file_size(file_size)})" if file_size else ""
            
            await message.reply(f"✅ **Indexed:** `{file_name}`{size_text}")
            
        elif code == 0:
            await private_index_collection.update_one(
                {'session_name': media_session['session_name'], 'admin_id': message.from_user.id},
                {'$inc': {'duplicates': 1}}
            )
            await message.reply("🔄 File already exists in database")
        else:
            await private_index_collection.update_one(
                {'session_name': media_session['session_name'], 'admin_id': message.from_user.id},
                {'$inc': {'errors': 1}}
            )
            await message.reply("❌ Error indexing file")
            
    except Exception as e:
        await private_index_collection.update_one(
            {'session_name': media_session['session_name'], 'admin_id': message.from_user.id},
            {'$inc': {'errors': 1}}
        )
        await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command('endmedia') & filters.user(ADMINS))
async def end_media_share(bot, message):
    """End media share session"""
    if len(message.command) < 2:
        return await message.reply("💡 **Usage:** `/endmedia session_name`")
    
    session_name = " ".join(message.command[1:])
    
    # Check if it's the active media session
    if (hasattr(temp, 'MEDIA_SHARE_SESSION') and temp.MEDIA_SHARE_SESSION == session_name and 
        hasattr(temp, 'MEDIA_SHARE_ADMIN') and temp.MEDIA_SHARE_ADMIN == message.from_user.id):
        
        delattr(temp, 'MEDIA_SHARE_SESSION')
        delattr(temp, 'MEDIA_SHARE_ADMIN')
        
        # Update session status
        await private_index_collection.update_one(
            {'session_name': session_name, 'admin_id': message.from_user.id},
            {'$set': {'status': 'completed', 'ended_at': time.time()}}
        )
        
        await message.reply(f"✅ **Media share session ended:** `{session_name}`")
    else:
        await message.reply(f"❌ No active media session named `{session_name}`")

# ==================== BULK PROCESSING ====================

@Client.on_message(filters.command('processbulk') & filters.user(ADMINS))
async def process_bulk_queue_command(bot, message):
    """Process queued bulk messages"""
    if len(message.command) < 2:
        return await message.reply("💡 **Usage:** `/processbulk session_name`")
    
    session_name = " ".join(message.command[1:])
    await process_bulk_queue_internal(session_name, message.from_user.id, message)

async def process_bulk_queue_internal(session_name, admin_id, message):
    """Internal function to process bulk queue"""
    try:
        # Get queued files
        queued_files = []
        async for doc in bulk_queue_collection.find({
            'session_name': session_name,
            'admin_id': admin_id,
            'processed': False
        }).limit(100):  # Process max 100 at a time
            queued_files.append(doc)
        
        if not queued_files:
            return await message.reply("📭 No files in queue for this session")
        
        progress_msg = await message.reply(f"📊 **Processing {len(queued_files)} queued files...**")
        
        processed = 0
        errors = 0
        duplicates = 0
        start_time = time.time()
        
        for i, doc in enumerate(queued_files, 1):
            try:
                msg_data = doc['message_data']
                
                # Create media object from stored data
                class MediaObj:
                    def __init__(self, data):
                        self.file_name = data.get('file_name')
                        self.file_id = data.get('file_id')
                        self.file_size = data.get('file_size')
                        self.mime_type = data.get('mime_type')
                        self.file_type = data.get('media_type')
                        self.caption = data.get('caption')
                        self.file_unique_id = data.get('file_unique_id')
                
                media = MediaObj(msg_data)
                
                # Apply filters
                file_filters = getattr(temp, 'FILE_FILTERS', set())
                if file_filters and not should_index_file(media, file_filters):
                    continue
                
                ok, code = await save_file(media)
                if ok:
                    processed += 1
                elif code == 0:
                    duplicates += 1
                else:
                    errors += 1
                
                # Mark as processed
                await bulk_queue_collection.update_one(
                    {'_id': doc['_id']},
                    {'$set': {'processed': True, 'processed_at': time.time()}}
                )
                
                # Update progress every 10 files
                if i % 10 == 0:
                    elapsed = time.time() - start_time
                    progress = (i / len(queued_files)) * 100
                    eta = (elapsed / i) * (len(queued_files) - i) if i > 0 else 0
                    
                    await progress_msg.edit_text(
                        f"📊 **Processing Bulk Queue**\n\n"
                        f"📦 **Progress:** {i}/{len(queued_files)} ({progress:.1f}%)\n"
                        f"✅ **Processed:** {processed}\n"
                        f"🔄 **Duplicates:** {duplicates}\n"
                        f"❌ **Errors:** {errors}\n"
                        f"⏱️ **Elapsed:** {get_readable_time(elapsed)}\n"
                        f"⏰ **ETA:** {get_readable_time(eta)}"
                    )
                
            except Exception as e:
                errors += 1
                LOGGER.error(f"Error processing bulk file: {e}")
        
        # Update session counts
        await private_index_collection.update_one(
            {'session_name': session_name, 'admin_id': admin_id},
            {
                '$inc': {
                    'indexed_count': processed,
                    'duplicates': duplicates,
                    'errors': errors,
                    'processed_count': len(queued_files)
                },
                '$set': {'last_activity': time.time()}
            }
        )
        
        elapsed = time.time() - start_time
        await progress_msg.edit_text(
            f"✅ **Bulk Processing Complete!**\n\n"
            f"📦 **Total Processed:** {len(queued_files)}\n"
            f"✅ **Successfully Indexed:** {processed}\n"
            f"🔄 **Duplicates:** {duplicates}\n"
            f"❌ **Errors:** {errors}\n"
            f"⏱️ **Time Taken:** {get_readable_time(elapsed)}\n"
            f"⚡ **Speed:** {len(queued_files)/elapsed:.1f} files/sec" if elapsed > 0 else ""
        )
        
    except Exception as e:
        LOGGER.error(f"Error in bulk processing: {e}")
        await message.reply(f"❌ **Error in bulk processing:** {e}")

@Client.on_message(filters.command('stopbulk') & filters.user(ADMINS))
async def stop_bulk_private(bot, message):
    """Stop bulk private indexing"""
    if hasattr(temp, 'BULK_PRIVATE_SESSION'):
        session_name = temp.BULK_PRIVATE_SESSION
        
        # Get current queue count
        session = await private_index_collection.find_one({
            'session_name': session_name,
            'admin_id': message.from_user.id
        })
        
        delattr(temp, 'BULK_PRIVATE_SESSION')
        if hasattr(temp, 'BULK_PRIVATE_ADMIN'):
            delattr(temp, 'BULK_PRIVATE_ADMIN')
        
        await private_index_collection.update_one(
            {'session_name': session_name, 'admin_id': message.from_user.id},
            {'$set': {'status': 'stopped', 'stopped_at': time.time()}}
        )
        
        queue_count = session.get('queued_count', 0) if session else 0
        await message.reply(
            f"🛑 **Bulk private indexing stopped**\n\n"
            f"📝 **Session:** `{session_name}`\n"
            f"📦 **Files in Queue:** {queue_count}\n"
            f"💡 **Use `/processbulk {session_name}` to process remaining files**"
        )
    else:
        await message.reply("❌ No active bulk session found")

@Client.on_message(filters.command('clearqueue') & filters.user(ADMINS))
async def clear_bulk_queue(bot, message):
    """Clear bulk processing queue"""
    if len(message.command) < 2:
        return await message.reply("💡 **Usage:** `/clearqueue session_name`")
    
    session_name = " ".join(message.command[1:])
    
    # Count queued files
    queue_count = await bulk_queue_collection.count_documents({
        'session_name': session_name,
        'admin_id': message.from_user.id,
        'processed': False
    })
    
    if queue_count == 0:
        return await message.reply("📭 No files in queue for this session")
    
    # Ask for confirmation
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Clear", callback_data=f"clear_queue_yes_{session_name}"),
            InlineKeyboardButton("❌ Cancel", callback_data="clear_queue_no")
        ]
    ]
    
    await message.reply(
        f"⚠️ **Confirm Queue Clearing**\n\n"
        f"📝 **Session:** `{session_name}`\n"
        f"📦 **Files to Clear:** {queue_count}\n\n"
        f"❌ **This action cannot be undone!**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ==================== JSON IMPORT ====================

@Client.on_message(filters.command('importjson') & filters.user(ADMINS))
async def import_json_data(bot, message):
    """Import files from JSON export data"""
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply(
            "💡 **Usage:** Reply to a JSON file with `/importjson session_name`\n\n"
            "📄 **Supported formats:**\n"
            "• Telegram export JSON\n"
            "• Custom media list JSON\n"
            "• Channel backup JSON\n\n"
            "📋 **JSON should contain media file information**"
        )
    
    if len(message.command) < 2:
        return await message.reply("💡 **Usage:** `/importjson session_name`")
    
    session_name = " ".join(message.command[1:])
    json_file = message.reply_to_message.document
    
    if not json_file.file_name.lower().endswith('.json'):
        return await message.reply("❌ Please provide a JSON file")
    
    file_size = json_file.file_size
    if file_size > 50 * 1024 * 1024:  # 50MB limit
        return await message.reply("❌ JSON file too large (max 50MB)")
    
    progress_msg = await message.reply("📥 **Downloading JSON file...**")
    
    try:
        # Download and read JSON file
        file_path = await message.reply_to_message.download()
        
        await progress_msg.edit_text("📄 **Reading JSON data...**")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        os.remove(file_path)  # Clean up
        
        # Process different JSON formats
        media_files = []
        
        # Telegram export format
        if 'messages' in data:
            for msg in data['messages']:
                if isinstance(msg, dict):
                    # Check for file/photo/video/audio
                    media_info = None
                    if 'file' in msg:
                        media_info = msg['file']
                    elif 'photo' in msg:
                        media_info = {'name': 'photo.jpg', 'mime_type': 'image/jpeg'}
                    elif 'video_file' in msg:
                        media_info = msg['video_file']
                    elif 'audio_file' in msg:
                        media_info = msg['audio_file']
                    
                    if media_info:
                        media_files.append({
                            'file_name': media_info.get('name', 'unknown'),
                            'file_size': media_info.get('file_size', 0),
                            'mime_type': media_info.get('mime_type', ''),
                            'caption': msg.get('text', ''),
                            'date': msg.get('date', '')
                        })
        
        # Custom format
        elif 'files' in data:
            for file_info in data['files']:
                if isinstance(file_info, dict):
                    media_files.append({
                        'file_name': file_info.get('name', file_info.get('filename', 'unknown')),
                        'file_size': file_info.get('size', file_info.get('file_size', 0)),
                        'mime_type': file_info.get('mime_type', file_info.get('type', '')),
                        'caption': file_info.get('caption', file_info.get('description', '')),
                        'date': file_info.get('date', file_info.get('timestamp', ''))
                    })
        
        # Direct array format
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and ('name' in item or 'filename' in item or 'file_name' in item):
                    media_files.append({
                        'file_name': item.get('name', item.get('filename', item.get('file_name', 'unknown'))),
                        'file_size': item.get('size', item.get('file_size', 0)),
                        'mime_type': item.get('mime_type', item.get('type', '')),
                        'caption': item.get('caption', item.get('description', '')),
                        'date': item.get('date', item.get('timestamp', ''))
                    })
        
        if not media_files:
            return await progress_msg.edit_text("❌ No media files found in JSON")
        
        # Apply filters
        file_filters = getattr(temp, 'FILE_FILTERS', set())
        if file_filters:
            filtered_files = []
            for file_info in media_files:
                extension = get_file_extension(file_info['file_name'])
                if extension in file_filters:
                    filtered_files.append(file_info)
            media_files = filtered_files
        
        if not media_files:
            return await progress_msg.edit_text("❌ No files match current filters")
        
        # Create session
        session_data = {
            'session_name': session_name,
            'admin_id': message.from_user.id,
            'created_at': time.time(),
            'status': 'json_processing',
            'indexed_count': 0,
            'duplicates': 0,
            'errors': 0,
            'method': 'json',
            'total_files': len(media_files)
        }
        
        await private_index_collection.update_one(
            {'session_name': session_name, 'admin_id': message.from_user.id},
            {'$set': session_data},
            upsert=True
        )
        
        await progress_msg.edit_text(f"📊 **Processing {len(media_files)} files from JSON...**")
        
        processed = 0
        errors = 0
        duplicates = 0
        start_time = time.time()
        
        for i, file_info in enumerate(media_files, 1):
            try:
                # Create mock media object for JSON data
                class JSONMedia:
                    def __init__(self, file_data):
                        self.file_name = file_data.get('file_name', 'unknown')
                        self.file_size = file_data.get('file_size', 0)
                        self.mime_type = file_data.get('mime_type', '')
                        self.file_type = 'document'  # Default type
                        self.caption = file_data.get('caption', '')
                        # Generate a unique file_id for JSON imports
                        self.file_id = f"json_import_{hash(str(file_data))}"
                        self.file_unique_id = self.file_id
                
                media = JSONMedia(file_info)
                
                # For JSON import, save as metadata only
                ok, code = await save_file(media)
                if ok:
                    processed += 1
                elif code == 0:
                    duplicates += 1
                else:
                    errors += 1
                
                # Update progress every 50 files
                if i % 50 == 0:
                    elapsed = time.time() - start_time
                    progress = (i / len(media_files)) * 100
                    eta = (elapsed / i) * (len(media_files) - i) if i > 0 else 0
                    
                    await progress_msg.edit_text(
                        f"📊 **JSON Import Progress**\n\n"
                        f"📦 **Progress:** {i}/{len(media_files)} ({progress:.1f}%)\n"
                        f"✅ **Processed:** {processed}\n"
                        f"🔄 **Duplicates:** {duplicates}\n"
                        f"❌ **Errors:** {errors}\n"
                        f"⏱️ **Elapsed:** {get_readable_time(elapsed)}\n"
                        f"⏰ **ETA:** {get_readable_time(eta)}"
                    )
                
            except Exception as e:
                errors += 1
                LOGGER.error(f"Error processing JSON file: {e}")
        
        # Update final session status
        elapsed = time.time() - start_time
        await private_index_collection.update_one(
            {'session_name': session_name, 'admin_id': message.from_user.id},
            {'$set': {
                'status': 'completed',
                'indexed_count': processed,
                'duplicates': duplicates,
                'errors': errors,
                'ended_at': time.time(),
                'duration': elapsed
            }}
        )
        
        await progress_msg.edit_text(
            f"✅ **JSON Import Complete!**\n\n"
            f"📝 **Session:** `{session_name}`\n"
            f"📦 **Total Files:** {len(media_files)}\n"
            f"✅ **Successfully Imported:** {processed}\n"
            f"🔄 **Duplicates:** {duplicates}\n"
            f"❌ **Errors:** {errors}\n"
            f"⏱️ **Time Taken:** {get_readable_time(elapsed)}\n"
            f"ℹ️ **Note:** JSON import saves metadata only"
        )
        
    except json.JSONDecodeError:
        await progress_msg.edit_text("❌ Invalid JSON format")
    except Exception as e:
        await progress_msg.edit_text(f"❌ Error processing JSON: {e}")
        LOGGER.error(f"JSON import error: {e}")

# ==================== CALLBACK HANDLERS ====================

@Client.on_callback_query(filters.regex(r'^clear_queue_'))
async def handle_clear_queue_callback(bot, query):
    """Handle queue clearing confirmation"""
    if query.data == "clear_queue_no":
        await query.message.edit_text("❌ Queue clearing cancelled")
        return
    
    if query.data.startswith('clear_queue_yes_'):
        session_name = query.data.replace('clear_queue_yes_', '')
        
        # Clear the queue
        result = await bulk_queue_collection.delete_many({
            'session_name': session_name,
            'admin_id': query.from_user.id,
            'processed': False
        })
        
        # Reset queue count in session
        await private_index_collection.update_one(
            {'session_name': session_name, 'admin_id': query.from_user.id},
            {'$set': {'queued_count': 0}}
        )
        
        await query.message.edit_text(
            f"✅ **Queue Cleared Successfully**\n\n"
            f"📝 **Session:** `{session_name}`\n"
            f"🗑️ **Files Removed:** {result.deleted_count}"
        )

# ==================== UTILITY FUNCTIONS ====================

def get_readable_file_size(size_bytes):
    """Convert bytes to readable format"""
    if not size_bytes:
        return "Unknown"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

# ==================== ORIGINAL INDEX CODE (ENHANCED) ====================

@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")
    _, raju, chat, lst_msg_id, from_user = query.data.split("#")
    if raju == 'reject':
        await query.message.delete()
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been declined by our moderators.',
                               reply_to_message_id=int(lst_msg_id))
        return

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
    msg = query.message

    await query.answer('Processing...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been accepted by our moderators and will be added soon.',
                               reply_to_message_id=int(lst_msg_id))
    await msg.edit(
        "Starting Indexing",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat)
    except:
        chat = chat
    await index_files_to_db(int(lst_msg_id), chat, msg, bot)

@Client.on_message((filters.forwarded | (filters.regex(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text ) & filters.private & filters.incoming)
async def send_for_index(bot, message):
    if message.text:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match:
            return await message.reply('Invalid link')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    elif message.forward_from_chat and message.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = message.forward_from_message_id
        chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else:
        return
    try:
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await message.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        LOGGER.error(e)
        return await message.reply(f'Errors - {e}')
    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That Iam An Admin In The Channel, if channel is private')
    if k.empty:
        return await message.reply('This may be group and i am not a admin of the group.')

    if message.from_user.id in ADMINS:
        buttons = [
            [InlineKeyboardButton('Yes', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')],
            [InlineKeyboardButton('Close', callback_data='close_data')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do you Want To Index This Channel/ Group ?\n\nChat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>\n\nɴᴇᴇᴅ sᴇᴛsᴋɪᴘ 👉🏻 /setskip\nFile filters 👉🏻 /setfilters\nAuto-index 👉🏻 /autoindex\n\n🔒 **Private Indexing Available:**\n• `/privateindex` - Forward based\n• `/bulkprivate` - Bulk processing\n• `/importjson` - JSON import',
            reply_markup=reply_markup)

    if type(chat_id) is int:
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('Make sure I am an admin in the chat and have permission to invite users.')
    else:
        link = f"@{message.forward_from_chat.username}"
    buttons = [
        [InlineKeyboardButton('Accept Index', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')],
        [InlineKeyboardButton('Reject Index', callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(LOG_CHANNEL,
                           f'#IndexRequest\n\nBy : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat ID/ Username - <code> {chat_id}</code>\nLast Message ID - <code>{last_msg_id}</code>\nInviteLink - {link}',
                           reply_markup=reply_markup)
    await message.reply('ThankYou For the Contribution, Wait For My Moderators to verify the files.')

@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
        except:
            return await message.reply("Skip number should be an integer.")
        await message.reply(f"Successfully set SKIP number as {skip}")
        temp.CURRENT = int(skip)
    else:
        await message.reply("Give me a skip number")

@Client.on_message(filters.command('setfilters') & filters.user(ADMINS))
async def set_file_filters(bot, message):
    """Set file extension filters for indexing"""
    if ' ' in message.text:
        _, filter_text = message.text.split(" ", 1)
        extensions = [ext.strip().lower() for ext in filter_text.split(',')]
        # Add dots if missing
        extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
        
        temp.FILE_FILTERS = set(extensions)
        await message.reply(f"✅ File filters set: {', '.join(extensions)}\n\nOnly files with these extensions will be indexed.")
    else:
        current_filters = getattr(temp, 'FILE_FILTERS', set())
        if current_filters:
            await message.reply(f"📁 Current filters: {', '.join(current_filters)}\n\n💡 Usage: `/setfilters .mp4,.mkv,.srt`\n\n🔄 To clear filters: `/clearfilters`")
        else:
            await message.reply("📁 No filters set. All supported files will be indexed.\n\n💡 Usage: `/setfilters .mp4,.mkv,.srt`\n\n📋 Supported formats:\n🎬 Video: .mp4, .mkv, .avi, .mov, .wmv, .flv, .webm, .m4v\n🎵 Audio: .mp3, .flac, .wav, .aac, .ogg, .m4a, .wma\n📝 Subtitles: .srt, .vtt, .ass, .ssa, .sub, .idx\n📄 Documents: .pdf, .txt, .doc, .docx, .zip, .rar, .7z")

@Client.on_message(filters.command('clearfilters') & filters.user(ADMINS))
async def clear_file_filters(bot, message):
    """Clear all file filters"""
    temp.FILE_FILTERS = set()
    await message.reply("✅ File filters cleared. All supported files will be indexed.")

@Client.on_message(filters.command('autoindex') & filters.user(ADMINS))
async def manage_auto_index(bot, message):
    """Enable/disable auto-indexing for channels with private mode support"""
    if len(message.command) < 2:
        config = await load_auto_index_config()
        if not config:
            return await message.reply(
                "📋 No auto-indexing channels configured.\n\n"
                "💡 Usage:\n"
                "• Enable: `/autoindex enable @channel`\n"
                "• Enable Private: `/autoindex enable @channel private`\n"
                "• Disable: `/autoindex disable @channel`\n"
                "• Set Filters: `/autoindex setfilters @channel .mp4,.mkv`\n"
                "• Clear Filters: `/autoindex clearfilters @channel`\n"
                "• List: `/autoindex list`"
            )
        
        text = "🤖 Auto-indexing Status:\n\n"
        for chat_id, settings in config.items():
            status = "✅ Enabled" if settings.get('enabled', False) else "❌ Disabled"
            mode = "🔒 Private" if settings.get('private_mode', False) else "🔓 Public"
            filters_info = f" | Filters: {', '.join(settings.get('filters', []))}" if settings.get('filters') else ""
            last_msg = settings.get('last_indexed_msg', 0)
            text += f"• <code>{chat_id}</code>\n  {status} | {mode}{filters_info}\n  Last: <code>{last_msg}</code>\n\n"
        
        await message.reply(text)
        return
    
    command = message.command[1].lower()
    
    if command == "list":
        config = await load_auto_index_config()
        if not config:
            return await message.reply("📋 No auto-indexing channels configured.")
        
        text = "🤖 Auto-indexing Channels:\n\n"
        for chat_id, settings in config.items():
            status = "✅ Enabled" if settings.get('enabled', False) else "❌ Disabled"
            mode = "🔒 Private" if settings.get('private_mode', False) else "🔓 Public"
            filters_info = f" | Filters: {', '.join(settings.get('filters', []))}" if settings.get('filters') else ""
            last_msg = settings.get('last_indexed_msg', 0)
            text += f"• <code>{chat_id}</code>\n  {status} | {mode}{filters_info}\n  Last: <code>{last_msg}</code>\n\n"
        
        await message.reply(text)
        return
    
    if len(message.command) < 3:
        return await message.reply(
            "💡 Usage:\n"
            "• Enable: `/autoindex enable @channel`\n"
            "• Enable Private: `/autoindex enable @channel private`\n"
            "• Disable: `/autoindex disable @channel`\n"
            "• Set Filters: `/autoindex setfilters @channel .mp4,.mkv`\n"
            "• Clear Filters: `/autoindex clearfilters @channel`\n"
            "• List: `/autoindex list`"
        )
    
    chat_identifier = message.command[2]
    
    try:
        chat = await bot.get_chat(chat_identifier)
        chat_id = str(chat.id)
    except Exception as e:
        return await message.reply(f"❌ Error getting chat info: {e}")
    
    config = await load_auto_index_config()
    
    if command == "enable":
        private_mode = len(message.command) > 3 and message.command[3].lower() == "private"
        
        settings = {
            'chat_id': int(chat_id),
            'enabled': True,
            'chat_title': chat.title or chat.username,
            'private_mode': private_mode,
            'filters': config.get(chat_id, {}).get('filters', []),
            'last_indexed_msg': config.get(chat_id, {}).get('last_indexed_msg', 0)
        }
        
        await save_auto_index_config(chat_id, settings)
        mode_text = "🔒 Private Mode" if private_mode else "🔓 Public Mode"
        await message.reply(
            f"✅ Auto-indexing enabled for {chat.title or chat.username} (<code>{chat_id}</code>)\n"
            f"Mode: {mode_text}\n\n"
            f"{'⚠️ Note: Private mode will index new messages only, not historical messages.' if private_mode else ''}"
        )
        
    elif command == "disable":
        if chat_id in config:
            await delete_auto_index_config(chat_id)
            await message.reply(f"❌ Auto-indexing disabled and removed for {chat.title or chat.username} (<code>{chat_id}</code>)")
        else:
            await message.reply("❌ This channel is not in auto-index list.")
    
    elif command == "setfilters":
        if len(message.command) < 4:
            return await message.reply("💡 Usage: `/autoindex setfilters @channel .mp4,.mkv,.srt`")
        
        filter_text = message.command[3]
        extensions = [ext.strip().lower() for ext in filter_text.split(',')]
        extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
        
        if chat_id not in config:
            return await message.reply("❌ This channel is not in auto-index list. Enable it first.")
        
        settings = config[chat_id]
        settings['filters'] = extensions
        settings['chat_id'] = int(chat_id)
        await save_auto_index_config(chat_id, settings)
        
        await message.reply(f"✅ Filters set for {chat.title or chat.username}: {', '.join(extensions)}")
    
    elif command == "clearfilters":
        if chat_id not in config:
            return await message.reply("❌ This channel is not in auto-index list.")
        
        settings = config[chat_id]
        settings['filters'] = []
        settings['chat_id'] = int(chat_id)
        await save_auto_index_config(chat_id, settings)
        
        await message.reply(f"✅ Filters cleared for {chat.title or chat.username}")
    
    else:
        await message.reply(
            "💡 Usage:\n"
            "• Enable: `/autoindex enable @channel`\n"
            "• Enable Private: `/autoindex enable @channel private`\n"
            "• Disable: `/autoindex disable @channel`\n"
            "• Set Filters: `/autoindex setfilters @channel .mp4,.mkv`\n"
            "• Clear Filters: `/autoindex clearfilters @channel`\n"
            "• List: `/autoindex list`"
        )
