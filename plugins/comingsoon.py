import asyncio
import aiohttp
import datetime
import json
import os
from typing import List, Dict, Optional, Tuple
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.enums import ParseMode
import logging
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from functools import wraps
import hashlib
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TMDB_API_KEY = "90dde61a7cf8339a2cff5d805d5597a9"
DEFAULT_POSTER = "https://via.placeholder.com/500x750/1a1a2e/eee?text=K-Drama"

# Database configuration
DATABASE_NAME = "pastppr"
DATABASE_URI = "mongodb+srv://kdramabot:Buo0fRGenkOAkgXH@pastppr.ipuyepp.mongodb.net/?retryWrites=true&w=majority&appName=pastppr"

# Redis configuration for caching
REDIS_URL = os.getenv("REDIS_URL", "redis://default:tfuIDVsvS9mOs65slDUY8uQJvkUygiX7@redis-19856.c11.us-east-1-2.ec2.redns.redis-cloud.com:19856")

# Cache settings
CACHE_TTL = {
    'drama_list': 3600,  # 1 hour
    'drama_details': 7200,  # 2 hours
    'trailer': 86400,  # 24 hours
    'image_validation': 1800,  # 30 minutes
}

# Initialize clients
mongo_client = AsyncIOMotorClient(DATABASE_URI)
db = mongo_client[DATABASE_NAME]
reminders_collection = db.reminders

# Redis client (will be initialized in main)
redis_client = None

# Connection pools and session management
class APIManager:
    def __init__(self):
        self.session = None
        self.connector = None
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            # Create connector with connection pooling
            self.connector = aiohttp.TCPConnector(
                limit=100,  # Total connection pool
                limit_per_host=30,  # Per host limit
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=timeout,
                headers={'User-Agent': 'K-Drama-Bot/1.0'}
            )
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        if self.connector:
            await self.connector.close()

api_manager = APIManager()

# Caching decorator
def cache_result(cache_key_prefix: str, ttl: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_data = f"{cache_key_prefix}_{str(args)}_{str(kwargs)}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try to get from cache
            if redis_client:
                try:
                    cached = await redis_client.get(cache_key)
                    if cached:
                        return json.loads(cached)
                except Exception as e:
                    logger.warning(f"Redis get error: {e}")
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            if redis_client and result:
                try:
                    await redis_client.setex(
                        cache_key, 
                        ttl, 
                        json.dumps(result, default=str)
                    )
                except Exception as e:
                    logger.warning(f"Redis set error: {e}")
            
            return result
        return wrapper
    return decorator

# Batch operations for database
class BatchOperations:
    def __init__(self, collection, batch_size=100):
        self.collection = collection
        self.batch_size = batch_size
        self.operations = []
    
    def add_operation(self, operation):
        self.operations.append(operation)
        if len(self.operations) >= self.batch_size:
            return self.execute()
        return None
    
    async def execute(self):
        if not self.operations:
            return None
        
        try:
            result = await self.collection.bulk_write(self.operations)
            self.operations.clear()
            return result
        except Exception as e:
            logger.error(f"Batch operation error: {e}")
            self.operations.clear()
            return None

# Optimized database functions with connection pooling
async def add_reminder(user_id: str, drama_id: str, drama_title: str) -> bool:
    """Add a reminder for a user with upsert optimization"""
    try:
        await reminders_collection.update_one(
            {"user_id": user_id, "drama_id": drama_id},
            {
                "$set": {
                    "user_id": user_id,
                    "drama_id": drama_id,
                    "drama_title": drama_title,
                    "created_at": datetime.datetime.utcnow()
                }
            },
            upsert=True
        )
        
        # Invalidate user reminders cache
        if redis_client:
            cache_key = hashlib.md5(f"user_reminders_{user_id}".encode()).hexdigest()
            await redis_client.delete(cache_key)
        
        return True
    except Exception as e:
        logger.error(f"Error adding reminder: {e}")
        return False

async def remove_reminder(user_id: str, drama_id: str) -> bool:
    """Remove a reminder for a user"""
    try:
        result = await reminders_collection.delete_one(
            {"user_id": user_id, "drama_id": drama_id}
        )
        
        # Invalidate user reminders cache
        if redis_client:
            cache_key = hashlib.md5(f"user_reminders_{user_id}".encode()).hexdigest()
            await redis_client.delete(cache_key)
        
        return result.deleted_count > 0
    except Exception as e:
        logger.error(f"Error removing reminder: {e}")
        return False

@cache_result("user_reminders", CACHE_TTL['drama_details'])
async def get_user_reminders(user_id: str) -> List[Dict]:
    """Get all reminders for a user with caching"""
    try:
        cursor = reminders_collection.find(
            {"user_id": user_id},
            {"_id": 0}  # Exclude _id field
        )
        reminders = await cursor.to_list(length=None)
        return reminders
    except Exception as e:
        logger.error(f"Error getting user reminders: {e}")
        return []

async def has_reminder(user_id: str, drama_id: str) -> bool:
    """Check if user has a reminder for a specific drama - optimized"""
    try:
        # Use projection to only get _id field for existence check
        reminder = await reminders_collection.find_one(
            {"user_id": user_id, "drama_id": drama_id},
            {"_id": 1}
        )
        return reminder is not None
    except Exception as e:
        logger.error(f"Error checking reminder: {e}")
        return False

@cache_result("all_reminders", CACHE_TTL['drama_details'])
async def get_all_reminders() -> List[Dict]:
    """Get all reminders from database with caching"""
    try:
        cursor = reminders_collection.find({}, {"_id": 0})
        reminders = await cursor.to_list(length=None)
        return reminders
    except Exception as e:
        logger.error(f"Error getting all reminders: {e}")
        return []

@cache_result("drama_reminders", CACHE_TTL['drama_details'])
async def get_reminders_by_drama(drama_id: str) -> List[Dict]:
    """Get all users who have reminders for a specific drama"""
    try:
        cursor = reminders_collection.find(
            {"drama_id": drama_id},
            {"_id": 0}
        )
        reminders = await cursor.to_list(length=None)
        return reminders
    except Exception as e:
        logger.error(f"Error getting reminders by drama: {e}")
        return []

@cache_result("image_validation", CACHE_TTL['image_validation'])
async def is_valid_image_url(url: str) -> bool:
    """Check if an image URL is accessible with async request"""
    if not url:
        return False
    
    try:
        session = await api_manager.get_session()
        async with session.head(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
            return (response.status == 200 and 
                   'image' in response.headers.get('content-type', ''))
    except Exception as e:
        logger.warning(f"Image validation error for {url}: {e}")
        return False

@cache_result("coming_soon", CACHE_TTL['drama_list'])
async def get_coming_soon(page=1) -> List[Dict]:
    """Fetch upcoming Korean dramas from TMDB with async requests"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    url = (
        f"https://api.themoviedb.org/3/discover/tv"
        f"?api_key={TMDB_API_KEY}"
        f"&with_origin_country=KR"
        f"&sort_by=first_air_date.asc"
        f"&first_air_date.gte={today}"
        f"&language=en-US&page={page}"
    )
    
    try:
        session = await api_manager.get_session()
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
    except Exception as e:
        logger.error(f"Error fetching dramas: {e}")
        return []
    
    dramas = []
    for item in data.get("results", []):
        drama = {
            "id": item["id"],
            "title": item["name"],
            "release_date": item.get("first_air_date", "TBA"),
            "overview": item.get("overview", "No description available."),
            "poster": f"https://image.tmdb.org/t/p/w500{item['poster_path']}" if item.get("poster_path") else DEFAULT_POSTER,
            "vote_average": item.get("vote_average", 0),
            "genre_ids": item.get("genre_ids", [])
        }
        dramas.append(drama)
    
    return dramas

@cache_result("drama_details", CACHE_TTL['drama_details'])
async def get_drama_details(drama_id: str) -> Optional[Dict]:
    """Get detailed information about a specific drama with caching"""
    url = f"https://api.themoviedb.org/3/tv/{drama_id}?api_key={TMDB_API_KEY}&language=en-US"
    
    try:
        session = await api_manager.get_session()
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
    except Exception as e:
        logger.error(f"Error fetching drama details: {e}")
        return None
    
    drama = {
        "id": data["id"],
        "title": data["name"],
        "release_date": data.get("first_air_date", "TBA"),
        "overview": data.get("overview", "No description available."),
        "poster": f"https://image.tmdb.org/t/p/w500{data['poster_path']}" if data.get("poster_path") else DEFAULT_POSTER,
        "vote_average": data.get("vote_average", 0),
        "genres": [g["name"] for g in data.get("genres", [])],
        "networks": [n["name"] for n in data.get("networks", [])],
        "status": data.get("status", "Unknown")
    }
    
    return drama

@cache_result("trailer", CACHE_TTL['trailer'])
async def get_trailer(tv_id: str) -> Optional[str]:
    """Get YouTube trailer link for a drama with caching"""
    url = f"https://api.themoviedb.org/3/tv/{tv_id}/videos?api_key={TMDB_API_KEY}&language=en-US"
    
    try:
        session = await api_manager.get_session()
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
    except Exception as e:
        logger.error(f"Error fetching trailer: {e}")
        return None
    
    for video in data.get("results", []):
        if video["site"] == "YouTube" and video["type"] == "Trailer":
            return f"https://youtu.be/{video['key']}"
    return None

def calculate_days_left(release_date: str) -> str:
    """Calculate days until release - optimized"""
    if release_date == "TBA":
        return ""
    
    try:
        rd = datetime.datetime.strptime(release_date, "%Y-%m-%d").date()
        diff = (rd - datetime.date.today()).days
        if diff > 0:
            return f"\n⏳ {diff} days left!"
        elif diff == 0:
            return f"\n🎉 Releases today!"
        else:
            return f"\n📺 Released {abs(diff)} days ago"
    except ValueError:
        return ""

# Rate limiting decorator
def rate_limit(max_calls: int, window: int):
    def decorator(func):
        calls = {}
        
        @wraps(func)
        async def wrapper(client, message_or_query):
            user_id = message_or_query.from_user.id
            now = time.time()
            
            # Clean old entries
            calls[user_id] = [call_time for call_time in calls.get(user_id, []) 
                            if now - call_time < window]
            
            if len(calls.get(user_id, [])) >= max_calls:
                if hasattr(message_or_query, 'answer'):
                    await message_or_query.answer("⏳ Please wait before making another request", show_alert=True)
                else:
                    await message_or_query.reply_text("⏳ Please wait before making another request")
                return
            
            calls.setdefault(user_id, []).append(now)
            return await func(client, message_or_query)
        
        return wrapper
    return decorator

# Optimized handlers with rate limiting
@Client.on_message(filters.command(["comingsoon", "upcoming"]))
@rate_limit(max_calls=3, window=60)  # 3 calls per minute
async def comingsoon_list(client, message):
    """Show list of upcoming K-dramas with optimizations"""
    try:
        # Use asyncio.gather for concurrent operations if needed
        dramas = await get_coming_soon()
        if not dramas:
            await message.reply_text("🌸 No upcoming K-Dramas found at the moment!")
            return
        
        buttons = []
        for drama in dramas[:15]:  # Show first 15 dramas
            title = drama["title"]
            if len(title) > 30:  # Truncate long titles
                title = title[:27] + "..."
            
            # Add rating emoji if available
            rating = drama.get("vote_average", 0)
            if rating >= 8:
                title = f"⭐ {title}"
            elif rating >= 7:
                title = f"✨ {title}"
            
            buttons.append([InlineKeyboardButton(title, callback_data=f"drama_{drama['id']}")])
        
        # Add navigation buttons
        nav_buttons = [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_list"),
            InlineKeyboardButton("📋 My Reminders", callback_data="show_reminders")
        ]
        buttons.append(nav_buttons)
        
        await message.reply_text(
            "🎬 <b>Upcoming K-Dramas</b>\n\n"
            "Click on a drama to see detailed information, trailers, and set reminders!",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in comingsoon_list: {e}")
        await message.reply_text("❌ Sorry, there was an error fetching the drama list. Please try again later.")

@Client.on_callback_query(filters.regex(r"^drama_"))
@rate_limit(max_calls=5, window=60)  # 5 calls per minute
async def drama_details(client, query):
    """Show detailed drama information with optimizations"""
    drama_id = query.data.split("_")[1]
    user_id = str(query.from_user.id)
    
    try:
        # Concurrent API calls
        tasks = [
            get_drama_details(drama_id),
            get_trailer(drama_id),
            has_reminder(user_id, drama_id)
        ]
        
        drama_data, trailer, is_reminded = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        if isinstance(drama_data, Exception) or not drama_data:
            await query.answer("❌ Drama not found!", show_alert=True)
            return
        
        if isinstance(trailer, Exception):
            trailer = None
        
        if isinstance(is_reminded, Exception):
            is_reminded = False
        
        release_date = drama_data.get("release_date", "TBA")
        days_left = calculate_days_left(release_date)
        
        # Build caption with detailed information
        caption = f"🎬 <b>{drama_data['title']}</b>\n"
        caption += f"📅 Release Date: {release_date}{days_left}\n"
        
        if drama_data.get("vote_average", 0) > 0:
            caption += f"⭐ Rating: {drama_data['vote_average']:.1f}/10\n"
        
        if drama_data.get("genres"):
            caption += f"🎭 Genres: {', '.join(drama_data['genres'])}\n"
        
        if drama_data.get("networks"):
            caption += f"📺 Networks: {', '.join(drama_data['networks'])}\n"
        
        if drama_data.get("status"):
            caption += f"📊 Status: {drama_data['status']}\n"
        
        caption += f"\n✨ <i>{drama_data['overview']}</i>"
        
        # Build buttons
        buttons = []
        if trailer:
            buttons.append([InlineKeyboardButton("▶️ Watch Trailer", url=trailer)])
        
        if is_reminded:
            buttons.append([InlineKeyboardButton("🔕 Remove Reminder", callback_data=f"unremind_{drama_id}")])
        else:
            buttons.append([InlineKeyboardButton("🔔 Set Reminder", callback_data=f"remind_{drama_id}")])
        
        buttons.append([InlineKeyboardButton("⬅️ Back to List", callback_data="refresh_list")])
        
        # Use poster if available
        photo_url = drama_data.get("poster") or DEFAULT_POSTER
        
        # Optimized message editing
        try:
            if query.message.photo:
                await query.message.edit_media(
                    media=InputMediaPhoto(photo_url, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                new_message = await client.send_photo(
                    chat_id=query.message.chat.id,
                    photo=photo_url,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML
                )
                try:
                    await query.message.delete()
                except:
                    pass
        
        except Exception as photo_error:
            logger.error(f"Error with photo, falling back to text: {photo_error}")
            caption_with_link = f"🖼️ [View Poster]({photo_url})\n\n{caption}"
            try:
                await query.message.edit_text(
                    caption_with_link,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False
                )
            except Exception as text_error:
                logger.error(f"Text fallback failed: {text_error}")
                await client.send_message(
                    chat_id=query.message.chat.id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML
                )
        
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error in drama_details: {e}")
        await query.answer("❌ Error loading drama details!", show_alert=True)

# Initialize Redis connection
async def init_redis():
    global redis_client
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Continuing without cache.")
        redis_client = None

# Cleanup function
async def cleanup():
    """Cleanup connections on shutdown"""
    await api_manager.close()
    if redis_client:
        await redis_client.close()
    mongo_client.close()

# Initialize connections
async def init_connections():
    await init_redis()

# Reminder notification system
async def check_and_send_reminders(client):
    """Check for dramas releasing today and send reminders"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    logger.info(f"Checking reminders for {today}")
    
    try:
        # Get all unique drama IDs from reminders
        drama_ids = await reminders_collection.distinct("drama_id")
        
        released_today = []
        
        # Check each drama's release date
        for drama_id in drama_ids:
            try:
                drama_data = await get_drama_details(str(drama_id))
                if drama_data and drama_data.get("release_date") == today:
                    released_today.append(drama_data)
            except Exception as e:
                logger.error(f"Error checking drama {drama_id}: {e}")
                continue
        
        # Send notifications for dramas releasing today
        for drama in released_today:
            await send_release_notifications(client, drama)
            
        logger.info(f"Processed {len(released_today)} dramas releasing today")
        
    except Exception as e:
        logger.error(f"Error in check_and_send_reminders: {e}")

async def send_release_notifications(client, drama_data: Dict):
    """Send notification to all users who have reminders for this drama"""
    drama_id = str(drama_data["id"])
    drama_title = drama_data["title"]
    
    try:
        # Get all users with reminders for this drama
        reminders = await get_reminders_by_drama(drama_id)
        
        if not reminders:
            return
        
        # Get trailer link
        trailer = await get_trailer(drama_id)
        
        # Build notification message
        message = f"🎉 <b>{drama_title}</b> is releasing TODAY!\n\n"
        message += f"📅 Release Date: {drama_data.get('release_date', 'Today')}\n"
        
        if drama_data.get("vote_average", 0) > 0:
            message += f"⭐ Rating: {drama_data['vote_average']:.1f}/10\n"
        
        if drama_data.get("genres"):
            message += f"🎭 Genres: {', '.join(drama_data['genres'])}\n"
        
        if drama_data.get("networks"):
            message += f"📺 Available on: {', '.join(drama_data['networks'])}\n"
        
        message += f"\n✨ <i>{drama_data.get('overview', 'No description available.')}</i>"
        
        # Build buttons
        buttons = []
        if trailer:
            buttons.append([InlineKeyboardButton("▶️ Watch Trailer", url=trailer)])
        
        buttons.append([
            InlineKeyboardButton("📋 View Details", callback_data=f"drama_{drama_id}"),
            InlineKeyboardButton("🔕 Remove Reminder", callback_data=f"unremind_{drama_id}")
        ])
        
        # Send to all users with reminders
        successful_sends = 0
        failed_sends = 0
        
        for reminder in reminders:
            user_id = reminder["user_id"]
            try:
                # Try to send with photo first
                try:
                    await client.send_photo(
                        chat_id=int(user_id),
                        photo=drama_data.get("poster") or DEFAULT_POSTER,
                        caption=message,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    # Fallback to text message
                    await client.send_message(
                        chat_id=int(user_id),
                        text=message,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=ParseMode.HTML
                    )
                
                successful_sends += 1
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed to send reminder to user {user_id}: {e}")
                failed_sends += 1
                
                # If user blocked bot or deleted account, remove their reminders
                if "bot was blocked" in str(e).lower() or "user not found" in str(e).lower():
                    try:
                        await reminders_collection.delete_many({"user_id": user_id})
                        logger.info(f"Removed all reminders for inactive user {user_id}")
                    except Exception as cleanup_error:
                        logger.error(f"Error cleaning up user {user_id}: {cleanup_error}")
        
        logger.info(f"Sent {successful_sends} reminders for '{drama_title}', {failed_sends} failed")
        
        # Mark notifications as sent to avoid duplicates
        await mark_drama_notified(drama_id)
        
    except Exception as e:
        logger.error(f"Error sending notifications for drama {drama_id}: {e}")

async def mark_drama_notified(drama_id: str):
    """Mark a drama as having notifications sent"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # Store in a separate collection to track sent notifications
    notifications_collection = db.sent_notifications
    
    try:
        await notifications_collection.update_one(
            {"drama_id": drama_id, "date": today},
            {
                "$set": {
                    "drama_id": drama_id,
                    "date": today,
                    "sent_at": datetime.datetime.utcnow()
                }
            },
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error marking drama as notified: {e}")

async def was_drama_notified_today(drama_id: str) -> bool:
    """Check if notifications were already sent for this drama today"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    notifications_collection = db.sent_notifications
    
    try:
        result = await notifications_collection.find_one({
            "drama_id": drama_id,
            "date": today
        })
        return result is not None
    except Exception as e:
        logger.error(f"Error checking if drama was notified: {e}")
        return False

# Background task scheduler
async def reminder_scheduler(client):
    """Background task to check for reminders periodically"""
    logger.info("Starting reminder scheduler")
    
    while True:
        try:
            current_time = datetime.datetime.now()
            
            # Run reminder check at 9 AM and 6 PM local time
            if current_time.hour in [9, 18] and current_time.minute == 0:
                await check_and_send_reminders(client)
            
            # Sleep for 1 minute before next check
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in reminder scheduler: {e}")
            # Wait 5 minutes before retrying on error
            await asyncio.sleep(300)

# Weekly digest system
async def send_weekly_digest(client):
    """Send weekly upcoming dramas digest to active users"""
    try:
        # Get dramas releasing in the next week
        today = datetime.date.today()
        next_week = today + datetime.timedelta(days=7)
        
        dramas_this_week = []
        
        # Check multiple pages for comprehensive results
        for page in range(1, 4):  # Check first 3 pages
            dramas = await get_coming_soon(page)
            if not dramas:
                break
                
            for drama in dramas:
                try:
                    release_date = datetime.datetime.strptime(drama["release_date"], "%Y-%m-%d").date()
                    if today <= release_date <= next_week:
                        dramas_this_week.append(drama)
                except ValueError:
                    continue
        
        if not dramas_this_week:
            return
        
        # Sort by release date
        dramas_this_week.sort(key=lambda x: x.get("release_date", "9999-12-31"))
        
        # Build digest message
        digest_message = "📅 <b>This Week's K-Drama Releases</b>\n\n"
        
        for drama in dramas_this_week[:10]:  # Limit to 10 dramas
            title = drama["title"]
            release_date = drama.get("release_date", "TBA")
            rating = drama.get("vote_average", 0)
            
            digest_message += f"🎬 <b>{title}</b>\n"
            digest_message += f"📅 {release_date}"
            
            if rating > 0:
                digest_message += f" • ⭐ {rating:.1f}/10"
            
            digest_message += "\n\n"
        
        digest_message += "Use /comingsoon to set reminders! 🔔"
        
        # Get all active users (users with reminders)
        active_users = await reminders_collection.distinct("user_id")
        
        # Send digest to active users
        for user_id in active_users:
            try:
                await client.send_message(
                    chat_id=int(user_id),
                    text=digest_message,
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(0.2)  # Rate limiting
            except Exception as e:
                logger.error(f"Failed to send digest to user {user_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in send_weekly_digest: {e}")

# Enhanced handlers with reminder functionality

@Client.on_callback_query(filters.regex(r"^remind_"))
@rate_limit(max_calls=5, window=60)
async def set_reminder(client, query):
    """Set reminder for a drama"""
    drama_id = query.data.split("_")[1]
    user_id = str(query.from_user.id)
    
    try:
        drama_data = await get_drama_details(drama_id)
        drama_title = drama_data["title"] if drama_data else f"Drama {drama_id}"
        
        success = await add_reminder(user_id, drama_id, drama_title)
        
        if success:
            # Check if drama releases today
            if drama_data and drama_data.get("release_date") == datetime.date.today().strftime("%Y-%m-%d"):
                await query.answer(f"🎉 '{drama_title}' releases TODAY! Reminder set!", show_alert=True)
            else:
                await query.answer(f"🔔 Reminder set for '{drama_title}'!", show_alert=True)
            
            # Update the button to show reminder is set
            await drama_details(client, query)
        else:
            await query.answer("❌ Error setting reminder!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error setting reminder: {e}")
        await query.answer("❌ Error setting reminder!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^unremind_"))
@rate_limit(max_calls=5, window=60)
async def remove_user_reminder(client, query):
    """Remove reminder for a drama"""
    drama_id = query.data.split("_")[1]
    user_id = str(query.from_user.id)
    
    try:
        drama_data = await get_drama_details(drama_id)
        drama_title = drama_data["title"] if drama_data else f"Drama {drama_id}"
        
        success = await remove_reminder(user_id, drama_id)
        
        if success:
            await query.answer(f"🔕 Reminder removed for '{drama_title}'!", show_alert=True)
        else:
            await query.answer(f"🔕 Reminder removed for '{drama_title}'!", show_alert=True)
        
        # Update the button to show reminder is removed
        await drama_details(client, query)
        
    except Exception as e:
        logger.error(f"Error removing reminder: {e}")
        await query.answer("❌ Error removing reminder!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^refresh_list$"))
@rate_limit(max_calls=3, window=60)
async def refresh_list(client, query):
    """Refresh the drama list"""
    # Clear cache to get fresh data
    if redis_client:
        try:
            await redis_client.flushpattern("coming_soon_*")
        except Exception as e:
            logger.warning(f"Error clearing cache: {e}")
    
    try:
        dramas = await get_coming_soon()
        if not dramas:
            await query.answer("🌸 No upcoming K-Dramas found!", show_alert=True)
            return
        
        buttons = []
        for drama in dramas[:15]:
            title = drama["title"]
            if len(title) > 30:
                title = title[:27] + "..."
            
            rating = drama.get("vote_average", 0)
            if rating >= 8:
                title = f"⭐ {title}"
            elif rating >= 7:
                title = f"✨ {title}"
            
            buttons.append([InlineKeyboardButton(title, callback_data=f"drama_{drama['id']}")])
        
        nav_buttons = [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_list"),
            InlineKeyboardButton("📋 My Reminders", callback_data="show_reminders")
        ]
        buttons.append(nav_buttons)
        
        await query.message.edit_text(
            "🎬 <b>Upcoming K-Dramas</b>\n\n"
            "Click on a drama to see detailed information, trailers, and set reminders!",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        await query.answer("✅ List refreshed!")
        
    except Exception as e:
        logger.error(f"Error refreshing list: {e}")
        await query.answer("❌ Error refreshing list!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^show_reminders$"))
@rate_limit(max_calls=3, window=60)
async def show_user_reminders(client, query):
    """Show user's reminders"""
    user_id = str(query.from_user.id)
    
    try:
        reminders = await get_user_reminders(user_id)
        
        if not reminders:
            await query.answer("📋 You have no reminders set!", show_alert=True)
            return
        
        buttons = []
        for reminder in reminders:
            drama_id = reminder["drama_id"]
            drama_title = reminder.get("drama_title", f"Drama {drama_id}")
            
            if len(drama_title) > 30:
                drama_title = drama_title[:27] + "..."
            
            buttons.append([InlineKeyboardButton(f"🔔 {drama_title}", callback_data=f"drama_{drama_id}")])
        
        buttons.append([InlineKeyboardButton("⬅️ Back to List", callback_data="refresh_list")])
        
        await query.message.edit_text(
            f"📋 <b>Your Reminders ({len(reminders)})</b>\n\n"
            "Click on a drama to view details or manage your reminder:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error showing reminders: {e}")
        await query.answer("❌ Error loading reminders!", show_alert=True)

# Manual reminder check command (for testing)
@Client.on_message(filters.command(["checkreminders"]))
async def manual_reminder_check(client, message):
    """Manually trigger reminder check (admin/testing)"""
    try:
        await message.reply_text("🔄 Checking for drama reminders...")
        await check_and_send_reminders(client)
        await message.reply_text("✅ Reminder check completed!")
    except Exception as e:
        logger.error(f"Error in manual reminder check: {e}")
        await message.reply_text("❌ Error checking reminders!")

@Client.on_message(filters.command(["comehelp"]))
async def help_command(client, message):
    """Show help information"""
    help_text = (
        "🎬 <b>K-Drama Bot Commands</b>\n\n"
        "🔸 /comingsoon or /upcoming - Show upcoming K-Dramas\n"
        "🔸 /help or /start - Show this help message\n\n"
        "<b>Features:</b>\n"
        "• View upcoming Korean dramas with release dates\n"
        "• Watch trailers directly from the bot\n"
        "• Set reminders for dramas you're interested in\n"
        "• Get automatic notifications on release day! 🔔\n"
        "• See ratings, genres, and detailed information\n"
        "• Navigate easily with interactive buttons\n\n"
        "<b>🔔 Reminder System:</b>\n"
        "• Get notified when your dramas release\n"
        "• Notifications sent twice daily (9 AM & 6 PM)\n"
        "• Weekly digest of upcoming releases\n\n"
        "Just use /comingsoon to get started! 🌟"
    )
    
    await message.reply_text(help_text, parse_mode=ParseMode.HTML)

# Initialize the bot with background tasks
async def start_bot(app: Client):
    """Start the bot and background tasks"""
    await init_connections()
    
    # Start background scheduler
    asyncio.create_task(reminder_scheduler(app))
    
    logger.info("Bot started with reminder system!")

# Shutdown handler
async def stop_bot():
    """Cleanup when bot stops"""
    await cleanup()
    logger.info("Bot stopped and cleaned up!")

# Add these to your main bot initialization:
# app.on_startup(start_bot)
# app.on_shutdown(stop_bot)
