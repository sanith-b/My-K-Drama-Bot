# handlers/quality_handlers.py

import math
import pytz
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import MessageNotModified

from info import QUALITIES, MAX_B_TN, temp
from utils import get_settings, save_group_settings, get_size, clean_filename, clean_search_text, get_cap
from database.ia_filterdb import get_search_results

# Global dictionaries (shared with other modules)
BUTTONS = {}
FRESH = {}


@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_cb_handler(client: Client, query: CallbackQuery):
    """Handle quality selection callback"""
    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ {query.from_user.first_name},\n"
                f"ᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇǫᴜᴇꜱᴛ,\nʀᴇǫᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass

    _, key = query.data.split("#")
    search = FRESH.get(key)
    
    if not search:
        return await query.answer("Session expired. Please search again.", show_alert=True)
    
    search = search.replace(' ', '_')

    btn = []
    for i in range(0, len(QUALITIES), 2):
        q1 = QUALITIES[i]
        row = [InlineKeyboardButton(
            text=q1, callback_data=f"fq#{q1.lower()}#{key}")]
        if i + 1 < len(QUALITIES):
            q2 = QUALITIES[i + 1]
            row.append(InlineKeyboardButton(
                text=q2, callback_data=f"fq#{q2.lower()}#{key}"))
        btn.append(row)

    btn.insert(0, [
        InlineKeyboardButton(text="⇊ ꜱᴇʟᴇᴄᴛ ǫᴜᴀʟɪᴛʏ ⇊", callback_data="ident")
    ])
    btn.append([
        InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs ↭",
                             callback_data=f"fq#homepage#{key}")
    ])

    await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))


@Client.on_callback_query(filters.regex(r"^fq#"))
async def filter_qualities_cb_handler(client: Client, query: CallbackQuery):
    """Handle quality filter selection"""
    _, qual, key = query.data.split("#")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    search = FRESH.get(key)
    
    if not search:
        return await query.answer("Session expired. Please search again.", show_alert=True)
    
    search = search.replace("_", " ")
    
    # Check if quality is already in search term
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
                f"⚠️ ʜᴇʟʟᴏ {query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇǫᴜᴇꜱᴛ,\nʀᴇǫᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...", 
                show_alert=True
            )
    except:
        pass
        
    if qual != "homepage":
        search = f"{search} {qual}"
        
    BUTTONS[key] = search
    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    
    if not files:
        await query.answer("🚫 ɴᴏ ꜰɪʟᴇꜱ ᴡᴇʀᴇ ꜰᴏᴜɴᴅ 🚫", show_alert=1)
        return
        
    temp.GETALL[key] = files
    settings = await get_settings(message.chat.id)
    
    btn = await build_quality_result_buttons(files, settings, key)
    btn = await add_quality_pagination(btn, settings, req, key, offset, total_results)
    
    if not settings.get("button"):
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
        dreamx_title = clean_search_text(search)
        cap = await get_cap(settings, remaining_seconds, files, query, total_results, dreamx_title, offset=1)
        
        try:
            await query.message.edit_text(
                text=cap, 
                reply_markup=InlineKeyboardMarkup(btn), 
                disable_web_page_preview=True
            )
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass
            
    await query.answer()


async def build_quality_result_buttons(files, settings, key):
    """Build buttons for quality filtered results"""
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


async def add_quality_pagination(btn, settings, req, key, offset, total_results):
    """Add pagination buttons for quality results"""
    if offset != "":
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
            await save_group_settings(key, 'max_btn', True)
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
            InlineKeyboardButton(
                text="↭ ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ ↭", 
                callback_data="pages"
            )
        ])
    
    return btn
