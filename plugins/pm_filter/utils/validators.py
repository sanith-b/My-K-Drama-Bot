"""
Input validation utilities
"""

import re
from typing import Optional, Tuple
from config.constants import URL_PATTERN, COMMAND_PATTERN, SPELL_CHECK_PATTERN

def validate_search_query(query: str) -> Tuple[bool, Optional[str]]:
    """
    Validate and sanitize search query
    
    Args:
        query: Raw search query from user
        
    Returns:
        Tuple of (is_valid, sanitized_query or error_message)
    """
    if not query or not isinstance(query, str):
        return False, "Empty or invalid query"
    
    # Check if it's a command
    if query.startswith(("/", "#")):
        return False, "Command detected"
    
    # Check for regex patterns that should be ignored
    if re.findall(COMMAND_PATTERN, query):
        return False, "Invalid pattern detected"
    
    # Check for URLs
    if re.search(URL_PATTERN, query):
        return False, "URLs not allowed in search"
    
    # Check minimum length
    if len(query.strip()) < 2:
        return False, "Query too short"
    
    # Check maximum length
    if len(query) > 100:
        return False, "Query too long (max 100 characters)"
    
    # Sanitize query
    sanitized = sanitize_search_query(query)
    
    return True, sanitized

def sanitize_search_query(query: str) -> str:
    """
    Sanitize search query by removing unwanted characters and patterns
    
    Args:
        query: Raw search query
        
    Returns:
        Sanitized query
    """
    # Remove extra whitespace and normalize
    query = re.sub(r'\s+', ' ', query).strip()
    
    # Remove special characters that might cause issues
    query = query.replace("-", " ")
    query = query.replace(":", "")
    query = query.replace(";", "")
    query = query.replace("'", "")
    query = query.replace('"', "")
    
    # Convert to lowercase for consistency
    query = query.lower()
    
    return query

def validate_chat_id(chat_id: str) -> Tuple[bool, Optional[int]]:
    """
    Validate Telegram chat ID format
    
    Args:
        chat_id: Chat ID as string
        
    Returns:
        Tuple of (is_valid, parsed_chat_id or None)
    """
    if not chat_id or not isinstance(chat_id, str):
        return False, None
    
    # Check if it's a valid format for channel/group ID
    if chat_id.startswith("-100") and chat_id[4:].isdigit() and len(chat_id) >= 10:
        try:
            parsed_id = int(chat_id)
            return True, parsed_id
        except ValueError:
            return False, None
    
    # Check if it's a valid user ID (positive integer)
    if chat_id.isdigit() and len(chat_id) <= 10:
        try:
            parsed_id = int(chat_id)
            if parsed_id > 0:
                return True, parsed_id
        except ValueError:
            pass
    
    return False, None

def validate_callback_data(callback_data: str) -> Tuple[bool, list]:
    """
    Validate and parse callback data
    
    Args:
        callback_data: Callback query data
        
    Returns:
        Tuple of (is_valid, parsed_parts)
    """
    if not callback_data or not isinstance(callback_data, str):
        return False, []
    
    # Check length limit
    if len(callback_data) > 64:  # Telegram limit
        return False, []
    
    # Split and validate parts
    parts = callback_data.split("#")
    
    # Basic validation - must have at least action
    if len(parts) < 1:
        return False, []
    
    return True, parts

def validate_user_permission(user_id: int, allowed_users: list = None, admins: list = None) -> bool:
    """
    Validate user permissions
    
    Args:
        user_id: User ID to check
        allowed_users: List of allowed user IDs
        admins: List of admin user IDs
        
    Returns:
        True if user has permission, False otherwise
    """
    if not user_id or not isinstance(user_id, int):
        return False
    
    if admins and user_id in admins:
        return True
    
    if allowed_users and user_id in allowed_users:
        return True
    
    return False

def validate_file_id(file_id: str) -> bool:
    """
    Validate Telegram file ID format
    
    Args:
        file_id: Telegram file ID
        
    Returns:
        True if valid format, False otherwise
    """
    if not file_id or not isinstance(file_id, str):
        return False
    
    # Basic validation - Telegram file IDs are usually alphanumeric with some special chars
    if len(file_id) < 10 or len(file_id) > 200:
        return False
    
    # Check for valid characters (basic check)
    if not re.match(r'^[A-Za-z0-9_-]+$', file_id.replace(':', '').replace('.', '')):
        return False
    
    return True

def validate_offset(offset_str: str) -> Tuple[bool, int]:
    """
    Validate pagination offset
    
    Args:
        offset_str: Offset as string
        
    Returns:
        Tuple of (is_valid, parsed_offset)
    """
    try:
        offset = int(offset_str)
        if offset < 0:
            return False, 0
        if offset > 10000:  # Reasonable upper limit
            return False, 0
        return True, offset
    except (ValueError, TypeError):
        return False, 0

def validate_quality_filter(quality: str, valid_qualities: list) -> bool:
    """
    Validate quality filter selection
    
    Args:
        quality: Quality string to validate
        valid_qualities: List of valid quality options
        
    Returns:
        True if valid, False otherwise
    """
    if not quality or not isinstance(quality, str):
        return False
    
    quality_lower = quality.lower().strip()
    valid_qualities_lower = [q.lower().strip() for q in valid_qualities]
    
    return quality_lower in valid_qualities_lower

def validate_season_filter(season: str, valid_seasons: list) -> bool:
    """
    Validate season filter selection
    
    Args:
        season: Season string to validate
        valid_seasons: List of valid season options
        
    Returns:
        True if valid, False otherwise
    """
    if not season or not isinstance(season, str):
        return False
    
    season_lower = season.lower().strip()
    valid_seasons_lower = [s.lower().strip() for s in valid_seasons]
    
    return season_lower in valid_seasons_lower

def clean_filename_for_display(filename: str) -> str:
    """
    Clean filename for safe display
    
    Args:
        filename: Original filename
        
    Returns:
        Cleaned filename safe for display
    """
    if not filename:
        return "Unknown File"
    
    # Remove file extension
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    
    # Replace common separators with spaces
    name = re.sub(r'[._\-\[\]()]', ' ', name)
    
    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Limit length
    if len(name) > 50:
        name = name[:47] + "..."
    
    return name or "Unknown File"
