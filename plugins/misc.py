import os
import requests
import base64
from pyrogram import Client, filters, enums
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant, MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from utils import extract_user, get_file_id, get_poster
import time
from datetime import datetime
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
import logging
import json

##
import asyncio
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://kdramabot:Buo0fRGenkOAkgXH@pastppr.ipuyepp.mongodb.net/?retryWrites=true&w=majority&appName=pastppr")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["kdrama_bot"]
users = db["users"]
reviews = db["reviews"]

# TMDB API configuration
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "90dde61a7cf8339a2cff5d805d5597a9")
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Cache for popular dramas
popular_cache = {"data": [], "last_update": None}

# Constants
ITEMS_PER_PAGE = 10
CACHE_DURATION = 21600  # 6 hours in seconds
AVERAGE_EPISODE_DURATION = 0.75  # 45 minutes in hours
##
# Global dictionary to store identified titles for users
identified_titles = {}

IMDB_TEMP = """
"🏷 <b>Title:</b> <a href={url}>{title} {year}</a> <a href={url}/ratings>{rating}</a>/ 10   
💎 <b>Story:</b> `{plot}` 

📺 <b>Type:</b> `{kind}` 
📚 <b>Also Known As:</b> `{aka}`
🎭 <b>Genres:</b> `{genres}`
📆 <b>Release date:</b> `{release_date}`
🧭 <b>Runtime</b>: `{runtime} Min`
🤵‍♂️ <b>Director:</b> `{director}` 
👤 <b>Writer:</b> `{writer}`
🎥 <b>Producer:</b> `{producer}`
"""

# Updated PosterIdentifier class with multiple FREE public APIs
class PosterIdentifier:
    def __init__(self):
        # API configurations
        self.ocr_space_api_key = "helloworld"  # Free demo key
        self.google_api_key = None  # Set your Google API key
        self.api_ninjas_key = None  # Set your API Ninjas key
        
    async def identify_with_ocr_space(self, image_path):
        """OCR.space - 25,000 requests/month free with demo key"""
        try:
            url = 'https://api.ocr.space/parse/image'
            
            with open(image_path, 'rb') as image_file:
                files = {'file': image_file}
                data = {
                    'apikey': self.ocr_space_api_key,
                    'language': 'eng',
                    'isOverlayRequired': False,
                    'detectOrientation': True,
                    'scale': True,
                    'isTable': False,
                    'OCREngine': 2  # Latest OCR engine
                }
                
                response = requests.post(url, files=files, data=data, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('ParsedResults') and len(result['ParsedResults']) > 0:
                        text = result['ParsedResults'][0].get('ParsedText', '')
                        if text.strip():
                            return self.extract_movie_title(text)
                            
        except Exception as e:
            logger.error(f"OCR.space error: {e}")
        return None
    
    async def identify_with_google_vision(self, image_path):
        """Google Cloud Vision API - 1,000 requests/month free"""
        if not self.google_api_key:
            return None
            
        try:
            with open(image_path, 'rb') as image_file:
                image_content = base64.b64encode(image_file.read()).decode()
            
            url = f'https://vision.googleapis.com/v1/images:annotate?key={self.google_api_key}'
            
            headers = {'Content-Type': 'application/json'}
            
            data = {
                'requests': [{
                    'image': {'content': image_content},
                    'features': [{'type': 'TEXT_DETECTION', 'maxResults': 50}]
                }]
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if (result.get('responses') and 
                    result['responses'][0].get('textAnnotations')):
                    text = result['responses'][0]['textAnnotations'][0]['description']
                    return self.extract_movie_title(text)
                    
        except Exception as e:
            logger.error(f"Google Vision error: {e}")
        return None
    
    async def identify_with_api_ninjas(self, image_path):
        """API Ninjas - Free tier with registration"""
        if not self.api_ninjas_key:
            return None
            
        try:
            url = 'https://api.api-ninjas.com/v1/imagetotext'
            
            with open(image_path, 'rb') as image_file:
                files = {'image': image_file}
                headers = {'X-Api-Key': self.api_ninjas_key}
                
                response = requests.post(url, files=files, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if result and len(result) > 0:
                        text = ' '.join([item.get('text', '') for item in result])
                        return self.extract_movie_title(text)
                        
        except Exception as e:
            logger.error(f"API Ninjas error: {e}")
        return None
    
    async def identify_with_free_ocr_api(self, image_path):
        """Try completely free OCR APIs (no registration)"""
        try:
            # Method 1: Try free-ocr.com API
            url = 'https://api.free-ocr.com/v1/upload'
            
            with open(image_path, 'rb') as image_file:
                files = {'file': image_file}
                data = {'language': 'eng'}
                
                response = requests.post(url, files=files, data=data, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('text'):
                        return self.extract_movie_title(result['text'])
                        
        except Exception as e:
            logger.error(f"Free OCR API error: {e}")
        return None
    
    def extract_movie_title(self, text):
        """Extract potential movie title from detected text with better accuracy"""
        if not text or len(text.strip()) < 2:
            return None
            
        lines = text.split('\n')
        potential_titles = []
        
        # Clean and filter lines
        for line in lines:
            line = line.strip()
            if len(line) < 3:
                continue
                
            # Remove lines that are just numbers or single characters
            if line.isdigit() or len(line) == 1:
                continue
                
            # Remove common poster elements and noise
            noise_words = [
                'rated', 'pg', 'coming', 'soon', 'theaters', 'dvd', 'blu-ray',
                'december', 'january', 'february', 'march', 'april', 'may', 
                'june', 'july', 'august', 'september', 'october', 'november',
                'director', 'producer', 'starring', 'from', 'the', 'maker',
                'certificate', 'mins', 'runtime', 'genre', 'imdb', 'trailer',
                'official', 'poster', 'movie', 'film', 'cinema', 'watch'
            ]
            
            line_lower = line.lower()
            if any(noise in line_lower for noise in noise_words):
                continue
                
            # Skip lines with too many special characters
            special_chars = sum(1 for c in line if not c.isalnum() and c != ' ')
            if special_chars > len(line) * 0.3:  # More than 30% special chars
                continue
            
            # Skip very short lines
            if len(line) < 5:
                continue
                
            # Prefer longer lines (movie titles are usually substantial)
            potential_titles.append((line, len(line)))
        
        # Sort by length and return the longest reasonable title
        if potential_titles:
            potential_titles.sort(key=lambda x: x[1], reverse=True)
            # Return the longest title, but not too long (movie titles are usually < 50 chars)
            for title, length in potential_titles:
                if 5 <= length <= 50:
                    return title
        
        return None
    
    async def identify_poster(self, image_path):
        """Try multiple FREE API methods to identify poster"""
        
        # Method 1: OCR.space (Free demo key - 25k/month)
        result = await self.identify_with_ocr_space(image_path)
        if result:
            return result
        
        # Method 2: Free OCR API (No registration)
        result = await self.identify_with_free_ocr_api(image_path)
        if result:
            return result
            
        # Method 3: Google Vision (if API key available)
        result = await self.identify_with_google_vision(image_path)
        if result:
            return result
            
        # Method 4: API Ninjas (if API key available)
        result = await self.identify_with_api_ninjas(image_path)
        if result:
            return result
        
        return None

# Configuration helper
def setup_api_keys():
    """Helper function to set up API keys"""
    poster_identifier = PosterIdentifier()
    
    # Option 1: Direct API keys (less secure but simpler)
    poster_identifier.google_api_key = "AIzaSyB_UlPqWvqKPJhO04P9h-i4nbk-0yP_bbs"
    poster_identifier.api_ninjas_key = "glWIrO/a4AXbFgQjcyrP0w==1Y2pIQ0CZbFsmRm0"
    
    # Option 2: Environment variables (more secure - uncomment if using .env)
    # poster_identifier.google_api_key = os.getenv('GOOGLE_VISION_API_KEY', "AIzaSyB_UlPqWvqKPJhO04P9h-i4nbk-0yP_bbs")
    # poster_identifier.api_ninjas_key = os.getenv('API_NINJAS_KEY', "glWIrO/a4AXbFgQjcyrP0w==1Y2pIQ0CZbFsmRm0")
    
    return poster_identifier

# Initialize poster identifier with API support
poster_identifier = setup_api_keys()

@Client.on_message(filters.command('id'))
async def showid(client, message):
    chat_type = message.chat.type
    if chat_type == enums.ChatType.PRIVATE:
        user_id = message.chat.id
        first = message.from_user.first_name
        last = message.from_user.last_name or ""
        username = message.from_user.username
        dc_id = message.from_user.dc_id or ""
        await message.reply_text(
            f"<b>⌬ First Name:</b> {first}\n<b>⌬ Last Name:</b> {last}\n<b>⌬ Username:</b> {username}\n<b>⌬ Telegram ID:</b> <code>{user_id}</code>\n<b>⌬ Data Centre:</b> <code>{dc_id}</code>",
            quote=True
        )

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        _id = ""
        _id += (
            "<b>➲ Chat ID</b>: "
            f"<code>{message.chat.id}</code>\n"
        )
        if message.reply_to_message:
            _id += (
                "<b>➲ User ID</b>: "
                f"<code>{message.from_user.id if message.from_user else 'Anonymous'}</code>\n"
                "<b>➲ Replied User ID</b>: "
                f"<code>{message.reply_to_message.from_user.id if message.reply_to_message.from_user else 'Anonymous'}</code>\n"
            )
            file_info = get_file_id(message.reply_to_message)
        else:
            _id += (
                "<b>➲ User ID</b>: "
                f"<code>{message.from_user.id if message.from_user else 'Anonymous'}</code>\n"
            )
            file_info = get_file_id(message)
        if file_info:
            _id += (
                f"<b>{file_info.message_type}</b>: "
                f"<code>{file_info.file_id}</code>\n"
            )
        await message.reply_text(
            _id,
            quote=True
        )

@Client.on_message(filters.command(['poster', 'identify']))
async def identify_poster_command(client, message):
    """Identify movie poster from image using FREE public APIs"""
    if message.reply_to_message and message.reply_to_message.photo:
        status_msg = await message.reply("🔍 Analyzing poster...")
        
        try:
            # Download the image
            photo = message.reply_to_message.photo
            file_path = await client.download_media(photo.file_id)
            
            await status_msg.edit("🤖")
            
            # Identify poster using FREE API methods
            identified_title = await poster_identifier.identify_poster(file_path)
            
            if identified_title:
                await status_msg.edit(f"🎬 Detected: **{identified_title}**\n\nSearching IMDB...")
                
                # Search IMDB with identified title
                movies = await get_poster(identified_title, bulk=True)
                
                if movies:
                    # Store the identified title for this user
                    identified_titles[message.from_user.id] = identified_title
                    
                    btn = [
                        [
                            InlineKeyboardButton(
                                text=f"{movie.get('title')} - {movie.get('year')}",
                                callback_data=f"imdb#{movie.movieID}#{message.from_user.id}",
                            )
                        ]
                        for movie in movies[:8]  # Limit to 8 results
                    ]
                    btn.append([InlineKeyboardButton("🔐 Close", callback_data="close_data")])
                    
                    await status_msg.edit(
                        f"🎯 **Identified:** {identified_title}\n"
                        f"✨ **Method:** OCR\n\n"
                        f"📽️ **IMDB Results:**\n"
                        f"💌 *Click any movie to get details in PM*\n\n"
                        f"✨ To download 🎬 `{identified_title}`,\n please send 📩 `{identified_title}` in the bot's PM 🤖"
                        ,
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                else:
                    await status_msg.edit(
                        f"🎬 **Detected:** {identified_title}\n"
                        f"✨ **Method:** FREE OCR APIs\n\n"
                        f"❌ No IMDB results found\n\n"
                        f"✨ To download 🎬 `{identified_title}`,\n please send 📩 `{identified_title}` in the bot's PM 🤖\n\n"
                        f"💡 Try searching manually: `/imdb {identified_title}`"
                    )
            else:
                await status_msg.edit(
                    "❌ Could not identify the poster text.\n\n"
                    "**Tips for better results:**\n"
                    "• Use clear, high-resolution images\n"
                    "• Ensure text is readable\n"
                    "• Avoid blurry or dark images\n"
                    "• Try cropping to just the title area\n\n"
                    "🔄 Or search manually: `/imdb movie name`"
                )
            
            # Clean up downloaded file
            if os.path.exists(file_path):
                os.remove(file_path)
                
        except Exception as e:
            logger.error(f"Poster identification error: {e}")
            await status_msg.edit(
                "❌ Error processing image.\n\n"
                "**Possible solutions:**\n"
                "• Check internet connection\n"
                "• Try a different image format (JPG/PNG)\n"
                "• Use a clearer image\n"
                "• Use manual search: `/imdb movie name`\n\n"
                "**Current API Status:**\n"
                "🟢 OCR.space: Available (Free)\n"
                "🟢 OCR APIs: Available\n"
                f"{'🟢' if poster_identifier.google_api_key else '🟡'} Google Vision: {'Enabled' if poster_identifier.google_api_key else 'Not configured'}\n"
                f"{'🟢' if poster_identifier.api_ninjas_key else '🟡'} API Ninjas: {'Enabled' if poster_identifier.api_ninjas_key else 'Not configured'}"
            )
    
    elif message.photo:
        # If command sent with photo directly
        await identify_poster_command(client, message.reply_to_message or message)
    else:
        await message.reply(
            "📷 **Movie Poster Identification Bot**\n\n"
            "**How to use:**\n"
            "1️⃣ Send any movie poster image\n"
            "2️⃣ Reply to it with `/poster` or `/identify`\n\n"
            "📖 **Manual search:** `/imdb movie name`"
        )

@Client.on_message(filters.command(["imdb", 'search']))
async def imdb_search(client, message):
    if ' ' in message.text:
        k = await message.reply('Searching ImDB')
        r, title = message.text.split(None, 1)
        movies = await get_poster(title, bulk=True)
        if not movies:
            return await message.reply("No results Found")
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{movie.get('title')} - {movie.get('year')}",
                    callback_data=f"imdb#{movie.movieID}",
                )
            ]
            for movie in movies
        ]
        btn.append([InlineKeyboardButton("🔐 Close", callback_data="close_data")])
        await k.edit('Here is what i found on IMDb', reply_markup=InlineKeyboardMarkup(btn))
    else:
        await message.reply('Give me a movie / series Name')

@Client.on_callback_query(filters.regex('^imdb'))
async def imdb_callback(bot: Client, quer_y: CallbackQuery):
    callback_data = quer_y.data.split('#')
    i = callback_data[0]
    movie = callback_data[1]
    user_id = int(callback_data[2]) if len(callback_data) > 2 else quer_y.from_user.id
    
    # Get the original identified title if available
    original_identified_title = identified_titles.get(user_id, "Unknown")
    
    imdb = await get_poster(query=movie, id=True)
    btn = [
            [
                InlineKeyboardButton(
                    text=f"{imdb.get('title')}",
                    url=imdb['url'],
                )
            ]
        ]
    message = quer_y.message.reply_to_message or quer_y.message
    if imdb:
        caption = IMDB_TEMP.format(
            query = imdb['title'],
            title = imdb['title'],
            votes = imdb['votes'],
            aka = imdb["aka"],
            seasons = imdb["seasons"],
            box_office = imdb['box_office'],
            localized_title = imdb['localized_title'],
            kind = imdb['kind'],
            imdb_id = imdb["imdb_id"],
            cast = imdb["cast"],
            runtime = imdb["runtime"],
            countries = imdb["countries"],
            certificates = imdb["certificates"],
            languages = imdb["languages"],
            director = imdb["director"],
            writer = imdb["writer"],
            producer = imdb["producer"],
            composer = imdb["composer"],
            cinematographer = imdb["cinematographer"],
            music_team = imdb["music_team"],
            distributors = imdb["distributors"],
            release_date = imdb['release_date'],
            year = imdb['year'],
            genres = imdb['genres'],
            poster = imdb['poster'],
            plot = imdb['plot'],
            rating = imdb['rating'],
            url = imdb['url'],
            **locals()
        )
    else:
        caption = "No Results"
    
    # Send private message to user with the identified title
    try:
        movie_title = imdb.get('title', 'Unknown Movie') if imdb else 'Unknown Movie'
        
        pm_message = f"🎬 **Movie Selected:** {movie_title}\n\n"
        pm_message += f"🔍 **Originally Identified From Poster:** {original_identified_title}\n"
        pm_message += f"🔗 **IMDB Link:** {imdb.get('url', 'N/A') if imdb else 'N/A'}\n"
        pm_message += f"⭐ **Rating:** {imdb.get('rating', 'N/A') if imdb else 'N/A'}/10\n"
        pm_message += f"📅 **Year:** {imdb.get('year', 'N/A') if imdb else 'N/A'}\n"
        pm_message += f"🎭 **Genres:** {imdb.get('genres', 'N/A') if imdb else 'N/A'}\n"
        pm_message += f"⏱️ **Runtime:** {imdb.get('runtime', 'N/A') if imdb else 'N/A'} min\n\n"
        pm_message += f"📝 **Plot:** {imdb.get('plot', 'N/A') if imdb else 'N/A'}\n\n"
        pm_message += f"✨ **This movie was automatically identified from your poster!**"
        
        await bot.send_message(
            chat_id=user_id,
            text=pm_message,
            disable_web_page_preview=False
        )
        
        # Clean up stored title after sending
        if user_id in identified_titles:
            del identified_titles[user_id]
        
        # Show success notification
        await quer_y.answer("✅ Movie details sent to your PM!", show_alert=False)
        
    except Exception as pm_error:
        logger.error(f"Failed to send PM: {pm_error}")
        await quer_y.answer("⚠️ Please start the bot in PM first to receive movie details", show_alert=True)
    
    if imdb.get('poster'):
        try:
            await quer_y.message.reply_photo(photo=imdb['poster'], caption=caption, reply_markup=InlineKeyboardMarkup(btn))
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            await quer_y.message.reply_photo(photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(btn))
        except Exception as e:
            logger.exception(e)
            await quer_y.message.reply(caption, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=False)
        await quer_y.message.delete()
    else:
        await quer_y.message.edit(caption, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=False)

@Client.on_callback_query(filters.regex('^close_data'))
async def close_callback(bot: Client, query: CallbackQuery):
    """Handle close button callback"""
    await query.message.delete()
    await query.answer("Closed!")

@Client.on_message(filters.command(["info"]))
async def who_is(client, message):
    status_message = await message.reply_text(
        "`Fetching user info...`"
    )
    await status_message.edit(
        "`Processing user info...`"
    )
    from_user = None
    from_user_id, _ = extract_user(message)
    try:
        from_user = await client.get_users(from_user_id)
    except Exception as error:
        await status_message.edit(str(error))
        return
    if from_user is None:
        return await status_message.edit("no valid user_id / message specified")
    message_out_str = ""
    message_out_str += f"<b>⌬First Name:</b> {from_user.first_name}\n"
    last_name = from_user.last_name or "<b>None</b>"
    message_out_str += f"<b>⌬Last Name:</b> {last_name}\n"
    message_out_str += f"<b>⌬Telegram ID:</b> <code>{from_user.id}</code>\n"
    username = from_user.username or "<b>None</b>"
    dc_id = from_user.dc_id or "[User Doesn't Have A Valid DP]"
    message_out_str += f"<b>⌬Data Centre:</b> <code>{dc_id}</code>\n"
    message_out_str += f"<b>⌬User Name:</b> @{username}\n"
    message_out_str += f"<b>⌬User 𝖫𝗂𝗇𝗄:</b> <a href='tg://user?id={from_user.id}'><b>Click Here</b></a>\n"
    if message.chat.type in ((enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL)):
        try:
            chat_member_p = await message.chat.get_member(from_user.id)
            joined_date = (
                chat_member_p.joined_date or datetime.now()
            ).strftime("%Y.%m.%d %H:%M:%S")
            message_out_str += (
                "<b>⌬Joined this Chat on:</b> <code>"
                f"{joined_date}"
                "</code>\n"
            )
        except UserNotParticipant:
            pass
    chat_photo = from_user.photo
    if chat_photo:
        local_user_photo = await client.download_media(
            message=chat_photo.big_file_id
        )
        buttons = [[
            InlineKeyboardButton('🔐 Close', callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=local_user_photo,
            quote=True,
            reply_markup=reply_markup,
            caption=message_out_str,
            parse_mode=enums.ParseMode.HTML,
            disable_notification=True
        )
        os.remove(local_user_photo)
    else:
        buttons = [[
            InlineKeyboardButton('🔐 Close', callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(
            text=message_out_str,
            reply_markup=reply_markup,
            quote=True,
            parse_mode=enums.ParseMode.HTML,
            disable_notification=True
        )
    await status_message.delete()

# Help command to show new features
@Client.on_message(filters.command(['pohelp']))
async def help_command(client, message):
    help_text = """
🤖 **Movie Bot - FREE OCR Poster Identification**

**📋 Commands:**
🎬 `/imdb <movie name>` - Search movie on IMDB
🔍 `/search <movie name>` - Same as /imdb
📷 `/poster` or `/identify` - Reply to image to identify movie poster
❓ `/pohelp` - Show this help message

**🎯 Poster Identification Feature:**
Send `/poster` or `/identify` by replying to any movie poster image:
1. 🔍 Analyzes poster using multiple FREE OCR APIs
2. 🎬 Identifies movie title automatically
3. 📽️ Searches IMDB and shows results
4. 📋 Displays detailed movie information

**💡 Tips for Better Results:**
• Use high-resolution, clear poster images
• Ensure movie title text is visible and readable
• Avoid extremely blurry or dark images
• Try cropping to focus on the title area

**🚀 Ready to use out of the box - No setup required!**
"""
    
    buttons = [[
        InlineKeyboardButton('🔐 Close', callback_data='close_data')
    ]]
    
    await message.reply_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )
###new
class temp:
    PAGE_JUMP = 5
    MAX_RESULTS = 20

# ------------------ UTILITY FUNCTIONS ------------------
async def get_user_data(user_id):
    """Get or create user data with enhanced error handling"""
    try:
        user = await users.find_one({"user_id": user_id})
        if not user:
            user = {
                "user_id": user_id,
                "watchlist": [],
                "favorites": [],
                "ratings": {},
                "preferences": {"genres": [], "countries": []},
                "joined_date": datetime.datetime.utcnow(),
                "stats": {"total_watched": 0, "total_hours": 0}
            }
            await users.insert_one(user)
            logger.info(f"Created new user: {user_id}")
        else:
            # Ensure all required fields exist for existing users
            update_fields = {}
            if "watchlist" not in user:
                update_fields["watchlist"] = []
            if "favorites" not in user:
                update_fields["favorites"] = []
            if "ratings" not in user:
                update_fields["ratings"] = {}
            if "preferences" not in user:
                update_fields["preferences"] = {"genres": [], "countries": []}
            if "stats" not in user:
                update_fields["stats"] = {"total_watched": 0, "total_hours": 0}
            
            if update_fields:
                await users.update_one(
                    {"user_id": user_id},
                    {"$set": update_fields}
                )
                user.update(update_fields)
                logger.info(f"Updated user fields for {user_id}: {list(update_fields.keys())}")
        
        return user
    except Exception as e:
        logger.error(f"Error getting user data for {user_id}: {e}")
        return None

async def update_user_stats(user_id):
    """Update user viewing statistics with better error handling"""
    try:
        user = await users.find_one({"user_id": user_id})
        if not user:
            return
        
        # Ensure watchlist exists
        watchlist = user.get("watchlist", [])
        watched_dramas = [d for d in watchlist if d.get("status") == "Watched"]
        total_episodes = sum(d.get("episode_count", 0) for d in watched_dramas)
        total_hours = total_episodes * AVERAGE_EPISODE_DURATION
        
        await users.update_one(
            {"user_id": user_id},
            {"$set": {
                "stats.total_watched": len(watched_dramas), 
                "stats.total_hours": round(total_hours, 1)
            }}
        )
    except Exception as e:
        logger.error(f"Error updating user stats for {user_id}: {e}")

def format_drama_title(drama_data):
    """Format drama title with year and rating"""
    title = drama_data.get('name', 'Unknown')
    year = drama_data.get('first_air_date', '')[:4] if drama_data.get('first_air_date') else 'N/A'
    rating = f"⭐{drama_data.get('vote_average', 0):.1f}" if drama_data.get('vote_average') else ""
    return f"{title} ({year}) {rating}"

def truncate_text(text, max_length=300):
    """Truncate text with ellipsis if too long"""
    if not text:
        return "No description available"
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

# ------------------ TMDB HELPERS ------------------
async def make_tmdb_request(endpoint, params=None):
    """Generic TMDB API request handler with error handling"""
    url = f"{TMDB_BASE_URL}/{endpoint}"
    default_params = {"api_key": TMDB_API_KEY, "language": "en-US"}
    
    if params:
        default_params.update(params)
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, params=default_params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"TMDB API returned status {response.status} for {endpoint}")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout error for TMDB request: {endpoint}")
    except Exception as e:
        logger.error(f"Error making TMDB request to {endpoint}: {e}")
    return None

async def search_tmdb(query: str, page=1):
    """Enhanced search with Korean drama filtering"""
    params = {
        "query": query,
        "page": page,
        "with_origin_country": "KR"
    }
    
    data = await make_tmdb_request("search/tv", params)
    return data.get("results", []) if data else []

async def get_tmdb_details(tv_id: int):
    """Enhanced details fetching with more info"""
    return await make_tmdb_request(f"tv/{tv_id}")

async def get_popular_kdramas():
    """Get popular Korean dramas with caching"""
    global popular_cache
    now = datetime.datetime.utcnow()
    
    # Check cache
    if (popular_cache["last_update"] and 
        (now - popular_cache["last_update"]).total_seconds() < CACHE_DURATION):
        return popular_cache["data"]
    
    params = {
        "with_origin_country": "KR",
        "sort_by": "popularity.desc",
        "vote_count.gte": 50,
    }
    
    data = await make_tmdb_request("discover/tv", params)
    if data:
        popular_cache["data"] = data.get("results", [])[:20]
        popular_cache["last_update"] = now
        return popular_cache["data"]
    
    return popular_cache["data"] or []

async def get_recommendations(tv_id: int, user_preferences=None):
    """Enhanced recommendations based on user preferences"""
    recommendations = []
    
    # Get TMDB recommendations
    data = await make_tmdb_request(f"tv/{tv_id}/recommendations")
    if data:
        recommendations.extend(data.get("results", []))
    
    # If few recommendations, get popular dramas
    if len(recommendations) < 5:
        popular = await get_popular_kdramas()
        recommendations.extend(popular)
    
    # Filter out duplicates
    seen_ids = set()
    unique_recs = []
    for rec in recommendations:
        if rec["id"] not in seen_ids:
            unique_recs.append(rec)
            seen_ids.add(rec["id"])
    
    return unique_recs[:10]

# ------------------ MESSAGE HANDLERS ------------------
async def send_error_message(message, error_text="❌ An error occurred. Please try again later."):
    """Send error message with retry button"""
    buttons = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
    try:
        await message.reply(error_text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error sending error message: {e}")

# ------------------ MAIN COMMANDS ------------------
@Client.on_message(filters.command(["start", "help", "uhelp"]))
async def start_command(client, message):
    """Welcome message with quick actions"""
    try:
        user = await get_user_data(message.from_user.id)
        if not user:
            return await send_error_message(message, "❌ Unable to load user data.")
        
        username = message.from_user.first_name or "User"
        text = f"🎭 Welcome {username} to K-Drama Bot! 🇰🇷\n\n"
        
        # Safely access watchlist with fallback
        watchlist = user.get("watchlist", [])
        if watchlist:
            watchlist_stats = {
                "total": len(watchlist),
                "watching": len([d for d in watchlist if d.get("status") == "Watching"]),
                "watched": len([d for d in watchlist if d.get("status") == "Watched"]),
                "to_watch": len([d for d in watchlist if d.get("status") == "To Watch"])
            }
            
            text += (f"📺 **Your Stats:**\n"
                    f"• Total dramas: {watchlist_stats['total']}\n"
                    f"• Watching: {watchlist_stats['watching']}\n"
                    f"• Completed: {watchlist_stats['watched']}\n"
                    f"• To Watch: {watchlist_stats['to_watch']}\n\n")
        
        text += ("🔍 **Available Commands:**\n"
                "• `/search <drama name>` - Find dramas\n"
                "• `/add <drama name>` - Add to watchlist\n"
                "• `/watchlist` - View your list\n"
                "• `/popular` - Trending dramas\n"
                "• `/recommend` - Get suggestions\n"
                "• `/profile` - Your profile\n"
                "• `/random` - Random drama\n"
                "• `/help` - Show this menu")
        
        buttons = [
            [InlineKeyboardButton("🔥 Popular Dramas", callback_data="popular_dramas")],
            [InlineKeyboardButton("📖 My Watchlist", callback_data="show_watchlist"), 
             InlineKeyboardButton("👤 Profile", callback_data="show_profile")],
            [InlineKeyboardButton("🎯 Get Recommendations", callback_data="get_recommendations"),
             InlineKeyboardButton("🎲 Random Drama", callback_data="random_drama")]
        ]
        
        await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await send_error_message(message)

@Client.on_message(filters.command(["search", "find"]))
async def search_dramas(client, message):
    """Enhanced search command with pagination"""
    try:
        query = " ".join(message.command[1:])
        if not query:
            return await message.reply(
                "❌ Please provide a drama name.\n\n"
                "**Examples:**\n"
                "• `/search Goblin`\n"
                "• `/search Crash Landing on You`\n"
                "• `/search Hotel del Luna`"
            )
        
        status_msg = await message.reply("🔍 Searching for dramas...")
        results = await search_tmdb(query)
        
        if not results:
            await status_msg.edit(
                f"⚠️ No dramas found for '{query}'.\n\n"
                "**Tips:**\n"
                "• Try different keywords\n"
                "• Check spelling\n"
                "• Use English or Korean title"
            )
            return
        
        buttons = []
        for r in results[:8]:
            buttons.append([
                InlineKeyboardButton(
                    format_drama_title(r),
                    callback_data=f"details_{r['id']}"
                )
            ])
        
        if len(results) > 8:
            buttons.append([
                InlineKeyboardButton(f"📄 Show more ({len(results) - 8} remaining)", 
                                   callback_data=f"search_more_{query}_1")
            ])
        
        buttons.append([InlineKeyboardButton("🔍 New Search", callback_data="new_search")])
        
        await status_msg.edit(
            f"🎬 Found {len(results)} dramas for '{query}':",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Error in search command: {e}")
        await send_error_message(message)

@Client.on_message(filters.command("add"))
async def add_watchlist(client, message):
    """Add drama to watchlist with enhanced selection"""
    try:
        user_id = message.from_user.id
        query = " ".join(message.command[1:])
        
        if not query:
            return await message.reply(
                "❌ Please provide a drama name.\n\n"
                "**Usage:** `/add <drama name>`\n"
                "**Example:** `/add Goblin`"
            )

        results = await search_tmdb(query)
        if not results:
            return await message.reply(
                f"⚠️ No dramas found for '{query}'.\n"
                "Try using `/search {query}` for more options."
            )

        buttons = []
        for r in results[:5]:
            buttons.append([
                InlineKeyboardButton(
                    format_drama_title(r),
                    callback_data=f"add_{r['id']}"
                )
            ])
        
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_add")])
        
        await message.reply(
            "🔍 Select a drama to add to your watchlist:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Error in add command: {e}")
        await send_error_message(message)

@Client.on_message(filters.command("popular"))
async def show_popular(client, message):
    """Show trending K-Dramas with enhanced display"""
    try:
        status_msg = await message.reply("📺 Loading popular K-Dramas...")
        popular = await get_popular_kdramas()
        
        if not popular:
            await status_msg.edit(
                "⚠️ Unable to load popular dramas right now.\n"
                "Please try again later."
            )
            return
        
        buttons = []
        for drama in popular[:ITEMS_PER_PAGE]:
            buttons.append([
                InlineKeyboardButton(
                    format_drama_title(drama),
                    callback_data=f"details_{drama['id']}"
                )
            ])
        
        if len(popular) > ITEMS_PER_PAGE:
            buttons.append([
                InlineKeyboardButton("📄 Show More", callback_data="popular_page_1")
            ])
        
        buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")])
        
        await status_msg.edit(
            "🔥 **Trending K-Dramas:**\n"
            "Click on any drama to see details and add to your watchlist.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Error in popular command: {e}")
        await send_error_message(message)

@Client.on_message(filters.command("watchlist"))
async def show_watchlist(client, message):
    """Enhanced watchlist with filtering and statistics"""
    try:
        user_id = message.from_user.id
        user = await users.find_one({"user_id": user_id})
        
        # Safely check for watchlist
        watchlist = user.get("watchlist", []) if user else []
        
        if not watchlist:
            buttons = [
                [InlineKeyboardButton("🔥 Browse Popular", callback_data="popular_dramas")],
                [InlineKeyboardButton("🔍 Search Dramas", callback_data="search_dramas")]
            ]
            return await message.reply(
                "📌 Your watchlist is empty.\n\n"
                "Start by adding dramas using `/add <name>` or browse popular dramas below.",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        stats = {
            "total": len(watchlist),
            "watching": len([d for d in watchlist if d.get("status") == "Watching"]),
            "watched": len([d for d in watchlist if d.get("status") == "Watched"]),
            "to_watch": len([d for d in watchlist if d.get("status") == "To Watch"])
        }
        
        # Calculate completion percentage
        completion_pct = round((stats["watched"] / stats["total"]) * 100) if stats["total"] > 0 else 0
        
        text = (f"📖 **Your Watchlist** ({stats['total']} dramas)\n\n"
               f"📊 **Statistics:**\n"
               f"• ▶️ Watching: {stats['watching']}\n"
               f"• ✅ Watched: {stats['watched']}\n"
               f"• ⏳ To Watch: {stats['to_watch']}\n"
               f"• 📈 Completion: {completion_pct}%\n\n"
               f"Select a filter to browse your dramas:")
        
        buttons = [
            [InlineKeyboardButton("📖 All", callback_data="filter_all_0"),
             InlineKeyboardButton("▶️ Watching", callback_data="filter_watching_0")],
            [InlineKeyboardButton("✅ Watched", callback_data="filter_watched_0"),
             InlineKeyboardButton("⏳ To Watch", callback_data="filter_towatch_0")],
            [InlineKeyboardButton("📊 Detailed Stats", callback_data="detailed_stats")]
        ]
        
        await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        logger.error(f"Error in watchlist command: {e}")
        await send_error_message(message)

@Client.on_message(filters.command("recommend"))
async def recommend(client, message):
    """Enhanced recommendations with multiple sources"""
    try:
        user_id = message.from_user.id
        user = await users.find_one({"user_id": user_id})
        
        # Safely access watchlist
        watchlist = user.get("watchlist", []) if user else []
        
        if not watchlist:
            # Show popular dramas for new users
            popular = await get_popular_kdramas()
            if popular:
                buttons = []
                for drama in popular[:5]:
                    buttons.append([
                        InlineKeyboardButton(
                            format_drama_title(drama),
                            callback_data=f"details_{drama['id']}"
                        )
                    ])
                return await message.reply(
                    "🎯 **Popular K-Dramas for New Users:**\n"
                    "Add some dramas to your watchlist for personalized recommendations!",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            return await message.reply("📌 Add some dramas to your watchlist first to get personalized recommendations!")

        # Get recommendations based on user's viewing history
        recent_dramas = [d for d in watchlist if d.get("status") in ["Watched", "Watching"]]
        if not recent_dramas:
            return await message.reply("📌 Watch some dramas first to get recommendations!")
        
        # Use multiple dramas for better recommendations
        base_drama = recent_dramas[-1]  # Most recent
        status_msg = await message.reply("🎯 Generating personalized recommendations...")
        
        recs = await get_recommendations(base_drama["tv_id"], user.get("preferences"))
        
        if not recs:
            await status_msg.edit("⚠️ No recommendations found right now. Try again later!")
            return

        buttons = []
        for r in recs[:8]:
            buttons.append([
                InlineKeyboardButton(
                    format_drama_title(r),
                    callback_data=f"details_{r['id']}"
                )
            ])

        buttons.append([
            InlineKeyboardButton("🔄 More Recommendations", callback_data="more_recommendations")
        ])

        await status_msg.edit(
            f"🎯 **Recommendations based on '{base_drama['title']}':**\n"
            "These dramas might interest you based on your viewing history.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Error in recommend command: {e}")
        await send_error_message(message)

@Client.on_message(filters.command("profile"))
async def profile(client, message):
    """Enhanced user profile with detailed statistics"""
    try:
        user_id = message.from_user.id
        user = await get_user_data(user_id)
        if not user:
            return await send_error_message(message, "❌ Unable to load profile data.")
            
        await update_user_stats(user_id)
        user = await users.find_one({"user_id": user_id})

        username = message.from_user.first_name or message.from_user.username or "User"
        joined = user["joined_date"].strftime("%B %Y")
        
        watchlist = user.get("watchlist", [])
        
        if not watchlist:
            text = (f"👤 **{username}'s Profile**\n"
                   f"🗓 Member since: {joined}\n\n"
                   f"📺 No dramas in watchlist yet\n"
                   f"➕ Start your K-Drama journey by adding some dramas!")
            
            buttons = [
                [InlineKeyboardButton("🔥 Popular Dramas", callback_data="popular_dramas")],
                [InlineKeyboardButton("🔍 Search Dramas", callback_data="search_dramas")]
            ]
        else:
            stats = user.get("stats", {})
            
            # Calculate detailed statistics
            total_dramas = len(watchlist)
            watching = len([d for d in watchlist if d.get("status") == "Watching"])
            watched = len([d for d in watchlist if d.get("status") == "Watched"])
            to_watch = len([d for d in watchlist if d.get("status") == "To Watch"])
            total_hours = stats.get("total_hours", 0)
            
            # Calculate favorite genre
            all_genres = []
            for drama in watchlist:
                all_genres.extend(drama.get("genres", []))
            
            fav_genre = "None yet"
            if all_genres:
                from collections import Counter
                genre_count = Counter(all_genres)
                fav_genre = genre_count.most_common(1)[0][0]
            
            # Calculate average rating
            rated_dramas = [d for d in watchlist if d.get("user_rating", 0) > 0]
            avg_rating = 0
            if rated_dramas:
                avg_rating = sum(d.get("user_rating", 0) for d in rated_dramas) / len(rated_dramas)
            
            text = (f"👤 **{username}'s Profile**\n"
                   f"🗓 Member since: {joined}\n"
                   f"🏆 Favorite Genre: {fav_genre}\n\n"
                   f"📊 **Statistics:**\n"
                   f"📖 Total Dramas: {total_dramas}\n"
                   f"✅ Completed: {watched}\n"
                   f"▶️ Watching: {watching}\n"
                   f"⏳ Plan to Watch: {to_watch}\n"
                   f"⏱ Total Watch Time: {total_hours}h\n")
            
            if avg_rating > 0:
                text += f"⭐ Average Rating: {avg_rating:.1f}/10"
            
            buttons = [
                [InlineKeyboardButton("📖 View Watchlist", callback_data="show_watchlist")],
                [InlineKeyboardButton("🎯 Get Recommendations", callback_data="get_recommendations"),
                 InlineKeyboardButton("📊 Detailed Stats", callback_data="detailed_stats")]
            ]

        await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        logger.error(f"Error in profile command: {e}")
        await send_error_message(message)

@Client.on_message(filters.command("random"))
async def random_drama(client, message):
    """Get a random popular drama recommendation"""
    try:
        status_msg = await message.reply("🎲 Finding a random drama for you...")
        popular = await get_popular_kdramas()
        
        if not popular:
            await status_msg.edit("⚠️ Unable to load dramas right now.")
            return
        
        import random
        random_drama = random.choice(popular)
        
        buttons = [
            [InlineKeyboardButton("📖 View Details", callback_data=f"details_{random_drama['id']}")],
            [InlineKeyboardButton("➕ Add to Watchlist", callback_data=f"add_{random_drama['id']}")],
            [InlineKeyboardButton("🎲 Another Random", callback_data="random_drama")]
        ]
        
        await status_msg.edit(
            f"🎲 **Random Drama Pick:**\n\n"
            f"🎬 {format_drama_title(random_drama)}\n\n"
            f"Give it a try! You might discover your next favorite drama.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Error in random command: {e}")
        await send_error_message(message)

# ------------------ CALLBACK HANDLERS ------------------
@Client.on_callback_query(filters.regex(r"^details_"))
async def show_drama_details(client, query: CallbackQuery):
    """Show detailed drama information with enhanced layout"""
    try:
        tv_id = int(query.data.split("_")[1])
        details = await get_tmdb_details(tv_id)
        
        if not details:
            return await query.answer("❌ Unable to load drama details", show_alert=True)
        
        # Format details
        title = details.get("name", "Unknown")
        year = details.get("first_air_date", "")[:4] if details.get("first_air_date") else "N/A"
        rating = f"{details.get('vote_average', 0):.1f}/10" if details.get('vote_average') else "N/A"
        genres = ", ".join([g["name"] for g in details.get("genres", [])])
        overview = truncate_text(details.get("overview", "No description available"), 400)
        
        episodes = details.get("number_of_episodes", "N/A")
        seasons = details.get("number_of_seasons", "N/A")
        status = details.get("status", "N/A")
        
        # Get additional info
        networks = ", ".join([n["name"] for n in details.get("networks", [])[:2]])
        origin_country = ", ".join(details.get("origin_country", []))
        
        text = (f"🎬 **{title}** ({year})\n\n"
               f"⭐ Rating: {rating}\n"
               f"📺 Episodes: {episodes} | Seasons: {seasons}\n"
               f"📊 Status: {status}\n"
               f"🌍 Country: {origin_country}\n")
        
        if networks:
            text += f"📡 Network: {networks}\n"
        
        text += f"🎭 Genres: {genres}\n\n"
        text += f"📖 **Synopsis:**\n{overview}"
        
        # Check if already in watchlist
        user = await users.find_one({"user_id": query.from_user.id})
        in_watchlist = False
        watchlist_item = None
        
        if user and user.get("watchlist"):
            for item in user["watchlist"]:
                if item.get("tv_id") == tv_id:
                    in_watchlist = True
                    watchlist_item = item
                    break
        
        buttons = []
        if not in_watchlist:
            buttons.append([InlineKeyboardButton("➕ Add to Watchlist", callback_data=f"add_{tv_id}")])
        else:
            status = watchlist_item.get("status", "To Watch")
            buttons.append([InlineKeyboardButton(f"✅ In Watchlist ({status})", callback_data="already_added")])
        
        # Add additional action buttons
        buttons.append([
            InlineKeyboardButton("🎯 Similar Dramas", callback_data=f"similar_{tv_id}"),
            InlineKeyboardButton("⭐ Rate Drama", callback_data=f"quick_rate_{tv_id}")
        ])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_search")])
        
        # Try to send with poster
        if details.get("poster_path"):
            poster_url = f"https://image.tmdb.org/t/p/w500{details['poster_path']}"
            try:
                await query.message.reply_photo(
                    poster_url,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode="Markdown"
                )
                await query.message.delete()
            except Exception as e:
                logger.warning(f"Failed to send poster image: {e}")
                await query.message.edit_text(
                    text, 
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode="Markdown"
                )
        else:
            await query.message.edit_text(
                text, 
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
        
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error showing drama details: {e}")
        await query.answer("❌ Error loading drama details", show_alert=True)

@Client.on_callback_query(filters.regex(r"^add_"))
async def confirm_add(client, query: CallbackQuery):
    """Add drama to watchlist with enhanced confirmation"""
    try:
        user_id = query.from_user.id
        tv_id = int(query.data.split("_")[1])
        
        # Check if already exists
        user = await users.find_one({"user_id": user_id})
        watchlist = user.get("watchlist", []) if user else []
        
        if any(d.get("tv_id") == tv_id for d in watchlist):
            return await query.answer("✅ Already in your watchlist!", show_alert=True)
        
        details = await get_tmdb_details(tv_id)
        if not details:
            return await query.answer("❌ Error loading drama details", show_alert=True)

        drama = {
            "tv_id": tv_id,
            "title": details.get("name", "Unknown"),
            "poster": f"https://image.tmdb.org/t/p/w500{details['poster_path']}" if details.get("poster_path") else None,
            "rating": details.get("vote_average", 0),
            "genres": [g["name"] for g in details.get("genres", [])],
            "year": details.get("first_air_date", "")[:4] if details.get("first_air_date") else "N/A",
            "episode_count": details.get("number_of_episodes", 0),
            "status": "To Watch",
            "user_rating": 0,
            "added_at": datetime.datetime.utcnow(),
            "notes": ""
        }

        await users.update_one(
            {"user_id": user_id},
            {"$push": {"watchlist": drama}},
            upsert=True
        )
        
        buttons = [
            [InlineKeyboardButton("🎯 Set Status", callback_data=f"quick_status_{tv_id}")],
            [InlineKeyboardButton("📖 View Watchlist", callback_data="show_watchlist"),
             InlineKeyboardButton("🎯 Get Similar", callback_data=f"similar_{tv_id}")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        
        await query.message.edit_text(
            f"✅ **{drama['title']}** added to your watchlist!\n\n"
            f"📌 Status: {drama['status']}\n"
            f"🎬 Episodes: {drama['episode_count']}\n"
            f"⭐ TMDB Rating: {drama['rating']:.1f}/10\n\n"
            f"Use the buttons below to manage your drama or get recommendations.",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        
        await query.answer("✅ Added to watchlist!")
        
    except Exception as e:
        logger.error(f"Error adding drama to watchlist: {e}")
        await query.answer("❌ Error adding drama", show_alert=True)

# ------------------ WATCHLIST MANAGEMENT ------------------
@Client.on_callback_query(filters.regex(r"^filter_"))
async def filter_watchlist(client, query: CallbackQuery):
    """Filter watchlist by status with improved error handling"""
    try:
        user_id = query.from_user.id
        user = await users.find_one({"user_id": user_id})
        
        watchlist = user.get("watchlist", []) if user else []
        
        if not watchlist:
            return await query.answer("⚠️ Watchlist is empty", show_alert=True)
        
        # Parse callback data
        data_parts = query.data.split("_")
        if len(data_parts) < 3:
            return await query.answer("❌ Invalid request", show_alert=True)
            
        filter_type = data_parts[1]
        try:
            page = int(data_parts[2])
        except ValueError:
            return await query.answer("❌ Invalid page number", show_alert=True)
        
        # Filter watchlist based on type
        if filter_type == "watching":
            filtered = [d for d in watchlist if d.get("status") == "Watching"]
            status_name = "Currently Watching"
        elif filter_type == "watched":
            filtered = [d for d in watchlist if d.get("status") == "Watched"]
            status_name = "Completed"
        elif filter_type == "towatch":
            filtered = [d for d in watchlist if d.get("status") == "To Watch"]
            status_name = "Plan to Watch"
        elif filter_type == "all":
            filtered = watchlist
            status_name = "All Dramas"
        else:
            return await query.answer("❌ Invalid filter type", show_alert=True)
        
        if not filtered:
            return await query.answer(f"⚠️ No dramas in {status_name}", show_alert=True)
        
        # Validate page number
        if page < 0 or page >= len(filtered):
            return await query.answer("❌ Invalid page", show_alert=True)
        
        await send_filtered_watchlist_page(query.message, filtered, page, filter_type, status_name)
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error in filter_watchlist: {e}")
        await query.answer("❌ An error occurred", show_alert=True)

async def send_filtered_watchlist_page(message, watchlist, page, filter_type, status_name):
    """Send filtered watchlist page with enhanced UI"""
    try:
        if page < 0 or page >= len(watchlist):
            return
            
        drama = watchlist[page]
        
        # Build drama info text
        text = f"📺 **{drama.get('title', 'Unknown Title')}**"
        if drama.get('year'):
            text += f" ({drama['year']})"
        text += f"\n\n📋 **{status_name}** ({page + 1}/{len(watchlist)})\n\n"
        
        # Drama details
        text += f"⭐ TMDB Rating: {drama.get('rating', 'N/A')}/10\n"
        
        genres = drama.get('genres', [])
        if isinstance(genres, list) and genres:
            text += f"🎭 Genres: {', '.join(genres[:3])}\n"
        
        text += f"📺 Episodes: {drama.get('episode_count', 'N/A')}\n"
        text += f"📌 Status: {drama.get('status', 'Unknown')}\n"
        
        if drama.get('user_rating', 0) > 0:
            text += f"🌟 Your Rating: {drama['user_rating']}/10\n"
        
        if drama.get('notes'):
            notes = truncate_text(drama['notes'], 100)
            text += f"📝 Notes: {notes}\n"
        
        added_date = drama.get('added_at')
        if added_date:
            if isinstance(added_date, datetime.datetime):
                text += f"📅 Added: {added_date.strftime('%b %Y')}\n"
        
        # Status change buttons
        status_buttons = []
        current_status = drama.get('status', 'To Watch')
        
        if current_status != "Watching":
            status_buttons.append(InlineKeyboardButton("▶️ Watching", callback_data=f"status_{page}_Watching_{filter_type}"))
        if current_status != "Watched":
            status_buttons.append(InlineKeyboardButton("✅ Watched", callback_data=f"status_{page}_Watched_{filter_type}"))
        if current_status != "To Watch":
            status_buttons.append(InlineKeyboardButton("⏳ To Watch", callback_data=f"status_{page}_To Watch_{filter_type}"))
        
        buttons = []
        if status_buttons:
            # Split status buttons into rows of 2
            for i in range(0, len(status_buttons), 2):
                buttons.append(status_buttons[i:i+2])
        
        # Action buttons
        action_buttons = [
            InlineKeyboardButton("⭐ Rate", callback_data=f"rate_{page}_{filter_type}"),
            InlineKeyboardButton("ℹ️ Details", callback_data=f"details_{drama.get('tv_id', '')}")
        ]
        buttons.append(action_buttons)
        
        # Management buttons
        manage_buttons = [
            InlineKeyboardButton("📝 Notes", callback_data=f"notes_{page}_{filter_type}"),
            InlineKeyboardButton("🗑 Remove", callback_data=f"confirm_remove_{page}_{filter_type}")
        ]
        buttons.append(manage_buttons)
        
        # Navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"filter_{filter_type}_{page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"{page+1}/{len(watchlist)}", callback_data="page_info"))
        
        if page < len(watchlist) - 1:
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"filter_{filter_type}_{page+1}"))
        
        buttons.append(nav_buttons)
        
        # Back to filters button
        buttons.append([InlineKeyboardButton("🔙 Back to Filters", callback_data="show_watchlist")])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        # Try to send with poster
        if drama.get("poster"):
            try:
                if message.photo:
                    await message.edit_media(
                        InputMediaPhoto(drama["poster"], caption=text, parse_mode="Markdown"),
                        reply_markup=reply_markup
                    )
                else:
                    new_message = await message.reply_photo(
                        drama["poster"], 
                        caption=text, 
                        reply_markup=reply_markup,
                        parse_mode="Markdown"
                    )
                    await message.delete()
                    return new_message
            except Exception as e:
                logger.warning(f"Error sending photo: {e}")
                await message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in send_filtered_watchlist_page: {e}")
        try:
            await message.edit_text(
                "❌ Error loading watchlist page", 
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Filters", callback_data="show_watchlist")
                ]])
            )
        except:
            pass

# ------------------ STATUS AND RATING MANAGEMENT ------------------
@Client.on_callback_query(filters.regex(r"^status_"))
async def update_status(client, query: CallbackQuery):
    """Update drama status in watchlist"""
    try:
        parts = query.data.split("_")
        if len(parts) < 4:
            return await query.answer("❌ Invalid request", show_alert=True)
        
        page = int(parts[1])
        new_status = parts[2]
        filter_type = parts[3]
        
        user_id = query.from_user.id
        user = await users.find_one({"user_id": user_id})
        
        watchlist = user.get("watchlist", []) if user else []
        if not watchlist:
            return await query.answer("❌ Watchlist not found", show_alert=True)
        
        # Get filtered watchlist
        if filter_type == "watching":
            filtered = [d for d in watchlist if d.get("status") == "Watching"]
        elif filter_type == "watched":
            filtered = [d for d in watchlist if d.get("status") == "Watched"]
        elif filter_type == "towatch":
            filtered = [d for d in watchlist if d.get("status") == "To Watch"]
        else:
            filtered = watchlist
        
        if page >= len(filtered):
            return await query.answer("❌ Invalid page", show_alert=True)
        
        drama_to_update = filtered[page]
        tv_id = drama_to_update.get("tv_id")
        
        # Update status in database
        await users.update_one(
            {"user_id": user_id, "watchlist.tv_id": tv_id},
            {"$set": {"watchlist.$.status": new_status}}
        )
        
        # Update stats if moved to watched
        if new_status == "Watched":
            await update_user_stats(user_id)
        
        await query.answer(f"✅ Status updated to {new_status}")
        
        # Refresh the page - if filter doesn't match new status, go back to filters
        if (filter_type == "watching" and new_status != "Watching") or \
           (filter_type == "watched" and new_status != "Watched") or \
           (filter_type == "towatch" and new_status != "To Watch"):
            # Status no longer matches filter, show watchlist menu
            await show_watchlist_menu(query.message)
        else:
            # Reload the current page
            await filter_watchlist(client, query)
        
    except Exception as e:
        logger.error(f"Error updating status: {e}")
        await query.answer("❌ Error updating status", show_alert=True)

async def show_watchlist_menu(message):
    """Show the main watchlist menu"""
    try:
        user_id = message.chat.id if hasattr(message, 'chat') else message.from_user.id
        user = await users.find_one({"user_id": user_id})
        
        watchlist = user.get("watchlist", []) if user else []
        
        if not watchlist:
            return await message.edit_text("📌 Your watchlist is empty.")
        
        stats = {
            "total": len(watchlist),
            "watching": len([d for d in watchlist if d.get("status") == "Watching"]),
            "watched": len([d for d in watchlist if d.get("status") == "Watched"]),
            "to_watch": len([d for d in watchlist if d.get("status") == "To Watch"])
        }
        
        completion_pct = round((stats["watched"] / stats["total"]) * 100) if stats["total"] > 0 else 0
        
        text = (f"📖 **Your Watchlist** ({stats['total']} dramas)\n\n"
               f"📊 **Statistics:**\n"
               f"• ▶️ Watching: {stats['watching']}\n"
               f"• ✅ Watched: {stats['watched']}\n"
               f"• ⏳ To Watch: {stats['to_watch']}\n"
               f"• 📈 Completion: {completion_pct}%\n\n"
               f"Select a filter to browse your dramas:")
        
        buttons = [
            [InlineKeyboardButton("📖 All", callback_data="filter_all_0"),
             InlineKeyboardButton("▶️ Watching", callback_data="filter_watching_0")],
            [InlineKeyboardButton("✅ Watched", callback_data="filter_watched_0"),
             InlineKeyboardButton("⏳ To Watch", callback_data="filter_towatch_0")]
        ]
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error showing watchlist menu: {e}")

@Client.on_callback_query(filters.regex(r"^rate_"))
async def rate_drama(client, query: CallbackQuery):
    """Show rating options for a drama"""
    try:
        parts = query.data.split("_")
        page = int(parts[1])
        filter_type = parts[2]
        
        # Create rating buttons (1-10)
        buttons = []
        for i in range(1, 11, 2):  # 1-3, 3-5, 5-7, 7-9, 9-10
            row = []
            for j in range(i, min(i+2, 11)):
                row.append(InlineKeyboardButton(f"{j}⭐", callback_data=f"set_rating_{page}_{j}_{filter_type}"))
            buttons.append(row)
        
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"filter_{filter_type}_{page}")])
        
        await query.message.edit_text(
            "⭐ **Rate this drama (1-10):**\n\nSelect your rating below:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error in rate_drama: {e}")
        await query.answer("❌ Error showing rating options", show_alert=True)

@Client.on_callback_query(filters.regex(r"^set_rating_"))
async def set_rating(client, query: CallbackQuery):
    """Set rating for a drama"""
    try:
        parts = query.data.split("_")
        page = int(parts[2])
        rating = int(parts[3])
        filter_type = parts[4]
        
        user_id = query.from_user.id
        user = await users.find_one({"user_id": user_id})
        
        watchlist = user.get("watchlist", []) if user else []
        if not watchlist:
            return await query.answer("❌ Watchlist not found", show_alert=True)
        
        # Get the correct drama from filtered list
        if filter_type == "watching":
            filtered = [d for d in watchlist if d.get("status") == "Watching"]
        elif filter_type == "watched":
            filtered = [d for d in watchlist if d.get("status") == "Watched"]
        elif filter_type == "towatch":
            filtered = [d for d in watchlist if d.get("status") == "To Watch"]
        else:
            filtered = watchlist
        
        if page >= len(filtered):
            return await query.answer("❌ Invalid page", show_alert=True)
        
        drama_to_rate = filtered[page]
        tv_id = drama_to_rate.get("tv_id")
        
        # Update rating in database
        await users.update_one(
            {"user_id": user_id, "watchlist.tv_id": tv_id},
            {"$set": {"watchlist.$.user_rating": rating}}
        )
        
        await query.answer(f"✅ Rated {rating}/10!")
        
        # Go back to the drama page
        callback_query = CallbackQuery(
            id=query.id,
            from_user=query.from_user,
            chat_instance=query.chat_instance,
            message=query.message,
            data=f"filter_{filter_type}_{page}"
        )
        await filter_watchlist(client, callback_query)
        
    except Exception as e:
        logger.error(f"Error setting rating: {e}")
        await query.answer("❌ Error setting rating", show_alert=True)

# ------------------ ADDITIONAL CALLBACK HANDLERS ------------------
@Client.on_callback_query(filters.regex(r"^main_menu$"))
async def main_menu(client, query: CallbackQuery):
    """Return to main menu"""
    await start_command(client, query.message)

@Client.on_callback_query(filters.regex(r"^show_watchlist$"))
async def show_watchlist_callback(client, query: CallbackQuery):
    """Show watchlist callback handler"""
    await show_watchlist(client, query.message)

@Client.on_callback_query(filters.regex(r"^show_profile$"))
async def show_profile_callback(client, query: CallbackQuery):
    """Show profile callback handler"""
    await profile(client, query.message)

@Client.on_callback_query(filters.regex(r"^get_recommendations$"))
async def get_recommendations_callback(client, query: CallbackQuery):
    """Get recommendations callback handler"""
    await recommend(client, query.message)

@Client.on_callback_query(filters.regex(r"^popular_dramas$"))
async def popular_dramas_callback(client, query: CallbackQuery):
    """Popular dramas callback handler"""
    await show_popular(client, query.message)

@Client.on_callback_query(filters.regex(r"^random_drama$"))
async def random_drama_callback(client, query: CallbackQuery):
    """Random drama callback handler"""
    await random_drama(client, query.message)

@Client.on_callback_query(filters.regex(r"^similar_"))
async def show_similar_dramas(client, query: CallbackQuery):
    """Show similar dramas"""
    try:
        tv_id = int(query.data.split("_")[1])
        
        status_msg = await query.message.reply("🔍 Finding similar dramas...")
        recommendations = await get_recommendations(tv_id)
        
        if not recommendations:
            await status_msg.edit("⚠️ No similar dramas found.")
            return
        
        buttons = []
        for rec in recommendations[:8]:
            buttons.append([
                InlineKeyboardButton(
                    format_drama_title(rec),
                    callback_data=f"details_{rec['id']}"
                )
            ])
        
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"details_{tv_id}")])
        
        await status_msg.edit(
            "🎯 **Similar Dramas:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error showing similar dramas: {e}")
        await query.answer("❌ Error loading similar dramas", show_alert=True)

@Client.on_callback_query(filters.regex(r"^already_added$"))
async def already_added(client, query: CallbackQuery):
    """Handle already added callback"""
    await query.answer("✅ This drama is already in your watchlist!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^page_info$"))
async def page_info(client, query: CallbackQuery):
    """Handle page info callback"""
    await query.answer("📄 Page information", show_alert=False)

# ------------------ ERROR HANDLING AND CLEANUP ------------------
@Client.on_callback_query()
async def handle_unknown_callback(client, query: CallbackQuery):
    """Handle unknown callback queries"""
    logger.warning(f"Unknown callback query: {query.data}")
    await query.answer("❌ Unknown action", show_alert=False)
