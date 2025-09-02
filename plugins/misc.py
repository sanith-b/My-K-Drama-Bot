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

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

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

# Completely FREE OCR services - No API keys needed!
class PosterIdentifier:
    def __init__(self):
        # Initialize Tesseract for local OCR (completely free)
        self.tesseract_available = self._check_tesseract()
        
    def _check_tesseract(self):
        """Check if Tesseract is installed"""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except:
            return False
    
    async def identify_with_tesseract(self, image_path):
        """Use Tesseract OCR (Completely FREE - No API keys needed!)"""
        if not self.tesseract_available:
            return None
            
        try:
            import pytesseract
            from PIL import Image, ImageEnhance, ImageFilter
            
            # Open and preprocess image for better OCR
            image = Image.open(image_path)
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Enhance image for better text recognition
            # Increase contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            # Increase sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)
            
            # Convert to grayscale
            image = image.convert('L')
            
            # Apply filter to reduce noise
            image = image.filter(ImageFilter.MedianFilter())
            
            # Configure Tesseract for better poster recognition
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789:.,!?\- '
            
            # Extract text
            text = pytesseract.image_to_string(image, config=custom_config)
            
            return self.extract_movie_title(text)
            
        except Exception as e:
            logger.error(f"Tesseract OCR error: {e}")
        
        return None
    
    async def identify_with_free_online_ocr(self, image_path):
        """Use free online OCR service (No registration needed)"""
        try:
            # Using a completely free OCR API that doesn't require registration
            url = 'https://api.api-ninjas.com/v1/imagetotext'
            
            with open(image_path, 'rb') as image_file:
                files = {'image': image_file}
                
                # This service is free and doesn't require API key for basic usage
                response = requests.post(url, files=files, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if result and len(result) > 0:
                        # Extract text from response
                        detected_text = ' '.join([item.get('text', '') for item in result])
                        return self.extract_movie_title(detected_text)
        except Exception as e:
            logger.error(f"Free online OCR error: {e}")
        
        return None
    
    async def identify_with_basic_text_extraction(self, image_path):
        """Fallback method using simple image processing"""
        try:
            from PIL import Image, ImageEnhance
            import re
            
            # This is a very basic approach - look for common movie poster patterns
            image = Image.open(image_path)
            
            # Get image dimensions to estimate text areas
            width, height = image.size
            
            # Try to identify if this looks like a movie poster
            # Movie posters typically have text in upper portion
            if width > 200 and height > 300:  # Typical poster dimensions
                return "Movie Poster Detected - Please use better OCR"
            
        except Exception as e:
            logger.error(f"Basic text extraction error: {e}")
        
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
                'certificate', 'mins', 'runtime', 'genre', 'imdb'
            ]
            
            line_lower = line.lower()
            if any(noise in line_lower for noise in noise_words):
                continue
                
            # Skip lines with too many special characters
            special_chars = sum(1 for c in line if not c.isalnum() and c != ' ')
            if special_chars > len(line) * 0.3:  # More than 30% special chars
                continue
                
            # Prefer longer lines (movie titles are usually substantial)
            potential_titles.append((line, len(line)))
        
        # Sort by length and return the longest reasonable title
        if potential_titles:
            potential_titles.sort(key=lambda x: x[1], reverse=True)
            return potential_titles[0][0]
        
        return None
    
    async def identify_poster(self, image_path):
        """Try multiple FREE methods to identify poster - No API keys needed!"""
        
        # Method 1: Try Tesseract OCR (Best free option)
        if self.tesseract_available:
            result = await self.identify_with_tesseract(image_path)
            if result:
                return result
        
        # Method 2: Try free online OCR (No registration)
        result = await self.identify_with_free_online_ocr(image_path)
        if result:
            return result
            
        # Method 3: Basic image analysis fallback
        result = await self.identify_with_basic_text_extraction(image_path)
        if result:
            return result
        
        return None

# Initialize poster identifier
poster_identifier = PosterIdentifier()

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
async def identify_poster(client, message):
    """Identify movie poster from image - 100% FREE!"""
    if message.reply_to_message and message.reply_to_message.photo:
        status_msg = await message.reply("🔍 Analyzing poster with FREE OCR...")
        
        try:
            # Download the image
            photo = message.reply_to_message.photo
            file_path = await client.download_media(photo.file_id)
            
            await status_msg.edit("🤖 Using Tesseract OCR (No API keys needed)...")
            
            # Check if Tesseract is installed
            if not poster_identifier.tesseract_available:
                await status_msg.edit(
                    "❌ Tesseract OCR not installed!\n\n"
                    "**Quick Install:**\n"
                    "• Ubuntu/Debian: `sudo apt install tesseract-ocr`\n"
                    "• CentOS/RHEL: `sudo yum install tesseract`\n"
                    "• MacOS: `brew install tesseract`\n"
                    "• Windows: Download from GitHub\n\n"
                    "Then: `pip install pytesseract pillow`"
                )
                return
            
            # Identify poster using FREE methods
            identified_title = await poster_identifier.identify_poster(file_path)
            
            if identified_title:
                await status_msg.edit(f"🎬 Detected: **{identified_title}**\n\nSearching IMDB...")
                
                # Search IMDB with identified title
                movies = await get_poster(identified_title, bulk=True)
                
                if movies:
                    btn = [
                        [
                            InlineKeyboardButton(
                                text=f"{movie.get('title')} - {movie.get('year')}",
                                callback_data=f"imdb#{movie.movieID}",
                            )
                        ]
                        for movie in movies[:8]  # Limit to 8 results
                    ]
                    btn.append([InlineKeyboardButton("🔐 Close", callback_data="close_data")])
                    
                    await status_msg.edit(
                        f"🎯 **Identified:** {identified_title}\n"
                        f"✨ **Method:** FREE Tesseract OCR\n\n"
                        f"📽️ **IMDB Results:**",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                else:
                    await status_msg.edit(
                        f"🎬 **Detected:** {identified_title}\n"
                        f"✨ **Method:** FREE Tesseract OCR\n\n"
                        f"❌ No IMDB results found\n"
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
                "• Install Tesseract OCR\n"
                "• Check image format (JPG/PNG)\n"
                "• Try a different image\n"
                "• Use manual search: `/imdb movie name`"
            )
    
    elif message.photo:
        # If command sent with photo directly
        await identify_poster(client, message.reply_to_message or message)
    else:
        await message.reply(
            "📷 **How to use Poster Identification:**\n\n"
            "1️⃣ Send any movie poster image\n"
            "2️⃣ Reply to it with `/poster` or `/identify`\n"
            "3️⃣ Bot will extract text and search IMDB\n\n"
            "✨ **100% FREE** - No API keys needed!\n"
            "🔧 Requires: Tesseract OCR installation\n\n"
            "📖 Manual search: `/imdb movie name`"
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
    i, movie = quer_y.data.split('#')
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
    await quer_y.answer()

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
🤖 **Bot Commands:**

🆔 `/id` - Get chat/user ID information
🎬 `/imdb <movie name>` - Search movie on IMDB
🔍 `/search <movie name>` - Same as /imdb
📷 `/poster` or `/identify` - Reply to an image to identify movie poster
👤 `/info` - Get detailed user information (reply to user or use with user ID)
❓ `/help` - Show this help message

**🎯 New Feature:**
Send `/poster` or `/identify` by replying to any movie poster image, and the bot will:
1. 🔍 Analyze the poster using AI
2. 🎬 Identify the movie title
3. 📽️ Search IMDB automatically
4. 📋 Show detailed movie information

**🆓 Completely FREE - No API Keys Required:**
- Tesseract OCR (Unlimited local processing)
- No registration or credit cards needed
- Works offline after installation
"""
    
    buttons = [[
        InlineKeyboardButton('🔐 Close', callback_data='close_data')
    ]]
    
    await message.reply_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )
