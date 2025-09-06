import time
import re
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from info import ADMINS, INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp, get_readable_time
from math import ceil
from logging_helper import LOGGER
import json
import os

lock = asyncio.Lock()

# File extension filters
SUPPORTED_VIDEO_FORMATS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
SUPPORTED_AUDIO_FORMATS = {'.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma'}
SUPPORTED_SUBTITLE_FORMATS = {'.srt', '.vtt', '.ass', '.ssa', '.sub', '.idx'}
SUPPORTED_DOCUMENT_FORMATS = {'.pdf', '.txt', '.doc', '.docx', '.zip', '.rar', '.7z'}

# Auto-indexing configuration file
AUTO_INDEX_CONFIG_FILE = "auto_index_config.json"

# Load auto-indexing configuration
def load_auto_index_config():
    if os.path.exists(AUTO_INDEX_CONFIG_FILE):
        with open(AUTO_INDEX_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save auto-indexing configuration
def save_auto_index_config(config):
    with open(AUTO_INDEX_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

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
    """Enable/disable auto-indexing for channels"""
    if len(message.command) < 2:
        config = load_auto_index_config()
        if not config:
            return await message.reply("📋 No auto-indexing channels configured.\n\n💡 Usage:\n• Enable: `/autoindex enable @channel`\n• Disable: `/autoindex disable @channel`\n• List: `/autoindex list`")
        
        text = "🤖 Auto-indexing Status:\n\n"
        for chat_id, settings in config.items():
            status = "✅ Enabled" if settings.get('enabled', False) else "❌ Disabled"
            filters_info = f" | Filters: {', '.join(settings.get('filters', []))}" if settings.get('filters') else ""
            text += f"• <code>{chat_id}</code>: {status}{filters_info}\n"
        
        await message.reply(text)
        return
    
    command = message.command[1].lower()
    
    if command == "list":
        config = load_auto_index_config()
        if not config:
            return await message.reply("📋 No auto-indexing channels configured.")
        
        text = "🤖 Auto-indexing Channels:\n\n"
        for chat_id, settings in config.items():
            status = "✅ Enabled" if settings.get('enabled', False) else "❌ Disabled"
            filters_info = f" | Filters: {', '.join(settings.get('filters', []))}" if settings.get('filters') else ""
            text += f"• <code>{chat_id}</code>: {status}{filters_info}\n"
        
        await message.reply(text)
        return
    
    if len(message.command) < 3:
        return await message.reply("💡 Usage:\n• Enable: `/autoindex enable @channel`\n• Disable: `/autoindex disable @channel`\n• List: `/autoindex list`")
    
    chat_identifier = message.command[2]
    
    try:
        chat = await bot.get_chat(chat_identifier)
        chat_id = str(chat.id)
    except Exception as e:
        return await message.reply(f"❌ Error getting chat info: {e}")
    
    config = load_auto_index_config()
    
    if command == "enable":
        if chat_id not in config:
            config[chat_id] = {}
        config[chat_id]['enabled'] = True
        config[chat_id]['chat_title'] = chat.title or chat.username
        save_auto_index_config(config)
        await message.reply(f"✅ Auto-indexing enabled for {chat.title or chat.username} (<code>{chat_id}</code>)")
        
    elif command == "disable":
        if chat_id in config:
            config[chat_id]['enabled'] = False
            save_auto_index_config(config)
            await message.reply(f"❌ Auto-indexing disabled for {chat.title or chat.username} (<code>{chat_id}</code>)")
        else:
            await message.reply("❌ This channel is not in auto-index list.")
    else:
        await message.reply("💡 Usage:\n• Enable: `/autoindex enable @channel`\n• Disable: `/autoindex disable @channel`\n• List: `/autoindex list`")

# Auto-indexing handler for new messages in monitored channels
@Client.on_message(filters.channel & ~filters.service)
async def auto_index_new_files(bot, message):
    """Automatically index new files from monitored channels"""
    try:
        config = load_auto_index_config()
        chat_id = str(message.chat.id)
        
        if chat_id not in config or not config[chat_id].get('enabled', False):
            return
        
        # Check if message has media
        if not message.media:
            return
        
        if message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
            return
        
        media = getattr(message, message.media.value, None)
        if not media:
            return
        
        # Apply file filters if set
        channel_filters = set(config[chat_id].get('filters', []))
        global_filters = getattr(temp, 'FILE_FILTERS', set())
        file_filters = channel_filters or global_filters
        
        if file_filters and not should_index_file(media, file_filters):
            return
        
        # Set media properties for saving
        media.file_type = message.media.value
        media.caption = message.caption
        
        # Save the file
        try:
            ok, code = await save_file(media)
            if ok:
                LOGGER.info(f"Auto-indexed file: {getattr(media, 'file_name', 'Unknown')} from {message.chat.title}")
                # Optional: Send notification to log channel
                if LOG_CHANNEL:
                    try:
                        await bot.send_message(
                            LOG_CHANNEL,
                            f"🤖 Auto-indexed file:\n"
                            f"📁 File: <code>{getattr(media, 'file_name', 'Unknown')}</code>\n"
                            f"📺 Channel: {message.chat.title} (<code>{chat_id}</code>)\n"
                            f"🆔 Message ID: <code>{message.id}</code>"
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
    filtered_out = 0  # New counter for filtered files
    BATCH_SIZE = 200
    start_time = time.time()

    # Get current file filters
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
