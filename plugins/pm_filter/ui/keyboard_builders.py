"""
Inline keyboard builders for various bot interactions
"""

import math
from typing import List, Dict, Any, Optional
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.constants import QUALITIES, SEASONS, DEFAULT_MAX_BUTTONS
from utils.helpers import get_size, clean_filename, extract_tag

def build_file_buttons(files: List, key: str, settings: Dict = None) -> List[List[InlineKeyboardButton]]:
    """
    Build inline keyboard buttons for file listing
    
    Args:
        files: List of file objects
        key: Unique key for this search
        settings: Group settings
        
    Returns:
        List of button rows
    """
    if not files:
        return []
    
    buttons = []
    settings = settings or {}
    
    # Add filter buttons at the top
    filter_row = [
        InlineKeyboardButton("⭐ Quality", callback_data=f"qualities#{key}#0"),
        InlineKeyboardButton("🗓️ Season", callback_data=f"seasons#{key}#0")
    ]
    buttons.append(filter_row)
    
    # Add "Send All Files" button
    send_all_row = [
        InlineKeyboardButton("🚀 Send All Files", callback_data=f"sendfiles#{key}")
    ]
    buttons.append(send_all_row)
    
    # Add file buttons only if button mode is enabled
    if settings.get('button', True):
        for file in files:
            file_text = f"{get_size(file.file_size)} | {extract_tag(file.file_name)} {clean_filename(file.file_name)}"
            file_button = [
                InlineKeyboardButton(
                    text=file_text,
                    callback_data=f'file#{file.file_id}'
                )
            ]
            buttons.append(file_button)
    
    return buttons

def build_pagination_buttons(
    offset: int, 
    total_results: int, 
    key: str, 
    req_user_id: int,
    max_buttons: int = DEFAULT_MAX_BUTTONS
) -> List[InlineKeyboardButton]:
    """
    Build pagination buttons for search results
    
    Args:
        offset: Current offset
        total_results: Total number of results
        key: Search key
        req_user_id: Requesting user ID
        max_buttons: Maximum buttons per page
        
    Returns:
        List of pagination buttons
    """
    buttons = []
    
    # Calculate pagination
    current_page = (offset // max_buttons) + 1
    total_pages = math.ceil(total_results / max_buttons)
    
    # Back button
    if offset > 0:
        prev_offset = max(0, offset - max_buttons)
        buttons.append(
            InlineKeyboardButton("⬅️ Back", callback_data=f"next_{req_user_id}_{key}_{prev_offset}")
        )
    
    # Page indicator
    buttons.append(
        InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="pages")
    )
    
    # Next button
    next_offset = offset + max_buttons
    if next_offset < total_results:
        buttons.append(
            InlineKeyboardButton("➡️ Next", callback_data=f"next_{req_user_id}_{key}_{next_offset}")
        )
    
    return buttons

def build_quality_buttons(key: str, offset: int = 0) -> List[List[InlineKeyboardButton]]:
    """
    Build quality filter buttons
    
    Args:
        key: Search key
        offset: Current offset
        
    Returns:
        List of button rows
    """
    buttons = []
    
    # Header
    buttons.append([
        InlineKeyboardButton("🎯 Select Quality", callback_data="ident")
    ])
    
    # Quality options in pairs
    for i in range(0, len(QUALITIES)-1, 2):
        row = [
            InlineKeyboardButton(
                text=QUALITIES[i].title(),
                callback_data=f"fq#{QUALITIES[i].lower()}#{key}#{offset}"
            ),
            InlineKeyboardButton(
                text=QUALITIES[i+1].title(),
                callback_data=f"fq#{QUALITIES[i+1].lower()}#{key}#{offset}"
            ),
        ]
        buttons.append(row)
    
    # Handle odd number of qualities
    if len(QUALITIES) % 2 == 1:
        buttons.append([
            InlineKeyboardButton(
                text=QUALITIES[-1].title(),
                callback_data=f"fq#{QUALITIES[-1].lower()}#{key}#{offset}"
            )
        ])
    
    # Back button
    buttons.append([
        InlineKeyboardButton("📂 Back to Files 📂", callback_data=f"fq#homepage#{key}#{offset}")
    ])
    
    return buttons

def build_season_buttons(key: str, offset: int = 0) -> List[List[InlineKeyboardButton]]:
    """
    Build season filter buttons
    
    Args:
        key: Search key
        offset: Current offset
        
    Returns:
        List of button rows
    """
    buttons = []
    
    # Header
    buttons.append([
        InlineKeyboardButton("🗓️ Select Season", callback_data="ident")
    ])
    
    # Season options in pairs
    for i in range(0, len(SEASONS)-1, 2):
        row = [
            InlineKeyboardButton(
                text=SEASONS[i].title(),
                callback_data=f"fs#{SEASONS[i].lower()}#{key}#{offset}"
            ),
            InlineKeyboardButton(
                text=SEASONS[i+1].title(),
                callback_data=f"fs#{SEASONS[i+1].lower()}#{key}#{offset}"
            ),
        ]
        buttons.append(row)
    
    # Handle odd number of seasons
    if len(SEASONS) % 2 == 1:
        buttons.append([
            InlineKeyboardButton(
                text=SEASONS[-1].title(),
                callback_data=f"fs#{SEASONS[-1].lower()}#{key}#{offset}"
            )
        ])
    
    # Back button
    buttons.append([
        InlineKeyboardButton("📂 Back to Files 📂", callback_data=f"fs#homepage#{key}#{offset}")
    ])
    
    return buttons

def build_settings_buttons(grp_id: int, settings: Dict[str, Any]) -> List[List[InlineKeyboardButton]]:
    """
    Build group settings buttons
    
    Args:
        grp_id: Group ID
        settings: Current settings
        
    Returns:
        List of button rows
    """
    buttons = [
        [
            InlineKeyboardButton('📄 Result Page',
                               callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}'),
            InlineKeyboardButton('Button' if settings.get("button") else 'Text',
                               callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('🛡️ Protected File',
                               callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ Enable' if settings["file_secure"] else '❌ Disable',
                               callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('🎬 IMDb Poster', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ Enable' if settings["imdb"] else '❌ Disable',
                               callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('👋 Welcome Message', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ Enable' if settings["welcome"] else '❌ Disable',
                               callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('🗑️ Auto Delete',
                               callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
            InlineKeyboardButton('✅ Enable' if settings["auto_delete"] else '❌ Disable',
                               callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('🔘 Max Buttons',
                               callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
            InlineKeyboardButton('10' if settings["max_btn"] else f'{DEFAULT_MAX_BUTTONS}',
                               callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('📜 Log Channel', callback_data=f'log_setgs#{grp_id}'),
            InlineKeyboardButton('📝 Add Caption', callback_data=f'caption_setgs#{grp_id}'),
        ],
        [
            InlineKeyboardButton('🔒 Exit Settings', callback_data='close_data')
        ]
    ]
    
    return buttons

def build_start_buttons() -> List[List[InlineKeyboardButton]]:
    """
    Build start command buttons
    
    Returns:
        List of button rows
    """
    return [
        [
            InlineKeyboardButton('🚀 Add Me Now!', url=f'http://telegram.me/{temp.U_NAME}?startgroup=true')
        ],
        [
            InlineKeyboardButton('🔥 Trending', callback_data="topsearch"),
            InlineKeyboardButton('ℹ️ About', callback_data='me')
        ],
        [
            InlineKeyboardButton('🆘 Help', callback_data='disclaimer'),
            InlineKeyboardButton('📞 Contact Us', callback_data="contact")
        ]
    ]

def build_spell_check_buttons(movies: List[Dict], user_id: int) -> List[List[InlineKeyboardButton]]:
    """
    Build spell check suggestion buttons
    
    Args:
        movies: List of movie suggestions
        user_id: User ID for callback validation
        
    Returns:
        List of button rows
    """
    buttons = []
    
    for movie in movies:
        buttons.append([
            InlineKeyboardButton(
                text=movie.get('title', 'Unknown'),
                callback_data=f"spol#{movie.get('movieID', 'unknown')}#{user_id}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton("❌ Close", callback_data='close_data')
    ])
    
    return buttons

def build_error_buttons(error_type: str = "general") -> List[List[InlineKeyboardButton]]:
    """
    Build error message buttons
    
    Args:
        error_type: Type of error for appropriate buttons
        
    Returns:
        List of button rows
    """
    if error_type == "no_files":
        return [
            [InlineKeyboardButton("💡 Try Different Search", callback_data="close_data")],
            [InlineKeyboardButton("📞 Report Issue", callback_data="contact")]
        ]
    elif error_type == "maintenance":
        return [
            [InlineKeyboardButton("🔄 Try Again Later", callback_data="close_data")]
        ]
    else:
        return [
            [InlineKeyboardButton("❌ Close", callback_data="close_data")]
        ]
