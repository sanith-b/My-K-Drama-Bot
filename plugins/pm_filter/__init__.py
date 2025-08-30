"""
PM Filter Plugin Package

This package contains the modular PM filter functionality for the K-Drama Bot.
It replaces the monolithic pm_filter.py with organized, maintainable modules.

Package Structure:
- config/: Configuration constants and settings
- models/: State management and data models
- utils/: Validation and helper functions  
- ui/: User interface builders (keyboards and messages)
- services/: Core business logic (search, filtering)
- handlers/: Pyrogram message and callback handlers

Usage:
The handlers are automatically loaded by Pyrogram when the bot starts.
Import specific components as needed:

    from plugins.pm_filter.models import state_manager
    from plugins.pm_filter.config import QUALITIES, SEASONS
    from plugins.pm_filter.utils import validate_search_query
"""

# Import all handler modules to ensure they're loaded by Pyrogram
from .handlers import (
    message_handlers,
    callback_handlers, 
    settings_handlers,
    admin_handlers
)

# Import key components for external access
from .models.state_manager import state_manager, temp
from .config.constants import QUALITIES, SEASONS, ERROR_MESSAGES

# Package metadata
__version__ = "2.0.0"
__author__ = "Bot Developer"
__description__ = "Modular PM Filter system for K-Drama Bot"

# Export main components
__all__ = [
    # Handler modules
    'message_handlers',
    'callback_handlers', 
    'settings_handlers',
    'admin_handlers',
    
    # Key components
    'state_manager',
    'temp', 
    'QUALITIES',
    'SEASONS',
    'ERROR_MESSAGES'
]

# Initialize package
import logging
logger = logging.getLogger(__name__)
logger.info("PM Filter package loaded successfully")

# Backwards compatibility for any existing code that imports from pm_filter
# This allows gradual migration from the old monolithic structure
try:
    from .models.state_manager import BUTTON, BUTTONS, FRESH, SPELL_CHECK
    
    # Make these available at package level for compatibility
    globals()['BUTTON'] = BUTTON
    globals()['BUTTONS'] = BUTTONS  
    globals()['FRESH'] = FRESH
    globals()['SPELL_CHECK'] = SPELL_CHECK
    
except ImportError as e:
    logger.warning(f"Backwards compatibility import failed: {e}")

# Optional: Add package-level initialization logic
async def initialize_pm_filter():
    """
    Initialize PM Filter package components
    This can be called during bot startup if needed
    """
    try:
        # Perform any necessary initialization
        await state_manager.cleanup_expired_data()
        logger.info("PM Filter initialized successfully")
    except Exception as e:
        logger.error(f"PM Filter initialization failed: {e}")

# Optional: Add cleanup function
async def cleanup_pm_filter():
    """
    Cleanup PM Filter package components
    This can be called during bot shutdown
    """
    try:
        await state_manager.cleanup_expired_data()
        logger.info("PM Filter cleanup completed")
    except Exception as e:
        logger.error(f"PM Filter cleanup failed: {e}")

# Version check and compatibility warnings
import sys
if sys.version_info < (3, 7):
    logger.warning("PM Filter requires Python 3.7 or higher for optimal performance")

try:
    import pyrogram
    if hasattr(pyrogram, '__version__'):
        version_parts = pyrogram.__version__.split('.')
        major, minor = int(version_parts[0]), int(version_parts[1])
        if major < 2:
            logger.warning("PM Filter is optimized for Pyrogram 2.0+")
except ImportError:
    logger.error("Pyrogram not found - PM Filter requires Pyrogram")
