"""
Business logic services for search, filtering, and core functionality
"""

from .search_service import (
    process_search_query, handle_search_pagination, handle_quality_filter,
    handle_season_filter, calculate_pagination_info, prepare_file_data_for_display,
    build_search_key, validate_search_permissions, extract_search_terms
)

from .filter_service import (
    auto_filter, handle_spell_check, ai_spell_check, advantage_spell_chok,
    build_search_response
)

__all__ = [
    # Search service
    'process_search_query', 'handle_search_pagination', 'handle_quality_filter',
    'handle_season_filter', 'calculate_pagination_info', 'prepare_file_data_for_display',
    'build_search_key', 'validate_search_permissions', 'extract_search_terms',
    
    # Filter service  
    'auto_filter', 'handle_spell_check', 'ai_spell_check', 'advantage_spell_chok',
    'build_search_response'
]
