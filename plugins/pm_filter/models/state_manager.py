"""
State management for button states, search queries, and temporary data
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

class StateManager:
    """Manages bot state including search queries, button states, and temporary data"""
    
    def __init__(self):
        self._buttons: Dict[str, str] = {}  # Filtered search queries
        self._fresh: Dict[str, str] = {}   # Original search queries
        self._spell_check: Dict[str, Any] = {}  # Spell check data
        self._temp_files: Dict[str, List] = {}  # Temporary file storage
        self._user_shortcuts: Dict[int, int] = {}  # User chat shortcuts
        self._imdb_cache: Dict[int, str] = {}  # IMDB caption cache
        self._lock = asyncio.Lock()
        
    async def store_search_query(self, key: str, original_query: str, filtered_query: str = None):
        """Store original and filtered search queries"""
        async with self._lock:
            self._fresh[key] = original_query
            if filtered_query:
                self._buttons[key] = filtered_query
    
    async def get_search_query(self, key: str, filtered: bool = False) -> Optional[str]:
        """Get stored search query"""
        if filtered and key in self._buttons:
            return self._buttons[key]
        return self._fresh.get(key)
    
    async def store_temp_files(self, key: str, files: List):
        """Store temporary files for pagination"""
        async with self._lock:
            self._temp_files[key] = files
    
    async def get_temp_files(self, key: str) -> List:
        """Get temporary files"""
        return self._temp_files.get(key, [])
    
    async def store_user_shortcut(self, user_id: int, chat_id: int):
        """Store user's current chat for shortcuts"""
        async with self._lock:
            self._user_shortcuts[user_id] = chat_id
    
    async def get_user_shortcut(self, user_id: int) -> Optional[int]:
        """Get user's shortcut chat"""
        return self._user_shortcuts.get(user_id)
    
    async def store_imdb_caption(self, user_id: int, caption: str):
        """Store IMDB caption for user"""
        async with self._lock:
            self._imdb_cache[user_id] = caption
    
    async def get_imdb_caption(self, user_id: int) -> Optional[str]:
        """Get IMDB caption for user"""
        return self._imdb_cache.get(user_id)
    
    async def store_spell_check(self, key: str, data: Any):
        """Store spell check data"""
        async with self._lock:
            self._spell_check[key] = data
    
    async def get_spell_check(self, key: str) -> Any:
        """Get spell check data"""
        return self._spell_check.get(key)
    
    async def cleanup_expired_data(self, max_age_minutes: int = 30):
        """Clean up expired data (should be called periodically)"""
        async with self._lock:
            current_time = datetime.now()
            # Note: This is a basic cleanup. In production, you'd want to store timestamps
            # and clean based on actual age
            
            # Clear spell check data (it's temporary)
            self._spell_check.clear()
            
            # Limit the size of other caches
            if len(self._fresh) > 1000:
                # Remove oldest entries (basic FIFO)
                keys_to_remove = list(self._fresh.keys())[:500]
                for key in keys_to_remove:
                    self._fresh.pop(key, None)
                    self._buttons.pop(key, None)
                    self._temp_files.pop(key, None)
    
    async def clear_user_data(self, user_id: int):
        """Clear data for specific user"""
        async with self._lock:
            self._user_shortcuts.pop(user_id, None)
            self._imdb_cache.pop(user_id, None)
            
            # Remove user-specific keys
            keys_to_remove = []
            for key in self._fresh.keys():
                if str(user_id) in key:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self._fresh.pop(key, None)
                self._buttons.pop(key, None)
                self._temp_files.pop(key, None)
    
    async def get_stats(self) -> Dict[str, int]:
        """Get current state statistics"""
        return {
            "fresh_queries": len(self._fresh),
            "filtered_queries": len(self._buttons),
            "temp_files": len(self._temp_files),
            "user_shortcuts": len(self._user_shortcuts),
            "imdb_cache": len(self._imdb_cache),
            "spell_check": len(self._spell_check)
        }

# Global state manager instance
state_manager = StateManager()

# Backwards compatibility with original global variables
class TempCompat:
    """Temporary compatibility class to maintain original variable names"""
    
    @property
    def GETALL(self) -> Dict[str, List]:
        return state_manager._temp_files
    
    @property
    def SHORT(self) -> Dict[int, int]:
        return state_manager._user_shortcuts
    
    @property
    def IMDB_CAP(self) -> Dict[int, str]:
        return state_manager._imdb_cache

temp = TempCompat()

# Original global variables for backwards compatibility
BUTTON = state_manager._buttons
BUTTONS = state_manager._buttons
FRESH = state_manager._fresh
SPELL_CHECK = state_manager._spell_check
