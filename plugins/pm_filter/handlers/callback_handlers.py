"""
Callback query handlers for inline keyboard interactions
"""

import asyncio
import math
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified
from services.search_service import handle_search_pagination, handle_quality_filter, handle_season_filter
from services.filter_service import auto_filter
from models.state_manager import state_manager, temp, FRESH, BUTTONS
from ui.keyboard_builders import (
    build_file_buttons, build_quality_buttons, build_season_buttons,
    build_pagination_buttons
)
from ui.message_builders import build_search_caption
from utils.validators import validate_callback_data, validate_user_permission
from utils.helpers import get_size, clean_filename, extract_tag
from config.constants import ERROR_MESSAGES
from logging_helper import LOGGER

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query: CallbackQuery):
    """
    Handle pagination for search results
    
    Args:
        bot: Pyrogram client
        query: Callback query object
    """
    try:
        is_valid, pagination_data = await handle_search_pagination(
            query.data, query.message.chat.id, query.from_user.id
        )
        
        if not is_valid:
            await query.answer(
                ERROR_MESSAGES.get("old_request", "This request has expired"),
                show_alert=True
            )
            return
        
        search_query = pagination_data["search_query"]
        offset = pagination_data["offset"]
        key = pagination_data["key"]
        req_user_id = pagination_data["req_user_id"]
        
        # Get new search results
        files, n_offset, total = await get_search_results(
            query.message.chat.id, search_query, offset=offset, filter=True
        )
        
        if not files:
            await query.answer("No more results found", show_alert=True)
            return
        
        # Store updated files
        await state_manager.store_temp_files(key, files)
        
        settings = await get_settings(query.message.chat.id)
        
        # Build new keyboard
        buttons = build_file_buttons(files, key, settings)
        
        # Add pagination buttons
        max_buttons = 10 if settings.get('max_btn', True) else int(settings.get('max_b_tn', 10))
        pagination_buttons = build_pagination_buttons(
            offset, total, key, req_user_id, max_buttons
        )
        
        if pagination_buttons:
            buttons.append(pagination_buttons)
        
        # Update message based on display mode
        if not settings.get('button', True):
            # Text mode - rebuild caption with file list
            caption = await build_text_mode_caption(
                settings, files, query, total, search_query, offset
            )
            try:
                await query.message.edit_text(
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True,
                    parse_mode="HTML"
                )
            except MessageNotModified:
                pass
        else:
            # Button mode - just update keyboard
            try:
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except MessageNotModified:
                pass
        
        await query.answer()
        
    except Exception as e:
        LOGGER.error(f"Error in next_page: {str(e)}")
        await query.answer("An error occurred", show_alert=True)

@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_cb_handler(client: Client, query: CallbackQuery):
    """
    Handle quality filter selection menu
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        # Validate user permission
        if not await validate_query_user(query):
            return
        
        _, key, offset = query.data.split("#")
        offset = int(offset)
        
        # Build quality selection buttons
        buttons = build_quality_buttons(key, offset)
        
        await query.edit_message_reply_markup(
            InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        LOGGER.error(f"Error in qualities handler: {str(e)}")
        await query.answer("Error loading quality options", show_alert=True)

@Client.on_callback_query(filters.regex(r"^fq#"))
async def filter_qualities_cb_handler(client: Client, query: CallbackQuery):
    """
    Handle quality filter application
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        # Validate user permission
        if not await validate_query_user(query):
            return
        
        is_valid, filter_data = await handle_quality_filter(
            query.data, query.message.chat.id, query.from_user.id
        )
        
        if not is_valid:
            await query.answer("Invalid quality filter", show_alert=True)
            return
        
        # Get filtered search results
        files, n_offset, total_results = await get_search_results(
            query.message.chat.id, 
            filter_data["filtered_search"], 
            offset=filter_data["offset"], 
            filter=True
        )
        
        if not files:
            await query.answer("No files found with this quality filter", show_alert=True)
            return
        
        # Store updated files and search query
        key = filter_data["key"]
        await state_manager.store_temp_files(key, files)
        
        # Update display
        await update_search_display(
            query, files, n_offset, total_results, key, filter_data["filtered_search"]
        )
        
    except Exception as e:
        LOGGER.error(f"Error in quality filter: {str(e)}")
        await query.answer("Error applying quality filter", show_alert=True)

@Client.on_callback_query(filters.regex(r"^seasons#"))
async def season_cb_handler(client: Client, query: CallbackQuery):
    """
    Handle season filter selection menu
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        # Validate user permission
        if not await validate_query_user(query):
            return
        
        _, key, offset = query.data.split("#")
        offset = int(offset)
        
        # Build season selection buttons
        buttons = build_season_buttons(key, offset)
        
        await query.edit_message_reply_markup(
            InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        LOGGER.error(f"Error in seasons handler: {str(e)}")
        await query.answer("Error loading season options", show_alert=True)

@Client.on_callback_query(filters.regex(r"^fs#"))
async def filter_season_cb_handler(client: Client, query: CallbackQuery):
    """
    Handle season filter application
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        # Validate user permission
        if not await validate_query_user(query):
            return
        
        is_valid, filter_data = await handle_season_filter(
            query.data, query.message.chat.id, query.from_user.id
        )
        
        if not is_valid:
            await query.answer("Invalid season filter", show_alert=True)
            return
        
        # Get filtered search results
        files, n_offset, total_results = await get_search_results(
            query.message.chat.id, 
            filter_data["filtered_search"], 
            offset=filter_data["offset"], 
            filter=True
        )
        
        if not files:
            await query.answer("No files found with this season filter", show_alert=True)
            return
        
        # Store updated files and search query
        key = filter_data["key"]
        await state_manager.store_temp_files(key, files)
        
        # Update display
        await update_search_display(
            query, files, n_offset, total_results, key, filter_data["filtered_search"]
        )
        
    except Exception as e:
        LOGGER.error(f"Error in season filter: {str(e)}")
        await query.answer("Error applying season filter", show_alert=True)

@Client.on_callback_query(filters.regex(r"^spol"))
async def advantage_spoll_choker(bot, query: CallbackQuery):
    """
    Handle spell check movie selection
    
    Args:
        bot: Pyrogram client
        query: Callback query object
    """
    try:
        _, movie_id, user = query.data.split('#')
        
        # Validate user
        if int(user) != 0 and query.from_user.id != int(user):
            await query.answer("This isn't your movie request", show_alert=True)
            return
        
        # Get movie details
        movies = await get_poster(movie_id, id=True)
        if not movies:
            await query.answer("Movie not found", show_alert=True)
            return
        
        movie = movies.get('title')
        movie = re.sub(r"[:-]", " ", movie)
        movie = re.sub(r"\s+", " ", movie).strip()
        
        await query.answer("Searching for selected movie...")
        
        # Search for the movie
        files, offset, total_results = await get_search_results(
            query.message.chat.id, movie, offset=0, filter=True
        )
        
        if files:
            # Create spell check result tuple
            k = (movie, files, offset, total_results)
            await auto_filter(bot, query, k)
        else:
            # No results found
            await query.message.edit_text(
                "Sorry, no files found for the selected movie.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔒 Close", callback_data="close_data")
                ]])
            )
            
    except Exception as e:
        LOGGER.error(f"Error in spell check selection: {str(e)}")
        await query.answer("Error processing selection", show_alert=True)

@Client.on_callback_query(filters.regex(r"^file"))
async def file_handler(client: Client, query: CallbackQuery):
    """
    Handle individual file selection
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        ident, file_id = query.data.split("#")
        
        # Validate user permission
        if not await validate_query_user(query):
            return
        
        # Generate file link
        bot_username = client.me.username
        file_link = f"https://t.me/{bot_username}?start=file_{query.message.chat.id}_{file_id}"
        
        await query.answer(url=file_link)
        
    except Exception as e:
        LOGGER.error(f"Error in file handler: {str(e)}")
        await query.answer("Error accessing file", show_alert=True)

@Client.on_callback_query(filters.regex(r"^sendfiles"))
async def send_all_files_handler(client: Client, query: CallbackQuery):
    """
    Handle send all files request
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        ident, key = query.data.split("#")
        
        # Generate all files link
        bot_username = client.me.username
        all_files_link = f"https://telegram.me/{bot_username}?start=allfiles_{query.message.chat.id}_{key}"
        
        await query.answer(url=all_files_link)
        
    except Exception as e:
        LOGGER.error(f"Error in send all files: {str(e)}")
        await query.answer("Error accessing files", show_alert=True)

@Client.on_callback_query(filters.regex(r"^pages"))
async def pages_handler(client: Client, query: CallbackQuery):
    """
    Handle page indicator clicks (no action)
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    await query.answer()

@Client.on_callback_query(filters.regex(r"^close_data"))
async def close_handler(client: Client, query: CallbackQuery):
    """
    Handle close button clicks
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        await query.message.delete()
    except Exception as e:
        LOGGER.error(f"Error closing message: {str(e)}")

# Helper functions
async def validate_query_user(query: CallbackQuery) -> bool:
    """
    Validate if user can interact with the query
    
    Args:
        query: Callback query object
        
    Returns:
        True if user is authorized, False otherwise
    """
    try:
        if query.message.reply_to_message:
            original_user = query.message.reply_to_message.from_user.id
            if int(original_user) != 0 and query.from_user.id != int(original_user):
                await query.answer(
                    f"Hello {query.from_user.first_name}! This isn't your movie request. Please send your own request.",
                    show_alert=True
                )
                return False
        return True
    except:
        return True

async def update_search_display(
    query: CallbackQuery, files: list, n_offset: str, 
    total_results: int, key: str, search_query: str
):
    """
    Update search results display after filtering
    
    Args:
        query: Callback query object
        files: Updated file list
        n_offset: Next offset for pagination
        total_results: Total results count
        key: Search key
        search_query: Current search query
    """
    try:
        settings = await get_settings(query.message.chat.id)
        
        # Build buttons
        buttons = build_file_buttons(files, key, settings)
        
        # Add pagination if needed
        if n_offset and n_offset != "":
            req_user_id = query.from_user.id
            max_buttons = 10 if settings.get('max_btn', True) else int(settings.get('max_b_tn', 10))
            
            pagination_buttons = build_pagination_buttons(
                offset=0, 
                total_results=total_results,
                key=key,
                req_user_id=req_user_id,
                max_buttons=max_buttons
            )
            
            if pagination_buttons:
                buttons.append(pagination_buttons)
        else:
            buttons.append([
                InlineKeyboardButton(text="🚫 That's everything!", callback_data="pages")
            ])
        
        # Update display based on mode
        if not settings.get('button', True):
            # Text mode
            caption = await build_text_mode_caption(
                settings, files, query, total_results, search_query, 0
            )
            try:
                await query.message.edit_text(
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True,
                    parse_mode="HTML"
                )
            except MessageNotModified:
                pass
        else:
            # Button mode
            try:
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except MessageNotModified:
                pass
        
        await query.answer()
        
    except Exception as e:
        LOGGER.error(f"Error updating search display: {str(e)}")

async def build_text_mode_caption(
    settings: dict, files: list, query: CallbackQuery, 
    total_results: int, search_query: str, offset: int
) -> str:
    """
    Build caption for text mode display
    
    Args:
        settings: Chat settings
        files: File list
        query: Callback query object
        total_results: Total results
        search_query: Search query
        offset: Current offset
        
    Returns:
        Formatted caption string
    """
    # Calculate time difference (simplified)
    remaining_seconds = "0.00"
    
    # Build caption using existing function
    caption = build_search_caption(
        search=search_query,
        files=files,
        total_results=total_results,
        user_mention=query.from_user.mention,
        settings=settings
    )
    
    return caption

# Import placeholder functions
async def get_search_results(chat_id, query, offset=0, filter=True):
    """Placeholder - import from database.ia_filterdb"""
    pass

async def get_settings(chat_id):
    """Placeholder - import from utils"""
    pass

async def get_poster(query, id=False):
    """Placeholder - import from utils"""
    pass
