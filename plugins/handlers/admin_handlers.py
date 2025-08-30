# handlers/admin_handlers.py

import asyncio
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from info import ADMINS, temp
from Script import script
from utils import get_settings, save_group_settings, is_check_admin, group_setting_buttons
from database.ia_filterdb import Media, Media2, get_bad_files
from database.users_chats_db import db

logger = logging.getLogger(__name__)

# Global lock for database operations
lock = asyncio.Lock()


@Client.on_callback_query(filters.regex(r"^autofilter_delete"))
async def autofilter_delete_callback(client, query):
    """Handle complete database deletion"""
    await Media.collection.drop()
    if hasattr(__import__('info'), 'MULTIPLE_DB') and __import__('info').MULTIPLE_DB:
        await Media2.collection.drop()
    
    await query.answer("Eᴠᴇʀʏᴛʜɪɴɢ's Gᴏɴᴇ")
    await query.message.edit('ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ᴀʟʟ ɪɴᴅᴇxᴇᴅ ꜰɪʟᴇꜱ ✅')


@Client.on_callback_query(filters.regex(r"^killfilesdq"))
async def killfiles_callback(client, query):
    """Handle selective file deletion by keyword"""
    ident, keyword = query.data.split("#")
    
    await query.message.edit_text(
        f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>"
    )
    
    files, total = await get_bad_files(keyword)
    await query.message.edit_text(
        "<b>ꜰɪʟᴇ ᴅᴇʟᴇᴛɪᴏɴ ᴘʀᴏᴄᴇꜱꜱ ᴡɪʟʟ ꜱᴛᴀʀᴛ ɪɴ 5 ꜱᴇᴄᴏɴᴅꜱ !</b>"
    )
    await asyncio.sleep(5)
    
    deleted = 0
    async with lock:
        try:
            for file in files:
                file_ids = file.file_id
                file_name = file.file_name
                
                result = await Media.collection.delete_one({'_id': file_ids})
                
                if not result.deleted_count and hasattr(__import__('info'), 'MULTIPLE_DB') and __import__('info').MULTIPLE_DB:
                    result = await Media2.collection.delete_one({'_id': file_ids})
                
                if result.deleted_count:
                    logger.info(
                        f'ꜰɪʟᴇ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ {keyword}! ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ {file_name} ꜰʀᴏᴍ ᴅᴀᴛᴀʙᴀꜱᴇ.'
                    )
                
                deleted += 1
                
                if deleted % 20 == 0:
                    await query.message.edit_text(
                        f"<b>ᴘʀᴏᴄᴇꜱꜱ ꜱᴛᴀʀᴛᴇᴅ ꜰᴏʀ ᴅᴇʟᴇᴛɪɴɢ ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ. ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ {str(deleted)} ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ ꜰᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ {keyword} !\n\nᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ...</b>"
                    )
                    
        except Exception as e:
            logger.exception(f"Error In killfiledq - {e}")
            await query.message.edit_text(f'Error: {e}')
        else:
            await query.message.edit_text(
                f"<b>ᴘʀᴏᴄᴇꜱꜱ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ꜰᴏʀ ꜰɪʟᴇ ᴅᴇʟᴇᴛᴀᴛɪᴏɴ !\n\nꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ {str(deleted)} ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ ꜰᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ {keyword}.</b>"
            )


@Client.on_callback_query(filters.regex(r"^opnsetgrp"))
async def open_group_settings(client, query):
    """Open group settings in group chat"""
    ident, grp_id = query.data.split("#")
    userid = query.from_user.id if query.from_user else None
    
    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
        and str(userid) not in ADMINS
    ):
        await query.answer("ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ʀɪɢʜᴛꜱ ᴛᴏ ᴅᴏ ᴛʜɪꜱ !", show_alert=True)
        return
    
    title = query.message.chat.title
    buttons = await build_settings_buttons(grp_id)
    
    await query.message.edit_text(
        text=f"<b>ᴄʜᴀɴɢᴇ ʏᴏᴜʀ ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ {title} ᴀꜱ ʏᴏᴜ ᴡɪꜱʜ ⚙</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex(r"^opnsetpm"))
async def open_pm_settings(client, query):
    """Send group settings to PM"""
    ident, grp_id = query.data.split("#")
    userid = query.from_user.id if query.from_user else None
    
    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
        and str(userid) not in ADMINS
    ):
        await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)
        return
    
    title = query.message.chat.title
    btn2 = [[
        InlineKeyboardButton(
            "ᴄʜᴇᴄᴋ ᴍʏ ᴅᴍ 🗳️", 
            url=f"telegram.me/{temp.U_NAME}"
        )
    ]]
    
    await query.message.edit_text(
        f"<b>ʏᴏᴜʀ sᴇᴛᴛɪɴɢs ᴍᴇɴᴜ ғᴏʀ {title} ʜᴀs ʙᴇᴇɴ sᴇɴᴛ ᴛᴏ ʏᴏᴜ ʙʏ ᴅᴍ.</b>",
        reply_markup=InlineKeyboardMarkup(btn2)
    )
    
    buttons = await build_settings_buttons(grp_id)
    
    await client.send_message(
        chat_id=userid,
        text=f"<b>ᴄʜᴀɴɢᴇ ʏᴏᴜʀ ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ {title} ᴀꜱ ʏᴏᴜ ᴡɪꜱʜ ⚙</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML,
        reply_to_message_id=query.message.id
    )


@Client.on_callback_query(filters.regex(r"^grp_pm"))
async def group_pm_callback(client, query):
    """Handle group selection for PM settings"""
    _, grp_id = query.data.split("#")
    user_id = query.from_user.id if query.from_user else None
    
    if not await is_check_admin(client, int(grp_id), user_id):
        return await query.answer(script.NT_ADMIN_ALRT_TXT, show_alert=True)

    btn = await group_setting_buttons(int(grp_id))
    dreamx = await client.get_chat(int(grp_id))
    
    await query.message.edit(
        text=f"ᴄʜᴀɴɢᴇ ʏᴏᴜʀ ɢʀᴏᴜᴘ ꜱᴇᴛᴛɪɴɢꜱ ✅\nɢʀᴏᴜᴘ ɴᴀᴍᴇ - '{dreamx.title}'</b>⚙", 
        reply_markup=InlineKeyboardMarkup(btn)
    )


@Client.on_callback_query(filters.regex(r"^removegrp"))
async def remove_group_callback(client, query):
    """Remove group from connections"""
    user_id = query.from_user.id
    data = query.data
    grp_id = int(data.split("#")[1])
    
    if not await is_check_admin(client, grp_id, query.from_user.id):
        return await query.answer(script.NT_ADMIN_ALRT_TXT, show_alert=True)
    
    await db.remove_group_connection(grp_id, user_id)
    await query.answer("Group removed from your connections.", show_alert=True)
    
    connected_groups = await db.get_connected_grps(user_id)
    if not connected_groups:
        await query.edit_message_text("Nᴏ Cᴏɴɴᴇᴄᴛᴇᴅ Gʀᴏᴜᴘs Fᴏᴜɴᴅ.")
        return
    
    group_list = []
    for group in connected_groups:
        try:
            Chat = await client.get_chat(group)
            group_list.append([
                InlineKeyboardButton(
                    text=Chat.title, 
                    callback_data=f"grp_pm#{Chat.id}"
                )
            ])
        except Exception as e:
            print(f"Error In PM Settings Button - {e}")
            pass
    
    await query.edit_message_text(
        "⚠️ ꜱᴇʟᴇᴄᴛ ᴛʜᴇ ɢʀᴏᴜᴘ ᴡʜᴏꜱᴇ ꜱᴇᴛᴛɪɴɢꜱ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴄʜᴀɴɢᴇ.\n\n"
        "ɪꜰ ʏᴏᴜʀ ɢʀᴏᴜᴘ ɪꜱ ɴᴏᴛ ꜱʜᴏᴡɪɴɢ ʜᴇʀᴇ,\n"
        "ᴜꜱᴇ /reload ɪɴ ᴛʜᴀᴛ ɢʀᴏᴜᴘ ᴀɴᴅ ɪᴛ ᴡɪʟʟ ᴀᴘᴘᴇᴀʀ ʜᴇʀᴇ.",
        reply_markup=InlineKeyboardMarkup(group_list)
    )


@Client.on_callback_query(filters.regex(r"^setgs"))
async def settings_callback(client, query):
    """Handle individual setting changes"""
    ident, set_type, status, grp_id = query.data.split("#")
    userid = query.from_user.id if query.from_user else None
    
    if not await is_check_admin(client, int(grp_id), userid):
        await query.answer(script.NT_ADMIN_ALRT_TXT, show_alert=True)
        return
    
    if status == "True":
        await save_group_settings(int(grp_id), set_type, False)
        await query.answer("ᴏꜰꜰ ✗")
    else:
        await save_group_settings(int(grp_id), set_type, True)
        await query.answer("ᴏɴ ✓")
    
    # Refresh the buttons
    buttons = await build_settings_buttons(grp_id)
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))


async def build_settings_buttons(grp_id):
    """Build settings buttons for a group"""
    settings = await get_settings(grp_id)
    if settings is None:
        return []

    buttons = [
        [
            InlineKeyboardButton('ʀᴇꜱᴜʟᴛ ᴘᴀɢᴇ',
                                 callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}'),
            InlineKeyboardButton('ʙᴜᴛᴛᴏɴ' if settings.get("button") else 'ᴛᴇxᴛ',
                                 callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('ꜰɪʟᴇ ꜱᴇᴄᴜʀᴇ',
                                 callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
            InlineKeyboardButton('✔ Oɴ' if settings["file_secure"] else '✘ Oғғ',
                                 callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton(
                'ɪᴍᴅʙ ᴘᴏꜱᴛᴇʀ', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
            InlineKeyboardButton('✔ Oɴ' if settings["imdb"] else '✘ Oғғ',
                                 callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton(
                'ᴡᴇʟᴄᴏᴍᴇ ᴍꜱɢ', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
            InlineKeyboardButton('✔ Oɴ' if settings["welcome"] else '✘ Oғғ',
                                 callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ',
                                 callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
            InlineKeyboardButton('✔ Oɴ' if settings["auto_delete"] else '✘ Oғғ',
                                 callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('ᴍᴀx ʙᴜᴛᴛᴏɴꜱ',
                                 callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
            InlineKeyboardButton('10' if settings["max_btn"] else f'{getattr(__import__("info"), "MAX_B_TN", "20")}',
                                 callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('ꜱᴘᴇʟʟ ᴄʜᴇᴄᴋ',
                                 callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
            InlineKeyboardButton('✔ Oɴ' if settings["spell_check"] else '✘ Oғғ',
                                 callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton(
                'Vᴇʀɪғʏ', callback_data=f'setgs#is_verify#{settings.get("is_verify", getattr(__import__("info"), "IS_VERIFY", False))}#{grp_id}'),
            InlineKeyboardButton('✔ Oɴ' if settings.get("is_verify", getattr(__import__("info"), "IS_VERIFY", False)) else '✘ Oғғ',
                                 callback_data=f'setgs#is_verify#{settings.get("is_verify", getattr(__import__("info"), "IS_VERIFY", False))}#{grp_id}'),
        ],
        [
            InlineKeyboardButton(
                "❌ Remove ❌ ", callback_data=f"removegrp#{grp_id}")
        ],
        [
            InlineKeyboardButton('⇋ ᴄʟᴏꜱᴇ ꜱᴇᴛᴛɪɴɢꜱ ᴍᴇɴᴜ ⇋',
                                 callback_data='close_data'
                                 )
        ]
    ]
    return buttons


@Client.on_callback_query(filters.regex(r"^delallcancel"))
async def delete_all_cancel_callback(client, query):
    """Handle cancel delete all callback"""
    userid = query.from_user.id
    chat_type = query.message.chat.type
    
    if chat_type == enums.ChatType.PRIVATE:
        await query.message.reply_to_message.delete()
        await query.message.delete()
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = query.message.chat.id
        st = await client.get_chat_member(grp_id, userid)
        if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
            await query.message.delete()
            try:
                await query.message.reply_to_message.delete()
            except:
                pass
        else:
            await query.answer("Tʜᴀᴛ's ɴᴏᴛ ғᴏʀ ʏᴏᴜ!!", show_alert=True)
