import os
import re, sys
import json
import base64
import random
import asyncio
import time
import pytz
from logging_helper import LOGGER
from .pm_filter import enhanced_auto_filter as auto_filter
from Script import script
from datetime import datetime
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
    if len(m.command) == 2 and m.command[1].startswith(('notcopy', 'sendall')):
        _, userid, verify_id, file_id = m.command[1].split("_", 3)
        user_id = int(userid)
        grp_id = temp.VERIFICATIONS.get(user_id, 0)
        settings = await get_settings(grp_id)         
        verify_id_info = await db.get_verify_id_info(user_id, verify_id)
        if not verify_id_info or verify_id_info["verified"]:
            await message.reply("<b>❌ Oops! That link is gone. Try again 🔄</b>")
            return  
        ist_timezone = pytz.timezone('Asia/Kolkata')
        if await db.user_verified(user_id):
            key = "third_time_verified"
        else:
            key = "second_time_verified" if await db.is_user_verified(user_id) else "last_verified"
        current_time = datetime.now(tz=ist_timezone)
        result = await db.update_notcopy_user(user_id, {key:current_time})
        await db.update_verify_id_info(user_id, verify_id, {"verified":True})
        if key == "third_time_verified": 
            num = 3 
        else: 
            num =  2 if key == "second_time_verified" else 1 
        if key == "third_time_verified": 
            msg = script.THIRDT_VERIFY_COMPLETE_TEXT
        else:
            msg = script.SECOND_VERIFY_COMPLETE_TEXT if key == "second_time_verified" else script.VERIFY_COMPLETE_TEXT
        if message.command[1].startswith('sendall'):
            verifiedfiles = f"https://telegram.me/{temp.U_NAME}?start=allfiles_{grp_id}_{file_id}"
        else:
            verifiedfiles = f"https://telegram.me/{temp.U_NAME}?start=file_{grp_id}_{file_id}"
        await client.send_message(settings['log'], script.VERIFIED_LOG_TEXT.format(m.from_user.mention, user_id, datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d %B %Y'), num))
        btn = [[
            InlineKeyboardButton("📂 ꜰɪʟᴇ ʀᴇᴀᴅʏ! • ᴛᴀᴘ ᴛᴏ ɢᴇᴛ ɪᴛ", url=verifiedfiles),
        ]]
        reply_markup=InlineKeyboardMarkup(btn)
        dlt=await m.reply_photo(
            photo=(VERIFY_IMG),
            caption=msg.format(message.from_user.mention, get_readable_time(TWO_VERIFY_GAP)),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await asyncio.sleep(300)
        await dlt.delete()
        return         
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        silenxbotz=await message.reply_sticker("CAACAgIAAxkBAAE5tX1oohS_GHHnWdQqxxH6sbcj2K9cRwACtA4AAnrnsEhInMQI4qVJTzYE")
        await asyncio.sleep(5)
        await silenxbotz.delete()
        if not await db.get_chat(message.chat.id):
            total=await client.get_chat_members_count(message.chat.id)
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
                expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
                user_data = {"id": user_id, "expiry_time": expiry_time}
                await db.update_user(user_data)		    
                await client.send_message(
                chat_id=user_id,
                text=f"<b>Hᴇʏ {uss.mention}\n\nYᴏᴜ ɢᴏᴛ 1 ᴍᴏɴᴛʜ ᴘʀᴇᴍɪᴜᴍ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ʙʏ ɪɴᴠɪᴛɪɴɢ 10 ᴜsᴇʀs ❗", disable_web_page_preview=True              
                )
            for admin in ADMINS:
                await client.send_message(chat_id=admin, text=f"successfully completed!\n\nUser Name: {uss.mention}\n\nUser ID: {uss.id}!")	
        else:
            referdb.add_refer_points(user_id, fromuse)
            await message.reply_text(f"🎉 You Were Invited By {uss.mention}!")
            await client.send_message(user_id, f"🎉 You Were Invited By ☞{message.from_user.mention}!")
        return
        
        
    if len(message.command) == 2 and message.command[1].startswith('getfile'):
        movies = message.command[1].split("-", 1)[1] 
        movie = movies.replace('-',' ')
        message.text = movie 
        await enhanced_auto_filter(client, message) 
        return
            
    data = message.command[1]
    try:
        pre, grp_id, file_id = data.split('_', 2)
    except:
        pre, grp_id, file_id = "", 0, data

    try:
        settings = await get_settings(int(data.split("_", 2)[1]))
        fsub_id_list = settings.get('fsub_id', [])
        btn = []
        i = 1
        fsub_id_list = fsub_id_list + AUTH_CHANNEL if AUTH_CHANNEL else fsub_id_list
        fsub_id_list = fsub_id_list + AUTH_REQ_CHANNEL if AUTH_REQ_CHANNEL else fsub_id_list
        
        if fsub_id_list:
            fsub_ids = []
            for chnl in fsub_id_list:
                if chnl not in fsub_ids:
                    fsub_ids.append(chnl)
                else:
                    continue
                try:
                    channel_name = (await client.get_chat(chnl)).title or f"Update Channel"
                except Exception:
                    channel_name = f"Update Channel"
                if AUTH_REQ_CHANNEL and chnl in AUTH_REQ_CHANNEL and not await is_req_subscribed(client, message, chnl):
                    try:
                        invite_link = await client.create_chat_invite_link(chnl, creates_join_request=True)
                    except ChatAdminRequired:
                        LOGGER.error("First, make me an Admin in the AUTH_CHANNEL")
                        return
                    btn.append([
                        InlineKeyboardButton(f"{i}. {channel_name}", url=invite_link.invite_link)
                    ])
                elif chnl not in AUTH_REQ_CHANNEL and not await is_subscribed(client, message.from_user.id, chnl):
                    try:
                        invite_link = await client.create_chat_invite_link(chnl)
                    except ChatAdminRequired:
                        LOGGER.error("First, make me an Admin in the AUTH_CHANNEL")
                        return
                    btn.append([
                        InlineKeyboardButton(f"{i}. {channel_name}", url=invite_link.invite_link)
                    ])
                i += 1

            if btn:
                if message.command[1] != "subscribe":
                    btn.append([InlineKeyboardButton("♻️ Retry!", url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}")])
                await client.send_photo(
                    chat_id=message.from_user.id,
                    photo=random.choice(FSUB_IMG),
                    caption=script.FORCESUB_TEXT,
                    reply_markup=InlineKeyboardMarkup(btn),
                    parse_mode=enums.ParseMode.HTML,
                )
                return
    except Exception as e:
        await log_error(client, f"Got Error In Force Subscription Function.\n\n Error - {e}")
        LOGGER.error(f"Error In Fsub :- {e}")
        
    user_id = m.from_user.id
    if not await db.has_premium_access(user_id):
        try:
            grp_id = int(grp_id)
            user_verified = await db.is_user_verified(user_id)
            settings = await get_settings(grp_id)
            is_second_shortener = await db.use_second_shortener(user_id, settings.get('verify_time', TWO_VERIFY_GAP)) 
            is_third_shortener = await db.use_third_shortener(user_id, settings.get('third_verify_time', THREE_VERIFY_GAP))
            if settings.get("is_verify", IS_VERIFY) and (not user_verified or is_second_shortener or is_third_shortener):                
                verify_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
                await db.create_verify_id(user_id, verify_id)
                temp.VERIFICATIONS[user_id] = grp_id
                if message.command[1].startswith('allfiles'):
                    verify = await get_shortlink(f"https://telegram.me/{temp.U_NAME}?start=sendall_{user_id}_{verify_id}_{file_id}", grp_id, is_second_shortener, is_third_shortener)
                else:
                    verify = await get_shortlink(f"https://telegram.me/{temp.U_NAME}?start=notcopy_{user_id}_{verify_id}_{file_id}", grp_id, is_second_shortener, is_third_shortener)
                if is_third_shortener:
                    howtodownload = settings.get('tutorial_3', TUTORIAL_3)
                else:
                    howtodownload = settings.get('tutorial_2', TUTORIAL_2) if is_second_shortener else settings.get('tutorial', TUTORIAL)
                buttons = [[
                    InlineKeyboardButton(text="♻️ ᴄʟɪᴄᴋ ʜᴇʀᴇ ᴛᴏ ᴠᴇʀɪꜰʏ ♻️", url=verify)
                ],[
                    InlineKeyboardButton(text="⁉️ ʜᴏᴡ ᴛᴏ ᴠᴇʀɪꜰʏ ⁉️", url=howtodownload)
                ]]
                reply_markup=InlineKeyboardMarkup(buttons)
                if await db.user_verified(user_id): 
                    msg = script.THIRDT_VERIFICATION_TEXT
                else:            
                    msg = script.SECOND_VERIFICATION_TEXT if is_second_shortener else script.VERIFICATION_TEXT
                n=await m.reply_text(
                    text=msg.format(message.from_user.mention),
                    protect_content = True,
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
                await asyncio.sleep(300) 
                await n.delete()
                await m.delete()
                return
        except Exception as e:
            await log_error(client, f"Got Error In Verification Funtion.\n\n Error - {e}")
            LOGGER.error(f"Error In Verification - {e}")
            pass
    
    if data.startswith("allfiles"):
        files = temp.GETALL.get(file_id)
        if not files:
            return await message.reply('<b><i>❌ No Such File Exists! </b></i>')
        filesarr = []
        for file in files:
            file_id = file.file_id
            files_ = await get_file_details(file_id)
            files1 = files_[0]
            title = clean_filename(files1.file_name) 
            size = get_size(files1.file_size)
            f_caption = files1.caption
            settings = await get_settings(int(grp_id))
            SILENTX_CAPTION = settings.get('caption', CUSTOM_FILE_CAPTION)
            if SILENTX_CAPTION:
                try:
                    f_caption=SILENTX_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
                except Exception as e:
                    logger.exception(e)
                    f_caption = f_caption
            if f_caption is None:
                f_caption = clean_filename(files1.file_name) 
            if STREAM_MODE:
                btn = [
                    [InlineKeyboardButton('𝖦𝖾𝗇𝖾𝗋𝖺𝗍𝖾 𝖲𝗍𝗋𝖾𝗆𝗂𝗇𝗀 𝖫𝗂𝗇𝗄', callback_data=f'streamfile:{file_id}')],
                    [InlineKeyboardButton('𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 📢', url=UPDATE_CHANNEL_LNK)]  
                ]
            else:
                btn = [
                    [InlineKeyboardButton('𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 📢 📢', url=UPDATE_CHANNEL_LNK)]
                ]
            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file_id,
                caption=f_caption,
                protect_content=settings.get('file_secure', PROTECT_CONTENT),
                reply_markup=InlineKeyboardMarkup(btn)
            )
            filesarr.append(msg)
        k = await client.send_message(chat_id=message.from_user.id, text=f"<b><u>⚠️ File disappears in ⏰ <code>{get_time(DELETE_TIME)}</code> \n📥 Forward to another chat to download!</i></b>")
        await asyncio.sleep(DELETE_TIME)
        for x in filesarr:
            await x.delete()
        await k.edit_text("<b>✨ File Deleted!</b>")
        return

    user = message.from_user.id
    files_ = await get_file_details(file_id)  
    settings = await get_settings(int(grp_id))
    if not files_:
        pre, file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
        try:
            if STREAM_MODE:
                btn = [
                    [InlineKeyboardButton('𝖦𝖾𝗇𝖾𝗋𝖺𝗍𝖾 𝖲𝗍𝗋𝖾𝗆𝗂𝗇𝗀 𝖫𝗂𝗇𝗄', callback_data=f'streamfile:{file_id}')],
                    [InlineKeyboardButton('𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 📢', url=UPDATE_CHANNEL_LNK)]
             
                ]
            else:
                btn = [
                    [InlineKeyboardButton('𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 📢', url=UPDATE_CHANNEL_LNK)]
                ]
            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file_id,
                protect_content=settings.get('file_secure', PROTECT_CONTENT),
                reply_markup=InlineKeyboardMarkup(btn))

            filetype = msg.media
            file = getattr(msg, filetype.value)
            title = clean_filename(file.file_name)              
            size=get_size(file.file_size)
            f_caption = f"<code>{title}</code>"
            settings = await get_settings(int(grp_id))
            SILENTX_CAPTION = settings.get('caption', CUSTOM_FILE_CAPTION)
            if SILENTX_CAPTION:
                try:
                    f_caption=SILENTX_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='')
                except:
                    return
            await msg.edit_caption(f_caption)
            k = await msg.reply(f"<b>⚠️ File disappears in ⏰ <code>{get_time(DELETE_TIME)}</code> \n📥 Forward to another chat to download!</b>", quote=True)
            await asyncio.sleep(DELETE_TIME)
            await msg.delete()
            await k.edit_text("<b>✨ File Deleted!</b>")
            return
        except:
            pass
        return await message.reply('❌ No Such File Exists! ')
    
    files = files_[0]
    title = clean_filename(files.file_name)
    size = get_size(files.file_size)
    f_caption = files.caption
    settings = await get_settings(int(grp_id))            
    SILENTX_CAPTION = settings.get('caption', CUSTOM_FILE_CAPTION)
    if SILENTX_CAPTION:
        try:
            f_caption=SILENTX_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
        except Exception as e:
            LOGGER.error(e)
            f_caption = f_caption

    if f_caption is None:
        f_caption = clean_filename(files.file_name)
    if STREAM_MODE:
        btn = [
            [InlineKeyboardButton('𝖦𝖾𝗇𝖾𝗋𝖺𝗍𝖾 𝖲𝗍𝗋𝖾𝗆𝗂𝗇𝗀 𝖫𝗂𝗇𝗄', callback_data=f'streamfile:{file_id}')],
            [InlineKeyboardButton('𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 📢', url=UPDATE_CHANNEL_LNK)]
        ]
    else:
        btn = [
            [InlineKeyboardButton('𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅 📢', url=UPDATE_CHANNEL_LNK)]
        ]
    msg = await client.send_cached_media(
        chat_id=message.from_user.id,
        file_id=file_id,
        caption=f_caption,
        protect_content=settings.get('file_secure', PROTECT_CONTENT),
        reply_markup=InlineKeyboardMarkup(btn)
    )
    k = await msg.reply(f"<b>⚠️ File disappears in ⏰ <code>{get_time(DELETE_TIME)}</code> \n📥 Forward to another chat to download!</b>", quote=True)     
    await asyncio.sleep(DELETE_TIME)
    await msg.delete()
    await k.edit_text("<b>✨ File Deleted!</b>")
    return

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

@Client.on_message((filters.command(["request", "Request"]) | filters.regex("#request") | filters.regex("#Request")) & filters.group)
async def requests(bot, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"🚧 Currently upgrading… Will return soon 🔜", disable_web_page_preview=True)
        return
    if REQST_CHANNEL is None or SUPPORT_CHAT_ID is None: return # Must add REQST_CHANNEL and SUPPORT_CHAT_ID to use this feature
    if message.reply_to_message and SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
        success = True
        content = message.reply_to_message.text
        try:
            if REQST_CHANNEL is not None:
                btn = [[
                        InlineKeyboardButton('📝 Request Details', url=f"{message.reply_to_message.link}"),
                        InlineKeyboardButton('🛠️ Open Options', callback_data=f'show_option#{reporter}')
                      ]]
                reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>📄 Request: <u>{content}</u> \n👥 Reported by: {mention} | ID: {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                success = True
            elif len(content) >= 3:
                for admin in ADMINS:
                    btn = [[
                        InlineKeyboardButton('📝 Request Details', url=f"{message.reply_to_message.link}"),
                        InlineKeyboardButton('🛠️ Open Options', callback_data=f'show_option#{reporter}')
                      ]]
                    reported_post = await bot.send_message(chat_id=admin, text=f"<b>📄 Request: <u>{content}</u> \n👥 Reported by: {mention} | ID: {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                    success = True
            else:
                if len(content) < 3:
                    await message.reply_text("<b>✏️ Type at least 3 characters for your request!</b>")
            if len(content) < 3:
                success = False
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            pass
        
    elif SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
        success = True
        content = message.text
        keywords = ["#request", "/request", "#Request", "/Request"]
        for keyword in keywords:
            if keyword in content:
                content = content.replace(keyword, "")
        try:
            if REQST_CHANNEL is not None and len(content) >= 3:
                btn = [[
                        InlineKeyboardButton('📝 Request Details', url=f"{message.link}"),
                        InlineKeyboardButton('🛠️ Open Options', callback_data=f'show_option#{reporter}')
                      ]]
                reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>📄 Request: <u>{content}</u> \n👥 Reported by: {mention} | ID: {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                success = True
            elif len(content) >= 3:
                for admin in ADMINS:
                    btn = [[
                        InlineKeyboardButton('📝 Request Details', url=f"{message.link}"),
                        InlineKeyboardButton('🛠️ Open Options', callback_data=f'show_option#{reporter}')
                      ]]
                    reported_post = await bot.send_message(chat_id=admin, text=f"<b>📄 Request: <u>{content}</u> \n👥 Reported by: {mention} | ID: {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                    success = True
            else:
                if len(content) < 3:
                    await message.reply_text("<b>✏️ Type at least 3 characters for your request!</b>")
            if len(content) < 3:
                success = False
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            pass
    
    elif SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
        success = True
        content = message.text
        keywords = ["#request", "/request", "#Request", "/Request"]
        for keyword in keywords:
            if keyword in content:
                content = content.replace(keyword, "")
        try:
            if REQST_CHANNEL is not None and len(content) >= 3:
                btn = [[
                        InlineKeyboardButton('📝 Request Details', url=f"{message.link}"),
                        InlineKeyboardButton('🛠️ Open Options', callback_data=f'show_option#{reporter}')
                      ]]
                reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>📄 Request: <u>{content}</u> \n👥 Reported by: {mention} | ID: {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                success = True
            elif len(content) >= 3:
                for admin in ADMINS:
                    btn = [[
                        InlineKeyboardButton('📝 Request Details', url=f"{message.link}"),
                        InlineKeyboardButton('🛠️ Open Options', callback_data=f'show_option#{reporter}')
                      ]]
                    reported_post = await bot.send_message(chat_id=admin, text=f"<b>📄 Request: <u>{content}</u> \n👥 Reported by: {mention} | ID: {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                    success = True
            else:
                if len(content) < 3:
                    await message.reply_text("<b>✏️ Type at least 3 characters for your request!</b>")
            if len(content) < 3:
                success = False
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            pass
    else:
        success = False    
    if success:
        link = await bot.create_chat_invite_link(int(REQST_CHANNEL))
        btn = [[
                InlineKeyboardButton('📢 Join Channel', url=link.invite_link),
                InlineKeyboardButton('📝 Request Details', url=f"{reported_post.link}")
              ]]
        await message.reply_text("<b>📝 Request Recorded!</b>", reply_markup=InlineKeyboardMarkup(btn))
   
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
                await message.reply_text("<b>ᴛʜɪꜱ ᴜꜱᴇʀ ᴅɪᴅɴ'ᴛ ꜱᴛᴀʀᴛᴇᴅ ᴛʜɪꜱ ʙᴏᴛ ʏᴇᴛ !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error: {e}</b>")
    else:
        await message.reply_text("<b>ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ᴀꜱ ᴀ ʀᴇᴘʟʏ ᴛᴏ ᴀɴʏ ᴍᴇꜱꜱᴀɢᴇ ᴜꜱɪɴɢ ᴛʜᴇ ᴛᴀʀɢᴇᴛ ᴄʜᴀᴛ ɪᴅ. ꜰᴏʀ ᴇɢ:  /send ᴜꜱᴇʀɪᴅ</b>")

@Client.on_message(filters.command("deletefiles") & filters.user(ADMINS))
async def deletemultiplefiles(bot, message):
    chat_type = message.chat.type
    if chat_type != enums.ChatType.PRIVATE:
        return await message.reply_text(f"<b>Hey {message.from_user.mention}, This command won't work in groups. It only works on my PM !</b>")
    else:
        pass
    try:
        keyword = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text(f"<b>Hey {message.from_user.mention}, Give me a keyword along with the command to delete files.</b>")
    k = await bot.send_message(chat_id=message.chat.id, text=f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
    files, total = await get_bad_files(keyword)
    await k.delete()
    btn = [[
       InlineKeyboardButton("⚠️ Yes, Continue ! ⚠️", callback_data=f"killfilesdq#{keyword}")
       ],[
       InlineKeyboardButton("❌ No, Abort operation ! ❌", callback_data="close_data")
    ]]
    await message.reply_text(
        text=f"<b>Found {total} files for your query {keyword} !\n\nDo you want to delete?</b>",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )

@Client.on_callback_query(filters.regex("topsearch"))
async def topsearch_callback(client, callback_query):    
    def is_alphanumeric(string):
        return bool(re.match('^[a-zA-Z0-9 ]*$', string))    
    limit = 20  
    top_messages = await silentdb.get_top_messages(limit)
    seen_messages = set()
    truncated_messages = []
    for msg in top_messages:
        msg_lower = msg.lower()
        if msg_lower not in seen_messages and is_alphanumeric(msg):
            seen_messages.add(msg_lower)            
            if len(msg) > 35:
                truncated_messages.append(msg[:32] + "...")
            else:
                truncated_messages.append(msg)
    keyboard = [truncated_messages[i:i+2] for i in range(0, len(truncated_messages), 2)]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, 
        one_time_keyboard=True, 
        resize_keyboard=True, 
        placeholder="Most searches of the day"
    )
    await callback_query.message.reply_text("<b>📊 Trending Searches</b>", reply_markup=reply_markup)
    await callback_query.answer()

@Client.on_message(filters.command('top_search'))
async def top(_, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"🛠️ Under Maintenance… Back Soon! 🔜", disable_web_page_preview=True)
        return
    def is_alphanumeric(string):
        return bool(re.match('^[a-zA-Z0-9 ]*$', string))
    try:
        limit = int(message.command[1])
    except (IndexError, ValueError):
        limit = 20
    top_messages = await silentdb.get_top_messages(limit)
    seen_messages = set()
    truncated_messages = []
    for msg in top_messages:
        if msg.lower() not in seen_messages and is_alphanumeric(msg):
            seen_messages.add(msg.lower())            
            if len(msg) > 35:
                truncated_messages.append(msg[:35 - 3])
            else:
                truncated_messages.append(msg)
    keyboard = []
    for i in range(0, len(truncated_messages), 2):
        row = truncated_messages[i:i+2]
        keyboard.append(row)
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, placeholder="Most searches of the day")
    await message.reply_text(f"<b>📊 Trending Searches</b>", reply_markup=reply_markup)

    
@Client.on_message(filters.command('trendlist'))
async def trendlist(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"🛠️ Under Maintenance… Back Soon! 🔜", disable_web_page_preview=True)
        return
    def is_alphanumeric(string):
        return bool(re.match('^[a-zA-Z0-9 ]*$', string))
    limit = 31
    if len(message.command) > 1:
        try:
            limit = int(message.command[1])
        except ValueError:
            await message.reply_text("Invalid number format.\nPlease provide a valid number after the /trendlist command.")
            return 
    try:
        top_messages = await silentdb.get_top_messages(limit)
    except Exception as e:
        await message.reply_text(f"Error retrieving messages: {str(e)}")
        return  
    if not top_messages:
        await message.reply_text("No top messages found.")
        return 
    seen_messages = set()
    truncated_messages = []
    for msg in top_messages:
        if msg.lower() not in seen_messages and is_alphanumeric(msg):
            seen_messages.add(msg.lower())
            truncated_messages.append(msg[:32] + '...' if len(msg) > 35 else msg)
    if not truncated_messages:
        await message.reply_text("No valid top messages found.")
        return  
    formatted_list = "\n".join([f"{i+1}. <b>{msg}</b>" for i, msg in enumerate(truncated_messages)])
    additional_message = "🔍 No edits, no tweaks — exactly as searched!"
    formatted_list += f"\n\n{additional_message}"
    reply_text = f"<b>Top {len(truncated_messages)} 🔥 Trending Today 👇:</b>\n\n{formatted_list}"
    await message.reply_text(reply_text)

@Client.on_message(filters.private & filters.command("pm_search") & filters.user(ADMINS))
async def set_pm_search(client, message):
    bot_id = client.me.id
    try:
        option = message.text.split(" ", 1)[1].strip().lower()
        enable_status = option in ['on', 'true']
    except (IndexError, ValueError):
        await message.reply_text("<b>💔 Invalid option. Please send 'on' or 'off' after the command..</b>")
        return
    try:
        await db.update_pm_search_status(bot_id, enable_status)
        response_text = (
            "<b> ᴘᴍ ꜱᴇᴀʀᴄʜ ᴇɴᴀʙʟᴇᴅ ✅</b>" if enable_status 
            else "<b> ᴘᴍ ꜱᴇᴀʀᴄʜ ᴅɪꜱᴀʙʟᴇᴅ ❌</b>"
        )
        await message.reply_text(response_text)
    except Exception as e:
        await log_error(client, f"Error in set_pm_search: {e}")
        await message.reply_text(f"<b>❗ An error occurred: {e}</b>")

@Client.on_message(filters.private & filters.command("movie_update") & filters.user(ADMINS))
async def set_movie_update_notification(client, message):
    bot_id = client.me.id
    try:
        option = message.text.split(" ", 1)[1].strip().lower()
        enable_status = option in ['on', 'true']
    except (IndexError, ValueError):
        await message.reply_text("<b>💔 Invalid option. Please send 'on' or 'off' after the command.</b>")
        return
    try:
        await db.update_movie_update_status(bot_id, enable_status)
        response_text = (
            "<b>ᴍᴏᴠɪᴇ ᴜᴘᴅᴀᴛᴇ ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ ᴇɴᴀʙʟᴇᴅ ✅</b>" if enable_status 
            else "<b>ᴍᴏᴠɪᴇ ᴜᴘᴅᴀᴛᴇ ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ ᴅɪꜱᴀʙʟᴇᴅ ❌</b>"
        )
        await message.reply_text(response_text)
    except Exception as e:
        await log_error(client, f"Error in set_movie_update_notification: {e}")
        await message.reply_text(f"<b>❗ An error occurred: {e}</b>")

@Client.on_message(filters.private & filters.command("maintenance") & filters.user(ADMINS))
async def set_maintenance_mode(client, message):
    bot_id = client.me.id
    try:
        option = message.text.split(" ", 1)[1].strip().lower()
        enable_status = option in ['on', 'true']
    except (IndexError, ValueError):
        await message.reply_text("💔 Invalid Option. Please Send 'on' or 'off' Along With Command.. Example- /maintenance on")
        return
    try:
        await db.update_maintenance_status(bot_id, enable_status)
        response_text = (
            "<b>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ᴇɴᴀʙʟᴇᴅ ✅</b>" if enable_status 
            else "<b>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ᴅɪꜱᴀʙʟᴇᴅ ❌</b>"
        )
        await message.reply_text(response_text)
    except Exception as e:
        await log_error(client, f"Error in set_maintenance_mode: {e}")
        await message.reply_text(f"<b>❗ An error occurred: {e}</b>")
        

@Client.on_message(filters.command("restart") & filters.user(ADMINS))
async def stop_button(bot, message):
    msg = await bot.send_message(text="<b><i>ʙᴏᴛ ɪꜱ ʀᴇꜱᴛᴀʀᴛɪɴɢ</i></b>", chat_id=message.chat.id)       
    await asyncio.sleep(3)
    await msg.edit("<b><i><u>ʙᴏᴛ ɪꜱ ʀᴇꜱᴛᴀʀᴛᴇᴅ</u> ✅</i></b>")
    os.execl(sys.executable, sys.executable, *sys.argv)


@Client.on_message(filters.command("reset_group"))
async def reset_group_command(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"🛠️ Under Maintenance… Back Soon! 🔜", disable_web_page_preview=True)
        return
    grp_id = message.chat.id
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text('<b>🚫 You’re Not an Admin!</b>')
    sts = await message.reply("<b>⏳ Checking…</b>")
    await asyncio.sleep(1.2)
    await sts.delete()
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text("<b>📌 Use This Command in Group…</b>")
    btn = [[
        InlineKeyboardButton('❌ Close', callback_data='close_data')
    ]]
    reply_markup = InlineKeyboardMarkup(btn)
    await save_group_settings(grp_id, 'shortner', SHORTENER_WEBSITE)
    await save_group_settings(grp_id, 'api', SHORTENER_API)
    await save_group_settings(grp_id, 'shortner_two', SHORTENER_WEBSITE2)
    await save_group_settings(grp_id, 'api_two', SHORTENER_API2)
    await save_group_settings(grp_id, 'shortner_three', SHORTENER_WEBSITE3)
    await save_group_settings(grp_id, 'api_three', SHORTENER_API3)
    await save_group_settings(grp_id, 'verify_time', TWO_VERIFY_GAP)
    await save_group_settings(grp_id, 'third_verify_time', THREE_VERIFY_GAP)
    await save_group_settings(grp_id, 'template', IMDB_TEMPLATE)
    await save_group_settings(grp_id, 'tutorial', TUTORIAL)
    await save_group_settings(grp_id, 'tutorial_2', TUTORIAL_2)
    await save_group_settings(grp_id, 'tutorial_3', TUTORIAL_3)
    await save_group_settings(grp_id, 'caption', CUSTOM_FILE_CAPTION)
    await save_group_settings(grp_id, 'log', LOG_VR_CHANNEL)
    await save_group_settings(grp_id, 'is_verify', IS_VERIFY)
    await save_group_settings(grp_id, 'fsub_id', AUTH_CHANNEL)
    await message.reply_text('✅ Group Settings Successfully Reset!')

@Client.on_message(filters.command('set_fsub'))
async def set_fsub(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"🛠️ Under Maintenance… Back Soon! 🔜", disable_web_page_preview=True)
        return
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text("<b>📌 Use This Command in Group…</b>")
    grp_id = message.chat.id
    title = message.chat.title
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text('<b>🚫 You’re Not an Admin!</b>')
    try:
        channel_id = int(message.text.split(" ", 1)[1])
    except IndexError:
        return await message.reply_text("<b>⚠️ Command Incomplete!\n\n❌ Incomplete Command!\n🔗 Use: /set_fsub -100******</code></b>")
    except ValueError:
        return await message.reply_text('<b>ID Must Be an Integer</b>')
    try:
        chat = await client.get_chat(channel_id)
    except Exception as e:
        return await message.reply_text(f"<b><code>{channel_id}</code>Invalid! Please Check <a href=https://t.me/{temp.B_LINK} BOT</a> Is Admin in That Channel\n\n<code>{e}</code></b>")
    if chat.type != enums.ChatType.CHANNEL:
        return await message.reply_text(f"🫥 <code>{channel_id}</code>  Not a Channel! Send Channel ID Only</b>")
    await save_group_settings(grp_id, 'fsub_id', [channel_id])
    mention = message.from_user.mention
    await client.send_message(LOG_API_CHANNEL, f"#Fsub_Channel_set\n\nUser - {mention} Set The Force Channel For {title}:\n\nFSUB Channel Name - {chat.title}\nChannel ID - `{channel_id}`")
    await message.reply_text(f"<b>🎯 Successfully Set Force Sub Channel for {title}\n\n📌 Channel Name - {chat.title}\nɪ📌 Channel ID - <code>{channel_id}</code></b>")

@Client.on_message(filters.command('remove_fsub'))
async def remove_fsub(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"🛠️ Under Maintenance… Back Soon! 🔜", disable_web_page_preview=True)
        return
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text("<b>📌 Use This Command in Group…</b>")       
    grp_id = message.chat.id
    title = message.chat.title
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text('<b>🚫 You’re Not an Admin!</b>')
    settings = await get_settings(grp_id)
    if (c in AUTH_CHANNEL for c in settings['fsub_id']):
        await message.reply_text("<b>⚠️ No Force Sub Channel Set... <code>[ᴅᴇғᴀᴜʟᴛ ᴀᴄᴛɪᴠᴀᴛᴇ]</code></b>")
    else:
        await save_group_settings(grp_id, 'fsub_id', AUTH_CHANNEL)
        mention = message.from_user.mention
        await client.send_message(LOG_API_CHANNEL, f"#Remove_Fsub_Channel\n\nUser - {mention} Remove FSUB Channel From {title}")
        await message.reply_text(f"<b>🗑️ Force Sub Channel Removed.</b>")         


@Client.on_message(filters.command('details'))
async def all_settings(client, message):    
    try:
        bot_id = client.me.id
        maintenance_mode = await db.get_maintenance_status(bot_id)
        if maintenance_mode and message.from_user.id not in ADMINS:
            await message.reply_text(f"🛠️ Under Maintenance… Back Soon! 🔜", disable_web_page_preview=True)
            return
        chat_type = message.chat.type
        if chat_type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return await message.reply_text("<b>📌 Use This Command in Group…</b>")
        grp_id = message.chat.id
        title = message.chat.title
        
        if not await is_check_admin(client, grp_id, message.from_user.id):
            return await message.reply_text('<b>🚫 You’re Not an Admin!</b>') 
        
        settings = await get_settings(grp_id)
        nbbotz = f"""<b>⚙️ Your Settings For - {title}</b>

📝 <b>Log Channel ID:</b> <code>{settings['log']}</code>
🚫 <b>Fsub Channel ID:</b> <code>{settings['fsub_id']}</code>

🎯 <b>IMDb Template:</b> <code>{settings['template']}</code>
📂 <b>File Caption:</b> <code>{settings['caption']}</code>

📌 <i>Note: To reset your settings, send <code>/reset_group</code>.</i>
"""        
        btn = [[            
            InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close_data")
        ]]
        reply_markup=InlineKeyboardMarkup(btn)
        dlt=await message.reply_text(nbbotz, reply_markup=reply_markup, disable_web_page_preview=True)
        await asyncio.sleep(300)
        await dlt.delete()
    except Exception as e:
        LOGGER.error(f"Error : {e}")
        await message.reply_text(f"Error: {e}")

@Client.on_message(filters.command('group_cmd'))
async def group_commands(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"🛠️ Under Maintenance… Back Soon! 🔜", disable_web_page_preview=True)
        return
    user = message.from_user.mention
    user_id = message.from_user.id
    await message.reply_text(script.GROUP_CMD, disable_web_page_preview=True)

@Client.on_message(filters.command('admin_cmd') & filters.user(ADMINS))
async def admin_commands(client, message):
    user = message.from_user.mention
    user_id = message.from_user.id
    await message.reply_text(script.ADMIN_CMD, disable_web_page_preview=True)

@Client.on_message(filters.private & filters.command("movies"))
async def siletxbotz_list_movies(client, message):
    try:
        bot_id = client.me.id
        maintenance_mode = await db.get_maintenance_status(bot_id)
        if maintenance_mode and message.from_user.id not in ADMINS:
            await message.reply_text(f"🛠️ Under Maintenance… Back Soon! 🔜", disable_web_page_preview=True)
            return
        movies = await siletxbotz_get_movies()
        if not movies:
            return await message.reply("❌ No Recent Movies Found", parse_mode=ParseMode.HTML)       
        msg = "<b>🆕 Latest Uploads</b>\n\n"
        msg += "<b>🎬 Movies:</b>\n"
        msg += "\n".join(f"<b>{i+1}. {m}</b>" for i, m in enumerate(movies))
        await message.reply(msg[:4096], parse_mode=ParseMode.HTML)
    except Exception as e:
        LOGGER.error(f"Error in siletxbotz_list_movies: {e}")
        await message.reply("An Error Occurred ☹️", parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("series"))
async def siletxbotz_list_series(client, message):
    try:
        bot_id = client.me.id
        maintenance_mode = await db.get_maintenance_status(bot_id)
        if maintenance_mode and message.from_user.id not in ADMINS:
            await message.reply_text(f"🛠️ Under Maintenance… Back Soon! 🔜", disable_web_page_preview=True)
            return
        series_data = await siletxbotz_get_series()
        if not series_data:
            return await message.reply("❌ No Recent Series Found", parse_mode=ParseMode.HTML)       
        msg = "<b>🆕 Latest Uploads</b>\n\n"
        msg += "<b>📺 Series:</b>\n"
        for i, (title, seasons) in enumerate(series_data.items(), 1):
            season_list = ", ".join(f"{s}" for s in seasons)
            msg += f"<b>{i}. {title} - Season {season_list}</b>\n"
        await message.reply(msg[:4096], parse_mode=ParseMode.HTML)
    except Exception as e:
        LOGGER.error(f"Error in siletxbotz_list_series: {e}")
        await message.reply("An Error Occurred ☹️", parse_mode=ParseMode.HTML)


@Client.on_message(filters.private & filters.command("resetall") & filters.user(ADMINS))
async def reset_all_settings(client, message):
    try:
        reset_count = await db.silentx_reset_settings()
        await message.reply(
            f"<b>✅ Successfully Deleted Group Settings! {reset_count} , \n\n⚙️ Default Values Will Be Used.</b>",
            quote=True
        )
    except Exception as e:
        LOGGER.error(f"Error Processing Reset All Settings Command: {str(e)}")
        await message.reply("<b>🚫 Oops! Couldn’t Delete Settings. ⏳ Try Again Later.</b>", quote=True)       
