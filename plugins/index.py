import time
import re
import asyncio
import threading
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied
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

# Progress writer for downloads/uploads
def progress(current, total, message, type):
    with open(f'{message.id}{type}status.txt',"w") as fileup:
        fileup.write(f"{current * 100 / total:.1f}%")

# Download status
def downstatus(statusfile, message, bot):
    while True:
        if os.path.exists(statusfile):
            break
    time.sleep(3)      
    while os.path.exists(statusfile):
        with open(statusfile,"r") as downread:
            txt = downread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"__Downloaded__ : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)

# Upload status
def upstatus(statusfile, message, bot):
    while True:
        if os.path.exists(statusfile):
            break
    time.sleep(3)      
    while os.path.exists(statusfile):
        with open(statusfile,"r") as upread:
            txt = upread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"𝐔𝐩𝐥𝐨𝐚𝐝𝐞𝐝 : **{txt}**")
            time.sleep(10)
        except:
            time.sleep(5)

# Get message type
def get_message_type(msg):
    try:
        msg.document.file_id
        return "Document"
    except: pass
    try:
        msg.video.file_id
        return "Video"
    except: pass
    try:
        msg.animation.file_id
        return "Animation"
    except: pass
    try:
        msg.sticker.file_id
        return "Sticker"
    except: pass
    try:
        msg.voice.file_id
        return "Voice"
    except: pass
    try:
        msg.audio.file_id
        return "Audio"
    except: pass
    try:
        msg.photo.file_id
        return "Photo"
    except: pass
    try:
        msg.text
        return "Text"
    except: pass

# Handle private/restricted content
async def handle_private_content(bot, message, chatid, msgid, user_client):
    """Handle downloading and forwarding restricted content"""
    try:
        msg = await user_client.get_messages(chatid, msgid)
        msg_type = get_message_type(msg)

        if "Text" == msg_type:
            await bot.send_message(message.chat.id, msg.text, entities=msg.entities, reply_to_message_id=message.id)
            return

        smsg = await bot.send_message(message.chat.id, '𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠...', reply_to_message_id=message.id)
        
        # Start download status thread
        dosta = threading.Thread(target=lambda: downstatus(f'{message.id}downstatus.txt', smsg, bot), daemon=True)
        dosta.start()
        
        file = await user_client.download_media(msg, progress=progress, progress_args=[message, "down"])
        
        if os.path.exists(f'{message.id}downstatus.txt'):
            os.remove(f'{message.id}downstatus.txt')

        # Start upload status thread
        upsta = threading.Thread(target=lambda: upstatus(f'{message.id}upstatus.txt', smsg, bot), daemon=True)
        upsta.start()
        
        thumb = None
        
        if "Document" == msg_type:
            try:
                thumb = await user_client.download_media(msg.document.thumbs[0].file_id)
            except: pass
            await bot.send_document(message.chat.id, file, thumb=thumb, caption=msg.caption, 
                                  caption_entities=msg.caption_entities, reply_to_message_id=message.id, 
                                  progress=progress, progress_args=[message, "up"])
        
        elif "Video" == msg_type:
            try: 
                thumb = await user_client.download_media(msg.video.thumbs[0].file_id)
            except: pass
            await bot.send_video(message.chat.id, file, duration=msg.video.duration, width=msg.video.width, 
                               height=msg.video.height, thumb=thumb, caption=msg.caption, 
                               caption_entities=msg.caption_entities, reply_to_message_id=message.id, 
                               progress=progress, progress_args=[message, "up"])
        
        elif "Animation" == msg_type:
            await bot.send_animation(message.chat.id, file, reply_to_message_id=message.id)
        
        elif "Sticker" == msg_type:
            await bot.send_sticker(message.chat.id, file, reply_to_message_id=message.id)
        
        elif "Voice" == msg_type:
            await bot.send_voice(message.chat.id, file, caption=msg.caption, 
                               caption_entities=msg.caption_entities, reply_to_message_id=message.id, 
                               progress=progress, progress_args=[message, "up"])
        
        elif "Audio" == msg_type:
            try:
                thumb = await user_client.download_media(msg.audio.thumbs[0].file_id)
            except: pass
            await bot.send_audio(message.chat.id, file, caption=msg.caption, 
                               caption_entities=msg.caption_entities, reply_to_message_id=message.id, 
                               progress=progress, progress_args=[message, "up"])
        
        elif "Photo" == msg_type:
            await bot.send_photo(message.chat.id, file, caption=msg.caption, 
                               caption_entities=msg.caption_entities, reply_to_message_id=message.id)
        
        # Cleanup
        if thumb and os.path.exists(thumb):
            os.remove(thumb)
        if os.path.exists(file):
            os.remove(file)
        if os.path.exists(f'{message.id}upstatus.txt'):
            os.remove(f'{message.id}upstatus.txt')
        
        await bot.delete_messages(message.chat.id, [smsg.id])
        
    except Exception as e:
        LOGGER.error(f"Error handling private content: {e}")
        await bot.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id)

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
    # Check if it's a join link
    if "https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text:
        # Handle join chat functionality
        user_client = getattr(temp, 'USER_CLIENT', None)
        if user_client is None:
            return await message.reply('String Session is not set. Cannot join private chats.')
        
        try:
            await user_client.join_chat(message.text)
            await message.reply("Chat Joined ✅")
        except UserAlreadyParticipant:
            await message.reply("Chat already Joined 😏")
        except InviteHashExpired:
            await message.reply("Invalid Link 😒")
        except Exception as e:
            await message.reply(f"Error: {e}")
        return
    
    # Handle indexing requests
    if message.text:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text.split()[0])  # Get first URL
        if not match:
            return await message.reply('Invalid link')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id = int(("-100" + chat_id))
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
        return await message.reply('Make Sure That I am An Admin In The Channel, if channel is private')
    
    if k.empty:
        return await message.reply('This may be group and i am not a admin of the group.')

    if message.from_user.id in ADMINS:
        buttons = [
            [InlineKeyboardButton('Yes', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')],
            [InlineKeyboardButton('Close', callback_data='close_data')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do you Want To Index This Channel/ Group ?\n\nChat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>\n\nɴᴇᴇᴅ sᴇᴛsᴋɪᴘ 👉🏻 /setskip\nFile filters 👉🏻 /setfilters\nAuto-index 👉🏻 /autoindex',
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

# Auto-indexing handler for new messages in monitored channels
@Client.on_message(filters.channel & ~filters.service)
async def auto_index_new_files(bot, message):
    """Automatically index new files from monitored channels"""
    try:
        config = await load_auto_index_config()
        chat_id = str(message.chat.id)
        
        if chat_id not in config or not config[chat_id].get('enabled', False):
            return
        
        if not message.media:
            return
        
        if message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
            return
        
        media = getattr(message, message.media.value, None)
        if not media:
            return
        
        channel_filters = set(config[chat_id].get('filters', []))
        global_filters = getattr(temp, 'FILE_FILTERS', set())
        file_filters = channel_filters or global_filters
        
        if file_filters and not should_index_file(media, file_filters):
            return
        
        media.file_type = message.media.value
        media.caption = message.caption
        
        try:
            ok, code = await save_file(media)
            if ok:
                LOGGER.info(f"Auto-indexed file: {getattr(media, 'file_name', 'Unknown')} from {message.chat.title}")
                
                settings = config[chat_id]
                settings['last_indexed_msg'] = message.id
                settings['chat_id'] = int(chat_id)
                await save_auto_index_config(chat_id, settings)
                
                if LOG_CHANNEL:
                    try:
                        mode_icon = "🔒" if config[chat_id].get('private_mode', False) else "🔓"
                        await bot.send_message(
                            LOG_CHANNEL,
                            f"🤖 Auto-indexed file:\n"
                            f"📁 File: <code>{getattr(media, 'file_name', 'Unknown')}</code>\n"
                            f"📺 Channel: {message.chat.title} (<code>{chat_id}</code>)\n"
                            f"🆔 Message ID: <code>{message.id}</code>\n"
                            f"Mode: {mode_icon}"
                        )
                    except:
                        pass
            elif code == 0:
                LOGGER.info(f"Duplicate file skipped: {getattr(media, 'file_name', 'Unknown')}")
        except Exception as e:
            LOGGER.error(f"Error auto-indexing file: {e}")
    
    except Exception as e:
        LOGGER.error(f"Error in auto_index_new_files: {e}")

def get_progress_bar(percent, length=10):
    filled = int(length * percent / 100)
    unfilled = length - filled
    return '█' * filled + '▒' * unfilled

async def index_files_to_db(lst_msg_id, chat, msg, bot):
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    filtered_out = 0
    BATCH_SIZE = 200
    start_time = time.time()

    file_filters = getattr(temp, 'FILE_FILTERS', set())

    async with lock:
        try:
            current = temp.CURRENT
            temp.CANCEL = False
            total_messages = lst_msg_id
            total_fetch = lst_msg_id - current
            if total_messages <= 0:
                await msg.edit(
                    "🚫 No Messages To Index.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Close', callback_data='close_data')]])
                )
                return
            batches = ceil(total_messages / BATCH_SIZE)
            batch_times = []
            
            filter_text = f"\n🔍 Active Filters: {', '.join(file_filters)}" if file_filters else "\n🔍 No Filters (All files)"
            
            await msg.edit(
                f"📊 Indexing Starting......\n"
                f"💬 Total Messages: <code>{total_messages}</code>\n"
                f"💾 Total Fetch: <code> {total_fetch}</code>\n"
                f"{filter_text}\n"
                f"⏰ Elapsed: <code>{get_readable_time(time.time() - start_time)}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Cancel', callback_data='index_cancel')]])
            )
            for batch in range(batches):
                if temp.CANCEL:
                    break
                batch_start = time.time()
                start_id = current + 1
                end_id = min(current + BATCH_SIZE, lst_msg_id)
                message_ids = range(start_id, end_id + 1)
                try:
                    messages = await bot.get_messages(chat, list(message_ids))
                    if not isinstance(messages, list):
                        messages = [messages]
                except Exception as e:
                    errors += len(message_ids)
                    current += len(message_ids)
                    continue
                save_tasks = []
                for message in messages:
                    current += 1
                    try:
                        if message.empty:
                            deleted += 1
                            continue
                        elif not message.media:
                            no_media += 1
                            continue
                        elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                            unsupported += 1
                            continue
                        media = getattr(message, message.media.value, None)
                        if not media:
                            unsupported += 1
                            continue
                        
                        # Apply file filters
                        if file_filters and not should_index_file(media, file_filters):
                            filtered_out += 1
                            continue
                        
                        media.file_type = message.media.value
                        media.caption = message.caption
                        save_tasks.append(save_file(media))

                    except Exception:
                        errors += 1
                        continue
                results = await asyncio.gather(*save_tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        errors += 1
                    else:
                        ok, code = result
                        if ok:
                            total_files += 1
                        elif code == 0:
                            duplicate += 1
                        elif code == 2:
                            errors += 1
                batch_time = time.time() - batch_start
                batch_times.append(batch_time)
                elapsed = time.time() - start_time
                progress = current - temp.CURRENT
                percentage = (progress / total_fetch) * 100
                avg_batch_time = sum(batch_times) / len(batch_times) if batch_times else 1
                eta = (total_fetch - progress) / BATCH_SIZE * avg_batch_time
                progress_bar = get_progress_bar(int(percentage))
                
                filter_info = f"🔍 Filtered: <code>{filtered_out}</code>\n" if file_filters else ""
                
                await msg.edit(
                    f"📊 Indexing Progress\n"
                    f"📦 Batch No: {batch + 1}/{batches}\n"
                    f"{progress_bar} <code>{percentage:.1f}%</code>\n"
                    f"💬 Total Messages: <code>{total_messages}</code>\n"
                    f"📥 Total Fetch: <code>{total_fetch}</code>\n"
                    f"⬇️ Fetched: <code>{current}</code>\n"
                    f"💾 Saved: <code>{total_files}</code>\n"
                    f"🔄 Duplicates: <code>{duplicate}</code>\n"
                    f"🗑️ Deleted: <code>{deleted}</code>\n"
                    f"📴 Non-Media: <code>{no_media + unsupported}</code> (🚫 Unsupported: <code>{unsupported}</code>)\n"
                    f"{filter_info}"
                    f"⚠️ Errors: <code>{errors}</code>\n"
                    f"⏱️ Elapsed: <code>{get_readable_time(elapsed)}</code>\n"
                    f"⏰ ETA: <code>{get_readable_time(eta)}</code>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Cancel', callback_data='index_cancel')]])
                )
            elapsed = time.time() - start_time
            
            filter_summary = f"🔍 Filtered: <code>{filtered_out}</code>\n" if file_filters else ""
            
            await msg.edit(
                f"✅ Indexing Completed!\n"
                f"💬 Total Message: <code>{total_messages}</code>\n" 
                f"📥 Total Fetch: <code>{total_fetch}</code>\n"
                f"⬇️ Fetched: <code>{current}</code>\n"
                f"💾 Saved: <code>{total_files}</code>\n"
                f"🔄 Duplicates: <code>{duplicate}</code>\n"
                f"🗑️ Deleted: <code>{deleted}</code>\n"
                f"📴 Non-Media: <code>{no_media + unsupported}</code> (Unsupported: <code>{unsupported}</code>)\n"
                f"{filter_summary}"
                f"⚠️ Errors: <code>{errors}</code>\n"
                f"⏰ Elapsed: <code>{get_readable_time(elapsed)}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Close', callback_data='close_data')]])
            )
        except Exception as e:
            await msg.edit(
                f"❌ Error: <code>{e}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Close', callback_data='close_data')]])
            )
