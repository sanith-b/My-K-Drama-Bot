import asyncio
import re
import ast
import math
import random
import pytz
from datetime import datetime, timedelta, date, time
lock = asyncio.Lock()
from database.users_chats_db import db
from database.refer import referdb
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
import pyrogram
from info import *
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, WebAppInfo
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid, MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
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
from typing import List, Dict, Optional, Tuple
import logging
from fuzzywuzzy import process
from pyrogram import enums

import aiohttp
import json
from dataclasses import dataclass
from enum import Enum



tracemalloc.start()

TIMEZONE = "Asia/Kolkata"
BUTTON = {}
BUTTONS = {}
FRESH = {}
SPELL_CHECK = {}

LOGGER = logging.getLogger(__name__)

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
            return await message.reply_text(f"<b>✨ Hello {message.from_user.mention}! \n\n✅ Your request is already available. \n📂 Files found: {str(total_results)} \n🔍 Search: <code>{search}</code> \n‼️ This is a <u>support group</u>, so you can’t get files from here. \n\n📝 Search Hear 👇</b>",   
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
    try:
        await silentdb.update_top_messages(user_id, content)
        pm_search = await db.pm_search_status(bot_id)
        if pm_search:
            await auto_filter(bot, message)
        else:
            await message.reply_text(
             text=f"<b><i>⚠️ Not available here! Join & search below 👇</i></b>",   
             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Start Search", url=GRP_LNK)]])
            )
    except Exception as e:
        LOGGER.error(f"An error occurred: {str(e)}")


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
        if BUTTONS.get(key)!=None:
            search = BUTTONS.get(key)
        else:
            search = FRESH.get(key)
        if not search:
            await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
            return
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=offset, filter=True)
        try:
            n_offset = int(n_offset)
        except:
            n_offset = 0
        if not files:
            return
        temp.GETALL[key] = files
        temp.SHORT[query.from_user.id] = query.message.chat.id
        settings = await get_settings(query.message.chat.id)
        if settings.get('button'):
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{silent_size(file.file_size)}| {extract_tag(file.file_name)} {clean_filename(file.file_name)}", callback_data=f'file#{file.file_id}'
                    ),
                ]
                for file in files
            ]
            btn.insert(0, 
                [ 
                    InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                        InlineKeyboardButton("🗓️ Season",  callback_data=f"seasons#{key}#0")
                ]
            )
            btn.insert(1, [
                InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}")
           
            ])
        else:
            btn = []
            btn.insert(0, 
                [
                    InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                        InlineKeyboardButton("🗓️ Season",  callback_data=f"seasons#{key}#0")
                ]
            )
            btn.insert(1, [
                InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}") 
           
            ])
        try:
            if settings['max_btn']:
                if 0 < offset <= 10:
                    off_set = 0
                elif offset == 0:
                    off_set = None
                else:
                    off_set = offset - 10
                if n_offset == 0:
                    btn.append(
                        [InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages")]
                    )
                elif off_set is None:
                    btn.append([InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"), InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")])
                else:
                    btn.append(
                        [
                            InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"),
                            InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                            InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
                        ],
                    )
            else:
                if 0 < offset <= int(MAX_B_TN):
                    off_set = 0
                elif offset == 0:
                    off_set = None
                else:
                    off_set = offset - int(MAX_B_TN)
                if n_offset == 0:
                    btn.append(
                        [InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages")]
                    )
                elif off_set is None:
                    btn.append([InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages"), InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")])
                else:
                    btn.append(
                        [
                            InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"),
                            InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages"),
                            InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
                        ],
                    )
        except KeyError:
            await save_group_settings(query.message.chat.id, 'max_btn', True)
            if 0 < offset <= 10:
                off_set = 0
            elif offset == 0:
                off_set = None
            else:
                off_set = offset - 10
            if n_offset == 0:
                btn.append(
                    [InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages")]
                )
            elif off_set is None:
                btn.append([InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"), InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")])
            else:
                btn.append(
                    [
                        InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req}_{key}_{off_set}"),
                        InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                        InlineKeyboardButton("➡️ Next", callback_data=f"next_{req}_{key}_{n_offset}")
                    ],
                )
        if not settings.get('button'):
            cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
            time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
            remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
            cap = await get_cap(settings, remaining_seconds, files, query, total, search, offset)
            try:
                await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
        else:
            try:
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except MessageNotModified:
                pass
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error In Next Funtion - {e}")

@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_cb_handler(client: Client, query: CallbackQuery):
    try:
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
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
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
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
        temp.GETALL[key] = files
        settings = await get_settings(message.chat.id)
        if settings.get('button'):
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{silent_size(file.file_size)}| {extract_tag(file.file_name)} {clean_filename(file.file_name)}", callback_data=f'file#{file.file_id}'
                    ),
                ]
                for file in files
            ]
            btn.insert(0, 
                [ 
                    InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                        InlineKeyboardButton("🗓️ Season",  callback_data=f"seasons#{key}#0")
                ]
            )
            btn.insert(1, [
                InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}")
           
            ])

        else:
            btn = []
            btn.insert(0, 
                [
                    InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                        InlineKeyboardButton("🗓️ Season",  callback_data=f"seasons#{key}#0")
                ]
            )
            btn.insert(1, [           
                InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}")
           
            ])
        if n_offset != "":
            try:
                if settings['max_btn']:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )
    
                else:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )
            except KeyError:
                await save_group_settings(query.message.chat.id, 'max_btn', True)
                btn.append(
                    [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                )
        else:
            n_offset = 0
            btn.append(
                [InlineKeyboardButton(text="🚫 That’s everything!",callback_data="pages")]
            )               
        if not settings.get('button'):
            cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
            time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
            remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
            cap = await get_cap(settings, remaining_seconds, files, query, total_results, search, offset)
            try:
                await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
            except MessageNotModified:
                pass
        else:
            try:
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except MessageNotModified:
                pass
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error In Quality - {e}")


@Client.on_callback_query(filters.regex(r"^languages#"))
async def languages_cb_handler(client: Client, query: CallbackQuery):
    try:
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
                    show_alert=True,
                )
        except:
            pass
        _, key, offset = query.data.split("#")
        search = FRESH.get(key)
        search = search.replace(' ', '_')
        offset = int(offset)
        btn = []
        for i in range(0, len(LANGUAGES)-1, 2):
            btn.append([
                InlineKeyboardButton(
                    text=LANGUAGES[i].title(),
                    callback_data=f"fl#{LANGUAGES[i].lower()}#{key}#{offset}"
                ),
                InlineKeyboardButton(
                    text=LANGUAGES[i+1].title(),
                    callback_data=f"fl#{LANGUAGES[i+1].lower()}#{key}#{offset}"
                ),
            ])
        btn.insert(
            0,
            [
                InlineKeyboardButton(
                    text="⇊ ꜱᴇʟᴇᴄᴛ ʟᴀɴɢᴜᴀɢᴇ ⇊", callback_data="ident"
                )
            ],
        )
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="📂 Back to Files 📂", callback_data=f"fl#homepage#{key}#{offset}")])
        await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    except Exception as e:
        LOGGER.error(f"Error In Language Cb Handaler - {e}")
    

@Client.on_callback_query(filters.regex(r"^fl#"))
async def filter_languages_cb_handler(client: Client, query: CallbackQuery):
    try:
        _, lang, key, offset = query.data.split("#")
        offset = int(offset)
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        search = FRESH.get(key)
        search = search.replace("_", " ")
        baal = lang in search
        if baal:
            search = search.replace(lang, "")
        else:
            search = search
        req = query.from_user.id
        chat_id = query.message.chat.id
        message = query.message
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
                    show_alert=True,
                )
        except:
            pass
        if lang != "homepage":
            search = f"{search} {lang}"
        BUTTONS[key] = search
        files, n_offset, total_results = await get_search_results(chat_id, search, offset=offset, filter=True)
        if not files:
            await query.answer("⚡ Sorry, nothing was found!", show_alert=1)
            return
        temp.GETALL[key] = files
        settings = await get_settings(message.chat.id)
        if settings.get('button'):
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{silent_size(file.file_size)}| {extract_tag(file.file_name)} {clean_filename(file.file_name)}", callback_data=f'file#{file.file_id}'
                    ),
                ]
                for file in files
            ]
            btn.insert(0, 
                [
                    InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                        InlineKeyboardButton("🗓️ Season",  callback_data=f"seasons#{key}#0")
                ]
            )
            btn.insert(1, [
                InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}")
            
            ])
        else:
            btn = []
            btn.insert(0, 
                [
                    InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                        InlineKeyboardButton("🗓️ Season",  callback_data=f"seasons#{key}#0")
                ]
            )
            btn.insert(1, [
                InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}")            
            ])
        if n_offset != "":
            try:
                if settings['max_btn']:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )
    
                else:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )
            except KeyError:
                await save_group_settings(query.message.chat.id, 'max_btn', True)
                btn.append(
                    [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                )
        else:
            n_offset = 0
            btn.append(
                [InlineKeyboardButton(text="🚫 That’s everything!",callback_data="pages")]
            )    

        if not settings.get('button'):
            cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
            time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
            remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
            cap = await get_cap(settings, remaining_seconds, files, query, total_results, search, offset)
            try:
                await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
        else:
            try:
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except MessageNotModified:
                pass
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error In Language - {e}")
        
@Client.on_callback_query(filters.regex(r"^seasons#"))
async def season_cb_handler(client: Client, query: CallbackQuery):
    try:
        try:
            if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
                return await query.answer(
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
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
                    text="⇊ ꜱᴇʟᴇᴄᴛ Sᴇᴀsᴏɴ ⇊", callback_data="ident"
                )
            ],
        )
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="📂 Back to Files 📂", callback_data=f"fl#homepage#{key}#{offset}")])
        await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    except Exception as e:
        LOGGER.error(f"Error In Season Cb Handaler - {e}")


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
                    f"⚠️ Hello {query.from_user.first_name}! \n❌ This isn’t your movie request. \n📝 Please send your own request.",
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
        temp.GETALL[key] = files
        settings = await get_settings(message.chat.id)
        if settings.get('button'):
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{silent_size(file.file_size)}| {extract_tag(file.file_name)} {clean_filename(file.file_name)}", callback_data=f'file#{file.file_id}'
                    ),
                ]
                for file in files
            ]
            btn.insert(0, 
                [
                    InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                        InlineKeyboardButton("🗓️ Season",  callback_data=f"seasons#{key}#0")
                ]
            )
            btn.insert(1, [
                InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}")

            ])
        else:
            btn = []
            btn.insert(0, 
                [
                    InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
                        InlineKeyboardButton("🗓️ Season",  callback_data=f"seasons#{key}#0")
                ]
            )
            btn.insert(1, [
                InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}")            
            ])
        if n_offset != "":
            try:
                if settings['max_btn']:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )

                else:
                    btn.append(
                        [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                    )
            except KeyError:
                await save_group_settings(query.message.chat.id, 'max_btn', True)
                btn.append(
                    [InlineKeyboardButton("📄 Page", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="➡️ Next",callback_data=f"next_{req}_{key}_{n_offset}")]
                )
        else:
            n_offset = 0
            btn.append(
                [InlineKeyboardButton(text="🚫 That’s everything!",callback_data="pages")]
            )    

        if not settings.get('button'):
            cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
            time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
            remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
            cap = await get_cap(settings, remaining_seconds, files, query, total_results, search, offset)
            try:
                await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
        else:
            try:
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except MessageNotModified:
                pass
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
        user = query.message.reply_to_message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
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
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)
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
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)
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

    elif query.data.startswith("show_option"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("• ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"unavailable#{from_user}"),
                InlineKeyboardButton("• ᴜᴘʟᴏᴀᴅᴇᴅ •", callback_data=f"uploaded#{from_user}")
             ],[
                InlineKeyboardButton("• ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"already_available#{from_user}")
             ],[
                InlineKeyboardButton("• ɴᴏᴛ ʀᴇʟᴇᴀꜱᴇᴅ •", callback_data=f"Not_Released#{from_user}"),
                InlineKeyboardButton("• Type Correct Spelling •", callback_data=f"Type_Correct_Spelling#{from_user}")
             ],[
                InlineKeyboardButton("• Not Available In The Hindi •", callback_data=f"Not_Available_In_The_Hindi#{from_user}")
             ]]
        btn2 = [[
                 InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Hᴇʀᴇ ᴀʀᴇ ᴛʜᴇ ᴏᴘᴛɪᴏɴs !")
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)
        
    elif query.data.startswith("unavailable"):
        ident, from_user = query.data.split("#")
        btn = [
            [InlineKeyboardButton("• ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"unalert#{from_user}")]
        ]
        btn2 = [
            [InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
            InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")]
        ]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Uɴᴀᴠᴀɪʟᴀʙʟᴇ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=f"<b>✨ Hello! {user.mention},</b>\n\n<u>{content}</u> Hᴀs Bᴇᴇɴ Mᴀʀᴋᴇᴅ Aᴅ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ...💔\n\n#Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️",
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=f"<b>✨ Hello! {user.mention},</b>\n\n<u>{content}</u> Hᴀs Bᴇᴇɴ Mᴀʀᴋᴇᴅ Aᴅ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ...💔\n\n#Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️\n\n<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small></b>",
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
   
    elif query.data.startswith("Not_Released"):
        ident, from_user = query.data.split("#")
        btn = [[InlineKeyboardButton("📌 Not Released 📌", callback_data=f"nralert#{from_user}")]]
        btn2 = [[
            InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
            InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
        ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Nᴏᴛ Rᴇʟᴇᴀꜱᴇᴅ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>✨ Hello! {user.mention}\n\n"
                        f"<code>{content}</code>, Oops! Your request is still pending 🕊️\n\n"
                        f"Stay tuned… #ComingSoon ✨</b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>✨ Hello! {user.mention}</u>\n\n"
                        f"<b><code>{content}</code>, Oops! Your request is still pending 🕊️\n\n"
                        f"Stay tuned… #ComingSoon ✨\n\n"
                        f"<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small></b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)

    elif query.data.startswith("Type_Correct_Spelling"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("✏️ Enter Correct Spelling", callback_data=f"wsalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
                 InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("✅ Spellcheck Enabled!")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>✨ Hello! {user.mention}\n\n"
                        f"❌ Request Declined: <code>{content}</code> \n📝 Reason: Spelling error 😢✍️\n\n"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>✨ Hello! {user.mention}</u>\n\n"
                        f"<b><code>{content}</code>, Wrong spelling detected!😢\n\n"
                        f"⚠️ #Wrong_Spelling\n\n"
                        f"<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small></b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)

    elif query.data.startswith("Not_Available_In_The_Hindi"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton(" Not Available In The Hindi ", callback_data=f"hnalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
                 InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ Iɴ Hɪɴᴅɪ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>✨ Hello! {user.mention}\n\n"
                        f"Yᴏᴜʀ Rᴇǫᴜᴇsᴛ <code>{content}</code> ɪs Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ ɪɴ Hɪɴᴅɪ ʀɪɢʜᴛ ɴᴏᴡ. Sᴏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ɪᴛ\n\n"
                        f"#Hɪɴᴅɪ_ɴᴏᴛ_ᴀᴠᴀɪʟᴀʙʟᴇ ❌</b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>✨ Hello! {user.mention}</u>\n\n"
                        f"<b><code>{content}</code> ɪs Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ ɪɴ Hɪɴᴅɪ ʀɪɢʜᴛ ɴᴏᴡ. Sᴏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ɪᴛ\n\n"
                        f"#Hɪɴᴅɪ_ɴᴏᴛ_ᴀᴠᴀɪʟᴀʙʟᴇ ❌\n\n"
                        f"<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small></b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)

    elif query.data.startswith("uploaded"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("• ᴜᴘʟᴏᴀᴅᴇᴅ •", callback_data=f"upalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
                 InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
               ],[
                 InlineKeyboardButton("Search Here 🔎", url=GRP_LNK)
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Uᴘʟᴏᴀᴅᴇᴅ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>✨ Hello! {user.mention},\n\n"
                        f"<u>{content}</u> ✅ Your request has been uploaded by our moderators!\n"
                        f"💡 Kindly look in the group first.</b>\n\n"
                        f"#Uploaded ✅"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>{content}</u>\n\n"
                        f"<b>✨ Hello! {user.mention}, ✅ Your request has been uploaded by our moderators!"
                        f"💡 Kindly look in the group first.</b>\n\n"
                        f"#Uploaded ✅\n\n"
                        f"<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)

    elif query.data.startswith("already_available"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("• ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"alalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
                 InlineKeyboardButton("📊 View Status", url=f"{query.message.link}")
               ],[
                 InlineKeyboardButton("Search Here 🔎", url=GRP_LNK)
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Set successfully to Available!")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>✨ Hello! {user.mention},\n\n"
                        f"<u>{content}</u> ✅ This request is already in our bot’s database!\n"
                        f"💡 Kindly look in the group first.</b>\n\n"
                        f"🚀 Available Now!"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<b>✨ Hello! {user.mention},\n\n"
                        f"<u>{content}</u> ✅ This request is already in our bot’s database!\n"
                        f"💡 Kindly look in the group first.</b>\n\n"
                        f"🚀 Available Now!\n"
                        f"<small>🚫 Blocked? Unblock the bot to get messages! 🔓</small></i>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("❌ You don’t have enough rights to do this!", show_alert=True)
            
    
    elif query.data.startswith("alalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, 🚀 Already uploaded – request exists!",
                show_alert=True
            )
        else:
            await query.answer("❌ Insufficient rights to perform this action!", show_alert=True)

    elif query.data.startswith("upalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, 🔼 Your request has been uploaded!",
                show_alert=True
            )
        else:
            await query.answer("❌ Insufficient rights to perform this action!", show_alert=True)

    elif query.data.startswith("unalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, Oops! This request isn’t available right now.⚠️",
                show_alert=True
            )
        else:
            await query.answer("❌ Insufficient rights to perform this action!", show_alert=True)

    elif query.data.startswith("hnalert"):
        ident, from_user = query.data.split("#")  # Hindi Not Available
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, ❌ Not available",
                show_alert=True
            )
        else:
            await query.answer("🚫 Permission denied – must be original requester", show_alert=True)

    elif query.data.startswith("nralert"):
        ident, from_user = query.data.split("#")  # Not Released
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, 🚫 Not released yet – stay tuned!",
                show_alert=True
            )
        else:
            await query.answer("❌ Action denied – youre not the original requester!", show_alert=True)

    elif query.data.startswith("wsalert"):
        ident, from_user = query.data.split("#")  # Wrong Spelling
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"✨ Hello! {user.first_name}, ❗ Request rejected – check your spelling!",
                show_alert=True
            )
        else:
            await query.answer("❌ You don’t have permission to view this!", show_alert=True)

    
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
                chat_id=BIN_CHANNEL,
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

    elif query.data.startswith("verification_setgs"):
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)

        settings = await get_settings(int(grp_id))
        verify_status = settings.get('is_verify', IS_VERIFY)
        btn = [[
            InlineKeyboardButton(f'ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ: {"ᴏɴ" if verify_status else "ᴏꜰꜰ"}', callback_data=f'toggleverify#is_verify#{verify_status}#{grp_id}'),
	],[
            InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ', callback_data=f'changeshortner#{grp_id}'),
            InlineKeyboardButton('ᴛɪᴍᴇ', callback_data=f'changetime#{grp_id}')
	],[
            InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ', callback_data=f'changetutorial#{grp_id}')
        ],[
            InlineKeyboardButton('⬅️ Back', callback_data=f'grp_pm#{grp_id}')
	]]    
        await query.message.edit("<b>🛠️ Advanced Settings Mode\n\nCustomize shortener values & verification interval here\n👇 Select an option below</b>", reply_markup=InlineKeyboardMarkup(btn))
	    

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
        await query.message.edit("<b>🛠️ Advanced Settings Mode\n\nʏCustomize your Log Channel value here\n👇 Select an option below<\b>", reply_markup=InlineKeyboardMarkup(btn))

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
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
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
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
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
                InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
            ]	
            await query.message.edit("<b>🎨 Customize caption & change values</b>", reply_markup=InlineKeyboardMarkup(btn))
            await m.delete()
            return
        await m.delete()	
        await save_group_settings(int(grp_id), f'caption', caption_msg.text)
        await client.send_message(LOG_API_CHANNEL, f"#Set_Caption\n\nGroup Title : {title}\n\nɢʀᴏᴜᴘ ɪᴅ: {grp_id}\nɪɴᴠɪᴛᴇ ʟɪɴᴋ : {invite_link}\n\nᴜᴘᴅᴀᴛᴇᴅ ʙʏ : {query.from_user.username}")	    
        btn = [            
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
        ]    
        await query.message.reply(f"<b>✅ Custom caption values updated!\n\n🎨 Caption Here: <code>{caption_msg.text}</code></b>", reply_markup=InlineKeyboardMarkup(btn))

	
    elif query.data.startswith("toggleverify"):
        _, set_type, status, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)    
        new_status = not (status == "True")
        await save_group_settings(int(grp_id), set_type, new_status)
        settings = await get_settings(int(grp_id))
        verify_status = settings.get('is_verify', IS_VERIFY)
        btn = [[
            InlineKeyboardButton(f'ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ: {"ᴏɴ" if verify_status else "ᴏꜰꜰ"}', callback_data=f'toggleverify#is_verify#{verify_status}#{grp_id}'),
	],[
            InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ', callback_data=f'changeshortner#{grp_id}'),
            InlineKeyboardButton('ᴛɪᴍᴇ', callback_data=f'changetime#{grp_id}')
	],[
            InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ', callback_data=f'changetutorial#{grp_id}')
        ],[
            InlineKeyboardButton('⬅️ Back', callback_data=f'grp_pm#{grp_id}')
	]]    
        await query.message.edit("<b>🛠️ Advanced Settings Mode\n\nCustomize shortener values & verification interval here\n👇 Select an option below</b>", reply_markup=InlineKeyboardMarkup(btn))


    elif query.data.startswith("changeshortner"):
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        btn = [
            [
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 1', callback_data=f'set_verify1#{grp_id}'),
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 2', callback_data=f'set_verify2#{grp_id}')
            ],
            [InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 3', callback_data=f'set_verify3#{grp_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
		]
        await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ꜱʜᴏʀᴛɴᴇʀ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("set_verify"):
        shortner_num = query.data.split("#")[0][-1]
        grp_id = query.data.split("#")[1]
        user_id = query.from_user.id if query.from_user else None
        silentx = await client.get_chat(int(grp_id))
        invite_link = await client.export_chat_invite_link(grp_id)
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        settings = await get_settings(int(grp_id))
        suffix = "" if shortner_num == "1" else f"_{'two' if shortner_num == '2' else 'three'}"
        current_url = settings.get(f'shortner{suffix}', "⚡ No value set – using default!")
        current_api = settings.get(f'api{suffix}', "⚡ No value set – using default!")    
        await query.message.edit(f"<b>📌 ᴅᴇᴛᴀɪʟꜱ ᴏꜰ ꜱʜᴏʀᴛɴᴇʀ {shortner_num}:\nᴡᴇʙꜱɪᴛᴇ: <code>{current_url}</code>\nᴀᴘɪ: <code>{current_api}</code></b>")
        m = await query.message.reply("<b>ꜱᴇɴᴅ ɴᴇᴡ ꜱʜᴏʀᴛɴᴇʀ ᴡᴇʙꜱɪᴛᴇ ᴏʀ ᴜꜱᴇ /cancel ᴛᴏ ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇꜱꜱ</b>") 
        url_msg = await client.listen(chat_id=query.message.chat.id, user_id=user_id)
        if url_msg.text == "/cancel":
            btn = [[
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 1', callback_data=f'set_verify1#{grp_id}'),
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 2', callback_data=f'set_verify2#{grp_id}')
            ],
            [InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 3', callback_data=f'set_verify3#{grp_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
            ]	
            await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ꜱʜᴏʀᴛɴᴇʀ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))
            await m.delete()
            return
        await m.delete()
        n = await query.message.reply("<b>ɴᴏᴡ ꜱᴇɴᴅ ꜱʜᴏʀᴛɴᴇʀ ᴀᴘɪ ᴏʀ ᴜꜱᴇ /cancel ᴛᴏ ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇꜱꜱ</b>")
        key_msg = await client.listen(chat_id=query.message.chat.id, user_id=user_id)
        if key_msg.text == "/cancel":
            btn = [[
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 1', callback_data=f'set_verify1#{grp_id}'),
                InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 2', callback_data=f'set_verify2#{grp_id}')
            ],
            [InlineKeyboardButton('ꜱʜᴏʀᴛɴᴇʀ 3', callback_data=f'set_verify3#{grp_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
            ]	
            await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ꜱʜᴏʀᴛɴᴇʀ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))
            await n.delete()
            return
        await n.delete()    		
        await save_group_settings(int(grp_id), f'shortner{suffix}', url_msg.text)
        await save_group_settings(int(grp_id), f'api{suffix}', key_msg.text)
        log_message = f"#New_Shortner_Set\n\n ꜱʜᴏʀᴛɴᴇʀ ɴᴏ - {shortner_num}\nɢʀᴏᴜᴘ ʟɪɴᴋ - `{invite_link}`\n\nɢʀᴏᴜᴘ ɪᴅ : `{grp_id}`\nᴀᴅᴅᴇᴅ ʙʏ - `{user_id}`\nꜱʜᴏʀᴛɴᴇʀ ꜱɪᴛᴇ - {url_msg.text}\nꜱʜᴏʀᴛɴᴇʀ ᴀᴘɪ - `{key_msg.text}`"
        await client.send_message(LOG_API_CHANNEL, log_message, disable_web_page_preview=True)
        next_shortner = int(shortner_num) + 1 if shortner_num in ["1", "2"] else None
        btn = [
            [InlineKeyboardButton(f'ꜱʜᴏʀᴛɴᴇʀ {next_shortner}', callback_data=f'set_verify{next_shortner}#{grp_id}')] if next_shortner else [],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
        ]    
        await query.message.reply(f"<b>ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴜᴘᴅᴀᴛᴇᴅ ꜱʜᴏʀᴛɴᴇʀ {shortner_num} ᴠᴀʟᴜᴇꜱ ✅\n\nᴡᴇʙꜱɪᴛᴇ: <code>{url_msg.text}</code>\nᴀᴘɪ: <code>{key_msg.text}</code></b>", reply_markup=InlineKeyboardMarkup(btn))

    
    elif query.data.startswith("changetime"):
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        btn = [
            [
                InlineKeyboardButton('2ɴᴅ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ', callback_data=f'set_time2#{grp_id}'),
	    ],[
                InlineKeyboardButton('3ʀᴅ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ', callback_data=f'set_time3#{grp_id}')
            ],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
		]
        await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ ɢᴀᴘ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("set_time"):
        time_num = query.data.split("#")[0][-1]
        grp_id = query.data.split("#")[1]
        user_id = query.from_user.id if query.from_user else None
        silentx = await client.get_chat(int(grp_id))
        invite_link = await client.export_chat_invite_link(grp_id)
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        settings = await get_settings(int(grp_id))
        suffix = "" if time_num == "2" else "third_" if time_num == "3" else ""
        current_time = settings.get(f'{suffix}verify_time', 'Not set')
        await query.message.edit(f"<b>📌 ᴅᴇᴛᴀɪʟꜱ ᴏꜰ {time_num} ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ:\n\nᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ: {current_time}</b>")
        m = await query.message.reply("<b>ꜱᴇɴᴅ ɴᴇᴡ ᴛᴜᴛᴏʀɪᴀʟ ᴜʀʟ ᴏʀ ᴜꜱᴇ /cancel ᴛᴏ ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇꜱꜱ.</b>")        
        while True:
            time_msg = await client.listen(chat_id=query.message.chat.id, user_id=user_id)
            if time_msg.text == "/cancel":
                await m.delete()
                btn = [
                    [InlineKeyboardButton('2ɴᴅ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ', callback_data=f'set_time2#{grp_id}')],
                    [InlineKeyboardButton('3ʀᴅ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ', callback_data=f'set_time3#{grp_id}')],
                    [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
		]   
                await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))
                return        
            if time_msg.text.isdigit() and int(time_msg.text) > 0:
                break
            else:
                await query.message.reply("<b>ɪɴᴠᴀʟɪᴅ ᴛɪᴍᴇ! ᴍᴜꜱᴛ ʙᴇ ᴀ ᴘᴏꜱɪᴛɪᴠᴇ ɴᴜᴍʙᴇʀ (ᴇxᴀᴍᴘʟᴇ: 60)</b>")
        await m.delete()
        await save_group_settings(int(grp_id), f'{suffix}verify_time', time_msg.text)
        log_message = f"#New_Time_Set\n\n ᴛɪᴍᴇ ɴᴏ - {time_num}\nɢʀᴏᴜᴘ ʟɪɴᴋ - `{invite_link}`\n\nɢʀᴏᴜᴘ ɪᴅ : `{grp_id}`\nᴀᴅᴅᴇᴅ ʙʏ - `{user_id}`\nᴛɪᴍᴇ - {time_msg.text}"
        await client.send_message(LOG_API_CHANNEL, log_message, disable_web_page_preview=True)
        next_time = int(time_num) + 1 if time_num in ["2"] else None
        btn = [
            [InlineKeyboardButton(f'{next_time} ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ', callback_data=f'set_time{next_time}#{grp_id}')] if next_time else [],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
        ]    
        await query.message.reply(f"<b>{time_num} ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ ᴜᴘᴅᴀᴛᴇ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ✅\n\nᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ: {time_msg.text}</b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("changetutorial"):
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        btn = [
            [
                InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 1', callback_data=f'set_tutorial1#{grp_id}'),
                InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 2', callback_data=f'set_tutorial2#{grp_id}')
            ],
            [InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 3', callback_data=f'set_tutorial3#{grp_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
		]
        await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ᴛᴜᴛᴏʀɪᴀʟ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("set_tutorial"):
        tutorial_num = query.data.split("#")[0][-1]
        grp_id = query.data.split("#")[1]
        user_id = query.from_user.id if query.from_user else None
        silentx = await client.get_chat(int(grp_id))
        invite_link = await client.export_chat_invite_link(grp_id)
        if not await is_check_admin(client, int(grp_id), user_id):
            return await query.answer("<b>💡 You must be an admin to use this</b>", show_alert=True)
        settings = await get_settings(int(grp_id))
        suffix = "" if tutorial_num == "1" else f"_{'2' if tutorial_num == '2' else '3'}"
        tutorial_url = settings.get(f'tutorial{suffix}', "⚡ No value set – using default!")    
        await query.message.edit(f"<b>📌 ᴅᴇᴛᴀɪʟꜱ ᴏꜰ ᴛᴜᴛᴏʀɪᴀʟ {tutorial_num}:\n\nᴛᴜᴛᴏʀɪᴀʟ ᴜʀʟ: {tutorial_url}.</b>")
        m = await query.message.reply("<b>ꜱᴇɴᴅ ɴᴇᴡ ᴛᴜᴛᴏʀɪᴀʟ ᴜʀʟ ᴏʀ ᴜꜱᴇ /cancel ᴛᴏ ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇꜱꜱ</b>") 
        tutorial_msg = await client.listen(chat_id=query.message.chat.id, user_id=user_id)
        if tutorial_msg.text == "/cancel":
            btn = [[
                InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 1', callback_data=f'set_tutorial1#{grp_id}'),
                InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 2', callback_data=f'set_tutorial2#{grp_id}')
            ],
            [InlineKeyboardButton('ᴛᴜᴛᴏʀɪᴀʟ 3', callback_data=f'set_tutorial3#{grp_id}')],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
            ]	
            await query.message.edit("<b>ᴄʜᴏᴏꜱᴇ ᴛᴜᴛᴏʀɪᴀʟ ᴀɴᴅ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴠᴀʟᴜᴇꜱ ᴀꜱ ʏᴏᴜ ᴡᴀɴᴛ ✅</b>", reply_markup=InlineKeyboardMarkup(btn))
            await m.delete()
            return
        await m.delete()	
        await save_group_settings(int(grp_id), f'tutorial{suffix}', tutorial_msg.text)
        log_message = f"#New_Tutorial_Set\n\n ᴛᴜᴛᴏʀɪᴀʟ ɴᴏ - {tutorial_num}\nɢʀᴏᴜᴘ ʟɪɴᴋ - `{invite_link}`\n\nɢʀᴏᴜᴘ ɪᴅ : `{grp_id}`\nᴀᴅᴅᴇᴅ ʙʏ - `{user_id}`\nᴛᴜᴛᴏʀɪᴀʟ - {tutorial_msg.text}"
        await client.send_message(LOG_API_CHANNEL, log_message, disable_web_page_preview=True)
        next_tutorial = int(tutorial_num) + 1 if tutorial_num in ["1", "2"] else None
        btn = [
            [InlineKeyboardButton(f'ᴛᴜᴛᴏʀɪᴀʟ {next_tutorial}', callback_data=f'set_tutorial{next_tutorial}#{grp_id}')] if next_tutorial else [],
            [InlineKeyboardButton('⬅️ Back', callback_data=f'verification_setgs#{grp_id}')]
        ]    
        await query.message.reply(f"<b>ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴜᴘᴅᴀᴛᴇᴅ ᴛᴜᴛᴏʀɪᴀʟ {tutorial_num} ᴠᴀʟᴜᴇꜱ ✅\n\nᴛᴜᴛᴏʀɪᴀʟ ᴜʀʟ: {tutorial_msg.text}</b>", reply_markup=InlineKeyboardMarkup(btn))
	    
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

    
class ContentType(Enum):
    KDRAMA = "k-drama"
    MOVIE = "movie"
    VARIETY_SHOW = "variety"
    DOCUMENTARY = "documentary"

@dataclass
class SearchResult:
    file_id: str
    file_name: str
    file_size: int
    quality: str = ""
    language: str = ""
    episode: str = ""
    season: str = ""
    content_type: ContentType = ContentType.KDRAMA

class KDramaBot:
    def __init__(self):
        self.search_cache = {}
        self.user_preferences = {}
        self.trending_cache = {}
        
    async def auto_filter(self, client, msg, spoll=False):
        """Enhanced auto filter with K-Drama specific features"""
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        
        if not spoll:
            message = msg
            if message.text.startswith("/"): 
                return
                
            # Enhanced regex to handle K-Drama specific terms
            if re.findall(r"((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
                return
                
            if len(message.text) < 100:
                # Enhanced search processing for K-Drama content
                search = await self.process_kdrama_search(message.text)
                
                # Show typing indicator for better UX
                await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
                
                m = await message.reply_text(
                    f'<b>🔍 Hey {message.from_user.mention}!\n'
                    f'Searching K-Drama: <code>{search}</code>\n'
                    f'⏱️ Please wait...</b>', 
                    reply_to_message_id=message.id
                )
                
                # Enhanced search with content type detection
                files, offset, total_results = await self.enhanced_search_results(
                    message.chat.id, search, offset=0, filter=True
                )
                
                settings = await get_settings(message.chat.id)
                
                if not files:
                    if settings.get("spell_check", True):
                        await self.handle_no_results(client, message, search, m)
                        return
        else:
            message = msg.message.reply_to_message
            search, files, offset, total_results = spoll
            m = await message.reply_text(
                f'<b>🎬 Searching: <code>{search}</code></b>', 
                reply_to_message_id=message.id
            )
            settings = await get_settings(message.chat.id)
            await msg.message.delete()

        # Generate enhanced results with K-Drama specific formatting
        await self.display_results(client, message, m, search, files, offset, total_results, settings)

    async def process_kdrama_search(self, text: str) -> str:
        """Enhanced search processing for K-Drama content"""
        search = await replace_words(text)
        search = search.lower()
        
        # K-Drama specific replacements
        kdrama_replacements = {
            "kdrama": "korean drama",
            "k-drama": "korean drama",
            "k drama": "korean drama",
            "ep": "episode",
            "eps": "episodes",
            "sub": "subtitle",
            "subs": "subtitles",
            "eng sub": "english subtitle",
            "hindi dub": "hindi dubbed",
            "tamil dub": "tamil dubbed"
        }
        
        for old, new in kdrama_replacements.items():
            search = search.replace(old, new)
            
        search = search.replace("-", " ")
        search = search.replace(":", "")
        search = re.sub(r'\s+', ' ', search).strip()
        
        return search

    async def enhanced_search_results(self, chat_id: int, query: str, offset: int = 0, filter: bool = True) -> Tuple[List[SearchResult], str, int]:
        """Enhanced search with content type detection and quality filtering"""
        # Get basic search results
        files, offset, total_results = await get_search_results(chat_id, query, offset, filter)
        
        # Convert to enhanced SearchResult objects
        enhanced_files = []
        for file in files:
            result = SearchResult(
                file_id=file.file_id,
                file_name=file.file_name,
                file_size=file.file_size,
                quality=self.extract_quality(file.file_name),
                language=self.extract_language(file.file_name),
                episode=self.extract_episode(file.file_name),
                season=self.extract_season(file.file_name),
                content_type=self.detect_content_type(file.file_name)
            )
            enhanced_files.append(result)
            
        return enhanced_files, offset, total_results

    def extract_quality(self, filename: str) -> str:
        """Extract video quality from filename"""
        quality_patterns = {
            r'(?i)(4k|2160p)': '4K',
            r'(?i)(1080p|fhd)': '1080p',
            r'(?i)(720p|hd)': '720p',
            r'(?i)(480p|sd)': '480p',
            r'(?i)(360p)': '360p'
        }
        
        for pattern, quality in quality_patterns.items():
            if re.search(pattern, filename):
                return quality
        return "HD"

    def extract_language(self, filename: str) -> str:
        """Extract language from filename"""
        lang_patterns = {
            r'(?i)(eng|english)': '🇺🇸 English',
            r'(?i)(kor|korean)': '🇰🇷 Korean',
            r'(?i)(hin|hindi)': '🇮🇳 Hindi',
            r'(?i)(tam|tamil)': '🇮🇳 Tamil',
            r'(?i)(tel|telugu)': '🇮🇳 Telugu',
            r'(?i)(mal|malayalam)': '🇮🇳 Malayalam'
        }
        
        for pattern, lang in lang_patterns.items():
            if re.search(pattern, filename):
                return lang
        return "🇰🇷 Korean"

    def extract_episode(self, filename: str) -> str:
        """Extract episode number from filename"""
        ep_patterns = [
            r'(?i)ep?\.?\s*(\d+)',
            r'(?i)episode\s*(\d+)',
            r'(?i)e(\d+)',
            r'(?i)\s(\d+)\s'
        ]
        
        for pattern in ep_patterns:
            match = re.search(pattern, filename)
            if match:
                return f"EP {match.group(1)}"
        return ""

    def extract_season(self, filename: str) -> str:
        """Extract season from filename"""
        season_patterns = [
            r'(?i)s(\d+)',
            r'(?i)season\s*(\d+)'
        ]
        
        for pattern in season_patterns:
            match = re.search(pattern, filename)
            if match:
                return f"S{match.group(1)}"
        return ""

    def detect_content_type(self, filename: str) -> ContentType:
        """Detect content type from filename"""
        filename_lower = filename.lower()
        
        if any(keyword in filename_lower for keyword in ['variety', 'show', 'running man', 'knowing bros']):
            return ContentType.VARIETY_SHOW
        elif any(keyword in filename_lower for keyword in ['documentary', 'docu']):
            return ContentType.DOCUMENTARY
        elif any(keyword in filename_lower for keyword in ['movie', 'film']):
            return ContentType.MOVIE
        else:
            return ContentType.KDRAMA

    async def generate_enhanced_buttons(self, files: List[SearchResult], key: str, settings: dict) -> List[List[InlineKeyboardButton]]:
        """Generate enhanced buttons with K-Drama specific features"""
        btn = []
        
        if settings.get('button'):
            # File buttons with enhanced formatting
            for file in files:
                file_info = self.format_file_info(file)
                btn.append([
                    InlineKeyboardButton(
                        text=file_info,
                        callback_data=f'file#{file.file_id}'
                    )
                ])
        
        # Enhanced filter buttons
        filter_buttons = [
            InlineKeyboardButton("🎬 Quality", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("🌐 Language", callback_data=f"languages#{key}#0"),
            InlineKeyboardButton("📺 Episode", callback_data=f"episodes#{key}#0")
        ]
        btn.insert(0, filter_buttons)
        
        # Action buttons
        action_buttons = [
            InlineKeyboardButton("📥 Send All", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("⭐ Add to Watchlist", callback_data=f"watchlist#{key}")
        ]
        btn.insert(1, action_buttons)
        
        # Quick access buttons
        quick_buttons = [
            InlineKeyboardButton("🔥 Trending", callback_data="trending_kdramas"),
            InlineKeyboardButton("🎲 Random", callback_data="random_kdrama")
        ]
        btn.insert(2, quick_buttons)
        
        return btn

    def format_file_info(self, file: SearchResult) -> str:
        """Format file information for button display"""
        size = silent_size(file.file_size)
        name = clean_filename(file.file_name)
        
        info_parts = [size]
        if file.quality:
            info_parts.append(file.quality)
        if file.episode:
            info_parts.append(file.episode)
        if file.language and file.language != "🇰🇷 Korean":
            info_parts.append(file.language.split()[-1])
            
        info = " | ".join(info_parts)
        
        # Add content type emoji
        type_emoji = {
            ContentType.KDRAMA: "🎭",
            ContentType.MOVIE: "🎬", 
            ContentType.VARIETY_SHOW: "🎪",
            ContentType.DOCUMENTARY: "📚"
        }
        
        return f"{type_emoji.get(file.content_type, '🎭')} {info} | {name}"

    async def handle_no_results(self, client, message, search: str, m):
        """Enhanced no results handler with K-Drama specific suggestions"""
        # Try AI spell check first
        ai_sts = await m.edit('🤖 Checking spelling with AI...')
        corrected = await self.ai_spell_check_kdrama(message.chat.id, search)
        
        if corrected:
            await ai_sts.edit(f'<b>✅ AI Suggested: <code>{corrected}</code>\n🔍 Searching now...</b>')
            await asyncio.sleep(2)
            message.text = corrected
            await ai_sts.delete()
            return await self.auto_filter(client, message)
            
        await ai_sts.delete()
        
        # Show K-Drama specific suggestions
        await self.show_kdrama_suggestions(client, message)

    async def ai_spell_check_kdrama(self, chat_id: int, wrong_name: str) -> Optional[str]:
        """AI spell check specifically for K-Drama titles"""
        try:
            # Search K-Drama databases
            kdrama_results = await self.search_kdrama_database(wrong_name)
            
            if not kdrama_results:
                return None
                
            # Find closest match
            closest_match = process.extractOne(wrong_name, kdrama_results)
            
            if closest_match and closest_match[1] > 75:  # 75% similarity threshold
                # Verify if files exist for this title
                files, _, _ = await get_search_results(chat_id, closest_match[0])
                if files:
                    return closest_match[0]
                    
        except Exception as e:
            LOGGER.error(f"AI spell check error: {e}")
            
        return None

    async def search_kdrama_database(self, query: str) -> List[str]:
        """Search K-Drama database for similar titles"""
        # This would integrate with K-Drama APIs like TMDB, MyDramaList, etc.
        # For now, return a mock list
        popular_kdramas = [
            "Squid Game", "Crash Landing on You", "Goblin", "Descendants of the Sun",
            "Hotel Del Luna", "It's Okay to Not Be Okay", "Start-Up", "True Beauty",
            "Vincenzo", "Business Proposal", "Hometown's Embrace", "Twenty Five Twenty One",
            "Our Beloved Summer", "Hometown Cha-Cha-Cha", "Red Sleeve", "Snowdrop"
        ]
        
        # Simple fuzzy matching for demo
        matches = process.extract(query, popular_kdramas, limit=10)
        return [match[0] for match in matches if match[1] > 50]

    async def show_kdrama_suggestions(self, client, message):
        """Show K-Drama suggestions when no results found"""
        search = message.text
        
        try:
            # Get trending K-Dramas
            trending = await self.get_trending_kdramas()
            
            if not trending:
                # Fallback to Google search
                google_url = f"https://www.google.com/search?q={search.replace(' ', '+')}+korean+drama"
                button = [[
                    InlineKeyboardButton("🔍 Search on Google", url=google_url),
                    InlineKeyboardButton("📺 Browse K-Dramas", callback_data="browse_kdramas")
                ]]
                
                k = await message.reply_text(
                    text=f"<b>😔 Sorry, couldn't find '{search}'\n\n"
                         f"🔍 Try searching with different keywords or check spelling</b>",
                    reply_markup=InlineKeyboardMarkup(button)
                )
            else:
                # Show trending suggestions
                buttons = []
                for drama in trending[:8]:  # Show top 8
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"🎭 {drama['title']}", 
                            callback_data=f"search#{drama['title']}"
                        )
                    ])
                
                buttons.append([
                    InlineKeyboardButton("🔍 Google Search", 
                                       url=f"https://www.google.com/search?q={search.replace(' ', '+')}+korean+drama"),
                    InlineKeyboardButton("🚫 Close", callback_data='close_data')
                ])
                
                k = await message.reply_text(
                    text=f"<b>😔 Couldn't find '{search}'\n\n"
                         f"🔥 Try these trending K-Dramas instead:</b>",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    reply_to_message_id=message.id
                )
            
            # Auto-delete after 2 minutes
            await asyncio.sleep(120)
            await k.delete()
            try:
                await message.delete()
            except:
                pass
                
        except Exception as e:
            LOGGER.error(f"Error showing suggestions: {e}")

    async def get_trending_kdramas(self) -> List[Dict]:
        """Get trending K-Dramas from external API"""
        # Cache trending data for 1 hour
        if hasattr(self, 'trending_cache') and self.trending_cache.get('expires', 0) > datetime.now().timestamp():
            return self.trending_cache.get('data', [])
            
        try:
            # This would integrate with TMDB or MyDramaList API
            # For demo purposes, return mock data
            trending = [
                {"title": "Business Proposal", "year": "2022", "rating": "8.5"},
                {"title": "Twenty Five Twenty One", "year": "2022", "rating": "8.7"},
                {"title": "Hometown Cha-Cha-Cha", "year": "2021", "rating": "8.9"},
                {"title": "Squid Game", "year": "2021", "rating": "8.0"},
                {"title": "Vincenzo", "year": "2021", "rating": "8.8"},
                {"title": "It's Okay to Not Be Okay", "year": "2020", "rating": "8.6"},
                {"title": "Crash Landing on You", "year": "2019", "rating": "8.7"},
                {"title": "Goblin", "year": "2016", "rating": "8.9"}
            ]
            
            # Cache for 1 hour
            self.trending_cache = {
                'data': trending,
                'expires': datetime.now().timestamp() + 3600
            }
            
            return trending
            
        except Exception as e:
            LOGGER.error(f"Error fetching trending K-Dramas: {e}")
            return []

    async def display_results(self, client, message, m, search: str, files: List[SearchResult], 
                            offset: str, total_results: int, settings: dict):
        """Enhanced result display with K-Drama specific formatting"""
        
        key = f"{message.chat.id}-{message.id}"
        FRESH[key] = search
        temp.GETALL[key] = files
        temp.SHORT[message.from_user.id] = message.chat.id
        
        # Generate enhanced buttons
        btn = await self.generate_enhanced_buttons(files, key, settings)
        
        # Pagination logic
        if offset != "":
            req = message.from_user.id if message.from_user else 0
            try:
                max_btn = 10 if settings.get('max_btn', True) else int(MAX_B_TN)
                total_pages = math.ceil(int(total_results) / max_btn)
                btn.append([
                    InlineKeyboardButton("◀️ Page", callback_data="pages"),
                    InlineKeyboardButton(f"1/{total_pages}", callback_data="pages"),
                    InlineKeyboardButton("Next ▶️", callback_data=f"next_{req}_{key}_{offset}")
                ])
            except:
                btn.append([
                    InlineKeyboardButton("◀️ Page", callback_data="pages"),
                    InlineKeyboardButton("1/1", callback_data="pages"),
                    InlineKeyboardButton("Next ▶️", callback_data=f"next_{req}_{key}_{offset}")
                ])
        else:
            btn.append([
                InlineKeyboardButton("📄 No more pages available", callback_data="pages")
            ])

        # Get K-Drama info instead of just IMDB
        kdrama_info = await self.get_kdrama_info(search, files[0].file_name if files else "") if settings.get("imdb", True) else None
        
        # Generate caption
        cap = await self.generate_result_caption(message, search, files, kdrama_info, settings)
        
        # Send result
        await self.send_result_message(m, cap, btn, kdrama_info, message, settings)

    async def get_kdrama_info(self, search: str, filename: str) -> Optional[Dict]:
        """Get K-Drama information from multiple sources"""
        try:
            # First try to get IMDB info
            imdb_info = await get_poster(search, file=filename)
            
            if imdb_info:
                # Enhance with K-Drama specific info
                imdb_info['content_type'] = 'K-Drama'
                
                # Add K-Drama specific fields if available
                if 'korean' in search.lower() or 'kdrama' in search.lower():
                    imdb_info['korean_title'] = await self.get_korean_title(search)
                    imdb_info['episodes'] = await self.get_episode_count(search)
                    
            return imdb_info
            
        except Exception as e:
            LOGGER.error(f"Error fetching K-Drama info: {e}")
            return None

    async def get_korean_title(self, title: str) -> str:
        """Get Korean title for K-Drama"""
        # This would integrate with K-Drama APIs
        # For now, return mock data
        korean_titles = {
            "squid game": "오징어 게임",
            "crash landing on you": "사랑의 불시착",
            "goblin": "도깨비",
            "hotel del luna": "호텔 델루나"
        }
        return korean_titles.get(title.lower(), "")

    async def get_episode_count(self, title: str) -> str:
        """Get episode count for K-Drama"""
        # This would integrate with K-Drama databases
        return "16 episodes"  # Default

    async def generate_result_caption(self, message, search: str, files: List[SearchResult], 
                                    kdrama_info: Optional[Dict], settings: dict) -> str:
        """Generate enhanced result caption"""
        
        if kdrama_info:
            # Use K-Drama template
            template = script.KDRAMA_TEMPLATE_TXT if hasattr(script, 'KDRAMA_TEMPLATE_TXT') else script.IMDB_TEMPLATE_TXT
            
            cap = template.format(
                query=search,
                mention=message.from_user.mention,
                **kdrama_info,
                **locals()
            )
            
            temp.IMDB_CAP[message.from_user.id] = cap
            
            if not settings.get('button'):
                # Add file list to caption
                for file_num, file in enumerate(files, start=1):
                    file_info = self.format_file_info(file)
                    cap += f"\n\n<b>{file_num}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>{file_info}</a></b>"
        else:
            # Basic caption
            content_stats = self.analyze_content_types(files)
            stats_text = " | ".join([f"{count} {type.value.title()}s" for type, count in content_stats.items() if count > 0])
            
            if settings.get('button'):
                cap = (f"<b>🎭 Hey {message.from_user.mention}!\n\n"
                      f"📂 Found <code>{len(files)}</code> results for: <code>{search}</code>\n"
                      f"📊 Content: {stats_text}\n\n"
                      f"🎬 Click buttons below to filter or download!</b>")
            else:
                cap = (f"<b>🎭 Hey {message.from_user.mention}!\n\n"
                      f"📂 Found <code>{len(files)}</code> results for: <code>{search}</code>\n"
                      f"📊 Content: {stats_text}\n\n</b>")
                      
                for file_num, file in enumerate(files, start=1):
                    file_info = self.format_file_info(file)
                    cap += f"<b>{file_num}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>{file_info}</a></b>\n\n"
                    
        return cap

    def analyze_content_types(self, files: List[SearchResult]) -> Dict[ContentType, int]:
        """Analyze content types in search results"""
        type_counts = {content_type: 0 for content_type in ContentType}
        
        for file in files:
            type_counts[file.content_type] += 1
            
        return type_counts

    async def send_result_message(self, m, cap: str, btn: List[List[InlineKeyboardButton]], 
                                kdrama_info: Optional[Dict], message, settings: dict):
        """Send the result message with appropriate media"""
        
        try:
            if kdrama_info and kdrama_info.get('poster'):
                try:
                    # Try to send with poster
                    result_msg = await m.edit_photo(
                        photo=kdrama_info['poster'],
                        caption=cap,
                        reply_markup=InlineKeyboardMarkup(btn),
                        parse_mode=enums.ParseMode.HTML
                    )
                except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
                    # Try alternative poster URL
                    poster_url = kdrama_info['poster'].replace('.jpg', "._V1_UX360.jpg")
                    result_msg = await m.edit_photo(
                        photo=poster_url,
                        caption=cap,
                        reply_markup=InlineKeyboardMarkup(btn),
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception as e:
                    LOGGER.error(f"Error sending photo: {e}")
                    # Fallback to text
                    result_msg = await m.edit_text(
                        text=cap,
                        reply_markup=InlineKeyboardMarkup(btn),
                        parse_mode=enums.ParseMode.HTML
                    )
            else:
                # Send text message
                result_msg = await m.edit_text(
                    text=cap,
                    reply_markup=InlineKeyboardMarkup(btn),
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.HTML
                )
            
            # Auto-delete if enabled
            if settings.get('auto_delete', False):
                await asyncio.sleep(DELETE_TIME)
                await result_msg.delete()
                try:
                    await message.delete()
                except:
                    pass
                    
        except Exception as e:
            LOGGER.error(f"Error sending result message: {e}")

# Initialize the enhanced bot
kdrama_bot = KDramaBot()

# Main function to replace the original
async def auto_filter(client, msg, spoll=False):
    """Main auto filter function - enhanced version"""
    return await kdrama_bot.auto_filter(client, msg, spoll)

# Enhanced spell check function
async def ai_spell_check_kdrama(chat_id: int, wrong_name: str) -> Optional[str]:
    """Enhanced AI spell check for K-Drama content"""
    return await kdrama_bot.ai_spell_check_kdrama(chat_id, wrong_name)

# Enhanced advantage spell check
async def advantage_spell_chok(client, message):
    """Enhanced spell check with K-Drama suggestions"""
    return await kdrama_bot.show_kdrama_suggestions(client, message)
