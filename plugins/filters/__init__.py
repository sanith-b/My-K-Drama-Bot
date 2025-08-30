"""
Filters Plugin Package for My K-Drama Bot

This package contains various filter modules for handling different types
of content filtering, user permissions, and message processing for the
K-Drama Telegram bot.

Available Filters:
- Content filters for K-Drama searches
- User permission filters
- Message type filters
- Spam/abuse filters
- Search result filters
"""

import os
import importlib
from typing import Dict, List, Any
from pyrogram import Client, filters
from pyrogram.types import Message

__version__ = "1.0.0"
__author__ = "sanith-b"

# Dictionary to store all loaded filter plugins
LOADED_FILTERS: Dict[str, Any] = {}

# List of filter module names (add your filter modules here)
FILTER_MODULES = [
    "content_filter",
    "user_filter", 
    "permission_filter",
    "search_filter",
    "spam_filter",
    "media_filter"
]

def load_filters():
    """
    Dynamically load all filter modules from the filters directory.
    This function imports and initializes all available filter plugins.
    """
    current_dir = os.path.dirname(__file__)
    
    for module_name in FILTER_MODULES:
        try:
            # Import the filter module
            module = importlib.import_module(f".{module_name}", package=__name__)
            
            # Store the module in our loaded filters dictionary
            LOADED_FILTERS[module_name] = module
            
            print(f"✅ Successfully loaded filter: {module_name}")
            
        except ImportError as e:
            print(f"⚠️ Could not load filter {module_name}: {e}")
        except Exception as e:
            print(f"❌ Error loading filter {module_name}: {e}")

def get_filter(filter_name: str):
    """
    Get a specific filter by name.
    
    Args:
        filter_name (str): Name of the filter to retrieve
        
    Returns:
        The filter module or None if not found
    """
    return LOADED_FILTERS.get(filter_name)

def get_all_filters():
    """
    Get all loaded filter modules.
    
    Returns:
        Dict: Dictionary of all loaded filter modules
    """
    return LOADED_FILTERS.copy()

def is_filter_loaded(filter_name: str) -> bool:
    """
    Check if a specific filter is loaded.
    
    Args:
        filter_name (str): Name of the filter to check
        
    Returns:
        bool: True if filter is loaded, False otherwise
    """
    return filter_name in LOADED_FILTERS

# Common filter combinations for K-Drama bot
def kdrama_content_filter():
    """
    Combined filter for K-Drama related content.
    Matches messages containing K-Drama keywords.
    """
    kdrama_keywords = [
        "kdrama", "k-drama", "korean drama", "dorama",
        "episode", "eng sub", "subtitle", "download",
        "streaming", "watch online", "drama korea"
    ]
    
    return filters.text & filters.regex(
        r'\b(?:' + '|'.join(kdrama_keywords) + r')\b',
        flags=0
    )

def admin_only_filter():
    """
    Filter that only allows administrators to use certain commands.
    """
    async def func(_, __, message: Message):
        if not message.from_user:
            return False
        
        # Check if user is admin (you'll need to implement admin checking logic)
        # This is a placeholder - implement your admin checking logic here
        return message.from_user.id in [1204352805]  # Replace with actual admin IDs
    
    return filters.create(func, name="AdminOnlyFilter")

def valid_user_filter():
    """
    Filter for valid users (not banned, not spam accounts).
    """
    async def func(_, __, message: Message):
        if not message.from_user:
            return False
        
        user = message.from_user
        
        # Basic validation checks
        if user.is_bot:
            return False
        
        # Add more validation logic here (check against ban list, etc.)
        
        return True
    
    return filters.create(func, name="ValidUserFilter")

# Initialize filters when the package is imported
load_filters()

# Export commonly used items
__all__ = [
    'LOADED_FILTERS',
    'FILTER_MODULES', 
    'load_filters',
    'get_filter',
    'get_all_filters',
    'is_filter_loaded',
    'kdrama_content_filter',
    'admin_only_filter',
    'valid_user_filter',
    '__version__',
    '__author__'
]
