"""
Settings handlers for group configuration management
"""

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import enums
from ui.keyboard_builders import build_settings_buttons
from ui.message_builders import build_settings_message
from utils.validators import validate_chat_id
from logging_helper import LOGGER

@Client.on_callback_query(filters.regex(r"^opnsetgrp"))
async def open_group_settings(client: Client, query: CallbackQuery):
    """
    Open group settings in the same chat
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        
        # Validate chat ID
        is_valid, parsed_grp_id = validate_chat_id(grp_id)
        if not is_valid:
            await query.answer("Invalid group ID", show_alert=True)
            return
        
        # Check admin permissions
        if not await is_check_admin(client, parsed_grp_id, user_id):
            await query.answer("You don't have enough rights to do this!", show_alert=True)
            return
        
        # Get group info and settings
        try:
            group_chat = await client.get_chat(parsed_grp_id)
            title = group_chat.title
        except:
            title = "Unknown Group"
        
        settings = await get_settings(parsed_grp_id)
        if not settings:
            await query.answer("Settings not found", show_alert=True)
            return
        
        # Build settings buttons
        buttons = build_settings_buttons(parsed_grp_id, settings)
        
        # Update message
        await query.message.edit_text(
            text=build_settings_message(title, settings),
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        LOGGER.error(f"Error in open_group_settings: {str(e)}")
        await query.answer("Error loading settings", show_alert=True)

@Client.on_callback_query(filters.regex(r"^opnsetpm"))
async def open_pm_settings(client: Client, query: CallbackQuery):
    """
    Send group settings to user's PM
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        _, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        
        # Validate chat ID
        is_valid, parsed_grp_id = validate_chat_id(grp_id)
        if not is_valid:
            await query.answer("Invalid group ID", show_alert=True)
            return
        
        # Check admin permissions
        if not await is_check_admin(client, parsed_grp_id, user_id):
            await query.answer("You don't have enough rights to do this!", show_alert=True)
            return
        
        # Get group info and settings
        try:
            group_chat = await client.get_chat(parsed_grp_id)
            title = group_chat.title
        except:
            title = "Unknown Group"
        
        settings = await get_settings(parsed_grp_id)
        if not settings:
            await query.answer("Settings not found", show_alert=True)
            return
        
        # Update current message to show PM sent
        bot_username = client.me.username
        btn = [[
            InlineKeyboardButton("📩 Check My DM!", url=f"telegram.me/{bot_username}")
        ]]
        
        await query.message.edit_text(
            f"Your settings menu for {title} has been sent to your DM!",
            reply_markup=InlineKeyboardMarkup(btn)
        )
        
        # Send settings to PM
        buttons = build_settings_buttons(parsed_grp_id, settings)
        
        await client.send_message(
            chat_id=user_id,
            text=build_settings_message(title, settings),
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        LOGGER.error(f"Error in open_pm_settings: {str(e)}")
        await query.answer("Error sending settings to PM", show_alert=True)

@Client.on_callback_query(filters.regex(r"^setgs"))
async def toggle_settings(client: Client, query: CallbackQuery):
    """
    Toggle individual group settings
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        ident, set_type, status, grp_id = query.data.split("#")
        user_id = query.from_user.id if query.from_user else None
        
        # Validate chat ID
        is_valid, parsed_grp_id = validate_chat_id(grp_id)
        if not is_valid:
            await query.answer("Invalid group ID", show_alert=True)
            return
        
        # Check admin permissions
        if not await is_check_admin(client, parsed_grp_id, user_id):
            await query.answer("You don't have enough rights to do this!", show_alert=True)
            return
        
        # Toggle setting
        current_status = status == "True"
        new_status = not current_status
        
        # Save new setting
        await save_group_settings(parsed_grp_id, set_type, new_status)
        
        # Get updated settings
        settings = await get_settings(parsed_grp_id)
        
        # Update keyboard
        buttons = build_settings_buttons(parsed_grp_id, settings)
        
        try:
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except:
            pass
        
        # Show feedback
        status_text = "ON ✓" if new_status else "OFF ✗"
        await query.answer(status_text)
        
    except Exception as e:
        LOGGER.error(f"Error in toggle_settings: {str(e)}")
        await query.answer("Error updating setting", show_alert=True)

@Client.on_callback_query(filters.regex(r"^log_setgs"))
async def log_channel_settings(client: Client, query: CallbackQuery):
    """
    Handle log channel settings (placeholder)
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        _, grp_id = query.data.split("#")
        
        # For now, just show a message
        await query.answer("Log channel settings coming soon!", show_alert=True)
        
    except Exception as e:
        LOGGER.error(f"Error in log_channel_settings: {str(e)}")
        await query.answer("Error accessing log settings", show_alert=True)

@Client.on_callback_query(filters.regex(r"^caption_setgs"))
async def caption_settings(client: Client, query: CallbackQuery):
    """
    Handle caption settings (placeholder)
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        _, grp_id = query.data.split("#")
        
        # For now, just show a message
        await query.answer("Caption settings coming soon!", show_alert=True)
        
    except Exception as e:
        LOGGER.error(f"Error in caption_settings: {str(e)}")
        await query.answer("Error accessing caption settings", show_alert=True)

# Import placeholder functions
async def is_check_admin(client, chat_id, user_id):
    """Placeholder - import from utils"""
    # Check if user is admin in the chat
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except:
        return False

async def get_settings(chat_id):
    """Placeholder - import from utils"""
    # Return default settings for now
    return {
        "button": True,
        "file_secure": False,
        "imdb": True,
        "welcome": True,
        "auto_delete": False,
        "max_btn": True,
        "spell_check": True
    }

async def save_group_settings(chat_id, setting_key, setting_value):
    """Placeholder - import from utils"""
    # Save setting to database
    pass
