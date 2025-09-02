import os
import re
import sys
import json
import base64
import random
import asyncio
import time
import pytz
from logging_helper import LOGGER
from .pm_filter import auto_filter 
from Script import script
from datetime import datetime, timedelta
from database.refer import referdb
from database.topdb import silentdb
from pyrogram.enums import ParseMode, ChatType
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, ChatAdminRequired
from pyrogram.types import *
from database.ia_filterdb import *
from database.users_chats_db import db
from info import *
from utils import *

TIMEZONE = "Asia/Kolkata"
BATCH_FILES = {}

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
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

    m = message
    # Verification system removed here

    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        silenxbotz = await message.reply_sticker("CAACAgIAAxkBAAE5tX1oohS_GHHnWdQqxxH6sbcj2K9cRwACtA4AAnrnsEhInMQI4qVJTzYE")
        await asyncio.sleep(5)
        await silenxbotz.delete()
        if not await db.get_chat(message.chat.id):
            total = await client.get_chat_members_count(message.chat.id)
            await client.send_message(LOG_CHANNEL, script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, "Unknown"))       
            await db.add_chat(message.chat.id, message.chat.title)
        return 

    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention))

    if len(message.command) != 2:
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
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML,
        )
        return

    if message.command[1].startswith("reff_"):
        try:
            user_id = int(message.command[1].split("_")[1])
        except ValueError:
            await message.reply_text("Invalid refer!")
            return
        if user_id == message.from_user.id:
            await message.reply_text("🤣 Hey Dude! You can’t refer yourself!")
            return
        if referdb.is_user_in_list(message.from_user.id):
            await message.reply_text("Yᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ᴀʟʀᴇᴀᴅʏ ɪɴᴠɪᴛᴇᴅ ❗")
            return
        try:
            uss = await client.get_users(user_id)
        except Exception:
            return 	    
        referdb.add_user(message.from_user.id)
        fromuse = referdb.get_refer_points(user_id) + 10
        if fromuse == 100:
            referdb.add_refer_points(user_id, 0) 
            await message.reply_text(f"👥 Friend Invited Successfully {uss.mention}!")		    
            await message.reply_text(user_id, f"🎉 You Were Invited By {message.from_user.mention}!") 	
            seconds = 2592000
            if seconds > 0:
                expiry_time = datetime.now() + timedelta(seconds=seconds)
                user_data = {"id": user_id, "expiry_time": expiry_time}
                await db.update_user(user_data)		    
                await client.send_message(
                    chat_id=user_id,
                    text=f"<b>Hᴇʏ {uss.mention}\n\nYᴏᴜ ɢᴏᴛ 1 ᴍᴏɴᴛʜ ᴘʀᴇᴍɪᴜᴍ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ʙʏ ɪɴᴠɪᴛɪɴɢ 10 ᴜsᴇʀs ❗", disable_web_page_preview=True              
                )
            for admin in ADMINS:
                await client.send_message(chat_id=admin, text=f"successfully completed!\n\nUser   Name: {uss.mention}\n\nUser   ID: {uss.id}!")	
        else:
            referdb.add_refer_points(user_id, fromuse)
            await message.reply_text(f"🎉 You Were Invited By {uss.mention}!")
            await client.send_message(user_id, f"🎉 You Were Invited By ☞{message.from_user.mention}!")
        return

async def check_subscriptions(client, message):
    try:
        btn = []
        if AUTH_REQ_CHANNELS:
            btn += await is_req_subscribed(client, message.from_user.id, AUTH_REQ_CHANNELS)

        if btn:
            if len(message.command) > 1 and "_" in message.command[1]:
                kk, file_id_retry = message.command[1].split("_", 1)
                btn.append([
                    InlineKeyboardButton("♻️ ᴛʀʏ ᴀɢᴀɪɴ ♻️", callback_data=f"checksub#{kk}#{file_id_retry}")
                ])

            reply_markup = InlineKeyboardMarkup(btn)
            photo = random.choice(FSUB_PICS) if FSUB_PICS else "https://graph.org/file/7478ff3eac37f4329c3d8.jpg"
            caption = (
                f"👋 ʜᴇʟʟᴏ {message.from_user.mention}\n\n"
                "🛑 ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴛʜᴇ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ.\n"
                "👉 ᴊᴏɪɴ ᴀʟʟ ᴛʜᴇ ʙᴇʟᴏᴡ ᴄʜᴀɴɴᴇʟs ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ."
            )
            await message.reply_photo(
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
            return
    except Exception as e:
        await log_error(client, f"❗️ Force Sub Error:\n\n{repr(e)}")
        LOGGER.error(f"❗️ Force Sub Error:\n\n{repr(e)}")

@Client.on_message(filters.command('logs') & filters.user(ADMINS))
async def log_file(bot, message):
    """Send log file"""
    try:
        await message.reply_document('TELEGRAM BOT.LOG')
    except Exception as e:
        await message.reply(str(e))


@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete(bot, message):
    """Delete file from database"""
    reply = message.reply_to_message
    if reply and reply.media:
        msg = await message.reply("Pʀᴏᴄᴇssɪɴɢ...⏳", quote=True)
    else:
        await message.reply('Rᴇᴘʟʏ ᴛᴏ ғɪʟᴇ ᴡɪᴛʜ /delete ᴡʜɪᴄʜ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ', quote=True)
        return
    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media:
            break
    else:
        await msg.edit('Tʜɪs ɪs ɴᴏᴛ sᴜᴘᴘᴏʀᴛᴇᴅ ғɪʟᴇ ғᴏʀᴍᴀᴛ')
        return    
    file_id, file_ref = unpack_new_file_id(media.file_id)
    result = await Media.collection.delete_one({'_id': file_id})
    if not result.deleted_count and MULTIPLE_DB:
        result = await Media2.collection.delete_one({'_id': file_id})
    if result.deleted_count:
        await msg.edit('Fɪʟᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴅᴀᴛᴀʙᴀsᴇ ✅')
        return
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
    result = await Media.collection.delete_many({
        'file_name': file_name,
        'file_size': media.file_size,
        'mime_type': media.mime_type
    })
    if not result.deleted_count and MULTIPLE_DB:
        result = await Media2.collection.delete_many({
            'file_name': file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
        })
    if result.deleted_count:
        await msg.edit('Fɪʟᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴅᴀᴛᴀʙᴀsᴇ ✅')
        return
    result = await Media.collection.delete_many({
        'file_name': media.file_name,
        'file_size': media.file_size,
        'mime_type': media.mime_type
    })
    if not result.deleted_count and MULTIPLE_DB:
        result = await Media2.collection.delete_many({
            'file_name': media.file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
        })
    if result.deleted_count:
        await msg.edit('Fɪʟᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴅᴀᴛᴀʙᴀsᴇ ✅')
    else:
        await msg.edit('Fɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ ❌')


@Client.on_message(filters.command('deleteall') & filters.user(ADMINS))
async def delete_all_index(bot, message):
    await message.reply_text(
        'ᴛʜɪꜱ ᴡɪʟʟ ᴅᴇʟᴇᴛᴇ ᴀʟʟ ʏᴏᴜʀ ɪɴᴅᴇxᴇᴅ ꜰɪʟᴇꜱ !\nᴅᴏ ʏᴏᴜ ꜱᴛɪʟʟ ᴡᴀɴᴛ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ?',
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⚠️ ʏᴇꜱ ⚠️", callback_data="autofilter_delete"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ ɴᴏ ❌", callback_data="close_data"
                    )
                ],
            ]
        ),
        quote=True,
    )

@Client.on_callback_query(filters.regex(r'^autofilter_delete'))
async def delete_all_index_confirm(bot, message):
    await Media.collection.drop()
    if MULTIPLE_DB:    
        await Media2.collection.drop()
    await message.answer("Eᴠᴇʀʏᴛʜɪɴɢ's Gᴏɴᴇ")
    await message.message.edit('ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ᴀʟʟ ɪɴᴅᴇxᴇᴅ ꜰɪʟᴇꜱ ✅')

@Client.on_message(filters.command('settings'))
async def settings(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"🚧 Currently upgrading… Will return soon 🔜", disable_web_page_preview=True)
        return
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return await message.reply(f"🕵️‍♂️ Admin Status: Anonymous")
    chat_type = message.chat.type
    if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        if not await is_check_admin(client, grp_id, message.from_user.id):
            return await message.reply_text('<b>🔒 Admin Privileges Required</b>')
        await db.connect_group(grp_id, user_id)
        btn = [[
                InlineKeyboardButton("👥 Start Private Chat", callback_data=f"opnsetpm#{grp_id}")
              ],[
                InlineKeyboardButton("👥 Open Here", callback_data=f"opnsetgrp#{grp_id}")
              ]]
        await message.reply_text(
                text="<b>🛠️ Pick Settings Menu Location</b>",
                reply_markup=InlineKeyboardMarkup(btn),
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=message.id
        )
    elif chat_type == enums.ChatType.PRIVATE:
        connected_groups = await db.get_connected_grps(user_id)
        if not connected_groups:
            return await message.reply_text("No Connected Groups Found .")
        group_list = []
        for group in connected_groups:
            try:
                silentx = await client.get_chat(group)
                group_list.append([
                    InlineKeyboardButton(text=silentx.title, callback_data=f"grp_pm#{silentx.id}")
                ])
            except Exception as e:
                LOGGER.error(f"Error In PM Settings Button - {e}")
                pass
        await message.reply_text('📌 Groups You’re Connected To', reply_markup=InlineKeyboardMarkup(group_list))
                                                                                                                

@Client.on_message(filters.command('reload'))
async def connect_group(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"🚧 Currently upgrading… Will return soon 🔜", disable_web_page_preview=True)
        return
    user_id = message.from_user.id
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await db.connect_group(message.chat.id, user_id)
        await message.reply_text("Group Reloaded ✅ Now You Can Manage This Group From PM.")
    elif message.chat.type == enums.ChatType.PRIVATE:
        if len(message.command) < 2:
            await message.reply_text("Use: /reload <group_id>")
            return
        try:
            group_id = int(message.command[1])
            if not await is_check_admin(client, group_id, user_id):
                await message.reply_text("You're Not Admin In That Group.")
                return
            chat = await client.get_chat(group_id)
            await db.connect_group(group_id, user_id)
            await message.reply_text(f"Linked {chat.title} to PM.")
        except:
            await message.reply_text("Invalid group ID or error occurred.")

@Client.on_message(filters.command("send") & filters.user(ADMINS))
async def send_msg(bot, message):
    if message.reply_to_message:
        target_id = message.text.split(" ", 1)[1]
        out = "Users Saved In DB Are:\n\n"
        success = False
        try:
            user = await bot.get_users(target_id)
            users = await db.get_all_users()
            async for usr in users:
                out += f"{usr['id']}"
                out += '\n'
            if str(user.id) in str(out):
                await message.reply_to_message.copy(int(user.id))
                success = True
            else:
                success = False
            if success:
                await message.reply_text(f"<b>ʏᴏᴜʀ ᴍᴇꜱꜱᴀɢᴇ ʜᴀꜱ ʙᴇᴇɴ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ꜱᴇɴᴛ ᴛᴏ {user.mention}.</b>")
            else:
                await message.reply_text("<b>ᴛʜɪꜱ ᴜꜱᴇʀ ᴅɪᴅ
