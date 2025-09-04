import os
import requests
import base64
from pyrogram import Client, filters, enums
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant, MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from utils import extract_user, get_file_id, get_poster
import time
from datetime import datetime
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import logging
import json

import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient
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



# ------------------ CONFIG ------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://kdramabot:Buo0fRGenkOAkgXH@pastppr.ipuyepp.mongodb.net/?retryWrites=true&w=majority&appName=pastppr")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["pastppr"]
users = db["users"]

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "90dde61a7cf8339a2cff5d805d5597a9")
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# ------------------ BOT CLIENT ------------------
# ------------------ TMDB HELPERS ------------------
async def search_tmdb(query: str):
    """Search TMDB for dramas by name"""
    url = f"{TMDB_BASE_URL}/search/tv?api_key={TMDB_API_KEY}&query={query}&language=en-US"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return data.get("results", [])

async def get_tmdb_details(tv_id: int):
    """Fetch drama details from TMDB"""
    url = f"{TMDB_BASE_URL}/tv/{tv_id}?api_key={TMDB_API_KEY}&language=en-US"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

async def get_recommendations(tv_id: int):
    """Fetch TMDB recommendations"""
    url = f"{TMDB_BASE_URL}/tv/{tv_id}/recommendations?api_key={TMDB_API_KEY}&language=en-US"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return data.get("results", [])

# ------------------ COMMANDS ------------------
@Client.on_message(filters.command("add"))
async def add_watchlist(client, message):
    """Add drama to watchlist"""
    user_id = message.from_user.id
    query = " ".join(message.command[1:])
    if not query:
        return await message.reply("❌ Please provide a drama name.\nUsage: `/add Goblin`")

    results = await search_tmdb(query)
    if not results:
        return await message.reply("⚠ No dramas found.")

    buttons = []
    for r in results[:5]:
        buttons.append([
            InlineKeyboardButton(f"{r['name']} ({r['first_air_date'][:4] if r.get('first_air_date') else 'N/A'})",
                                 callback_data=f"add_{r['id']}")
        ])
    await message.reply("🔍 Select a drama to add:", reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^add_"))
async def confirm_add(client, query: CallbackQuery):
    """Confirm adding selected drama"""
    user_id = query.from_user.id
    tv_id = int(query.data.split("_")[1])
    details = await get_tmdb_details(tv_id)

    drama = {
        "tv_id": tv_id,
        "title": details["name"],
        "poster": f"https://image.tmdb.org/t/p/w500{details['poster_path']}" if details.get("poster_path") else None,
        "rating": details.get("vote_average", 0),
        "genres": [g["name"] for g in details.get("genres", [])],
        "status": "To Watch",
        "added_at": datetime.datetime.utcnow()
    }

    await users.update_one(
        {"user_id": user_id},
        {"$push": {"watchlist": drama}},
        upsert=True
    )
    await query.message.edit_text(f"✅ Added **{drama['title']}** to your watchlist!")


@Client.on_message(filters.command("watchlist"))
async def show_watchlist(client, message):
    """Display paginated watchlist"""
    user_id = message.from_user.id
    user = await users.find_one({"user_id": user_id})
    if not user or "watchlist" not in user or not user["watchlist"]:
        return await message.reply("📌 Your watchlist is empty. Add dramas using `/add <name>`.")

    await send_watchlist_page(message, user["watchlist"], 0)


async def send_watchlist_page(message, watchlist, page):
    """Helper to send one page of watchlist"""
    if page < 0 or page >= len(watchlist):
        return

    drama = watchlist[page]
    text = (
        f"**🎬 {drama['title']}**\n\n"
        f"⭐ Rating: {drama['rating']}/10\n"
        f"📖 Genres: {', '.join(drama['genres']) if drama['genres'] else 'N/A'}\n"
        f"📌 Status: {drama['status']}\n"
    )

    buttons = [
        [
            InlineKeyboardButton("▶ Watching", callback_data=f"status_{page}_Watching"),
            InlineKeyboardButton("✅ Watched", callback_data=f"status_{page}_Watched"),
        ],
        [
            InlineKeyboardButton("⏳ To Watch", callback_data=f"status_{page}_To Watch"),
            InlineKeyboardButton("🗑 Remove", callback_data=f"remove_{page}")
        ],
        [
            InlineKeyboardButton("⬅ Prev", callback_data=f"page_{page-1}"),
            InlineKeyboardButton("➡ Next", callback_data=f"page_{page+1}")
        ]
    ]

    if drama.get("poster"):
        await message.reply_photo(drama["poster"], caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^page_"))
async def paginate_watchlist(client, query: CallbackQuery):
    """Handle watchlist pagination"""
    user_id = query.from_user.id
    user = await users.find_one({"user_id": user_id})
    if not user or "watchlist" not in user:
        return await query.answer("⚠ Watchlist empty.", show_alert=True)

    page = int(query.data.split("_")[1])
    await query.message.delete()
    await send_watchlist_page(query.message, user["watchlist"], page)


@Client.on_callback_query(filters.regex(r"^status_"))
async def change_status(client, query: CallbackQuery):
    """Update drama status"""
    user_id = query.from_user.id
    _, page, status = query.data.split("_", 2)
    page = int(page)

    user = await users.find_one({"user_id": user_id})
    if not user or "watchlist" not in user:
        return await query.answer("⚠ Watchlist empty.", show_alert=True)

    watchlist = user["watchlist"]
    if page < 0 or page >= len(watchlist):
        return

    watchlist[page]["status"] = status
    await users.update_one({"user_id": user_id}, {"$set": {"watchlist": watchlist}})

    await query.answer(f"✅ Status updated to {status}")
    await query.message.delete()
    await send_watchlist_page(query.message, watchlist, page)


@Client.on_callback_query(filters.regex(r"^remove_"))
async def remove_drama(client, query: CallbackQuery):
    """Remove drama from watchlist"""
    user_id = query.from_user.id
    page = int(query.data.split("_")[1])

    user = await users.find_one({"user_id": user_id})
    if not user or "watchlist" not in user:
        return await query.answer("⚠ Watchlist empty.", show_alert=True)

    watchlist = user["watchlist"]
    if page < 0 or page >= len(watchlist):
        return

    removed = watchlist.pop(page)
    await users.update_one({"user_id": user_id}, {"$set": {"watchlist": watchlist}})
    await query.message.edit_text(f"🗑 Removed **{removed['title']}** from your watchlist.")


@Client.on_message(filters.command("recommend"))
async def recommend(client, message):
    """Suggest similar dramas based on last watched"""
    user_id = message.from_user.id
    user = await users.find_one({"user_id": user_id})
    if not user or "watchlist" not in user or not user["watchlist"]:
        return await message.reply("📌 Your watchlist is empty. Add dramas using `/add <name>`.")

    # Pick the most recent drama
    last = user["watchlist"][-1]
    recs = await get_recommendations(last["tv_id"])
    if not recs:
        return await message.reply("⚠ No recommendations found.")

    text = f"🎯 Recommendations based on **{last['title']}**:\n\n"
    for r in recs[:5]:
        text += f"🎬 {r['name']} ({r['first_air_date'][:4] if r.get('first_air_date') else 'N/A'}) ⭐ {r['vote_average']}/10\n"

    await message.reply(text)


@Client.on_message(filters.command("profile"))
async def profile(client, message):
    """Show user profile + watchlist summary"""
    user_id = message.from_user.id
    user = await users.find_one({"user_id": user_id})

    if not user or "watchlist" not in user or not user["watchlist"]:
        return await message.reply(
            f"👤 Profile: @{message.from_user.username or message.from_user.first_name}\n"
            f"📌 You don't have any dramas in your watchlist yet.\n\n"
            f"➕ Add dramas with `/add <name>`"
        )

    watchlist = user["watchlist"]
    watching = len([d for d in watchlist if d["status"] == "Watching"])
    watched = len([d for d in watchlist if d["status"] == "Watched"])
    to_watch = len([d for d in watchlist if d["status"] == "To Watch"])

    text = (
        f"👤 Profile: @{message.from_user.username or message.from_user.first_name}\n"
        f"🆔 User ID: `{user_id}`\n\n"
        f"📖 Watchlist Summary:\n"
        f"🎬 Watching: {watching}\n"
        f"✅ Watched: {watched}\n"
        f"⏳ To Watch: {to_watch}\n"
        f"📌 Total: {len(watchlist)} dramas"
    )

    buttons = [[InlineKeyboardButton("📖 View Watchlist", callback_data="page_0")]]
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))
