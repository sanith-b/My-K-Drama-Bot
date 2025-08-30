# handlers/seasons_handlers.py

import math
import pytz
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import MessageNotModified

from info import SEASONS, MAX_B_TN, temp
from utils import (
    get_settings, save_group_settings, get_size, clean_filename, 
    clean_search_text, get_cap, generate_season_variations
)
from database.ia_filterdb import get_search_results

# Global dictionaries (shared with other modules)
BUTTONS = {}
FRESH = {}


@Client.on_callback_query(filters.regex(r"^seasons#"))
async def seasons_cb_handler(client: Client, query: CallbackQuery):
    """Handle season selection callback"""
    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ {query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇǫᴜᴇꜱᴛ,\nʀᴇǫᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ…",
                show_alert=True,
            )
    except Exception:
        pass
        
    _, key = query.data.split("#")
    search = FRESH.get(key)
    
    if not search:
        return await query.answer("Session expired. Please search again.", show_alert=True)
        
    search = search.replace(" ", "_")
    req = query.from_user.id
    offset = 0
    
    btn = []
    for i in range(0, len(SEASONS) - 1, 2):
        btn.append([
            InlineKeyboardButton(
                f"Sᴇᴀꜱᴏɴ {SEASONS[i][1:]}", 
                callback_data=f"fs#{SEASONS[i].lower()}#{key}"
            ),
            InlineKeyboardButton(
                f"Sᴇᴀꜱᴏɴ {SEASONS[i+1][1:]}", 
                callback_data=f"fs#{SEASONS[i+1].lower()}#{key}"
            )
        ])

    btn.insert(
        0,
        [InlineKeyboardButton("⇊ ꜱᴇʟᴇᴄᴛ ꜱᴇᴀꜱᴏɴ ⇊", callback_data="ident")],
    )
    btn.append([InlineKeyboardButton(
        text="↭ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs ​↭",
        callback_data=f"next_{req}_{key}_{offset}"
    )])
    
    await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^fs#"))
async def filter_seasons_cb_handler(client: Client, query: CallbackQuery):
    """Handle season filter selection"""
    _, season_tag, key = query.data.split("#")
    search = FRESH.get(key)
    
    if not search:
        return await query.answer("Session expired. Please search again.", show_alert=True)
        
    search = search.replace("_", " ")
    season_tag = season_tag.lower()
    
    if season_tag == "homepage":
        search_final = search
        query_input = search_final
    else:
        season_number = int(season_tag[1:])
        query_input = generate_season_variations(search, season_number)
        search_final = query_input[0] if query_input else search

    BUTTONS[key] = search_final
    
    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer("⚠️ Not your request", show_alert=True)
    except Exception:
        pass

    chat_id = query.message.chat.id
    req = query.from_user.id
    files, n_offset, total_results = await get_search_results(
        chat_id, query_input, offset=0, filter=True
    )
    
    if not files:
        return await query.answer("🚫 ɴᴏ ꜰɪʟᴇꜱ ꜰᴏᴜɴᴅ 🚫", show_alert=True)

    temp.GETALL[key] = files
    settings = await get_settings(chat_id)
    
    btn = await build_season_result_buttons(files, settings, key)
    btn = await add_season_pagination(btn, settings, req, key, n_offset, total_results)
    
    if not settings.get("button"):
        curr_time = datetime.now(pytz.timezone("Asia/Kolkata")).time()
        time_difference = timedelta(
            hours=curr_time.hour,
            minutes=curr_time.minute,
            seconds=curr_time.second + curr_time.microsecond / 1_000_000,
        )
        remaining_seconds = f"{time_difference.total_seconds():.2f}"
        dreamx_title = clean_search_text(search_final)
        cap = await get_cap(
            settings, remaining_seconds, files, query, total_results, dreamx_title, offset=1
        )
        
        try:
            await query.message.edit_text(
                text=cap,
                reply_markup=InlineKeyboardMarkup(btn),
                disable_web_page_preview=True,
            )
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass
            
    await query.answer()


async def build_season_result_buttons(files, settings, key):
    """Build buttons for season filtered results"""
    btn = []
    
    if settings.get("button"):
        btn.extend([
            [InlineKeyboardButton(
                f"🔗 {get_size(f.file_size)} ≽ " + clean_filename(f.file_name),
                callback_data=f"file#{f.file_id}",
            )]
            for f in files
        ])
    
    # Add filter buttons
    btn.insert(0, [
        InlineKeyboardButton("Qᴜᴀʟɪᴛʏ", callback_data=f"qualities#{key}"),
        InlineKeyboardButton("Lᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}"),
        InlineKeyboardButton("Sᴇᴀꜱᴏɴ", callback_data=f"seasons#{key}"),
    ])
    
    # Add premium and send all buttons
    btn.insert(0, [
        InlineKeyboardButton(
            "⚜️ 𝐑𝐞𝐦𝐨𝐯𝐞 Aᴅꜱ ⚜️", 
            url=f"https://t.me/{temp.U_NAME}?start=premium"
        ),
        InlineKeyboardButton("Sᴇɴᴅ Aʟʟ", callback_data=f"sendfiles#{key}"),
    ])
    
    return btn


async def add_season_pagination(btn, settings, req, key, n_offset, total_results):
    """Add pagination buttons for season results"""
    if n_offset != "":
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
                        callback_data=f"next_{req}_{key}_{n_offset}"
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
                        callback_data=f"next_{req}_{key}_{n_offset}"
                    )
                ])
        except KeyError:
            # Fallback to default settings
            btn.append([
                InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), 
                InlineKeyboardButton(
                    text=f"1/{math.ceil(int(total_results)/10)}", 
                    callback_data="pages"
                ), 
                InlineKeyboardButton(
                    text="ɴᴇxᴛ ⋟", 
                    callback_data=f"next_{req}_{key}_{n_offset}"
                )
            ])
    else:
        btn.append([
            InlineKeyboardButton(
                "↭  ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ ↭", 
                callback_data="pages"
            )
        ])
    
    return btn
