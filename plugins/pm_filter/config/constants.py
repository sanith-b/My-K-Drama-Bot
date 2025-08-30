"""
Configuration constants for the bot
"""

TIMEZONE = "Asia/Kolkata"

# Quality options
QUALITIES = [
    "720p", "1080p", "480p", "360p", 
    "1080p x265", "720p x265", "480p x265",
    "4k", "2k", "hdrip", "bluray"
]

# Season options
SEASONS = [
    "season 1", "season 2", "season 3", "season 4",
    "season 5", "season 6", "season 7", "season 8",
    "season 9", "season 10", "s01", "s02", "s03",
    "s04", "s05", "s06", "s07", "s08", "s09", "s10"
]

# Reaction emojis
REACTIONS = ["👍", "❤️", "🔥", "💯", "🎬", "⭐", "🎭", "🍿"]

# Button limits
DEFAULT_MAX_BUTTONS = 10
PAGINATION_LIMIT = 10

# Time limits
AUTO_DELETE_TIME = 600  # 10 minutes
SPELL_CHECK_TIMEOUT = 60  # 1 minute

# Regex patterns
URL_PATTERN = r'https?://\S+|www\.\S+|t\.me/\S+'
COMMAND_PATTERN = r"((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)"
SPELL_CHECK_PATTERN = r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)"

# Error messages
ERROR_MESSAGES = {
    "no_files": "⚡ Sorry, nothing was found!",
    "old_request": "This request has expired. Please make a new search.",
    "unauthorized": "You don't have permission to use this.",
    "maintenance": "🚧 Currently upgrading… Will return soon 🔜",
    "support_group": "This is a support group, so you can't get files from here.",
    "spell_check_failed": "I couldn't find any matches. Please try a different search term.",
    "admin_only": "💡 You must be an admin to use this"
}

# Success messages
SUCCESS_MESSAGES = {
    "search_complete": "✅ Search completed successfully",
    "settings_updated": "✅ Settings updated successfully",
    "files_found": "📂 Files found"
}

# File size formatting
SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB']

# IMDB template placeholders
IMDB_FIELDS = [
    'title', 'votes', 'aka', 'seasons', 'box_office', 'localized_title',
    'kind', 'imdb_id', 'cast', 'runtime', 'countries', 'certificates',
    'languages', 'director', 'writer', 'producer', 'composer',
    'cinematographer', 'music_team', 'distributors', 'release_date',
    'year', 'genres', 'poster', 'plot', 'rating', 'url'
]
