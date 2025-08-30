# handlers/callback_handlers.py

import asyncio
import logging
import math
import pytz
import random
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from pyrogram.errors import MessageNotModified, UserIsBlocked, PeerIdInvalid
from urllib.parse import quote_plus

from info import *
from Script import script
from utils import (
    get_settings, save_group_settings, get_size, clean_filename, 
    clean_search_text, get_cap, is_check_admin, temp
)
from database.ia_filterdb import get_search_results, get_file_details, get_bad_files, Media, Media2
from database.users_chats_db import db
from database.refer import referdb

logger = logging.getLogger(__name__)

# Global dictionaries for caching
BUTTONS = {}
FRESH = {}


@Client.on_callback_query(filters.regex(r"^reffff"))
async def refercall(bot, query):
    """Handle referral callback"""
    btn = [[
        InlineKeyboardButton(
            'invite link', 
            url=f'https://telegram.me/share/url?url=https://t.me/{bot.me.username}?start=reff_{query.from_user.id}&text=Hello%21%20Experience%20a%20bot%20that%20offers%20a%20vast%20library%20of%20unlimited%20movies%20and%20series.%20%F0%9F%98%83'
        ),
        InlineKeyboardButton(
            f'⏳ {referdb.get_refer_points(query.from_user.id)}', 
            callback_data='ref_point'
        ),
        InlineKeyboardButton('Back', callback_data='premium_info')
    ]]
    reply_markup = InlineKeyboardMarkup(btn)
    
    try:
        await bot.edit_message_media(
            query.message.chat.id,
            query.message.id,
            InputMediaPhoto("https://graph.org/file/1a2e64aee3d4d10edd930.jpg")
        )
    except Exception:
        pass
    
    await query.message.edit_text(
        text=f'Hay Your refer link:\n\nhttps://t.me/{bot.me.username}?start=reff_{query.from_user.id}\n\nShare this link with your friends, Each time they join, you will get 10 refferal points and after 100 points you will get 1 month premium subscription.',
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )
    await query.answer()


@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    """Handle next page navigation"""
    ident, req, key, offset = query.data.split("_")
    
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    
    try:
        offset = int(offset)
    except:
        offset = 0
    
    search = BUTTONS.get(key) or FRESH.get(key)
    if not search:
        await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        return
    
    files, n_offset, total = await get_search_results(
        query.message.chat.id, search, offset=offset, filter=True
    )
    
    try:
        n_offset = int(n_offset)
    except:
        n_offset = 0
    
    if not files:
        return
    
    temp.GETALL[key] = files
    temp.SHORT[query.from_user.id] = query.message.chat.id
    settings = await get_settings(query.message.chat.id)
    
    # Build button layout
    btn = await build_file_buttons(files, settings, key)
    btn = await add_navigation_buttons(btn, settings, req, key, offset, n_offset, total)
    
    if not settings.get("button"):
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        cap = await get_cap(settings, "0.00", files, query, total, clean_search_text(search), offset+1)
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


async def build_file_buttons(files, settings, key):
    """Build file buttons based on settings"""
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
        InlineKeyboardButton('Qᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}"),
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


async def add_navigation_buttons(btn, settings, req, key, offset, n_offset, total):
    """Add navigation buttons for pagination"""
    try:
        max_btn = settings.get('max_btn', True)
        page_size = 10 if max_btn else int(MAX_B_TN)
        
        if 0 < offset <= page_size:
            off_set = 0
        elif offset == 0:
            off_set = None
        else:
            off_set = offset - page_size
        
        current_page = math.ceil(int(offset)/page_size) + 1
        total_pages = math.ceil(total/page_size)
        
        if n_offset == 0:
            btn.append([
                InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"{current_page} / {total_pages}", callback_data="pages")
            ])
        elif off_set is None:
            btn.append([
                InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"),
                InlineKeyboardButton(f"{current_page} / {total_pages}", callback_data="pages"),
                InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{n_offset}")
            ])
        else:
            btn.append([
                InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"{current_page} / {total_pages}", callback_data="pages"),
                InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{n_offset}")
            ])
    except KeyError:
        await save_group_settings(query.message.chat.id if hasattr(query, 'message') else None, 'max_btn', True)
        # Fallback to default pagination
        btn.append([
            InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset-10}"),
            InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
            InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{n_offset}")
        ])
    
    return btn


@Client.on_callback_query(filters.regex(r"^sendfiles"))
async def sendfiles_callback(client, query):
    """Handle send files callback"""
    clicked = query.from_user.id
    ident, key = query.data.split("#")
    
    try:
        await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=allfiles_{query.message.chat.id}_{key}")
        return
    except UserIsBlocked:
        await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
    except PeerIdInvalid:
        await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles3_{key}")
    except Exception as e:
        logger.exception(e)
        await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles4_{key}")


@Client.on_callback_query(filters.regex(r"^file"))
async def file_callback(client, query):
    """Handle individual file callback"""
    ident, file_id = query.data.split("#")
    user = query.message.reply_to_message.from_user.id if query.message.reply_to_message else query.from_user.id
    
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    
    await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}")


@Client.on_callback_query(filters.regex(r"^close_data"))
async def close_callback(client, query):
    """Handle close button callback"""
    try:
        user = query.message.reply_to_message.from_user.id
    except:
        user = query.from_user.id
    
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer(script.NT_ALRT_TXT, show_alert=True)
    
    await query.answer("ᴛʜᴀɴᴋs ꜰᴏʀ ᴄʟᴏsᴇ 🙈")
    await query.message.delete()
    
    try:
        await query.message.reply_to_message.delete()
    except:
        pass


@Client.on_callback_query(filters.regex(r"^pages"))
async def pages_callback(client, query):
    """Handle pages button callback"""
    await query.answer("ᴛʜɪs ɪs ᴘᴀɢᴇs ʙᴜᴛᴛᴏɴ 😅")


@Client.on_callback_query(filters.regex(r"^ref_point"))
async def ref_point_callback(client, query):
    """Handle referral points callback"""
    await query.answer(
        f'You Have: {referdb.get_refer_points(query.from_user.id)} Refferal points.', 
        show_alert=True
    )


@Client.on_callback_query(filters.regex(r"^premium_info"))
async def premium_info_callback(client, query):
    """Handle premium info callback"""
    try:
        btn = [[
            InlineKeyboardButton('• ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ •', callback_data='buy_info'),
        ],[
            InlineKeyboardButton('• ʀᴇꜰᴇʀ ꜰʀɪᴇɴᴅꜱ', callback_data='reffff'),
            InlineKeyboardButton('ꜰʀᴇᴇ ᴛʀɪᴀʟ •', callback_data='give_trial')
        ],[            
            InlineKeyboardButton('⇋ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ⇋', callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(btn)
        
        await client.edit_message_media(
            chat_id=query.message.chat.id,
            message_id=query.message.id,
            media=InputMediaPhoto(
                media=SUBSCRIPTION, 
                caption=script.BPREMIUM_TXT, 
                parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=reply_markup
        )
    except Exception as e:
        logging.exception("Exception in 'premium_info' callback")


@Client.on_callback_query(filters.regex(r"^give_trial"))
async def give_trial_callback(client, query):
    """Handle free trial callback"""
    try:
        user_id = query.from_user.id
        has_free_trial = await db.check_trial_status(user_id)
        
        if has_free_trial:
            await query.answer(
                "🚸 ʏᴏᴜ'ᴠᴇ ᴀʟʀᴇᴀᴅʏ ᴄʟᴀɪᴍᴇᴅ ʏᴏᴜʀ ꜰʀᴇᴇ ᴛʀɪᴀʟ ᴏɴᴄᴇ !\n\n📌 ᴄʜᴇᴄᴋᴏᴜᴛ ᴏᴜʀ ᴘʟᴀɴꜱ ʙʏ : /plan",
                show_alert=True
            )
            return
        
        await db.give_free_trial(user_id)
        await query.answer("✅ Trial activated!", show_alert=True)
        
        msg = await client.send_photo(
            chat_id=query.message.chat.id,
            photo="https://i.ibb.co/0jC8MSDZ/photo-2025-07-26-10-42-36-7531339283701956616.jpg",
            caption=(
                "<b>🥳 ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴꜱ\n\n"
                "🎉 ʏᴏᴜ ᴄᴀɴ ᴜsᴇ ꜰʀᴇᴇ ᴛʀᴀɪʟ ꜰᴏʀ <u>5 ᴍɪɴᴜᴛᴇs</u> ꜰʀᴏᴍ ɴᴏᴡ !\n\n"
                "ɴᴇᴇᴅ ᴘʀᴇᴍɪᴜᴍ 👉🏻 /plan</b>"
            ),
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 Buy Premium 🚀", callback_data="premium_info")
            ]])
        )
        
        await asyncio.sleep(DELETE_TIME)
        await msg.delete()
        
    except Exception as e:
        logging.exception("Error in give_trial callback")
