"""
Utility helper functions for file formatting, text processing, and common operations
"""

import re
import math
from typing import Optional, Dict, Any
from config.constants import SIZE_UNITS, SPELL_CHECK_PATTERN

def get_size(size_bytes: int) -> str:
    """
    Convert bytes to human readable format
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Human readable size string
    """
    if size_bytes == 0:
        return "0 B"
    
    try:
        size_bytes = int(size_bytes)
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {SIZE_UNITS[i]}"
    except (ValueError, OverflowError, IndexError):
        return "Unknown"

def silent_size(size_bytes: int) -> str:
    """
    Alias for get_size for backwards compatibility
    """
    return get_size(size_bytes)

def clean_filename(filename: str) -> str:
    """
    Clean filename for display by removing common prefixes/suffixes and formatting
    
    Args:
        filename: Original filename
        
    Returns:
        Cleaned filename
    """
    if not filename:
        return "Unknown File"
    
    # Remove file extension
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    
    # Remove common prefixes
    prefixes_to_remove = [
        r'^\[.*?\]\s*',  # [Something] prefix
        r'^www\.\w+\.\w+\s*',  # website prefixes
        r'^\d{4}\s*',  # Year prefix
    ]
    
    for prefix in prefixes_to_remove:
        name = re.sub(prefix, '', name, flags=re.IGNORECASE)
    
    # Replace separators with spaces
    name = re.sub(r'[._\-\[\](){}]', ' ', name)
    
    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Capitalize words properly
    name = ' '.join(word.capitalize() for word in name.split())
    
    return name or "Unknown File"

def extract_tag(filename: str) -> str:
    """
    Extract quality/format tags from filename
    
    Args:
        filename: Original filename
        
    Returns:
        Extracted tags as string
    """
    if not filename:
        return ""
    
    tags = []
    filename_lower = filename.lower()
    
    # Quality tags
    quality_patterns = [
        r'\b(720p|1080p|480p|360p|4k|2k|1440p)\b',
        r'\b(hd|full\s*hd|ultra\s*hd|uhd)\b',
        r'\b(x264|x265|h264|h265|hevc|avc)\b',
        r'\b(bluray|blu-ray|brrip|bdrip|web-dl|webrip|hdtv)\b',
        r'\b(5\.1|7\.1|atmos|dts|ac3|aac)\b'
    ]
    
    for pattern in quality_patterns:
        matches = re.findall(pattern, filename_lower, re.IGNORECASE)
        tags.extend([match.upper() if isinstance(match, str) else match[0].upper() for match in matches])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    
    return ' | '.join(unique_tags[:3])  # Limit to 3 tags

def replace_words(text: str) -> str:
    """
    Replace common misspellings and normalize search terms
    
    Args:
        text: Original text
        
    Returns:
        Text with replacements applied
    """
    if not text:
        return ""
    
    # Common replacements for movie searches
    replacements = {
        # Language variations
        'malayalam': 'malayalam',
        'tamil': 'tamil',
        'hindi': 'hindi',
        'telugu': 'telugu',
        'kannada': 'kannada',
        
        # Common misspellings
        'moive': 'movie',
        'moives': 'movies',
        'flim': 'film',
        'flims': 'films',
        'seriez': 'series',
        'seires': 'series',
        
        # Format variations
        'hd': 'HD',
        'fullhd': 'Full HD',
        'blu ray': 'BluRay',
        'web dl': 'WEB-DL',
        
        # Remove common unnecessary words
        'please': '',
        'send': '',
        'give': '',
        'share': '',
        'need': '',
        'want': '',
    }
    
    text_lower = text.lower()
    for old, new in replacements.items():
        text_lower = text_lower.replace(old, new)
    
    # Remove extra whitespace
    text_lower = re.sub(r'\s+', ' ', text_lower).strip()
    
    return text_lower

def format_search_results_count(count: int) -> str:
    """
    Format search results count for display
    
    Args:
        count: Number of results
        
    Returns:
        Formatted count string
    """
    if count == 0:
        return "No files"
    elif count == 1:
        return "1 file"
    elif count < 1000:
        return f"{count} files"
    elif count < 1000000:
        return f"{count/1000:.1f}K files"
    else:
        return f"{count/1000000:.1f}M files"

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to specified length
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def extract_year(filename: str) -> Optional[str]:
    """
    Extract year from filename
    
    Args:
        filename: Filename to search
        
    Returns:
        Extracted year or None
    """
    if not filename:
        return None
    
    # Look for 4-digit year patterns
    year_patterns = [
        r'\b(19[8-9]\d|20[0-4]\d)\b',  # 1980-2049
        r'\((\d{4})\)',  # Year in parentheses
        r'[\.\s](\d{4})[\.\s]',  # Year surrounded by dots or spaces
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, filename)
        if match:
            year = match.group(1) if len(match.groups()) > 0 else match.group(0)
            if 1900 <= int(year) <= 2050:
                return year
    
    return None

def format_duration(seconds: int) -> str:
    """
    Format duration in seconds to human readable format
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"

def sanitize_caption(text: str) -> str:
    """
    Sanitize caption text for Telegram
    
    Args:
        text: Raw caption text
        
    Returns:
        Sanitized caption
    """
    if not text:
        return ""
    
    # Remove potentially problematic characters
    text = re.sub(r'[<>]', '', text)  # Remove < > that might interfere with HTML
    
    # Limit length (Telegram caption limit is 1024 characters)
    if len(text) > 1020:
        text = text[:1017] + "..."
    
    return text

def extract_episode_info(filename: str) -> Dict[str, Optional[str]]:
    """
    Extract season and episode information from filename
    
    Args:
        filename: Filename to analyze
        
    Returns:
        Dict with season and episode info
    """
    info = {"season": None, "episode": None}
    
    if not filename:
        return info
    
    filename_lower = filename.lower()
    
    # Season patterns
    season_patterns = [
        r'season\s*(\d+)',
        r's(\d{1,2})',
        r'series\s*(\d+)',
    ]
    
    for pattern in season_patterns:
        match = re.search(pattern, filename_lower)
        if match:
            info["season"] = f"Season {match.group(1)}"
            break
    
    # Episode patterns
    episode_patterns = [
        r'episode\s*(\d+)',
        r'ep\s*(\d+)',
        r'e(\d{1,3})',
        r's\d{1,2}e(\d{1,3})',
    ]
    
    for pattern in episode_patterns:
        match = re.search(pattern, filename_lower)
        if match:
            info["episode"] = f"Episode {match.group(1)}"
            break
    
    return info

def clean_search_query(query: str) -> str:
    """
    Clean and prepare search query
    
    Args:
        query: Raw search query
        
    Returns:
        Cleaned search query
    """
    if not query:
        return ""
    
    # Remove spell check patterns
    query = re.sub(SPELL_CHECK_PATTERN, "", query, flags=re.IGNORECASE)
    query = query.strip() + " movie" if query.strip() else ""
    
    # Basic cleaning
    query = re.sub(r'\s+', ' ', query).strip()
    
    return query
