"""
Message handlers for group and private messages
"""

import asyncio
import re
import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.filter_service import auto_filter
from models.state_manager import state_manager
from ui.message_builders import (
    build_maintenance_message, build_support_group_message, 
    build_pm_search_disabled_message
)
from utils.validators import validate_search_query
from config.constants import ERROR_MESSAGES, URL_PATTERN
from logging_helper import LOGGER

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    """
    Handle group messages for auto-filtering
    
    Args:
        client: Pyrogram client
        message: Incoming message
    """
    try:
        bot_id = client.me.id
        
        # React with emoji if enabled
        if hasattr(client, 'EMOJI_MODE') and client.EMOJI_MODE:
            try:
                from config.constants import REACTIONS
                await message.react(emoji=random.choice(REACTIONS))
            except Exception:
                pass
        
        # Check maintenance mode
        maintenance_mode = await db.get_maintenance_status(bot_id)
        if maintenance_mode and message.from_user.id not in client.ADMINS:
            await message.reply_text(
                build_maintenance_message(),
                disable_web_page_preview=True
            )
            return
        
        # Update user statistics
        await update_user_stats(message.from_user.id, message.text)
        
        # Handle support group differently
        if message.chat.id == client.SUPPORT_CHAT_ID:
            await handle_support_group_message(client, message)
            return
        
        # Get group settings
        settings = await get_settings(message.chat.id)
        if not settings.get('auto_ffilter', True):
            return
        
        # Check for URLs and handle admin permissions
        if re.search(URL_PATTERN, message.text):
            if await is_check_admin(client, message.chat.id, message.from_user.id):
                return
            return await message.delete()
        
        # Process auto-filter
        await auto_filter(client, message)
        
    except Exception as e:
        LOGGER.error(f"Error in give_filter: {str(e)}")

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_text(bot, message):
    """
    Handle private messages
    
    Args:
        bot: Pyrogram client
        message: Incoming message
    """
    try:
        bot_id = bot.me.id
        content = message.text
        user = message.from_user.first_name
        user_id = message.from_user.id
        
        # React with emoji if enabled
        if hasattr(bot, 'EMOJI_MODE') and bot.EMOJI_MODE:
            try:
                from config.constants import REACTIONS
                await message.react(emoji=random.choice(REACTIONS))
            except Exception:
                pass
        
        # Check maintenance mode
        maintenance_mode = await db.get_maintenance_status(bot_id)
        if maintenance_mode and message.from_user.id not in bot.ADMINS:
            await message.reply_text(
                build_maintenance_message(),
                disable_web_page_preview=True
            )
            return
        
        # Skip commands
        if content.startswith(("/", "#")):
            return
        
        # Update user statistics
        await update_user_stats(user_id, content)
        
        # Check if PM search is enabled
        pm_search = await db.pm_search_status(bot_id)
        if pm_search:
            await auto_filter(bot, message)
        else:
            await message.reply_text(
                text=build_pm_search_disabled_message(),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔍 Start Search", url=bot.GRP_LNK)
                ]])
            )
            
    except Exception as e:
        LOGGER.error(f"Error in pm_text: {str(e)}")

async def handle_support_group_message(client, message):
    """
    Handle messages in support group
    
    Args:
        client: Pyrogram client
        message: Message in support group
    """
    try:
        search = message.text
        
        # Quick search to check if files exist
        temp_files, temp_offset, total_results = await get_search_results(
            chat_id=message.chat.id, 
            query=search.lower(), 
            offset=0, 
            filter=True
        )
        
        if total_results == 0:
            return
        
        # Send support group response
        await message.reply_text(
            build_support_group_message(
                user_mention=message.from_user.mention,
                total_results=total_results,
                search=search,
                group_link=client.GRP_LNK
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚡ Join & Explore 🔍", url=client.GRP_LNK)
            ]])
        )
        
    except Exception as e:
        LOGGER.error(f"Error in support group handler: {str(e)}")

async def update_user_stats(user_id: int, message_text: str):
    """
    Update user statistics and top messages
    
    Args:
        user_id: User ID
        message_text: Message content
    """
    try:
        from database.topdb import silentdb
        await silentdb.update_top_messages(user_id, message_text)
    except Exception as e:
        LOGGER.error(f"Error updating user stats: {str(e)}")

# Import placeholder functions
async def get_search_results(chat_id, query, offset=0, filter=True):
    """Placeholder - import from database.ia_filterdb"""
    pass

async def get_settings(chat_id):
    """Placeholder - import from utils"""
    pass

async def is_check_admin(client, chat_id, user_id):
    """Placeholder - import from utils"""
    pass

# Import db object
try:
    from database.users_chats_db import db
except ImportError:
    db = None
