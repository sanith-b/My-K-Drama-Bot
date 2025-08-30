"""
Auto Filter Plugin for My K-Drama Bot

This module handles automatic filtering and searching of K-Drama content
when users send messages to the bot. It searches the database for matching
content and provides inline keyboard results.
"""

import asyncio
import re
from typing import List, Dict, Any
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid

from info import DELETE_TIME, MAX_B_TN,
from database.connections_mdb import active_connection
from utils import get_size, is_subscribed, get_poster, search_gagala, temp as utils_temp
from database.filters_mdb import Media, get_search_results, get_bad_files
from database.users_mdb import get_user, update_user

# Pattern for file names and queries
BUTTONS = {}
SPELL_CHECK = {}
class TempData:
    def __init__(self):
        self.BUTTONS: Dict[int, Dict] = {}
        self.SPELL_CHECK: Dict[int, bool] = {}
        self.USER_SESSIONS: Dict[int, Any] = {}
        self.INVITE_LINK = os.environ.get("INVITE_LINK", "")

temp = TempData()

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(bot, message: Message):
    """
    Main auto filter function that processes incoming messages
    and searches for K-Drama content automatically
    """
    # Skip if message is from a bot
    if message.from_user and message.from_user.is_bot:
        return
    
    # Get group settings
    group_id = message.chat.id
    name = message.text
    
    # Skip if auto filter is disabled for this group
    k = await is_subscribed(bot, message)
    if k == False:
        btn = [[
            InlineKeyboardButton('🤖 Join Updates Channel', url=temp.INVITE_LINK)
        ]]
        if message.from_user:
            try:
                await message.reply_text(
                    "**You are not in our back-up channel given below so you do not get result from this bot. First join and try again.**",
                    reply_markup=InlineKeyboardMarkup(btn),
                    parse_mode=enums.ParseMode.MARKDOWN
                )
            except:
                pass
        return
    
    # Clean and prepare search query
    name = re.sub(r"[+\-!@#$%^&*()_{}|\"'?.,;`~\[\]\\]", " ", name).strip()
    name = re.sub(r"\s+", " ", name)  # Remove extra spaces
    
    # Skip very short queries
    if len(name) < 2:
        return
    
    # Search for files in database
    files, offset, total_results = await get_search_results(name, max_results=10)
    
    if not files:
        # No results found - check for spelling suggestions
        if temp.SPELL_CHECK.get(message.from_user.id):
            return
        
        # Try spell check or similar search
        is_misspelled = await search_gagala(name)
        if is_misspelled:
            btn = [[
                InlineKeyboardButton("Search Google", url=f"https://www.google.com/search?q={name}")
            ]]
            await message.reply_text(
                f"**I couldn't find anything related to '{name}'. Check the spelling or try searching on Google.**",
                reply_markup=InlineKeyboardMarkup(btn)
            )
        return
    
    # Create pagination buttons
    pre = 'filep' if settings['file_secure'] else 'file'
    
    if total_results == 1:
        # Single result - send directly
        await send_single_result(bot, message, files[0], name)
    else:
        # Multiple results - send with pagination
        await send_multiple_results(bot, message, files, name, total_results, offset)

async def send_single_result(bot: Client, message: Message, file: Media, query: str):
    """Send a single file result"""
    try:
        file_caption = f"**File Name:** `{file.file_name}`\n**Size:** `{get_size(file.file_size)}`"
        
        btn = [[
            InlineKeyboardButton("📁 Get File", callback_data=f"file#{file.file_id}"),
        ]]
        
        # Add more info button if available
        if file.caption:
            btn.append([
                InlineKeyboardButton("ℹ️ More Info", callback_data=f"info#{file.file_id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(btn)
        
        k = await message.reply_text(
            text=file_caption,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        # Auto-delete message after specified time
        if DELETE_TIME:
            await asyncio.sleep(DELETE_TIME)
            await k.delete()
            
    except Exception as e:
        print(f"Error sending single result: {e}")

async def send_multiple_results(bot: Client, message: Message, files: List[Media], 
                              query: str, total_results: int, offset: int):
    """Send multiple file results with pagination"""
    try:
        # Create file buttons
        btn = []
        for file in files:
            btn.append([
                InlineKeyboardButton(
                    f"📁 {file.file_name[:35]}...",
                    callback_data=f"file#{file.file_id}"
                )
            ])
        
        # Add pagination buttons if needed
        nav_buttons = []
        if offset > 0:
            nav_buttons.append(
                InlineKeyboardButton("⬅️ Previous", callback_data=f"next_{query}_{offset-10}")
            )
        if offset + 10 < total_results:
            nav_buttons.append(
                InlineKeyboardButton("Next ➡️", callback_data=f"next_{query}_{offset+10}")
            )
        
        if nav_buttons:
            btn.append(nav_buttons)
        
        # Add close button
        btn.append([
            InlineKeyboardButton("❌ Close", callback_data="close_data")
        ])
        
        reply_markup = InlineKeyboardMarkup(btn)
        
        caption = f"**Found {total_results} results for:** `{query}`\n**Showing:** `{offset+1}-{min(offset+10, total_results)}`"
        
        k = await message.reply_text(
            text=caption,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        # Store message info for pagination
        temp.BUTTONS[k.id] = {
            'query': query,
            'total': total_results,
            'files': files
        }
        
        # Auto-delete message after specified time
        if DELETE_TIME:
            await asyncio.sleep(DELETE_TIME)
            try:
                await k.delete()
                if k.id in temp.BUTTONS:
                    del temp.BUTTONS[k.id]
            except:
                pass
                
    except Exception as e:
        print(f"Error sending multiple results: {e}")

@Client.on_callback_query(filters.regex(r"^next_"))
async def next_page(bot: Client, query: CallbackQuery):
    """Handle pagination for search results"""
    try:
        _, search_query, offset = query.data.split('_', 2)
        offset = int(offset)
        
        # Search for files with new offset
        files, _, total_results = await get_search_results(search_query, offset=offset, max_results=10)
        
        if not files:
            await query.answer("No more results!", show_alert=True)
            return
        
        # Create new buttons
        btn = []
        for file in files:
            btn.append([
                InlineKeyboardButton(
                    f"📁 {file.file_name[:35]}...",
                    callback_data=f"file#{file.file_id}"
                )
            ])
        
        # Navigation buttons
        nav_buttons = []
        if offset > 0:
            nav_buttons.append(
                InlineKeyboardButton("⬅️ Previous", callback_data=f"next_{search_query}_{offset-10}")
            )
        if offset + 10 < total_results:
            nav_buttons.append(
                InlineKeyboardButton("Next ➡️", callback_data=f"next_{search_query}_{offset+10}")
            )
        
        if nav_buttons:
            btn.append(nav_buttons)
        
        btn.append([
            InlineKeyboardButton("❌ Close", callback_data="close_data")
        ])
        
        reply_markup = InlineKeyboardMarkup(btn)
        caption = f"**Found {total_results} results for:** `{search_query}`\n**Showing:** `{offset+1}-{min(offset+10, total_results)}`"
        
        await query.edit_message_text(
            text=caption,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
    except Exception as e:
        print(f"Error in pagination: {e}")
        await query.answer("Error occurred!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^file#"))
async def send_file(bot: Client, query: CallbackQuery):
    """Handle file sending when user clicks on a file button"""
    try:
        file_id = query.data.split('#')[1]
        
        # Get file details from database
        file = await Media.get(file_id)
        if not file:
            await query.answer("File not found!", show_alert=True)
            return
        
        # Check if user is subscribed (if required)
        if not await is_subscribed(bot, query.message):
            await query.answer("Join our channel first!", show_alert=True)
            return
        
        # Send the file
        caption = f"**{file.file_name}**\n\n**Size:** `{get_size(file.file_size)}`\n**Join:** @YourChannel"
        
        await bot.send_cached_media(
            chat_id=query.from_user.id,
            file_id=file.file_id,
            caption=caption,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        await query.answer("File sent to your PM!", show_alert=True)
        
    except UserIsBlocked:
        await query.answer("Start me in PM first!", show_alert=True)
    except PeerIdInvalid:
        await query.answer("Start me in PM first!", show_alert=True)
    except Exception as e:
        print(f"Error sending file: {e}")
        await query.answer("Error occurred!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^close_data"))
async def close_data(bot: Client, query: CallbackQuery):
    """Close/delete the search results message"""
    try:
        await query.message.delete()
    except:
        await query.message.edit_text("**Closed!**")

# Helper function to check group settings
async def get_group_settings(group_id: int) -> Dict[str, Any]:
    """Get group-specific settings"""
    # This would connect to your database and get group settings
    # Placeholder implementation
    return {
        'auto_filter': True,
        'file_secure': False,
        'auto_delete': True,
        'spell_check': True
    }

# Add this filter to the available filters list
__filter_info__ = {
    'name': 'auto_filter',
    'description': 'Automatic K-Drama content filtering and search',
    'version': '1.0.0',
    'handlers': [
        'give_filter',
        'next_page', 
        'send_file',
        'close_data'
    ]
}
