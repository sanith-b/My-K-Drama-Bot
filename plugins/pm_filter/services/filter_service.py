"""
Core filtering service for auto-filtering messages and spell checking
"""

import asyncio
import re
from typing import List, Dict, Any, Tuple, Optional, Union
from fuzzywuzzy import process
from models.state_manager import state_manager, temp
from services.search_service import process_search_query, build_search_key
from ui.message_builders import (
    build_search_caption, build_search_progress_message, 
    build_ai_spell_check_message, build_spell_correction_message,
    build_no_results_message, build_spell_check_message
)
from ui.keyboard_builders import build_file_buttons, build_pagination_buttons, build_spell_check_buttons
from utils.helpers import replace_words, clean_search_query, get_size, clean_filename
from utils.validators import validate_search_query
from config.constants import AUTO_DELETE_TIME, SPELL_CHECK_TIMEOUT

async def auto_filter(client, msg, spoll: Union[bool, Tuple] = False) -> None:
    """
    Main auto-filtering function for processing search requests
    
    Args:
        client: Pyrogram client
        msg: Message object or callback query
        spoll: Spell check data or False
    """
    try:
        if not spoll:
            # Regular message processing
            message = msg
            
            # Validate message
            if not message.text or message.text.startswith("/"):
                return
            
            # Check for command patterns
            if re.findall(r"((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
                return
            
            # Process search query
            if len(message.text) < 100:
                is_valid, search_query = await process_search_query(message.text)
                if not is_valid:
                    return
                
                # Show search progress
                progress_msg = await message.reply_text(
                    build_search_progress_message(message.from_user.mention, search_query),
                    reply_to_message_id=message.id
                )
                
                # Get search results
                files, offset, total_results = await get_search_results(
                    message.chat.id, search_query, offset=0, filter=True
                )
                
                settings = await get_settings(message.chat.id)
                
                # Handle no results
                if not files:
                    if settings.get("spell_check", True):
                        await handle_spell_check(client, message, search_query, progress_msg)
                        return
                    else:
                        await progress_msg.edit_text(
                            build_no_results_message(search_query, message.from_user.mention)
                        )
                        await asyncio.sleep(SPELL_CHECK_TIMEOUT)
                        await progress_msg.delete()
                        return
            else:
                return
        else:
            # Spell check callback processing
            message = msg.message.reply_to_message
            search_query, files, offset, total_results = spoll
            progress_msg = await message.reply_text(
                build_search_progress_message(message.from_user.mention, search_query),
                reply_to_message_id=message.id
            )
            settings = await get_settings(message.chat.id)
            await msg.message.delete()
        
        # Store search data
        key = await build_search_key(message.chat.id, message.id)
        await state_manager.store_search_query(key, search_query)
        await state_manager.store_temp_files(key, files)
        await state_manager.store_user_shortcut(message.from_user.id, message.chat.id)
        
        # Build response
        await build_search_response(
            client, message, progress_msg, search_query, files, 
            offset, total_results, key, settings
        )
        
    except Exception as e:
        from logging_helper import LOGGER
        LOGGER.error(f"Error in auto_filter: {str(e)}")

async def handle_spell_check(client, message, search_query: str, progress_msg) -> None:
    """
    Handle spell checking when no results found
    
    Args:
        client: Pyrogram client
        message: Original message
        search_query: Search query that returned no results
        progress_msg: Progress message to edit
    """
    try:
        # Show AI spell check progress
        await progress_msg.edit_text(build_ai_spell_check_message())
        
        # Perform AI spell check
        corrected_query = await ai_spell_check(message.chat.id, search_query)
        
        if corrected_query:
            # Show correction and search again
            await progress_msg.edit_text(
                build_spell_correction_message(corrected_query)
            )
            await asyncio.sleep(2)
            
            # Create new message object with corrected query
            message.text = corrected_query
            await progress_msg.delete()
            return await auto_filter(client, message)
        
        # Fall back to manual spell check suggestions
        await progress_msg.delete()
        await advantage_spell_chok(client, message)
        
    except Exception as e:
        from logging_helper import LOGGER
        LOGGER.error(f"Error in spell check: {str(e)}")
        await progress_msg.delete()

async def ai_spell_check(chat_id: int, wrong_name: str) -> Optional[str]:
    """
    AI-powered spell checking using IMDB search
    
    Args:
        chat_id: Chat ID for search context
        wrong_name: Potentially misspelled query
        
    Returns:
        Corrected query or None if no correction found
    """
    try:
        # Import here to avoid circular imports
        from utils import get_poster
        
        # Search for movie suggestions
        async def search_movie(query):
            try:
                search_results = await get_poster(query, bulk=True)
                return [movie['title'] for movie in search_results] if search_results else []
            except:
                return []
        
        movie_list = await search_movie(wrong_name)
        if not movie_list:
            return None
        
        # Try to find best matches
        for _ in range(5):
            closest_match = process.extractOne(wrong_name, movie_list)
            if not closest_match or closest_match[1] <= 80:
                return None
            
            movie = closest_match[0]
            
            # Test if this correction returns results
            files, _, total_results = await get_search_results(
                chat_id=chat_id, query=movie
            )
            
            if files and total_results > 0:
                return movie
            
            # Remove this option and try next
            movie_list.remove(movie)
        
        return None
        
    except Exception as e:
        from logging_helper import LOGGER
        LOGGER.error(f"Error in AI spell check: {str(e)}")
        return None

async def advantage_spell_chok(client, message) -> None:
    """
    Manual spell check with movie suggestions
    
    Args:
        client: Pyrogram client
        message: Original message
    """
    try:
        search = message.text
        chat_id = message.chat.id
        
        # Clean query for movie search
        query = clean_search_query(search) + " movie"
        
        # Get movie suggestions
        try:
            from utils import get_poster
            movies = await get_poster(search, bulk=True)
        except:
            # Send error message
            error_msg = await message.reply(
                build_no_results_message(search, message.from_user.mention)
            )
            await asyncio.sleep(SPELL_CHECK_TIMEOUT)
            await error_msg.delete()
            return
        
        if not movies:
            # No suggestions found
            error_msg = await message.reply(
                build_no_results_message(search, message.from_user.mention)
            )
            await asyncio.sleep(SPELL_CHECK_TIMEOUT)
            await error_msg.delete()
            return
        
        # Show spell check suggestions
        user_id = message.from_user.id if message.from_user else 0
        buttons = build_spell_check_buttons(movies, user_id)
        
        suggestion_msg = await message.reply_text(
            build_spell_check_message(search, message.from_user.mention),
            reply_markup=InlineKeyboardMarkup(buttons),
            reply_to_message_id=message.id
        )
        
        # Auto-delete after timeout
        await asyncio.sleep(SPELL_CHECK_TIMEOUT)
        await suggestion_msg.delete()
        
    except Exception as e:
        from logging_helper import LOGGER
        LOGGER.error(f"Error in advantage_spell_chok: {str(e)}")

async def build_search_response(
    client, message, progress_msg, search_query: str, files: List,
    offset: str, total_results: int, key: str, settings: Dict
) -> None:
    """
    Build and send the search response with files
    
    Args:
        client: Pyrogram client
        message: Original message
        progress_msg: Progress message to edit
        search_query: Search query
        files: Found files
        offset: Pagination offset
        total_results: Total results count
        key: Search key
        settings: Chat settings
    """
    try:
        from datetime import datetime, timedelta
        import pytz
        from pyrogram.types import InlineKeyboardMarkup
        from pyrogram import enums
        
        # Build keyboard
        buttons = build_file_buttons(files, key, settings)
        
        # Add pagination if needed
        if offset and offset != "":
            req_user_id = message.from_user.id if message.from_user else 0
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
        
        # Get IMDB data if enabled
        imdb_data = None
        if settings.get("imdb", False):
            try:
                from utils import get_poster
                imdb_data = await get_poster(search_query, file=files[0].file_name)
            except:
                pass
        
        # Build caption
        caption = build_search_caption(
            search=search_query,
            files=files,
            total_results=total_results,
            user_mention=message.from_user.mention,
            settings=settings,
            imdb_data=imdb_data
        )
        
        # Store IMDB caption if available
        if imdb_data:
            await state_manager.store_imdb_caption(message.from_user.id, caption)
        
        # Send response
        try:
            if imdb_data and imdb_data.get('poster'):
                # Try with IMDB poster
                try:
                    response_msg = await progress_msg.edit_photo(
                        photo=imdb_data.get('poster'),
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception:
                    # Fallback to modified poster URL
                    poster_url = imdb_data.get('poster', '').replace('.jpg', "._V1_UX360.jpg")
                    response_msg = await progress_msg.edit_photo(
                        photo=poster_url,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.HTML
                    )
            else:
                # Text-only response
                response_msg = await progress_msg.edit_text(
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.HTML
                )
        except Exception as e:
            # Final fallback to simple text
            response_msg = await progress_msg.edit_text(
                text=caption,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        
        # Handle auto-delete if enabled
        if settings.get('auto_delete', False):
            await asyncio.sleep(AUTO_DELETE_TIME)
            try:
                await response_msg.delete()
                await message.delete()
            except:
                pass
                
    except Exception as e:
        from logging_helper import LOGGER
        LOGGER.error(f"Error building search response: {str(e)}")

# Import placeholder functions (these would be imported from your existing modules)
async def get_search_results(chat_id: int, query: str, offset: int = 0, filter: bool = True):
    """Placeholder for database search function"""
    # This should be imported from database.ia_filterdb
    pass

async def get_settings(chat_id: int):
    """Placeholder for settings function"""
    # This should be imported from utils
    pass

async def get_poster(query: str, file: str = None, bulk: bool = False):
    """Placeholder for IMDB function"""
    # This should be imported from utils
    pass
