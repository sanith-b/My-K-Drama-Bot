"""
Search service for handling file searches, filtering, and pagination
"""

import math
from typing import List, Dict, Any, Tuple, Optional
from models.state_manager import state_manager
from utils.helpers import replace_words, clean_search_query
from utils.validators import validate_search_query, validate_offset, validate_quality_filter, validate_season_filter
from config.constants import QUALITIES, SEASONS, DEFAULT_MAX_BUTTONS

async def process_search_query(query: str) -> Tuple[bool, str]:
    """
    Process and validate search query
    
    Args:
        query: Raw search query
        
    Returns:
        Tuple of (is_valid, processed_query or error_message)
    """
    is_valid, result = validate_search_query(query)
    if not is_valid:
        return False, result
    
    # Apply word replacements and cleaning
    processed_query = replace_words(result)
    processed_query = clean_search_query(processed_query)
    
    return True, processed_query

async def handle_search_pagination(
    query_data: str,
    chat_id: int,
    user_id: int
) -> Tuple[bool, Dict[str, Any]]:
    """
    Handle pagination for search results
    
    Args:
        query_data: Callback query data (next_{req}_{key}_{offset})
        chat_id: Chat ID
        user_id: User ID making the request
        
    Returns:
        Tuple of (success, result_data)
    """
    try:
        parts = query_data.split("_")
        if len(parts) != 4:
            return False, {"error": "Invalid pagination data"}
        
        _, req_user_id, key, offset_str = parts
        
        # Validate requesting user
        if int(req_user_id) not in [user_id, 0]:
            return False, {"error": "Unauthorized pagination request"}
        
        # Validate offset
        is_valid_offset, offset = validate_offset(offset_str)
        if not is_valid_offset:
            return False, {"error": "Invalid offset"}
        
        # Get search query
        search_query = await state_manager.get_search_query(key, filtered=True)
        if not search_query:
            search_query = await state_manager.get_search_query(key, filtered=False)
        
        if not search_query:
            return False, {"error": "Search query expired"}
        
        return True, {
            "search_query": search_query,
            "offset": offset,
            "key": key,
            "req_user_id": int(req_user_id)
        }
        
    except (ValueError, IndexError) as e:
        return False, {"error": f"Pagination parsing error: {str(e)}"}

async def handle_quality_filter(
    callback_data: str,
    chat_id: int,
    user_id: int
) -> Tuple[bool, Dict[str, Any]]:
    """
    Handle quality filtering for search results
    
    Args:
        callback_data: Callback data (fq#{quality}#{key}#{offset})
        chat_id: Chat ID
        user_id: User ID
        
    Returns:
        Tuple of (success, filter_result)
    """
    try:
        _, quality, key, offset_str = callback_data.split("#")
        
        # Validate offset
        is_valid_offset, offset = validate_offset(offset_str)
        if not is_valid_offset:
            return False, {"error": "Invalid offset"}
        
        # Get original search query
        original_search = await state_manager.get_search_query(key, filtered=False)
        if not original_search:
            return False, {"error": "Original search query not found"}
        
        # Handle quality filtering
        if quality == "homepage":
            # Reset to original search
            filtered_search = original_search
        else:
            # Validate quality
            if not validate_quality_filter(quality, QUALITIES):
                return False, {"error": "Invalid quality filter"}
            
            # Apply quality filter
            search_words = original_search.replace("_", " ").lower()
            
            # Remove existing quality if present
            for qual in QUALITIES:
                if qual.lower() in search_words:
                    search_words = search_words.replace(qual.lower(), "").strip()
            
            # Add new quality
            filtered_search = f"{search_words} {quality}".strip()
        
        # Store filtered search
        await state_manager.store_search_query(key, original_search, filtered_search)
        
        return True, {
            "filtered_search": filtered_search,
            "original_search": original_search,
            "offset": offset,
            "key": key,
            "quality": quality
        }
        
    except (ValueError, IndexError) as e:
        return False, {"error": f"Quality filter parsing error: {str(e)}"}

async def handle_season_filter(
    callback_data: str,
    chat_id: int,
    user_id: int
) -> Tuple[bool, Dict[str, Any]]:
    """
    Handle season filtering for search results
    
    Args:
        callback_data: Callback data (fs#{season}#{key}#{offset})
        chat_id: Chat ID
        user_id: User ID
        
    Returns:
        Tuple of (success, filter_result)
    """
    try:
        _, season, key, offset_str = callback_data.split("#")
        
        # Validate offset
        is_valid_offset, offset = validate_offset(offset_str)
        if not is_valid_offset:
            return False, {"error": "Invalid offset"}
        
        # Get original search query
        original_search = await state_manager.get_search_query(key, filtered=False)
        if not original_search:
            return False, {"error": "Original search query not found"}
        
        # Handle season filtering
        if season == "homepage":
            # Reset to original search
            filtered_search = original_search
        else:
            # Validate season
            if not validate_season_filter(season, SEASONS):
                return False, {"error": "Invalid season filter"}
            
            # Apply season filter
            search_words = original_search.replace("_", " ").lower()
            
            # Remove existing season if present
            for seas in SEASONS:
                if seas.lower() in search_words:
                    search_words = search_words.replace(seas.lower(), "").strip()
            
            # Add new season
            filtered_search = f"{search_words} {season}".strip()
        
        # Store filtered search
        await state_manager.store_search_query(key, original_search, filtered_search)
        
        return True, {
            "filtered_search": filtered_search,
            "original_search": original_search,
            "offset": offset,
            "key": key,
            "season": season
        }
        
    except (ValueError, IndexError) as e:
        return False, {"error": f"Season filter parsing error: {str(e)}"}

async def calculate_pagination_info(
    offset: int,
    total_results: int,
    max_buttons: int = DEFAULT_MAX_BUTTONS
) -> Dict[str, Any]:
    """
    Calculate pagination information
    
    Args:
        offset: Current offset
        total_results: Total number of results
        max_buttons: Maximum buttons per page
        
    Returns:
        Dictionary with pagination info
    """
    current_page = (offset // max_buttons) + 1
    total_pages = math.ceil(total_results / max_buttons) if total_results > 0 else 1
    
    # Calculate previous offset
    prev_offset = None
    if offset > 0:
        prev_offset = max(0, offset - max_buttons)
    
    # Calculate next offset
    next_offset = None
    if offset + max_buttons < total_results:
        next_offset = offset + max_buttons
    
    return {
        "current_page": current_page,
        "total_pages": total_pages,
        "prev_offset": prev_offset,
        "next_offset": next_offset,
        "has_prev": prev_offset is not None,
        "has_next": next_offset is not None,
        "is_last_page": next_offset is None
    }

async def prepare_file_data_for_display(files: List, settings: Dict = None) -> List[Dict]:
    """
    Prepare file data for display in UI
    
    Args:
        files: List of file objects
        settings: Display settings
        
    Returns:
        List of prepared file data
    """
    prepared_files = []
    settings = settings or {}
    
    for file in files:
        file_data = {
            "id": file.file_id,
            "name": file.file_name,
            "size": file.file_size,
            "display_name": clean_filename(file.file_name) if hasattr(file, 'file_name') else "Unknown",
            "size_text": get_size(file.file_size) if hasattr(file, 'file_size') else "Unknown"
        }
        
        # Add additional metadata if available
        if hasattr(file, 'caption'):
            file_data["caption"] = file.caption
        
        prepared_files.append(file_data)
    
    return prepared_files

async def build_search_key(chat_id: int, message_id: int) -> str:
    """
    Build unique search key for state management
    
    Args:
        chat_id: Chat ID
        message_id: Message ID
        
    Returns:
        Unique search key
    """
    return f"{chat_id}-{message_id}"

async def validate_search_permissions(
    chat_id: int,
    user_id: int,
    settings: Dict = None
) -> Tuple[bool, str]:
    """
    Validate if user can perform search in given chat
    
    Args:
        chat_id: Chat ID where search is requested
        user_id: User ID requesting search
        settings: Chat settings
        
    Returns:
        Tuple of (can_search, reason if not allowed)
    """
    settings = settings or {}
    
    # Check if PM search is enabled for private chats
    if chat_id > 0:  # Private chat
        pm_search_enabled = settings.get('pm_search', True)
        if not pm_search_enabled:
            return False, "PM search is disabled"
    
    # Add more permission checks as needed
    return True, "Allowed"

def extract_search_terms(query: str) -> Dict[str, Any]:
    """
    Extract various search terms and filters from query
    
    Args:
        query: Search query
        
    Returns:
        Dictionary with extracted terms
    """
    query_lower = query.lower()
    
    # Extract quality terms
    detected_quality = None
    for quality in QUALITIES:
        if quality.lower() in query_lower:
            detected_quality = quality
            break
    
    # Extract season terms
    detected_season = None
    for season in SEASONS:
        if season.lower() in query_lower:
            detected_season = season
            break
    
    # Extract year
    import re
    year_match = re.search(r'\b(19[8-9]\d|20[0-4]\d)\b', query)
    detected_year = year_match.group(0) if year_match else None
    
    # Clean query (remove detected filters)
    clean_query = query_lower
    if detected_quality:
        clean_query = clean_query.replace(detected_quality.lower(), "").strip()
    if detected_season:
        clean_query = clean_query.replace(detected_season.lower(), "").strip()
    if detected_year:
        clean_query = clean_query.replace(detected_year, "").strip()
    
    return {
        "clean_query": clean_query,
        "quality": detected_quality,
        "season": detected_season,
        "year": detected_year,
        "original_query": query
    }
