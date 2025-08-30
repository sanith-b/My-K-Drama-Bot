# handlers/utility_handlers.py

import asyncio
import logging
import pytz
import random
from datetime import datetime
from urllib.parse import quote_plus
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from pyrogram.errors import UserIsBlocked, PeerIdInvalid

from info import *
from Script import script
from utils import temp, get_size, is_subscribed, is_req_subscribed, log_error
from database.users_chats_db import db
from database.refer import referdb
from dreamxbotz.util.file_properties import get_name, get_hash

logger = logging.getLogger(__name__)


@Client.on_callback_query(filters.regex(r"^checksub"))
async def check_subscription_callback(client, query):
    """Handle subscription check callback"""
    try:
        ident, kk, file_id = query.data.split("#")
        btn = []
        chat = file_id.split("_")[0]
        settings = await get_settings(chat)
        
        # Get force sub channels
        fsub_channels = list(dict.fromkeys(
            (settings.get('fsub', []) if settings else []) + AUTH_CHANNELS
        ))
        
        btn += await is_subscribed(client, query.from_user.id, fsub_channels)
        btn += await is_req_subscribed(client, query.from_user.id, AUTH_REQ_CHANNELS)
        
        if btn:
            btn.append([InlineKeyboardButton(
                "♻️ ᴛʀʏ ᴀɢᴀɪɴ ♻️", 
                callback_data=f"checksub#{kk}#{file_id}"
            )])
            
            try:
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
            except MessageNotModified:
                pass
                
            await query.answer(
                f"👋 Hello {query.from_user.first_name},\n\n"
                "🛑 Yᴏᴜ ʜᴀᴠᴇ ɴᴏᴛ ᴊᴏɪɴᴇᴅ ᴀʟʟ ʀᴇǫᴜɪʀᴇᴅ ᴜᴘᴅᴀᴛᴇ Cʜᴀɴɴᴇʟs.\n"
                "👉 Pʟᴇᴀsᴇ ᴊᴏɪɴ ᴇᴀᴄʜ ᴏɴᴇ ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ.\n",
                show_alert=True
            )
            return
            
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start={kk}_{file_id}")
        await query.message.delete()
        
    except Exception as e:
        await log_error(client, f"❌ Error in checksub callback:\n\n{repr(e)}")
        logger.error(f"❌ Error in checksub callback:\n\n{repr(e)}")


@Client.on_callback_query(filters.regex(r"^generate_stream_link"))
async def generate_stream_link_callback(client, query):
    """Generate streaming link callback"""
    _, file_id = query.data.split(":")
    
    try:
        user_id = query.from_user.id
        username = query.from_user.mention
        log_msg = await client.send_cached_media(chat_id=LOG_CHANNEL, file_id=file_id)
        fileName = quote_plus(get_name(log_msg))
        dreamx_stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
        dreamx_download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
        
        xo = await query.message.reply_text(f'💘')
        await asyncio.sleep(1)
        await xo.delete()
        
        await log_msg.reply_text(
            text=f"•• ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇᴅ ꜰᴏʀ ɪᴅ #{user_id} \n•• ᴜꜱᴇʀɴᴀᴍᴇ : {username} \n\n•• ᖴᎥᒪᗴ Nᗩᗰᗴ : {fileName}",
            quote=True,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🚀 Fast Download 🚀", url=dreamx_download),
                    InlineKeyboardButton('🖥️ Watch online 🖥️', url=dreamx_stream)
                ]
            ])
        )
        
        dreamcinezone = await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🚀 Download ", url=dreamx_download),
                    InlineKeyboardButton('🖥️ Watch ', url=dreamx_stream)
                ],
                [
                    InlineKeyboardButton('📌 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇꜱ ᴄʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)
                ]
            ])
        )
        
        await asyncio.sleep(DELETE_TIME)
        await dreamcinezone.delete()
        
    except Exception as e:
        print(e)
        await query.answer(f"⚠️ SOMETHING WENT WRONG STREAM LINK  \n\n{e}", show_alert=True)


@Client.on_callback_query(filters.regex(r"^prestream"))
async def prestream_callback(client, query):
    """Handle pre-stream alert callback"""
    await query.answer(text=script.PRE_STREAM_ALERT, show_alert=True)
    
    dreamcinezone = await client.send_photo(
        chat_id=query.message.chat.id,
        photo="https://i.ibb.co/whf8xF7j/photo-2025-07-26-10-42-46-7531339305176793100.jpg",
        caption=script.PRE_STREAM,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Buy Premium 🚀", callback_data="premium_info")]
        ])
    )
    
    await asyncio.sleep(DELETE_TIME)
    await dreamcinezone.delete()


@Client.on_callback_query(filters.regex(r"^start"))
async def start_callback(client, query):
    """Handle start button callback"""
    buttons = [
        [
            InlineKeyboardButton(
                '🔰 ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ 🔰', 
                url=f'http://telegram.me/{temp.U_NAME}?startgroup=true'
            )
        ],
        [
            InlineKeyboardButton(' ʜᴇʟᴘ 📢', callback_data='help'),
            InlineKeyboardButton(' ᴀʙᴏᴜᴛ 📖', callback_data='about')
        ],
        [
            InlineKeyboardButton('ᴛᴏᴘ sᴇᴀʀᴄʜɪɴɢ ⭐', callback_data="topsearch"),
            InlineKeyboardButton('ᴜᴘɢʀᴀᴅᴇ 🎟', callback_data="premium_info"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    current_time = datetime.now(pytz.timezone(TIMEZONE))
    curr_time = current_time.hour
    
    if curr_time < 12:
        gtxt = "ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ 🌞"
    elif curr_time < 17:
        gtxt = "ɢᴏᴏᴅ ᴀғᴛᴇʀɴᴏᴏɴ 🌓"
    elif curr_time < 21:
        gtxt = "ɢᴏᴏᴅ ᴇᴠᴇɴɪɴɢ 🌘"
    else:
        gtxt = "ɢᴏᴏᴅ ɴɪɢʜᴛ 🌑"
    
    try:
        await client.edit_message_media(
            query.message.chat.id,
            query.message.id,
            InputMediaPhoto(random.choice(PICS))
        )
    except Exception:
        pass
    
    await query.message.edit_text(
        text=script.START_TXT.format(query.from_user.mention, gtxt, temp.U_NAME, temp.B_NAME),
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )
    await query.answer(MSG_ALRT)


@Client.on_callback_query(filters.regex(r"^help"))
async def help_callback(client, query):
    """Handle help button callback"""
    buttons = [
        [InlineKeyboardButton('⇋ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ⇋', callback_data='start')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await query.message.edit_text(
        text=script.HELP_TXT,
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex(r"^about"))
async def about_callback(client, query):
    """Handle about button callback"""
    buttons = [
        [
            InlineKeyboardButton('‼️ ᴅɪꜱᴄʟᴀɪᴍᴇʀ ‼️', callback_data='disclaimer'),
            InlineKeyboardButton('🪔 sᴏᴜʀᴄᴇ', callback_data='source'),
        ],
        [
            InlineKeyboardButton('ᴅᴏɴᴀᴛɪᴏɴ 💰', callback_data='donation'),
        ],
        [
            InlineKeyboardButton('⇋ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ⇋', callback_data='start')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await query.message.edit_text(
        text=script.ABOUT_TXT.format(temp.U_NAME, temp.B_NAME, OWNER_LNK),
        reply_markup=reply_markup,
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex(r"^source"))
async def source_callback(client, query):
    """Handle source button callback"""
    buttons = [
        [
            InlineKeyboardButton('ᴅʀᴇᴀᴍxʙᴏᴛᴢ 📜', url='https://github.com/DreamXBotz/Auto_Filter_Bot.git'),
            InlineKeyboardButton('⇋ ʙᴀᴄᴋ ⇋', callback_data='about')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await query.message.edit_text(
        text=script.SOURCE_TXT,
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex(r"^disclaimer"))
async def disclaimer_callback(client, query):
    """Handle disclaimer button callback"""
    btn = [
        [InlineKeyboardButton("⇋ ʙᴀᴄᴋ ⇋", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(btn)
    
    await query.message.edit_text(
        text=script.DISCLAIMER_TXT,
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex(r"^buy_"))
async def buy_star_callback(client, query):
    """Handle star purchase callback"""
    stars = int(query.data.split("_")[1])
    
    if stars not in STAR_PREMIUM_PLANS:
        await query.answer("Invalid plan selected.", show_alert=True)
        return
    
    # Handle star purchase logic here
    await query.answer(f"Selected {stars} stars plan", show_alert=True)
