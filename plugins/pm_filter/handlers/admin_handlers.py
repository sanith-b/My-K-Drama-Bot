"""
Admin handlers for file management and bot administration
"""

import asyncio
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from models.state_manager import state_manager
from ui.message_builders import (
    build_file_delete_progress_message, build_file_delete_start_message,
    build_file_delete_progress, build_file_delete_complete_message
)
from logging_helper import LOGGER

@Client.on_callback_query(filters.regex(r"^killfilesdq"))
async def kill_files_handler(client: Client, query: CallbackQuery):
    """
    Handle bulk file deletion by keyword
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        ident, keyword = query.data.split("#")
        
        # Check if user is admin
        if query.from_user.id not in client.ADMINS:
            await query.answer("You don't have permission to delete files", show_alert=True)
            return
        
        # Start deletion process
        await query.message.edit_text(
            build_file_delete_progress_message(keyword)
        )
        
        # Get files to delete
        files, total = await get_bad_files(keyword)
        
        if not files:
            await query.message.edit_text(
                f"No files found for keyword: {keyword}"
            )
            return
        
        # Show deletion start message
        await query.message.edit_text(build_file_delete_start_message())
        await asyncio.sleep(5)
        
        # Start deletion process
        deleted = 0
        lock = asyncio.Lock()
        
        async with lock:
            try:
                for file in files:
                    file_id = file.file_id
                    file_name = file.file_name
                    
                    # Delete from primary database
                    result = await Media.collection.delete_one({'_id': file_id})
                    
                    # Try secondary database if enabled
                    if not result.deleted_count and hasattr(client, 'MULTIPLE_DB') and client.MULTIPLE_DB:
                        result = await Media2.collection.delete_one({'_id': file_id})
                    
                    if result.deleted_count:
                        LOGGER.info(f'Successfully deleted {file_name} from database for query {keyword}')
                    
                    deleted += 1
                    
                    # Update progress every 20 deletions
                    if deleted % 20 == 0:
                        await query.message.edit_text(
                            build_file_delete_progress(deleted, keyword)
                        )
                        
            except Exception as e:
                LOGGER.error(f"Error in file deletion: {str(e)}")
                await query.message.edit_text(f'Error during deletion: {str(e)}')
                return
            
            # Show completion message
            await query.message.edit_text(
                build_file_delete_complete_message(deleted, keyword)
            )
            
    except Exception as e:
        LOGGER.error(f"Error in kill_files_handler: {str(e)}")
        await query.answer("Error processing file deletion", show_alert=True)

@Client.on_callback_query(filters.regex(r"^maintenance"))
async def maintenance_handler(client: Client, query: CallbackQuery):
    """
    Handle maintenance mode toggle
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        if query.from_user.id not in client.ADMINS:
            await query.answer("You don't have admin privileges", show_alert=True)
            return
        
        # Toggle maintenance mode
        current_status = await db.get_maintenance_status(client.me.id)
        new_status = not current_status
        
        await db.set_maintenance_status(client.me.id, new_status)
        
        status_text = "enabled" if new_status else "disabled"
        await query.answer(f"Maintenance mode {status_text}", show_alert=True)
        
    except Exception as e:
        LOGGER.error(f"Error in maintenance_handler: {str(e)}")
        await query.answer("Error toggling maintenance mode", show_alert=True)

@Client.on_callback_query(filters.regex(r"^broadcast"))
async def broadcast_handler(client: Client, query: CallbackQuery):
    """
    Handle broadcast message initiation
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        if query.from_user.id not in client.ADMINS:
            await query.answer("You don't have admin privileges", show_alert=True)
            return
        
        await query.answer("Broadcast feature coming soon!", show_alert=True)
        
    except Exception as e:
        LOGGER.error(f"Error in broadcast_handler: {str(e)}")
        await query.answer("Error accessing broadcast", show_alert=True)

@Client.on_callback_query(filters.regex(r"^stats"))
async def stats_handler(client: Client, query: CallbackQuery):
    """
    Handle bot statistics display
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        if query.from_user.id not in client.ADMINS:
            await query.answer("You don't have admin privileges", show_alert=True)
            return
        
        # Get state manager stats
        stats = await state_manager.get_stats()
        
        # Build stats message
        stats_text = f"""<b>Bot Statistics</b>

<b>Memory Usage:</b>
• Fresh queries: {stats['fresh_queries']}
• Filtered queries: {stats['filtered_queries']}
• Temporary files: {stats['temp_files']}
• User shortcuts: {stats['user_shortcuts']}
• IMDB cache: {stats['imdb_cache']}
• Spell check cache: {stats['spell_check']}

<b>Database Stats:</b>
• Total users: {await get_total_users()}
• Total chats: {await get_total_chats()}
• Total files: {await get_total_files()}"""
        
        await query.message.edit_text(stats_text, parse_mode="HTML")
        
    except Exception as e:
        LOGGER.error(f"Error in stats_handler: {str(e)}")
        await query.answer("Error loading statistics", show_alert=True)

@Client.on_callback_query(filters.regex(r"^cleanup"))
async def cleanup_handler(client: Client, query: CallbackQuery):
    """
    Handle memory cleanup
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        if query.from_user.id not in client.ADMINS:
            await query.answer("You don't have admin privileges", show_alert=True)
            return
        
        # Perform cleanup
        await state_manager.cleanup_expired_data()
        
        await query.answer("Memory cleanup completed", show_alert=True)
        
    except Exception as e:
        LOGGER.error(f"Error in cleanup_handler: {str(e)}")
        await query.answer("Error performing cleanup", show_alert=True)

@Client.on_callback_query(filters.regex(r"^ban_user"))
async def ban_user_handler(client: Client, query: CallbackQuery):
    """
    Handle user ban/unban
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        if query.from_user.id not in client.ADMINS:
            await query.answer("You don't have admin privileges", show_alert=True)
            return
        
        _, user_id = query.data.split("#")
        
        # Toggle ban status
        is_banned = await db.is_user_banned(int(user_id))
        
        if is_banned:
            await db.unban_user(int(user_id))
            await query.answer(f"User {user_id} unbanned", show_alert=True)
        else:
            await db.ban_user(int(user_id))
            await query.answer(f"User {user_id} banned", show_alert=True)
        
    except Exception as e:
        LOGGER.error(f"Error in ban_user_handler: {str(e)}")
        await query.answer("Error processing ban/unban", show_alert=True)

@Client.on_callback_query(filters.regex(r"^reset_stats"))
async def reset_stats_handler(client: Client, query: CallbackQuery):
    """
    Handle statistics reset
    
    Args:
        client: Pyrogram client
        query: Callback query object
    """
    try:
        if query.from_user.id not in client.ADMINS:
            await query.answer("You don't have admin privileges", show_alert=True)
            return
        
        # Reset all state manager data
        await state_manager.cleanup_expired_data()
        
        # Additional cleanup if needed
        from models.state_manager import FRESH, BUTTONS
        FRESH.clear()
        BUTTONS.clear()
        
        await query.answer("All statistics and cache data reset", show_alert=True)
        
    except Exception as e:
        LOGGER.error(f"Error in reset_stats_handler: {str(e)}")
        await query.answer("Error resetting statistics", show_alert=True)

# Import placeholder functions
async def get_bad_files(keyword):
    """Placeholder - import from database.ia_filterdb"""
    # This should return files matching the keyword for deletion
    return [], 0

async def get_total_users():
    """Placeholder - import from database.users_chats_db"""
    try:
        return await db.total_users_count()
    except:
        return 0

async def get_total_chats():
    """Placeholder - import from database.users_chats_db"""
    try:
        return await db.total_chat_count()
    except:
        return 0

async def get_total_files():
    """Placeholder - import from database.ia_filterdb"""
    try:
        from database.ia_filterdb import Media
        return await Media.count_documents({})
    except:
        return 0

# Import database objects
try:
    from database.users_chats_db import db
    from database.ia_filterdb import Media, Media2
except ImportError:
    db = None
    Media = None
    Media2 = None
