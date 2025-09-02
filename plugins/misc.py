import os
import json
import aiohttp
import re
from pyrogram import Client, filters, enums
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant, MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from utils import extract_user, get_file_id, get_poster
import time
from datetime import datetime
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# K-Drama API Configuration
KDRAMA_APIS = {
    "mydramalist": {
        "url": "https://api.mydramalist.com/v1/search",
        "params": {"q": "{query}", "type": "drama"},
        "api_key_required": False,
        "description": "Search K-Dramas on MyDramaList"
    },
    "tmdb_kdrama": {
        "url": "https://api.themoviedb.org/3/search/tv",
        "params": {"api_key": "{api_key}", "query": "{query}", "with_origin_country": "KR"},
        "api_key_required": True,
        "description": "Search Korean dramas on TMDB"
    },
    "korean_shows": {
        "url": "https://api.tvmaze.com/search/shows",
        "params": {"q": "{query} korean"},
        "api_key_required": False,
        "description": "Search Korean shows on TVMaze"
    }
}

# API Keys for K-Drama services
API_KEYS = {
    "tmdb_kdrama": os.getenv("TMDB_API_KEY", "90dde61a7cf8339a2cff5d805d5597a9")
}

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

KDRAMA_TEMP = """
🎬 <b>Title:</b> {title} ({year})
🇰🇷 <b>Korean Title:</b> {korean_title}
⭐ <b>Rating:</b> {rating}/10
📺 <b>Episodes:</b> {episodes}
📅 <b>Aired:</b> {air_date}
🏢 <b>Network:</b> {network}
🎭 <b>Genre:</b> {genre}
📖 <b>Synopsis:</b> {synopsis}
👥 <b>Cast:</b> {cast}
"""

# K-Drama matching patterns for autofilter
KDRAMA_PATTERNS = [
    r'(?i)(kdrama|k-drama|korean drama)',
    r'(?i)(episode|ep)\s*(\d+)',
    r'(?i)(season|s)\s*(\d+)',
    r'(?i)(hindi|english|korean)\s*(sub|dub)',
    r'(?i)(720p|1080p|480p|4k)',
    r'(?i)(complete|ongoing|finished)',
]

async def make_kdrama_api_request(api_name, query=None, **kwargs):
    """Make a request to K-Drama APIs"""
    if api_name not in KDRAMA_APIS:
        return {"error": "K-Drama API not found"}
    
    api_config = KDRAMA_APIS[api_name]
    url = api_config["url"]
    params = api_config["params"].copy()
    
    # Replace placeholders
    for key, value in params.items():
        if isinstance(value, str):
            if "{query}" in value:
                params[key] = value.format(query=query or "")
            if "{api_key}" in value and api_name in API_KEYS:
                params[key] = value.format(api_key=API_KEYS[api_name])
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"API returned status {response.status}"}
    except Exception as e:
        return {"error": str(e)}

def format_kdrama_response(api_name, data):
    """Format K-Drama API response"""
    if "error" in data:
        return f"❌ Error: {data['error']}"
    
    if api_name == "tmdb_kdrama" and "results" in data:
        if not data["results"]:
            return "❌ No K-Dramas found"
        
        drama = data["results"][0]
        return KDRAMA_TEMP.format(
            title=drama.get("name", "N/A"),
            korean_title=drama.get("original_name", "N/A"),
            year=drama.get("first_air_date", "N/A")[:4] if drama.get("first_air_date") else "N/A",
            rating=drama.get("vote_average", "N/A"),
            episodes=drama.get("number_of_episodes", "N/A"),
            air_date=drama.get("first_air_date", "N/A"),
            network=", ".join([network["name"] for network in drama.get("networks", [])]) or "N/A",
            genre=", ".join([genre["name"] for genre in drama.get("genres", [])]) or "N/A",
            synopsis=drama.get("overview", "N/A")[:300] + "..." if len(drama.get("overview", "")) > 300 else drama.get("overview", "N/A"),
            cast="Loading..."
        )
    
    elif api_name == "korean_shows" and isinstance(data, list):
        if not data:
            return "❌ No Korean shows found"
        
        show = data[0]["show"]
        return f"🎬 <b>{show.get('name', 'N/A')}</b>\n" \
               f"📅 Premiered: {show.get('premiered', 'N/A')}\n" \
               f"🏢 Network: {show.get('network', {}).get('name', 'N/A') if show.get('network') else 'N/A'}\n" \
               f"⭐ Rating: {show.get('rating', {}).get('average', 'N/A') if show.get('rating') else 'N/A'}\n" \
               f"📖 Summary: {show.get('summary', 'N/A')[:200]}..."
    
    return f"📋 <b>K-Drama Info</b>\n\n<code>{json.dumps(data, indent=2)[:1000]}</code>"

def extract_kdrama_info(filename):
    """Extract K-Drama information from filename"""
    info = {
        "title": "",
        "episode": None,
        "season": None,
        "quality": None,
        "subtitle": None,
        "year": None,
        "is_kdrama": False
    }
    
    filename = filename.lower()
    
    # Check if it's a K-Drama
    kdrama_keywords = ['kdrama', 'k-drama', 'korean', 'hindi dubbed', 'eng sub']
    info["is_kdrama"] = any(keyword in filename for keyword in kdrama_keywords)
    
    # Extract episode number
    ep_match = re.search(r'(?:episode|ep)[\s\-]*(\d+)', filename)
    if ep_match:
        info["episode"] = int(ep_match.group(1))
    
    # Extract season
    season_match = re.search(r'(?:season|s)[\s\-]*(\d+)', filename)
    if season_match:
        info["season"] = int(season_match.group(1))
    
    # Extract quality
    quality_match = re.search(r'(480p|720p|1080p|4k)', filename)
    if quality_match:
        info["quality"] = quality_match.group(1)
    
    # Extract subtitle info
    if 'hindi' in filename and ('dub' in filename or 'dubbed' in filename):
        info["subtitle"] = "Hindi Dubbed"
    elif 'eng' in filename and 'sub' in filename:
        info["subtitle"] = "English Subtitles"
    elif 'korean' in filename:
        info["subtitle"] = "Korean Audio"
    
    # Extract year
    year_match = re.search(r'(20\d{2})', filename)
    if year_match:
        info["year"] = int(year_match.group(1))
    
    return info

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

# K-DRAMA SPECIFIC FEATURES

@Client.on_message(filters.command(["drama"]))
async def kdrama_search(client, message):
    """Search for K-Dramas using external APIs"""
    if ' ' in message.text:
        k = await message.reply('🔍 Searching for K-Drama...')
        r, title = message.text.split(None, 1)
        
        # Search using TMDB API for Korean dramas
        data = await make_kdrama_api_request("tmdb_kdrama", query=title)
        formatted_response = format_kdrama_response("tmdb_kdrama", data)
        
        if "results" in data and data["results"]:
            drama = data["results"][0]
            btn = [
                [
                    InlineKeyboardButton(
                        text="🔗 View on TMDB",
                        url=f"https://www.themoviedb.org/tv/{drama.get('id')}"
                    ),
                    InlineKeyboardButton(
                        text="📺 Search Episodes",
                        callback_data=f"episodes#{drama.get('id')}#{title}"
                    )
                ]
            ]
            
            if drama.get("poster_path"):
                poster_url = f"https://image.tmdb.org/t/p/w500{drama['poster_path']}"
                try:
                    await k.delete()
                    await message.reply_photo(
                        photo=poster_url,
                        caption=formatted_response,
                        reply_markup=InlineKeyboardMarkup(btn),
                        parse_mode=enums.ParseMode.HTML
                    )
                except:
                    await k.edit(formatted_response, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
            else:
                await k.edit(formatted_response, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
        else:
            await k.edit("❌ No K-Drama found with that title. Try a different search term.")
    else:
        await message.reply('Please provide a K-Drama title.\n\n**Usage:** `/kdrama Squid Game`')

@Client.on_message(filters.command("analyze"))
async def analyze_filename(client, message):
    """Analyze K-Drama filename for autofilter matching"""
    if message.reply_to_message and message.reply_to_message.document:
        filename = message.reply_to_message.document.file_name
    elif ' ' in message.text:
        _, filename = message.text.split(None, 1)
    else:
        await message.reply("Reply to a file or provide filename to analyze.\n\n**Usage:** `/analyze filename.mkv`")
        return
    
    info = extract_kdrama_info(filename)
    
    analysis = f"📋 <b>Filename Analysis</b>\n\n"
    analysis += f"📁 <b>File:</b> <code>{filename}</code>\n\n"
    analysis += f"🎭 <b>K-Drama:</b> {'✅ Yes' if info['is_kdrama'] else '❌ No'}\n"
    
    if info['episode']:
        analysis += f"📺 <b>Episode:</b> {info['episode']}\n"
    if info['season']:
        analysis += f"📅 <b>Season:</b> {info['season']}\n"
    if info['quality']:
        analysis += f"🎥 <b>Quality:</b> {info['quality']}\n"
    if info['subtitle']:
        analysis += f"🗣 <b>Audio/Sub:</b> {info['subtitle']}\n"
    if info['year']:
        analysis += f"📆 <b>Year:</b> {info['year']}\n"
    
    # Generate matching keywords
    keywords = []
    if info['is_kdrama']:
        keywords.extend(['kdrama', 'korean drama'])
    if info['episode']:
        keywords.extend([f"episode {info['episode']}", f"ep {info['episode']}"])
    if info['quality']:
        keywords.append(info['quality'])
    
    if keywords:
        analysis += f"\n🔍 <b>Suggested Keywords:</b>\n<code>{', '.join(keywords)}</code>"
    
    await message.reply(analysis, parse_mode=enums.ParseMode.HTML)

@Client.on_message(filters.command("trending"))
async def trending_kdramas(client, message):
    """Get trending K-Dramas"""
    status_msg = await message.reply("🔥 Fetching trending K-Dramas...")
    
    # You can integrate with APIs like TMDB, MyDramaList, etc.
    trending_list = """🔥 <b>Trending K-Dramas This Week</b>

🥇 <b>Squid Game Season 2</b>
   📺 Episodes: 7 | ⭐ 9.2/10
   🔗 Search: <code>/kdrama Squid Game</code>

🥈 <b>Kingdom: Legendary War</b>
   📺 Episodes: 12 | ⭐ 8.9/10
   🔗 Search: <code>/kdrama Kingdom</code>

🥉 <b>Hometown's Embrace</b>
   📺 Episodes: 16 | ⭐ 8.7/10
   🔗 Search: <code>/kdrama Hometown Embrace</code>

💡 <b>Tip:</b> Use <code>/kdrama [title]</code> to get detailed info about any drama!"""
    
    btn = [
        [
            InlineKeyboardButton("🔍 Search K-Drama", callback_data="search_kdrama"),
            InlineKeyboardButton("📱 Drama APIs", callback_data="drama_apis")
        ]
    ]
    
    await status_msg.edit(trending_list, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_message(filters.command("match"))
async def smart_match(client, message):
    """Smart matching for drama requests"""
    if not message.reply_to_message:
        await message.reply("Reply to a user's drama request to use smart matching.")
        return
    
    request_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    
    # Analyze the request
    info = extract_kdrama_info(request_text)
    
    match_results = f"🎯 <b>Smart Match Results</b>\n\n"
    match_results += f"📝 <b>Request:</b> {request_text[:100]}...\n\n"
    
    if info['is_kdrama']:
        match_results += "✅ <b>Drama Type:</b> K-Drama detected\n"
        
        suggestions = []
        if info['episode']:
            suggestions.append(f"Episode {info['episode']}")
        if info['quality']:
            suggestions.append(info['quality'])
        if info['subtitle']:
            suggestions.append(info['subtitle'])
        
        if suggestions:
            match_results += f"🔍 <b>Matching criteria:</b> {', '.join(suggestions)}\n"
        
        # Generate search buttons
        btn = [
            [
                InlineKeyboardButton("🔍 Search in Database", callback_data=f"search_db#{request_text[:20]}"),
                InlineKeyboardButton("📊 Get Info", callback_data=f"drama_info#{request_text[:20]}")
            ]
        ]
        
        await message.reply(match_results, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    else:
        match_results += "❌ <b>Drama Type:</b> Not a K-Drama request\n"
        await message.reply(match_results, parse_mode=enums.ParseMode.HTML)

@Client.on_callback_query(filters.regex('^episodes#'))
async def episodes_callback(bot: Client, query: CallbackQuery):
    """Handle episode search callback"""
    _, drama_id, title = query.data.split('#')
    
    episodes_text = f"📺 <b>Episodes for: {title}</b>\n\n"
    episodes_text += "🔍 <b>Search in your database using these keywords:</b>\n"
    episodes_text += f"• <code>{title} episode</code>\n"
    episodes_text += f"• <code>{title} ep</code>\n"
    episodes_text += f"• <code>{title} hindi dubbed</code>\n"
    episodes_text += f"• <code>{title} eng sub</code>\n\n"
    episodes_text += "💡 <b>Tip:</b> Try different episode numbers like 'episode 1', 'episode 2', etc."
    
    btn = [
        [
            InlineKeyboardButton("🔙 Back to Drama Info", callback_data=f"drama_back#{drama_id}"),
            InlineKeyboardButton("🗑 Close", callback_data="close_data")
        ]
    ]
    
    await query.message.edit(episodes_text, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_callback_query(filters.regex('^search_kdrama'))
async def search_kdrama_callback(bot: Client, query: CallbackQuery):
    """Handle search K-Drama callback"""
    search_help = """🔍 <b>How to Search K-Dramas</b>

<b>Available Commands:</b>
• <code>/kdrama [title]</code> - Search drama info
• <code>/analyze [filename]</code> - Analyze file for matching
• <code>/match</code> - Smart match (reply to request)
• <code>/trending</code> - Get trending dramas

<b>Search Examples:</b>
• <code>/kdrama Squid Game</code>
• <code>/kdrama Hometown Embrace</code>
• <code>/analyze Squid.Game.S01E01.Hindi.1080p.mkv</code>

<b>Smart Matching:</b>
Reply to any drama request with <code>/match</code> to get intelligent suggestions for your autofilter bot."""
    
    await query.message.edit(search_help, parse_mode=enums.ParseMode.HTML)

@Client.on_callback_query(filters.regex('^drama_apis'))
async def drama_apis_callback(bot: Client, query: CallbackQuery):
    """Show available drama APIs"""
    apis_info = """🔌 <b>Available K-Drama APIs</b>

<b>Integrated APIs:</b>
• 🎬 <b>TMDB Korean TV</b> - Detailed drama info
• 📺 <b>TVMaze Korean Shows</b> - Episode information
• 🎭 <b>MyDramaList</b> - Community ratings

<b>Features:</b>
✅ Drama search and information
✅ Episode tracking
✅ Ratings and reviews
✅ Cast and crew details
✅ Poster and images

<b>Setup:</b>
Add your TMDB API key to environment:
<code>TMDB_API_KEY=your_api_key_here</code>"""
    
    btn = [
        [
            InlineKeyboardButton("🔙 Back to Trending", callback_data="trending_back"),
            InlineKeyboardButton("🗑 Close", callback_data="close_data")
        ]
    ]
    
    await query.message.edit(apis_info, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_callback_query(filters.regex('^close_data'))
async def close_callback(bot: Client, query: CallbackQuery):
    await query.message.delete()
    await query.answer("Closed!")
