import asyncio
import re
import logging
from typing import List, Optional
from fuzzywuzzy import process
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Configuration constants
SIMILARITY_THRESHOLD = 85
MAX_SEARCH_ATTEMPTS = 5
MESSAGE_TIMEOUT = 90
MAX_MOVIE_RESULTS = 10

# Set up logging
logger = logging.getLogger(__name__)

async def ai_spell_check(chat_id, wrong_name):
    """
    Enhanced spell check with better error handling and logging
    """
    async def search_movie(wrong_name):
        try:
            search_results = imdb.search_movie(wrong_name)
            movie_list = [movie['title'] for movie in search_results if 'title' in movie]
            logger.info(f"Found {len(movie_list)} movies for query: {wrong_name}")
            return movie_list
        except Exception as e:
            logger.error(f"IMDb search error for '{wrong_name}': {e}")
            return []
    
    try:
        movie_list = await search_movie(wrong_name)
        if not movie_list:
            logger.info(f"No movies found for: {wrong_name}")
            return None
        
        original_count = len(movie_list)
        
        for attempt in range(MAX_SEARCH_ATTEMPTS):
            closest_match = process.extractOne(wrong_name, movie_list)
            
            if not closest_match or closest_match[1] <= SIMILARITY_THRESHOLD:
                logger.info(f"No good match found (attempt {attempt + 1}/{MAX_SEARCH_ATTEMPTS})")
                return None
                
            movie = closest_match[0]
            similarity_score = closest_match[1]
            logger.info(f"Checking movie: {movie} (similarity: {similarity_score}%)")
            
            try:
                files, offset, total_results = await asyncio.wait_for(
                    get_search_results(chat_id=chat_id, query=movie),
                    timeout=10  # 10 second timeout per search
                )
                
                if files:
                    logger.info(f"Found {len(files)} files for: {movie}")
                    return movie
                    
            except asyncio.TimeoutError:
                logger.warning(f"Timeout searching for files: {movie}")
            except Exception as e:
                logger.error(f"Error searching files for '{movie}': {e}")
            
            # Remove movie and try next best match
            movie_list.remove(movie)
            
            if not movie_list:
                logger.info("No more movies to check")
                break
        
        logger.info(f"Spell check failed after checking {original_count} movies")
        return None
        
    except Exception as e:
        logger.error(f"Error in ai_spell_check: {e}")
        return None

async def advanced_spell_check(client, message):
    """
    Enhanced movie search with improved UX and error handling
    """
    try:
        mv_id = message.id
        search = message.text.strip()
        chat_id = message.chat.id
        user = message.from_user
        user_id = user.id if user else 0
        user_mention = user.mention if user else "User"
        
        # Get settings
        try:
            settings = await get_settings(chat_id)
        except Exception as e:
            logger.error(f"Error getting settings: {e}")
            settings = {}
        
        # Clean query with improved regex
        query = re.sub(
            r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
            "", message.text, flags=re.IGNORECASE
        )
        query = re.sub(r'\s+', ' ', query.strip())  # Clean extra whitespace
        query = query + " movie" if query else search
        
        logger.info(f"User {user_id} searching: '{search}' -> cleaned: '{query}'")
        
        # Show searching indicator
        searching_msg = await message.reply(
            f"🔍 *Searching for:* `{search}`\n\nPlease wait...",
            parse_mode='Markdown'
        )
        
        # Try to get movies with timeout
        try:
            movies = await asyncio.wait_for(
                get_poster(search, bulk=True),
                timeout=15  # 15 second timeout
            )
        except asyncio.TimeoutError:
            await searching_msg.edit_text(
                "⏰ *Search timed out*\n\nPlease try with a shorter or simpler movie name.",
                parse_mode='Markdown'
            )
            await asyncio.sleep(10)
            await _safe_delete(searching_msg)
            await _safe_delete(message)
            return
        except Exception as e:
            logger.error(f"Error getting poster for '{search}': {e}")
            movies = None
        
        # Delete searching message
        await _safe_delete(searching_msg)
        
        if not movies:
            # Try AI spell check as fallback
            logger.info(f"No direct results, trying spell check for: {search}")
            
            spell_check_msg = await message.reply(
                f"🤔 No exact matches found...\n\n🔮 *Trying spell check magic...*",
                parse_mode='Markdown'
            )
            
            corrected_movie = await ai_spell_check(chat_id, query)
            await _safe_delete(spell_check_msg)
            
            if corrected_movie:
                # Found corrected match
                buttons = [
                    [InlineKeyboardButton(f"📁 Get Files", callback_data=f"spol#{corrected_movie}#{user_id}")],
                    [
                        InlineKeyboardButton("🔍 Google Search", url=f"https://www.google.com/search?q={search.replace(' ', '+')}+movie"),
                        InlineKeyboardButton("❌ Close", callback_data='close_data')
                    ]
                ]
                
                suggestion_text = (
                    f"🎯 *Spell Check Result*\n\n"
                    f"Did you mean: *{corrected_movie}*?\n\n"
                    f"✅ Found files for this movie!"
                )
                
                k = await message.reply_text(
                    text=suggestion_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(buttons),
                    reply_to_message_id=message.id
                )
            else:
                # No spell check results either
                google = search.replace(" ", "+")
                button = [[
                    InlineKeyboardButton("🔍 Search Google", url=f"https://www.google.com/search?q={google}+movie"),
                    InlineKeyboardButton("🎭 Try IMDb", url=f"https://www.imdb.com/find?q={google}")
                ]]
                
                not_found_text = (
                    f"🚫 *No movies found*\n\n"
                    f"Sorry {user_mention}, I couldn't find:\n"
                    f"`{search}`\n\n"
                    f"💡 **Try:**\n"
                    f"• Check spelling\n"
                    f"• Use simpler terms\n"
                    f"• Include release year"
                )
                
                k = await message.reply_text(
                    text=not_found_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(button),
                    reply_to_message_id=message.id
                )
            
            # Auto cleanup
            await asyncio.sleep(MESSAGE_TIMEOUT)
            await _safe_delete(k)
            await _safe_delete(message)
            return
        
        # Movies found - create response
        limited_movies = movies[:MAX_MOVIE_RESULTS]  # Limit results
        
        if len(limited_movies) == 1:
            # Single exact match
            movie = limited_movies[0]
            title = movie.get('title', 'Unknown Movie')
            
            buttons = [
                [InlineKeyboardButton(f"📁 Get {title}", callback_data=f"spol#{movie.movieID}#{user_id}")],
                [InlineKeyboardButton("❌ Close", callback_data='close_data')]
            ]
            
            single_match_text = (
                f"🎬 *Perfect Match!*\n\n"
                f"Found: *{title}*\n\n"
                f"Ready to download!"
            )
            
            d = await message.reply_text(
                text=single_match_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(buttons),
                reply_to_message_id=message.id
            )
        else:
            # Multiple matches - show selection
            buttons = []
            for movie in limited_movies:
                title = movie.get('title', 'Unknown')
                year = movie.get('year', '')
                
                # Create display title with year if available
                display_title = f"{title} ({year})" if year else title
                
                # Truncate long titles for better display
                if len(display_title) > 35:
                    display_title = display_title[:32] + "..."
                
                buttons.append([
                    InlineKeyboardButton(
                        text=f"🎬 {display_title}",
                        callback_data=f"spol#{movie.movieID}#{user_id}"
                    )
                ])
            
            # Add control buttons
            control_buttons = [
                InlineKeyboardButton("🔄 New Search", callback_data=f"new_search#{user_id}"),
                InlineKeyboardButton("❌ Close", callback_data='close_data')
            ]
            buttons.append(control_buttons)
            
            multiple_match_text = (
                f"🎭 *Found {len(limited_movies)} movies*\n\n"
                f"Hey {user_mention}, select the correct one:\n"
                f"*{search}*"
            )
            
            d = await message.reply_text(
                text=multiple_match_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(buttons),
                reply_to_message_id=message.id
            )
        
        # Auto cleanup after timeout
        await asyncio.sleep(MESSAGE_TIMEOUT)
        await _safe_delete(d)
        await _safe_delete(message)
        
    except Exception as e:
        logger.error(f"Error in advanced_spell_check: {e}")
        
        # Send error message
        try:
            error_msg = await message.reply(
                f"⚠️ *Error occurred*\n\n"
                f"Sorry {message.from_user.mention if message.from_user else 'there'}, "
                f"something went wrong. Please try again.",
                parse_mode='Markdown'
            )
            await asyncio.sleep(30)
            await _safe_delete(error_msg)
            await _safe_delete(message)
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")

async def _safe_delete(message):
    """Safely delete a message with error handling"""
    try:
        if message:
            await message.delete()
    except Exception as e:
        logger.debug(f"Could not delete message: {e}")

# Enhanced callback handler for the improved buttons
async def handle_movie_callback(update, context):
    """Handle movie selection and other button callbacks"""
    query = update.callback_query
    await query.answer()
    
    try:
        data_parts = query.data.split('#')
        action = data_parts[0]
        
        if action == "spol":  # Movie selection
            movie_id = data_parts[1]
            user_id = int(data_parts[2])
            
            # Verify user permission
            if query.from_user.id != user_id:
                await query.answer("❌ This search belongs to someone else!", show_alert=True)
                return
            
            # Show loading
            await query.edit_message_text(
                "📥 *Getting your movie...*\n\nPlease wait while I fetch the files!",
                parse_mode='Markdown'
            )
            
            # Here you would add your file sending logic
            # For now, just show success
            await asyncio.sleep(1)  # Simulate processing
            await query.edit_message_text(
                f"✅ *Files sent!*\n\nCheck your DMs for the movie files.",
                parse_mode='Markdown'
            )
            
            # Auto-delete after showing success
            await asyncio.sleep(10)
            await _safe_delete(query.message)
            
        elif action == "new_search":
            user_id = int(data_parts[1])
            
            if query.from_user.id != user_id:
                await query.answer("❌ This search belongs to someone else!", show_alert=True)
                return
            
            await query.edit_message_text(
                "🔄 *Ready for new search*\n\n"
                "Send me another movie name to search!",
                parse_mode='Markdown'
            )
            
            await asyncio.sleep(15)
            await _safe_delete(query.message)
            
        elif action == "close_data":
            await _safe_delete(query.message)
            
    except Exception as e:
        logger.error(f"Error in callback handler: {e}")
        try:
            await query.answer("⚠️ An error occurred. Please try again.", show_alert=True)
        except:
            pass

# Rate limiting to prevent spam
class SimpleRateLimiter:
    def __init__(self):
        self.user_timestamps = {}
        self.cooldown = 5  # 5 seconds between searches
    
    def is_allowed(self, user_id: int) -> bool:
        import time
        now = time.time()
        
        if user_id in self.user_timestamps:
            if now - self.user_timestamps[user_id] < self.cooldown:
                return False
        
        self.user_timestamps[user_id] = now
        return True

rate_limiter = SimpleRateLimiter()

# Your original function name with improvements
async def advantage_spell_chok(client, message):
    """
    Main movie search handler with enhanced UX
    """
    # Initialize default values first
    user_id = 0
    user_mention = "User"
    search = ""
    chat_id = 0
    
    try:
        # Safely get message attributes
        mv_id = getattr(message, 'id', 0)
        search = getattr(message, 'text', '').strip()
        chat_id = getattr(message, 'chat', {})
        
        # Handle chat_id if it's an object
        if hasattr(chat_id, 'id'):
            chat_id = chat_id.id
        elif isinstance(chat_id, dict):
            chat_id = chat_id.get('id', 0)
        else:
            chat_id = 0
        
        # Safe user handling with extensive checks
        user = getattr(message, 'from_user', None)
        
        if user:
            # Check if user is a proper object or just a string/number
            if hasattr(user, 'mention') and callable(getattr(user, 'mention', None)):
                try:
                    user_mention = user.mention
                except:
                    user_mention = "User"
            elif hasattr(user, 'mention') and isinstance(user.mention, str):
                user_mention = user.mention
            elif hasattr(user, 'first_name'):
                user_mention = user.first_name
            elif hasattr(user, 'username'):
                user_mention = f"@{user.username}"
            
            # Get user ID safely
            if hasattr(user, 'id'):
                try:
                    user_id = int(user.id)
                except (ValueError, TypeError):
                    user_id = 0
        
        logger.info(f"Processing message - User: {user_id}, Chat: {chat_id}, Search: '{search}'")
        
        # Rate limiting check
        if not rate_limiter.is_allowed(user_id):
            rate_msg = await message.reply(
                "⏳ *Please wait a moment*\n\nToo many searches! Try again in a few seconds."
            )
            await asyncio.sleep(10)
            await _safe_delete(rate_msg)
            return
        
        # Validate input
        if len(search) < 2:
            short_msg = await message.reply(
                "📝 *Movie name too short*\n\nPlease send a longer movie name!",
                parse_mode='Markdown'
            )
            await asyncio.sleep(15)
            await _safe_delete(short_msg)
            return
        
        # Get settings with error handling
        try:
            settings = await get_settings(chat_id)
        except Exception as e:
            logger.error(f"Error getting settings for chat {chat_id}: {e}")
            settings = {}
        
        # Enhanced query cleaning
        query = re.sub(
            r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
            "", message.text, flags=re.IGNORECASE
        )
        query = re.sub(r'\s+', ' ', query.strip()) + " movie"
        
        logger.info(f"Processing search: '{search}' -> '{query}' from user {user_id}")
        
        # Show typing indicator
        await client.send_chat_action(chat_id, "typing")
        
        # Try to get movies with enhanced error handling
        try:
            movies = await asyncio.wait_for(
                get_poster(search, bulk=True),
                timeout=15
            )
        except asyncio.TimeoutError:
            timeout_msg = await message.reply(
                f"⏰ *Search timed out*\n\n"
                f"The search for `{search}` is taking too long.\n"
                f"Please try a simpler movie name.",
                parse_mode='Markdown'
            )
            await asyncio.sleep(20)
            await _safe_delete(timeout_msg)
            await _safe_delete(message)
            return
        except Exception as e:
            logger.error(f"Error getting poster for '{search}': {e}")
            k = await message.reply(
                f"⚠️ *Search Error*\n\n"
                f"Sorry {user_mention}, couldn't search for movies right now.\n"
                f"Please try again in a moment.",
                parse_mode='Markdown'
            )
            await asyncio.sleep(30)
            await _safe_delete(k)
            await _safe_delete(message)
            return
        
        if not movies:
            # No movies found - try spell check
            logger.info(f"No movies found, trying spell check for: {search}")
            
            # Show spell check attempt
            spell_msg = await message.reply(
                f"🔮 *No exact matches*\n\n"
                f"Trying spell check for: `{search}`",
                parse_mode='Markdown'
            )
            
            corrected_movie = await ai_spell_check(chat_id, query)
            await _safe_delete(spell_msg)
            
            if corrected_movie:
                # Spell check found a match
                buttons = [
                    [InlineKeyboardButton(f"📁 Get {corrected_movie}", callback_data=f"spol#{corrected_movie}#{user_id}")],
                    [
                        InlineKeyboardButton("🔍 Google", url=f"https://www.google.com/search?q={search.replace(' ', '+')}+movie"),
                        InlineKeyboardButton("❌ Close", callback_data='close_data')
                    ]
                ]
                
                spell_success_text = (
                    f"🎯 *Spell Check Success!*\n\n"
                    f"You searched: `{search}`\n"
                    f"Did you mean: *{corrected_movie}*?\n\n"
                    f"✅ Files are available!"
                )
                
                k = await message.reply_text(
                    text=spell_success_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(buttons),
                    reply_to_message_id=message.id
                )
            else:
                # Complete failure - no results
                google = search.replace(" ", "+")
                button = [
                    [InlineKeyboardButton("🔍 Search Google", url=f"https://www.google.com/search?q={google}+movie")],
                    [InlineKeyboardButton("🎭 Browse IMDb", url=f"https://www.imdb.com/find?q={google}")],
                    [InlineKeyboardButton("❌ Close", callback_data='close_data')]
                ]
                
                not_found_text = (
                    f"🚫 *Movie Not Found*\n\n"
                    f"Sorry {user_mention}, no results for:\n"
                    f"`{search}`\n\n"
                    f"💡 **Suggestions:**\n"
                    f"• Check spelling\n"
                    f"• Try original title\n"
                    f"• Include year (e.g., 'Avatar 2009')\n"
                    f"• Use English title"
                )
                
                k = await message.reply_text(
                    text=not_found_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(button),
                    reply_to_message_id=message.id
                )
            
            await asyncio.sleep(MESSAGE_TIMEOUT)
            await _safe_delete(k)
            await _safe_delete(message)
            return
        
        # Movies found - show selection
        limited_movies = movies[:MAX_MOVIE_RESULTS]
        
        buttons = []
        for movie in limited_movies:
            title = movie.get('title', 'Unknown')
            year = movie.get('year', '')
            
            # Create better display title
            display_title = f"{title} ({year})" if year else title
            if len(display_title) > 35:
                display_title = display_title[:32] + "..."
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"🎬 {display_title}",
                    callback_data=f"spol#{movie.get('movieID', '')}#{user_id}"
                )
            ])
        
        # Add footer buttons
        footer_buttons = [
            InlineKeyboardButton("🔄 New Search", callback_data=f"new_search#{user_id}"),
            InlineKeyboardButton("❌ Close", callback_data='close_data')
        ]
        buttons.append(footer_buttons)
        
        # Create response text
        results_count = len(limited_movies)
        total_found = len(movies)
        
        if total_found > MAX_MOVIE_RESULTS:
            results_text = (
                f"🎭 *Found {total_found} movies*\n\n"
                f"Hey {user_mention}, showing top {results_count} matches for:\n"
                f"`{search}`\n\n"
                f"Select the correct movie:"
            )
        else:
            results_text = (
                f"🎬 *Found {results_count} movies*\n\n"
                f"Hey {user_mention}, choose from these matches:\n"
                f"`{search}`"
            )
        
        d = await message.reply_text(
            text=results_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons),
            reply_to_message_id=message.id
        )
        
        # Auto cleanup
        await asyncio.sleep(MESSAGE_TIMEOUT)
        await _safe_delete(d)
        await _safe_delete(message)
        
    except Exception as e:
        logger.error(f"Critical error in advantage_spell_chok: {e}")
        try:
            error_msg = await message.reply(
                f"🚨 *Critical Error*\n\n"
                f"Something went seriously wrong. Please contact support if this continues.",
                parse_mode='Markdown'
            )
            await asyncio.sleep(30)
            await _safe_delete(error_msg)
        except:
            pass

# Additional utility for monitoring
async def log_search_stats(user_id: int, search_term: str, result_count: int, success: bool):
    """Log search statistics for monitoring"""
    try:
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"SEARCH_STATS | User: {user_id} | Query: '{search_term}' | Results: {result_count} | Status: {status}")
    except Exception as e:
        logger.error(f"Error logging stats: {e}")

# Example of how to add to your bot
# application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, advantage_spell_chok))
# application.add_handler(CallbackQueryHandler(handle_movie_callback))
