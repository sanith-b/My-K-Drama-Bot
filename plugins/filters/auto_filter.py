# filters/auto_filter.py

import asyncio
import logging
import math
import pytz
import re
from datetime import datetime, timedelta
from pyrogram import enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty

from info import DELETE_TIME, MAX_B_TN, temp
from Script import script
from utils import (
    get_settings, save_group_settings, get_size, clean_filename,
    clean_search_text, get_cap, get_poster, temp
)
from database.ia_filterdb import get_search_results
from handlers.spell_check import advantage_spell_chok, ai_spell_check

logger = logging.getLogger(__name__)

# Global dictionaries
FRESH = {}


async def auto_filter(client, msg, spoll=False):
    """Main auto filter function"""
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    
    if not spoll:
        message = msg
        if message.text.startswith("/"):
            return
            
        if re.findall(r"((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
            
        if len(message.text) < 100:
            search = message.text
            search = search.lower()
            m = await message.reply_text(
                f'**🔎 sᴇᴀʀᴄʜɪɴɢ** `{search}`', 
                reply_to_message_id=message.id
            )
            
            # Clean and process search query
            search = await clean_search_query(search)
            
            files, offset, total_results = await get_search_results(
                message.chat.id, search, offset=0, filter=True
            )
            settings = await get_settings(message.chat.id)
            
            if not files:
                return await handle_no_results(client, message, m, search, settings)
        else:
            return
    else:
        message = msg.message.reply_to_message
        search, files, offset, total_results = spoll
        m = await message.reply_text(
            f'**🔎 sᴇᴀʀᴄʜɪɴɢ** `{search}`', 
            reply_to_message_id=message.id
        )
        settings = await get_settings(message.chat.id)
        await msg.message.delete()
    
    # Generate unique key for this search
    key = f"{message.chat.id}-{message.id}"
    FRESH[key] = search
    temp.GETALL[key] = files
    temp.SHORT[message.from_user.id] = message.chat.id
    
    # Build button layout
    btn = await build_search_buttons(files, settings, key)
    btn = await add_search_pagination(btn, settings, message, key, offset, total_results)
    
    # Get IMDB info if enabled
    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    
    # Generate caption
    cap = await generate_search_caption(settings, search, files, total_results, message, imdb)
    
    # Send results
    await send_search_results(message, m, cap, btn, imdb, settings)


async def clean_search_query(search):
    """Clean and process search query"""
    find = search.split(" ")
    search = ""
    removes = ["in", "upload", "series", "full", "horror", "thriller", "mystery", "print", "file"]
    
    for x in find:
        if x in removes:
            continue
        else:
            search = search + x + " "
    
    # Remove common patterns
    search = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|bro|bruh|broh|helo|that|find|dubbed|link|venum|iruka|pannunga|pannungga|anuppunga|anupunga|anuppungga|anupungga|film|undo|kitti|kitty|tharu|kittumo|kittum|movie|any(one)|with\ssubtitle(s)?)", 
        "", search, flags=re.IGNORECASE
    )
    
    search = re.sub(r"\s+", " ", search).strip()
    search = search.replace("-", " ")
    search = search.replace(":", "")
    
    return search


async def handle_no_results(client, message, m, search, settings):
    """Handle case when no files are found"""
    if settings["spell_check"]:
        ai_sts = await m.edit('🤖 ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ, ᴀɪ ɪꜱ ᴄʜᴇᴄᴋɪɴɢ ʏᴏᴜʀ ꜱᴘᴇʟʟɪɴɢ...')
        is_misspelled = await ai_spell_check(chat_id=message.chat.id, wrong_name=search)
        
        if is_misspelled:
            await ai_sts.edit(f'✅ Aɪ Sᴜɢɢᴇsᴛᴇᴅ: <code>{is_misspelled}</code>\n🔍 Searching for it...')
            message.text = is_misspelled
            await ai_sts.delete()
            return await auto_filter(client, message)
            
        await ai_sts.delete()
        return await advantage_spell_chok(client, message)
    else:
        await m.delete()
        return await advantage_spell_chok(client, message)


async def build_search_buttons(files, settings, key):
    """Build buttons for search results"""
    btn = []
    
    if settings.get('button'):
        btn = [
            [InlineKeyboardButton(
                text=f"🔗 {get_size(file.file_size)} ≽ " + clean_filename(file.file_name),
                callback_data=f'file#{file.file_id}'
            )]
            for file in files
        ]
    
    # Add filter buttons
    btn.insert(0, [
        InlineKeyboardButton(f'Qᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
        InlineKeyboardButton("Lᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}"),
        InlineKeyboardButton("Sᴇᴀsᴏɴ", callback_data=f"seasons#{key}")
    ])
    
    # Add premium and send all buttons
    btn.insert(0, [
        InlineKeyboardButton(
            "⚜️ 𝐑𝐞𝐦𝐨𝐯𝐞 𝐚𝐝𝐬 ⚜️",
            url=f"https://t.me/{temp.U_NAME}?start=premium"
        ),
        InlineKeyboardButton("Sᴇɴᴅ Aʟʟ", callback_data=f"sendfiles#{key}")
    ])
    
    return btn


async def add_search_pagination(btn, settings, message, key, offset, total_results):
    """Add pagination buttons"""
    if offset != "":
        req = message.from_user.id if message.from_user else 0
        try:
            if settings.get('max_btn', True):
                btn.append([
                    InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"),
                    InlineKeyboardButton(
                        text=f"1/{math.ceil(int(total_results)/10)}",
                        callback_data="pages"
                    ),
                    InlineKeyboardButton(
                        text="ɴᴇxᴛ ⋟",
                        callback_data=f"next_{req}_{key}_{offset}"
                    )
                ])
            else:
                btn.append([
                    InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"),
                    InlineKeyboardButton(
                        text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",
                        callback_data="pages"
                    ),
                    InlineKeyboardButton(
                        text="ɴᴇxᴛ ⋟",
                        callback_data=f"next_{req}_{key}_{offset}"
                    )
                ])
        except KeyError:
            await save_group_settings(message.chat.id, 'max_btn', True)
            btn.append([
                InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"),
                InlineKeyboardButton(
                    text=f"1/{math.ceil(int(total_results)/10)}",
                    callback_data="pages"
                ),
                InlineKeyboardButton(
                    text="ɴᴇxᴛ ⋟",
                    callback_data=f"next_{req}_{key}_{offset}"
                )
            ])
    else:
        btn.append([InlineKeyboardButton(
            text="↭ ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ ↭",
            callback_data="pages"
        )])
    
    return btn


async def generate_search_caption(settings, search, files, total_results, message, imdb):
    """Generate caption for search results"""
    cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    remaining_seconds = "0.00"  # Simplified for now
    
    TEMPLATE = script.IMDB_TEMPLATE_TXT
    if settings.get('template'):
        TEMPLATE = settings['template']
    
    if imdb:
        cap = TEMPLATE.format(
            query=search,
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
            cap += "\n\n<b>🧾 <u>Your Requested Files Are Here</u> 👇</b>"
            for idx, file in enumerate(files, start=1):
                cap += f"<b>\n{idx}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>[{get_size(file.file_size)}] {clean_filename(file.file_name)}\n</a></b>"
    else:
        if settings.get('button'):
            cap = f"<b>🏷 ᴛɪᴛʟᴇ : <code>{search}</code>\n🧱 ᴛᴏᴛᴀʟ ꜰɪʟᴇꜱ : <code>{total_results}</code>\n⏰ ʀᴇsᴜʟᴛ ɪɴ : <code>{remaining_seconds} Sᴇᴄᴏɴᴅs</code>\n\n📝 ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ : {message.from_user.mention}\n⚜️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ : ⚡ {message.chat.title or temp.B_LINK or 'ᴅʀᴇᴀᴍxʙᴏᴛᴢ'} \n\n🧾 <u>Your Requested Files Are Here</u> 👇 \n\n</b>"
        else:
            cap = f"<b>🏷 ᴛɪᴛʟᴇ : <code>{search}</code>\n🧱 ᴛᴏᴛᴀʟ ꜰɪʟᴇꜱ : <code>{total_results}</code>\n⏰ ʀᴇsᴜʟᴛ ɪɴ : <code>{remaining_seconds} Sᴇᴄᴏɴᴅs</code>\n\n📝 ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ : {message.from_user.mention}\n⚜️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ : ⚡ {message.chat.title or temp.B_LINK or 'ᴅʀᴇᴀᴍxʙᴏᴛᴢ'} \n\n🧾 <u>Your Requested Files Are Here</u> 👇 \n\n</b>"

            for idx, file in enumerate(files, start=1):
                cap += f"<b>\n{idx}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>[{get_size(file.file_size)}] {clean_filename(file.file_name)}\n</a></b>"
    
    return cap


async def send_search_results(message, m, cap, btn, imdb, settings):
    """Send search results to user"""
    if imdb and imdb.get('poster'):
        try:
            hehe = await message.reply_photo(
                photo=imdb.get('poster'), 
                caption=cap, 
                reply_markup=InlineKeyboardMarkup(btn), 
                parse_mode=enums.ParseMode.HTML
            )
            await m.delete()
            await handle_auto_delete(settings, hehe, message)
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            hmm = await message.reply_photo(
                photo=poster, 
                caption=cap, 
                reply_markup=InlineKeyboardMarkup(btn), 
                parse_mode=enums.ParseMode.HTML
            )
            await m.delete()
            await handle_auto_delete(settings, hmm, message)
        except Exception as e:
            logger.exception(e)
            dxb = await message.reply_text(
                text=cap, 
                reply_markup=InlineKeyboardMarkup(btn), 
                parse_mode=enums.ParseMode.HTML
            )
            await m.delete()
            await handle_auto_delete(settings, dxb, message)
    else:
        dxb = await message.reply_text(
            text=cap, 
            reply_markup=InlineKeyboardMarkup(btn), 
            disable_web_page_preview=True, 
            parse_mode=enums.ParseMode.HTML
        )
        await m.delete()
        await handle_auto_delete(settings, dxb, message)


async def handle_auto_delete(settings, sent_message, original_message):
    """Handle auto deletion of messages"""
    try:
        if settings.get('auto_delete', False):
            await asyncio.sleep(DELETE_TIME)
            await sent_message.delete()
            await original_message.delete()
    except KeyError:
        await save_group_settings(original_message.chat.id, 'auto_delete', True)
        await asyncio.sleep(DELETE_TIME)
        await sent_message.delete()
        await original_message.delete()
    except Exception as e:
        logger.exception(f"Error in auto delete: {e}")
