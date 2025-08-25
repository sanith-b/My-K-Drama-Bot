# inline_search.py - Fixed version with correct parse mode

import re
import asyncio
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineQuery, InlineQueryResultArticle, InlineQueryResultPhoto,
    InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
)
from pyrogram.errors import QueryIdInvalid
from database.ia_filterdb import get_search_results
from utils import get_size, is_subscribed, get_poster
from Script import script

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MAX_INLINE_RESULTS = 50
MIN_QUERY_LENGTH = 3

@Client.on_inline_query()
async def inline_search(bot, query: InlineQuery):
    """
    Handle inline queries for drama/movie search
    Usage: @myKdrama_bot [search query]
    """
    try:
        # Get search query
        search_query = query.query.strip()
        
        # Handle empty query - show help
        if not search_query:
            await show_inline_help(query)
            return
        
        # Handle too short query
        if len(search_query) < MIN_QUERY_LENGTH:
            await show_query_too_short(query, search_query)
            return
        
        # Handle special commands
        if search_query.lower().startswith(('help', 'start', 'info')):
            await show_inline_help(query)
            return
        
        # Perform the search
        await perform_inline_search(bot, query, search_query)
        
    except Exception as e:
        logger.error(f"Error in inline search: {e}")
        await show_inline_error(query)

async def perform_inline_search(bot, query: InlineQuery, search_query: str):
    """
    Perform the actual search and return results
    """
    try:
        # Clean the search query
        search_query = re.sub(r"[^\w\s]", " ", search_query).strip()
        search_query = re.sub(r"\s+", " ", search_query)
        
        # Search in database
        files, offset, total_results = await get_search_results(
            chat_id=query.from_user.id,
            query=search_query,
            offset=0,
            filter=True
        )
        
        if not files:
            await show_no_results(query, search_query)
            return
        
        # Prepare inline results
        results = []
        
        for idx, file in enumerate(files[:MAX_INLINE_RESULTS]):
            try:
                # Get file info
                file_name = getattr(file, 'file_name', 'Unknown File')
                file_size = get_size(getattr(file, 'file_size', 0))
                file_id = getattr(file, 'file_id', '')
                file_type = getattr(file, 'file_type', 'document')
                
                # Create description
                description = f"📁 {file_size}"
                if hasattr(file, 'duration') and file.duration:
                    description += f" • ⏱️ {format_duration(file.duration)}"
                
                # Create inline keyboard
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Get File", callback_data=f"file#{file_id}#{query.from_user.id}")],
                    [InlineKeyboardButton("🔍 More Results", switch_inline_query_current_chat=search_query)]
                ])
                
                # Create message content - FIXED: Using HTML instead of markdown
                message_text = f"<b>🎬 {file_name}</b>\n\n📁 Size: {file_size}\n🎭 Type: {file_type.title()}\n\n💡 Click 'Get File' to download!"
                
                # Create inline result
                result = InlineQueryResultArticle(
                    id=f"file_{idx}_{file_id[:10]}",
                    title=file_name[:64],
                    description=description,
                    input_message_content=InputTextMessageContent(
                        message_text=message_text,
                        parse_mode=enums.ParseMode.HTML  # FIXED: Use enums.ParseMode.HTML
                    ),
                    reply_markup=keyboard,
                    thumb_url="https://telegra.ph/file/default-thumb.jpg"
                )
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error creating inline result for file {idx}: {e}")
                continue
        
        # Add "Show More" result if there are more files
        if total_results > MAX_INLINE_RESULTS:
            more_result = InlineQueryResultArticle(
                id="show_more",
                title=f"📂 {total_results - MAX_INLINE_RESULTS} More Results Available",
                description=f"Found {total_results} total results for '{search_query}'",
                input_message_content=InputTextMessageContent(
                    message_text=f"🔍 Search Results for <b>{search_query}</b>\n\n"
                                f"📊 Total Results: {total_results}\n"
                                f"📋 Showing: {len(results)}\n\n"
                                f"💡 Use /search {search_query} for complete results in private chat!",
                    parse_mode=enums.ParseMode.HTML  # FIXED: Use enums.ParseMode.HTML
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Full Search", url=f"https://t.me/{bot.me.username}?start=search_{search_query.replace(' ', '_')}")]
                ])
            )
            results.insert(0, more_result)
        
        # Answer the inline query
        await query.answer(
            results=results,
            cache_time=60,
            switch_pm_text="🎭 Open K-Drama Bot",
            switch_pm_parameter="inline_search"
        )
        
    except Exception as e:
        logger.error(f"Error in perform_inline_search: {e}")
        await show_inline_error(query)

async def show_inline_help(query: InlineQuery):
    """Show help message for inline queries"""
    help_result = InlineQueryResultArticle(
        id="help",
        title="🆘 How to use Inline Search",
        description="Learn how to search for K-Dramas inline",
        input_message_content=InputTextMessageContent(
            message_text="🎭 <b>K-Drama Bot - Inline Search Help</b>\n\n"
                        "<b>How to use:</b>\n"
                        "• Type <code>@myKdrama_bot [drama name]</code> in any chat\n"
                        "• Example: <code>@myKdrama_bot Squid Game</code>\n"
                        "• Minimum 3 characters required\n\n"
                        "<b>Features:</b>\n"
                        "📱 Search from any chat\n"
                        "🎬 Instant results\n"
                        "📥 Direct file access\n"
                        "🔍 Smart search suggestions\n\n"
                        "<b>Popular Searches:</b>\n"
                        "• Crash Landing on You\n"
                        "• Descendants of the Sun\n"
                        "• Goblin\n"
                        "• Hotel Del Luna\n\n"
                        "Start typing to search! 🚀",
            parse_mode=enums.ParseMode.HTML  # FIXED: Use enums.ParseMode.HTML
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎭 Open Bot", url=f"https://t.me/myKdrama_bot")],
            [InlineKeyboardButton("📢 Channel", url="https://t.me/your_channel")]
        ])
    )
    
    await query.answer(
        results=[help_result],
        cache_time=300,
        switch_pm_text="🎭 Open K-Drama Bot",
        switch_pm_parameter="help"
    )

async def show_query_too_short(query: InlineQuery, search_query: str):
    """Show message when query is too short"""
    short_result = InlineQueryResultArticle(
        id="too_short",
        title=f"⚠️ Query too short: '{search_query}'",
        description="Please type at least 3 characters to search",
        input_message_content=InputTextMessageContent(
            message_text=f"⚠️ <b>Search Query Too Short</b>\n\n"
                        f"Your query: <code>{search_query}</code>\n"
                        f"Required: Minimum 3 characters\n\n"
                        f"<b>Try searching for:</b>\n"
                        f"• Drama names: <code>Squid Game</code>\n"
                        f"• Actor names: <code>Song Joong Ki</code>\n"
                        f"• Genres: <code>Romance Drama</code>\n\n"
                        f"Type more characters to search! 🔍",
            parse_mode=enums.ParseMode.HTML  # FIXED: Use enums.ParseMode.HTML
        )
    )
    
    await query.answer(
        results=[short_result],
        cache_time=30
    )

async def show_no_results(query: InlineQuery, search_query: str):
    """Show message when no results found"""
    no_results = InlineQueryResultArticle(
        id="no_results",
        title=f"❌ No results for '{search_query}'",
        description="Try different keywords or request the drama",
        input_message_content=InputTextMessageContent(
            message_text=f"❌ <b>No Results Found</b>\n\n"
                        f"Search query: <code>{search_query}</code>\n\n"
                        f"<b>Suggestions:</b>\n"
                        f"• Try different keywords\n"
                        f"• Check spelling\n"
                        f"• Use English names\n"
                        f"• Request the drama: <code>/req {search_query}</code>\n\n"
                        f"<b>Popular Dramas:</b>\n"
                        f"• Crash Landing on You\n"
                        f"• Descendants of the Sun\n"
                        f"• Goblin\n"
                        f"• Hotel Del Luna",
            parse_mode=enums.ParseMode.HTML  # FIXED: Use enums.ParseMode.HTML
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Request Drama", url=f"https://t.me/myKdrama_bot?start=req_{search_query.replace(' ', '_')}")],
            [InlineKeyboardButton("🎭 Browse All", url="https://t.me/myKdrama_bot")]
        ])
    )
    
    await query.answer(
        results=[no_results],
        cache_time=60
    )

async def show_inline_error(query: InlineQuery):
    """Show error message - FIXED VERSION"""
    try:
        error_result = InlineQueryResultArticle(
            id="error",
            title="❌ Search Error",
            description="Something went wrong. Please try again.",
            input_message_content=InputTextMessageContent(
                message_text="❌ <b>Search Error</b>\n\n"
                            "Something went wrong while searching.\n\n"
                            "<b>Please try:</b>\n"
                            "• Refreshing the search\n"
                            "• Using different keywords\n"
                            "• Contacting support if issue persists\n\n"
                            "Sorry for the inconvenience! 🙏",
                parse_mode=enums.ParseMode.HTML  # FIXED: Use enums.ParseMode.HTML
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Retry", switch_inline_query_current_chat="")],
                [InlineKeyboardButton("💬 Support", url="https://t.me/your_support")]
            ])
        )
        
        await query.answer(
            results=[error_result],
            cache_time=10
        )
    except Exception as e:
        logger.error(f"Critical error in show_inline_error: {e}")
        # Fallback - answer with empty results
        try:
            await query.answer(results=[], cache_time=1)
        except:
            pass  # Even fallback failed

def format_duration(duration):
    """Format duration in seconds to readable format"""
    try:
        duration = int(duration)
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    except:
        return "Unknown"

# Handler for inline callback queries
@Client.on_callback_query(filters.regex(r"^file#"))
async def handle_inline_file_request(bot, query):
    """
    Handle file requests from inline results
    """
    try:
        _, file_id, user_id = query.data.split('#')
        
        # Verify user
        if query.from_user.id != int(user_id):
            await query.answer("❌ This button is not for you!", show_alert=True)
            return
        
        # Send the file
        try:
            await bot.send_cached_media(
                chat_id=query.from_user.id,
                file_id=file_id,
                caption="🎬 <b>Here's your requested file!</b>\n\n"
                       "📤 Sent via inline search\n"
                       "🎭 @myKdrama_bot\n\n"
                       "💡 Share with friends: @myKdrama_bot",
                parse_mode=enums.ParseMode.HTML,  # FIXED: Use enums.ParseMode.HTML
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Search More", switch_inline_query="")],
                    [InlineKeyboardButton("📢 Share Bot", url="https://t.me/share/url?url=https://t.me/myKdrama_bot")]
                ])
            )
            await query.answer("📥 File sent to your private chat!", show_alert=True)
            
        except Exception as e:
            logger.error(f"Error sending file {file_id}: {e}")
            await query.answer("❌ Failed to send file. Please try again.", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in handle_inline_file_request: {e}")
        await query.answer("❌ Something went wrong!", show_alert=True)

# Simplified script class if script.py is missing
try:
    import script
except ImportError:
    class script:
        ALRT_TXT = "Hey {first_name}, This Is Not For You!"
        TOP_ALRT_MSG = "Searching... Please wait! ⏳"
        MVE_NT_FND = "❌ Movie not found. Try different keywords."
        NORSLTS = "No results for {2} by user {1}"
