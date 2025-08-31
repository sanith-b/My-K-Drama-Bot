import re
import os
from os import environ, getenv
from Script import script

id_pattern = re.compile(r'^.\d+$')

def is_enabled(value, default):
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default


SESSION = environ.get('SESSION', 'media_search')
API_ID = int(environ.get('API_ID', ''))
API_HASH = environ.get('API_HASH', '')
BOT_TOKEN = environ.get('BOT_TOKEN', "")

CACHE_TIME = int(environ.get('CACHE_TIME', 300))
USE_CAPTION_FILTER = bool(environ.get('USE_CAPTION_FILTER', True))

PICS = (environ.get('PICS', 'https://files.catbox.moe/llj57o.jpg')).split() 
NOR_IMG = environ.get("NOR_IMG", "https://graph.org/file/62efbcc4e7580b76530ba.jpg")
MELCOW_VID = environ.get("MELCOW_VID", "https://graph.org/file/e215d12bfd4fa2155e90e.mp4")
SPELL_IMG = environ.get("SPELL_IMG", "https://files.catbox.moe/lh51io.jpg")
SUBSCRIPTION = (environ.get('SUBSCRIPTION', 'https://files.catbox.moe/ehs5i7.jpg'))
FSUB_IMG = (environ.get('FSUB_IMG', 'https://files.catbox.moe/h7bsns.jpg')).split() 
USDT = (environ.get('USDT', 'https://files.catbox.moe/9dg5rf.jpg'))
TON = (environ.get('TON', 'https://files.catbox.moe/myk6p2.jpg'))
BITCOIN = (environ.get('BITCOIN', 'https://files.catbox.moe/ehs5i7.jpg'))
USDTQR = (environ.get('USDTQR', 'https://files.catbox.moe/yyepjk.jpg'))
TONQR = (environ.get('TONQR', 'https://files.catbox.moe/nzx7g3.jpg'))
BITCOINQR = (environ.get('BITCOINQR', 'https://files.catbox.moe/wqfh2c.jpg'))

ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '').split()] 
CHANNELS = [int(ch) if id_pattern.search(ch) else ch for ch in environ.get('CHANNELS', '-100').split()]
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', '-100'))  
BIN_CHANNEL = int(environ.get('BIN_CHANNEL', '-100'))  
MOVIE_UPDATE_CHANNEL = int(environ.get('MOVIE_UPDATE_CHANNEL', ' -1002958535470'))  
PREMIUM_LOGS = int(environ.get('PREMIUM_LOGS', '-1003013348666')) 
auth_grp = environ.get('AUTH_GROUP')
AUTH_GROUPS = [int(ch) for ch in auth_grp.split()] if auth_grp else None
reqst_channel = environ.get('REQST_CHANNEL_ID', '-1003028947753') 
REQST_CHANNEL = int(reqst_channel) if reqst_channel and id_pattern.search(reqst_channel) else None
support_chat_id = environ.get('SUPPORT_CHAT_ID', '-1003088011737') 
SUPPORT_CHAT_ID = int(support_chat_id) if support_chat_id and id_pattern.search(support_chat_id) else None
auth_users = [int(user) if id_pattern.search(user) else user for user in environ.get('AUTH_USERS', '').split()]
AUTH_USERS = (auth_users + ADMINS) if auth_users else []
au_channel = environ.get('AU_CHANNEL', '-1001271383721')
AU_CHANNEL = int(au_channel) if au_channel and id_pattern.search(au_channel) else None

DATABASE_URI = environ.get('DATABASE_URI', "")
DATABASE_NAME = environ.get('DATABASE_NAME', "Cluster0")
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'SilentXBotz_files')

# If MULTIPLE_DB Is True Then Fill DATABASE_URI2 Value Else You Will Get Error.
MULTIPLE_DB = is_enabled(os.environ.get('MULTIPLE_DB', "False"), False) # Type True For Turn On MULTIPLE DB FUNTION 
DATABASE_URI2 = environ.get('DATABASE_URI2', "")
DB_CHANGE_LIMIT = int(environ.get('DB_CHANGE_LIMIT', "432")) 

GRP_LNK = environ.get('GRP_LNK', 'https://t.me/+QpT2tR1AdsBmYmZl')
CHNL_LNK = environ.get('CHNL_LNK', 'https://t.me/+5oPx_k2OQNQxZmY1')
OWNER_LNK = environ.get('OWNER_LNK', 'https://t.me/SupMyKDramaBot')
UPDATE_CHANNEL_LNK = environ.get('UPDATE_CHANNEL_LNK', 'https://t.me/+5oPx_k2OQNQxZmY1')

AUTH_CHANNEL = environ.get("AUTH_CHANNEL", "") # add multiple channels here, separated by single space
AUTH_REQ_CHANNEL = environ.get('AUTH_REQ_CHANNEL', '') # add multiple channels here, separated by single space

IS_VERIFY = is_enabled('IS_VERIFY', False)
LOG_VR_CHANNEL = int(environ.get('LOG_VR_CHANNEL', '100'))
LOG_API_CHANNEL = int(environ.get('LOG_API_CHANNEL', '-100'))
VERIFY_IMG = environ.get("VERIFY_IMG", "https://telegra.ph/file/9ecc5d6e4df5b83424896.jpg")

TUTORIAL = environ.get("TUTORIAL", "https://t.me/")
TUTORIAL_2 = environ.get("TUTORIAL_2", "https://t.me/")
TUTORIAL_3 = environ.get("TUTORIAL_3", "https://t.me/")

SHORTENER_API = environ.get("SHORTENER_API", "")
SHORTENER_WEBSITE = environ.get("SHORTENER_WEBSITE", "")

SHORTENER_API2 = environ.get("SHORTENER_API2", "")
SHORTENER_WEBSITE2 = environ.get("SHORTENER_WEBSITE2", "")

SHORTENER_API3 = environ.get("SHORTENER_API3", "")
SHORTENER_WEBSITE3 = environ.get("SHORTENER_WEBSITE3", "")

TWO_VERIFY_GAP = int(environ.get('TWO_VERIFY_GAP', "1200"))
THREE_VERIFY_GAP = int(environ.get('THREE_VERIFY_GAP', "54000"))

MOVIE_UPDATE_NOTIFICATION = bool(environ.get("MOVIE_UPDATE_NOTIFICATION", False))
NO_RESULTS_MSG = bool(environ.get("NO_RESULTS_MSG", True))
MAX_B_TN = environ.get("MAX_B_TN", "8")
MAX_BTN = is_enabled((environ.get('MAX_BTN', "True")), True)
PORT = environ.get("PORT", "8089")
MSG_ALRT = environ.get('MSG_ALRT', 'Powered by My K-Drama Bot 🎭')
SUPPORT_CHAT = environ.get('SUPPORT_CHAT', 'https://t.me/+QpT2tR1AdsBmYmZl') 
P_TTI_SHOW_OFF = is_enabled((environ.get('P_TTI_SHOW_OFF', "False")), False)
IMDB = is_enabled((environ.get('IMDB', "False")), False)
AUTO_FFILTER = is_enabled((environ.get('AUTO_FFILTER', "True")), True)
AUTO_DELETE = is_enabled((environ.get('AUTO_DELETE', "True")), True)
DELETE_TIME = int(environ.get("DELETE_TIME", "43200"))  
LINK_MODE = is_enabled((environ.get('LINK_MODE', "True")), True)
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", f"{script.CAPTION}")
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)
IMDB_TEMPLATE = environ.get("IMDB_TEMPLATE", f"{script.IMDB_TEMPLATE_TXT}")
LONG_IMDB_DESCRIPTION = is_enabled(environ.get("LONG_IMDB_DESCRIPTION", "False"), False)
SPELL_CHECK_REPLY = is_enabled(environ.get("SPELL_CHECK_REPLY", "True"), True)
MAX_LIST_ELM = environ.get("MAX_LIST_ELM", None)
INDEX_REQ_CHANNEL = int(environ.get('INDEX_REQ_CHANNEL', LOG_CHANNEL))
FILE_STORE_CHANNEL = [int(ch) for ch in (environ.get('FILE_STORE_CHANNEL', '')).split()]
MELCOW_NEW_USERS = is_enabled((environ.get('MELCOW_NEW_USERS', "False")), False)
PROTECT_CONTENT = is_enabled((environ.get('PROTECT_CONTENT', "False")), True)
PM_SEARCH = bool(environ.get('PM_SEARCH', True)) 
EMOJI_MODE = bool(environ.get('EMOJI_MODE', False)) 
PAID_STREAM = bool(environ.get('PAID_STREAM', False)) 
STREAM_MODE = bool(environ.get('STREAM_MODE', False))
MAINTENANCE_MODE = bool(environ.get('MAINTENANCE_MODE', False)) 


IGNORE_WORDS = (list(os.environ.get("IGNORE_WORDS").split(",")) if os.environ.get("IGNORE_WORDS") else []) #Remove Words While Searching Files
IGNORE_WORDS= ["movies", "Movies", ",", "episode", "Episode", "episodes", "Episodes", "south indian", "south indian movie", "South Indian Movie", "south movie", "South Movie", "South Indian", "web-series", "hindi me bhejo", "gujrati", "combined", "!", "kro", "jaldi", "Audio", "audio", "movi", "language", "Language", "Hollywood", "All", "all", "bollywood", "Bollywood", "South", "south", "HD", "hd", "karo", "Karo", "fullepisode", "please", "plz", "Please", "Plz", "send", "link", "Link", "full", "Full", "dabbed", "dubbed", "season", "Season", "web", "series", "Web", "Series", "webseries", "WebSeries", "upload", "HD", "Hd", "bhejo", "ful", "Send", "Bhejo"]

BAD_WORDS = ["Hdhub4u", "cinevood", "skymoviedHD"] #Remove Words From File_Name

LANGUAGES = ["malayalam", "", "tamil", "", "english", "", "hindi", "", "telugu", "", "kannada", "", "gujarati", "", "marathi", "", "punjabi", ""]
QUALITIES = ["480P", "", "540P", "", "720P", "", "1080P", "", "2160P", ""]
SEASONS = ["s01" , "s02" , "s03" , "s04", "s05"]


NO_PORT = bool(environ.get('NO_PORT', False))
APP_NAME = None
if 'DYNO' in environ:
    ON_HEROKU = True
    APP_NAME = environ.get('APP_NAME')
else:
    ON_HEROKU = False
BIND_ADRESS = str(getenv('WEB_SERVER_BIND_ADDRESS', '0.0.0.0'))
FQDN = str(getenv('FQDN', BIND_ADRESS)) if not ON_HEROKU or getenv('FQDN') else APP_NAME+'.herokuapp.com'
URL = "https://{}/".format(FQDN) if ON_HEROKU or NO_PORT else "https://{}/".format(FQDN, PORT)
SLEEP_THRESHOLD = int(environ.get('SLEEP_THRESHOLD', '60'))
WORKERS = int(environ.get('WORKERS', '4'))
SESSION_NAME = str(environ.get('SESSION_NAME', 'SilentXBotz'))
MULTI_CLIENT = False
name = str(environ.get('name', 'SilentX'))
PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  # 20 minutes
if 'DYNO' in environ:
    ON_HEROKU = True
    APP_NAME = str(getenv('APP_NAME'))
else:
    ON_HEROKU = False
HAS_SSL = bool(getenv('HAS_SSL', False))
if HAS_SSL:
    URL = "https://{}/".format(FQDN)
else:
    URL = "http://{}/".format(FQDN)


REACTIONS = ["🤝", "😇", "🤗", "😍", "👍", "🎅", "😐", "🥰", "🤩", "😱", "🤣", "😘", "👏", "😛", "😈", "🎉", "⚡️", "🫡", "🤓", "😎", "🏆", "🔥", "🤭", "🌚", "🆒", "👻", "😁"]

STAR_PREMIUM_PLANS = {
    1: "10year",
    5: "10year",    
    10: "10year", 
    20: "10year",   
    50: "10year",   
    100: "10year",   
}

Bot_cmds = {
    "start": "ꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ",
    "trendlist": "ɢᴇᴛ ᴛᴏᴘ ꜱᴇᴀʀᴄʜ ʟɪꜱᴛ",
    "myplan" : "ᴄʜᴇᴄᴋ ᴘʀᴇᴍɪᴜᴍ ꜱᴜʙꜱᴄʀɪᴘᴛɪᴏɴ",
    "plan" :"ᴄʜᴇᴄᴋ ᴘʀᴇᴍɪᴜᴍ ᴘʀɪᴄᴇ",
    "settings": "ᴄʜᴀɴɢᴇ sᴇᴛᴛɪɴɢs",
    "group_cmd": "ᴅᴇʟᴇᴛᴇ ᴀ ꜱᴘᴇᴄɪꜰɪᴄ ꜰɪʟᴇ ꜰʀᴏᴍ ᴅʙ.",
    "admin_cmd": "ᴅᴇʟᴇᴛᴇ ᴀ ꜱᴘᴇᴄɪꜰɪᴄ ꜰɪʟᴇ ꜰʀᴏᴍ ᴅʙ.",
    "details": "ꜱᴇᴇ ɢʀᴏᴜᴘ ꜱᴇᴛᴛɪɴɢꜱ",
    "reset_group": "ʀᴇꜱᴇᴛ ɢʀᴏᴜᴘ ꜱᴇᴛᴛɪɴɢꜱ", 
    "stats": "ᴄʜᴇᴄᴋ ʙᴏᴛ ꜱᴛᴀᴛᴜꜱ.",
    "delete": "ᴅᴇʟᴇᴛᴇ ᴀ ꜱᴘᴇᴄɪꜰɪᴄ ꜰɪʟᴇ ꜰʀᴏᴍ ᴅʙ.",
    "movie_update": "ᴏɴ ᴏғғ ᴀᴄᴄᴏʀᴅɪɴɢ ʏᴏᴜʀ ɴᴇᴇᴅᴇᴅ...",
    "pm_search": "ᴘᴍ sᴇᴀʀᴄʜ ᴏɴ ᴏғғ ᴀᴄᴄᴏʀᴅɪɴɢ ʏᴏᴜʀ ɴᴇᴇᴅᴇᴅ...",
    "restart": "ʀᴇꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ."
}

#Don't Change Anything Here

if MULTIPLE_DB == False:
    DATABASE_URI = DATABASE_URI
    DATABASE_URI2 = DATABASE_URI
else:
    DATABASE_URI = DATABASE_URI
    DATABASE_URI2 = DATABASE_URI2

AUTH_CHANNEL = [int(ch) for ch in AUTH_CHANNEL.strip().split()] if AUTH_CHANNEL else []
AUTH_REQ_CHANNEL = [int(ch) for ch in AUTH_REQ_CHANNEL.strip().split()] if AUTH_REQ_CHANNEL else []
