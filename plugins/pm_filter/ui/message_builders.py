"""
Message content builders for search results, captions, and UI text
"""

from typing import List, Dict, Any, Optional
from utils.helpers import get_size, clean_filename, format_search_results_count
from config.constants import IMDB_FIELDS

def build_search_caption(
    search: str,
    files: List,
    total_results: int,
    user_mention: str,
    settings: Dict = None,
    imdb_data: Dict = None
) -> str:
    """
    Build caption for search results
    
    Args:
        search: Search query
        files: List of files
        total_results: Total number of results
        user_mention: User mention string
        settings: Group settings
        imdb_data: IMDB data if available
        
    Returns:
        Formatted caption string
    """
    settings = settings or {}
    
    if imdb_data:
        return build_imdb_caption(imdb_data, search, files, user_mention, total_results)
    
    # Basic caption without IMDB
    if settings.get('button', True):
        caption = f"<b><blockquote>Hey!, {user_mention}</blockquote>\n\n📂 Voilà! Your result: <code>{search}</code></b>\n\n"
    else:
        caption = f"<b><blockquote>✨ Hello!, {user_mention}</blockquote>\n\n📂 Voilà! Your result: <code>{search}</code></b>\n\n"
        
        # Add file list for text mode
        for file_num, file in enumerate(files, start=1):
            file_link = f"https://telegram.me/{{bot_username}}?start=file_{{chat_id}}_{file.file_id}"
            caption += f"<b>{file_num}. <a href='{file_link}'>{get_size(file.file_size)} | {clean_filename(file.file_name)}</a></b>\n\n"
    
    return caption

def build_imdb_caption(
    imdb_data: Dict,
    search: str,
    files: List = None,
    user_mention: str = "",
    total_results: int = 0
) -> str:
    """
    Build IMDB-based caption using template
    
    Args:
        imdb_data: IMDB movie data
        search: Search query
        files: List of files (for text mode)
        user_mention: User mention string
        total_results: Total results count
        
    Returns:
        Formatted IMDB caption
    """
    # Default IMDB template
    template = """<b>🎬 {title}</b>

<b>📅 Year:</b> {year}
<b>⭐ Rating:</b> {rating}/10
<b>🗳️ Votes:</b> {votes}
<b>⏱️ Runtime:</b> {runtime}
<b>🎭 Genres:</b> {genres}
<b>🌍 Countries:</b> {countries}
<b>🗣️ Languages:</b> {languages}

<b>👨‍💼 Director:</b> {director}
<b>✍️ Writer:</b> {writer}
<b>🎬 Cast:</b> {cast}

<b>📖 Plot:</b> {plot}

<b>🔍 Search:</b> <code>{search}</code>
<b>📊 Files Found:</b> {total_results}"""

    # Prepare data with fallbacks
    safe_data = {}
    for field in IMDB_FIELDS:
        value = imdb_data.get(field, 'N/A')
        if isinstance(value, list):
            value = ', '.join(value[:3]) if value else 'N/A'  # Limit list items
        elif not value or value == 'None':
            value = 'N/A'
        safe_data[field] = str(value)[:100]  # Limit field length
    
    # Add search and results info
    safe_data.update({
        'search': search,
        'total_results': format_search_results_count(total_results),
        'user_mention': user_mention
    })
    
    try:
        caption = template.format(**safe_data)
    except KeyError as e:
        # Fallback to basic caption if template fails
        caption = f"<b>🎬 {safe_data.get('title', 'Unknown')}</b>\n\n"
        caption += f"<b>🔍 Search:</b> <code>{search}</code>\n"
        caption += f"<b>📊 Files Found:</b> {format_search_results_count(total_results)}"
    
    # Add file list for text mode if files provided
    if files and not safe_data.get('button_mode', True):
        caption += "\n\n<b>📁 Files:</b>\n"
        for file_num, file in enumerate(files[:10], start=1):  # Limit to 10 files
            file_link = f"https://telegram.me/{{bot_username}}?start=file_{{chat_id}}_{file.file_id}"
            caption += f"{file_num}. <a href='{file_link}'>{get_size(file.file_size)} | {clean_filename(file.file_name)}</a>\n"
    
    return caption

def build_settings_message(group_title: str, settings: Dict[str, Any]) -> str:
    """
    Build settings menu message
    
    Args:
        group_title: Name of the group
        settings: Current group settings
        
    Returns:
        Formatted settings message
    """
    return f"<b>⚙ Customize your {group_title} settings as you like!</b>"

def build_no_results_message(search: str, user_mention: str) -> str:
    """
    Build message for no search results
    
    Args:
        search: Search query that returned no results
        user_mention: User mention string
        
    Returns:
        Formatted no results message
    """
    return f"""<b>🔍 Sorry {user_mention}!</b>

I couldn't find any files matching "<code>{search}</code>"

<b>💡 Try these tips:</b>
• Check your spelling
• Use different keywords
• Try a more general search
• Remove special characters

<b>🎬 Popular searches:</b> movie name + year"""

def build_spell_check_message(search: str, user_mention: str) -> str:
    """
    Build spell check suggestion message
    
    Args:
        search: Original search query
        user_mention: User mention string
        
    Returns:
        Formatted spell check message
    """
    return f"""<b>🔍 Hey {user_mention}!</b>

I couldn't find "<code>{search}</code>" but here are some similar titles you might be looking for:

<b>💡 Click on a title below to search:</b>"""

def build_maintenance_message() -> str:
    """
    Build maintenance mode message
    
    Returns:
        Maintenance message
    """
    return "🚧 Currently upgrading… Will return soon 🔜"

def build_support_group_message(user_mention: str, total_results: int, search: str, group_link: str) -> str:
    """
    Build support group response message
    
    Args:
        user_mention: User mention string
        total_results: Number of files found
        search: Search query
        group_link: Link to main group
        
    Returns:
        Formatted support group message
    """
    return f"""<b>✨ Hello {user_mention}! 

✅ Your request is already available. 
📂 Files found: {total_results} 
🔍 Search: <code>{search}</code> 
‼️ This is a <u>support group</u>, so you can't get files from here. 

📝 Search Here 👇</b>"""

def build_pm_search_disabled_message() -> str:
    """
    Build message for when PM search is disabled
    
    Returns:
        PM search disabled message
    """
    return "<b><i>⚠️ Not available here! Join & search below 👇</i></b>"

def build_search_progress_message(user_mention: str, search: str) -> str:
    """
    Build search progress message
    
    Args:
        user_mention: User mention string
        search: Search query
        
    Returns:
        Search progress message
    """
    return f"<b>🕐 Hold on... {user_mention} Searching for your query: <i>{search}...</i></b>"

def build_ai_spell_check_message() -> str:
    """
    Build AI spell check progress message
    
    Returns:
        AI spell check message
    """
    return "🤖 Hang tight… AI is checking your spelling!"

def build_spell_correction_message(corrected_term: str) -> str:
    """
    Build spell correction found message
    
    Args:
        corrected_term: AI-corrected search term
        
    Returns:
        Spell correction message
    """
    return f"<b>🔹 My pick <code>{corrected_term}</code>\nOn the search for <code>{corrected_term}</code></b>"

def build_file_delete_progress_message(keyword: str) -> str:
    """
    Build file deletion progress message
    
    Args:
        keyword: Keyword being used for deletion
        
    Returns:
        File deletion progress message
    """
    return f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>"

def build_file_delete_start_message() -> str:
    """
    Build file deletion start message
    
    Returns:
        File deletion start message
    """
    return "<b>ꜰɪʟᴇ ᴅᴇʟᴇᴛɪᴏɴ ᴘʀᴏᴄᴇꜱꜱ ᴡɪʟʟ ꜱᴛᴀʀᴛ ɪɴ 5 ꜱᴇᴄᴏɴᴅꜱ !</b>"

def build_file_delete_progress(deleted_count: int, keyword: str) -> str:
    """
    Build file deletion progress update message
    
    Args:
        deleted_count: Number of files deleted so far
        keyword: Keyword being used for deletion
        
    Returns:
        File deletion progress update
    """
    return f"""<b>ᴘʀᴏᴄᴇꜱꜱ ꜱᴛᴀʀᴛᴇᴅ ꜰᴏʀ ᴅᴇʟᴇᴛɪɴɢ ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ. 
ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ {deleted_count} ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ ꜰᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ {keyword} !

ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ...</b>"""

def build_file_delete_complete_message(deleted_count: int, keyword: str) -> str:
    """
    Build file deletion completion message
    
    Args:
        deleted_count: Total number of files deleted
        keyword: Keyword that was used for deletion
        
    Returns:
        File deletion completion message
    """
    return f"""<b>ᴘʀᴏᴄᴇꜱꜱ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ꜰᴏʀ ꜰɪʟᴇ ᴅᴇʟᴇᴛᴀᴛɪᴏɴ !

ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ {deleted_count} ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ ꜰᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ {keyword}.</b>"""
