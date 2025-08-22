import requests
import datetime
import json
import os
from typing import List, Dict, Optional
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.enums import ParseMode
import logging
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TMDB_API_KEY = "90dde61a7cf8339a2cff5d805d5597a9"
DEFAULT_POSTER = "https://via.placeholder.com/500x750/1a1a2e/eee?text=K-Drama"

# Database configuration
DATABASE_NAME = "pastppr"
DATABASE_URI = "mongodb+srv://kdramabot:Buo0fRGenkOAkgXH@pastppr.ipuyepp.mongodb.net/?retryWrites=true&w=majority&appName=pastppr"

# Initialize MongoDB client
mongo_client = AsyncIOMotorClient(DATABASE_URI)
db = mongo_client[DATABASE_NAME]
reminders_collection = db.reminders
viewing_sessions_collection = db.viewing_sessions
user_stats_collection = db.user_stats

# Cache for drama data to avoid repeated API calls
drama_cache = {}

# Initialize timezone
TIMEZONE = pytz.timezone('UTC')

async def add_reminder(user_id: str, drama_id: str, drama_title: str) -> bool:
    """Add a reminder for a user"""
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
        return result.deleted_count > 0
    except Exception as e:
        logger.error(f"Error removing reminder: {e}")
        return False

async def get_user_reminders(user_id: str) -> List[Dict]:
    """Get all reminders for a user"""
    try:
        cursor = reminders_collection.find({"user_id": user_id})
        reminders = await cursor.to_list(length=None)
        return reminders
    except Exception as e:
        logger.error(f"Error getting user reminders: {e}")
        return []

async def has_reminder(user_id: str, drama_id: str) -> bool:
    """Check if user has a reminder for a specific drama"""
    try:
        reminder = await reminders_collection.find_one(
            {"user_id": user_id, "drama_id": drama_id}
        )
        return reminder is not None
    except Exception as e:
        logger.error(f"Error checking reminder: {e}")
        return False

async def get_all_reminders() -> List[Dict]:
    """Get all reminders from database for notification purposes"""
    try:
        cursor = reminders_collection.find({})
        reminders = await cursor.to_list(length=None)
        return reminders
    except Exception as e:
        logger.error(f"Error getting all reminders: {e}")
        return []

async def get_reminders_by_drama(drama_id: str) -> List[Dict]:
    """Get all users who have reminders for a specific drama"""
    try:
        cursor = reminders_collection.find({"drama_id": drama_id})
        reminders = await cursor.to_list(length=None)
        return reminders
    except Exception as e:
        logger.error(f"Error getting reminders by drama: {e}")
        return []

# Watch time tracking functions
async def start_viewing_session(user_id: str, username: str, drama_id: str, drama_title: str) -> bool:
    """Start a new viewing session"""
    try:
        # Check if user already has an active session
        active_session = await viewing_sessions_collection.find_one({
            "user_id": user_id,
            "end_time": None
        })
        
        if active_session:
            return False
        
        # Create new session
        await viewing_sessions_collection.insert_one({
            "user_id": user_id,
            "username": username,
            "drama_id": drama_id,
            "drama_title": drama_title,
            "start_time": datetime.datetime.utcnow(),
            "end_time": None,
            "duration_minutes": None
        })
        
        # Update user stats
        await user_stats_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "username": username,
                    "timezone": "UTC"
                },
                "$inc": {
                    "total_sessions": 1
                }
            },
            upsert=True
        )
        
        return True
    except Exception as e:
        logger.error(f"Error starting viewing session: {e}")
        return False

async def end_viewing_session(user_id: str) -> Optional[Dict]:
    """End the current viewing session and return session details"""
    try:
        # Find active session
        session = await viewing_sessions_collection.find_one({
            "user_id": user_id,
            "end_time": None
        })
        
        if not session:
            return None
        
        # Calculate duration
        start_time = session["start_time"]
        end_time = datetime.datetime.utcnow()
        duration = int((end_time - start_time).total_seconds() / 60)
        
        # Update session
        await viewing_sessions_collection.update_one(
            {"_id": session["_id"]},
            {
                "$set": {
                    "end_time": end_time,
                    "duration_minutes": duration
                }
            }
        )
        
        # Update user stats
        await user_stats_collection.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "total_minutes": duration,
                    "dramas_watched": 1
                },
                "$set": {
                    "last_session": end_time
                }
            }
        )
        
        return {
            "drama_id": session["drama_id"],
            "drama_title": session["drama_title"],
            "duration": duration,
            "start_time": start_time,
            "end_time": end_time
        }
    except Exception as e:
        logger.error(f"Error ending viewing session: {e}")
        return None

async def get_user_viewing_stats(user_id: str) -> Optional[Dict]:
    """Get viewing statistics for a user"""
    try:
        stats = await user_stats_collection.find_one({"user_id": user_id})
        
        if not stats:
            return None
            
        # Calculate additional metrics
        total_minutes = stats.get("total_minutes", 0)
        total_sessions = stats.get("total_sessions", 0)
        dramas_watched = stats.get("dramas_watched", 0)
        
        # Get first session time
        first_session = await viewing_sessions_collection.find_one(
            {"user_id": user_id},
            sort=[("start_time", 1)]
        )
        
        # Calculate days active
        if first_session and "last_session" in stats:
            first_date = first_session["start_time"].date()
            last_date = stats["last_session"].date()
            days_active = (last_date - first_date).days + 1
            daily_avg = total_minutes / days_active if days_active > 0 else 0
        else:
            days_active = 0
            daily_avg = 0
        
        return {
            "total_minutes": total_minutes,
            "total_sessions": total_sessions,
            "dramas_watched": dramas_watched,
            "avg_session": round(total_minutes / total_sessions, 1) if total_sessions > 0 else 0,
            "first_session": first_session["start_time"] if first_session else None,
            "last_session": stats.get("last_session"),
            "days_active": days_active,
            "daily_avg": round(daily_avg, 1),
            "timezone": stats.get("timezone", "UTC")
        }
    except Exception as e:
        logger.error(f"Error getting user viewing stats: {e}")
        return None

async def get_viewing_leaderboard(limit: int = 10) -> List[Dict]:
    """Get top viewers by watch time"""
    try:
        pipeline = [
            {"$sort": {"total_minutes": -1}},
            {"$limit": limit}
        ]
        
        cursor = user_stats_collection.aggregate(pipeline)
        leaderboard = await cursor.to_list(length=limit)
        
        return leaderboard
    except Exception as e:
        logger.error(f"Error getting viewing leaderboard: {e}")
        return []

async def set_user_timezone(user_id: str, timezone: str) -> bool:
    """Set user's timezone for localized reports"""
    try:
        # Validate timezone
        pytz.timezone(timezone)
        
        await user_stats_collection.update_one(
            {"user_id": user_id},
            {"$set": {"timezone": timezone}},
            upsert=True
        )
        return True
    except pytz.UnknownTimeZoneError:
        return False
    except Exception as e:
        logger.error(f"Error setting user timezone: {e}")
        return False

def is_valid_image_url(url: str) -> bool:
    """Check if an image URL is accessible"""
    if not url:
        return False
    try:
        response = requests.head(url, timeout=5)
        return response.status_code == 200 and 'image' in response.headers.get('content-type', '')
    except:
        return False

def get_coming_soon(page=1) -> List[Dict]:
    """Fetch upcoming Korean dramas from TMDB"""
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
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
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
        # Cache the drama data
        drama_cache[str(item["id"])] = drama
    
    return dramas

def get_drama_details(drama_id: str) -> Optional[Dict]:
    """Get detailed information about a specific drama"""
    # Check cache first
    if drama_id in drama_cache:
        return drama_cache[drama_id]
    
    url = f"https://api.themoviedb.org/3/tv/{drama_id}?api_key={TMDB_API_KEY}&language=en-US"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
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
    
    # Cache the drama data
    drama_cache[drama_id] = drama
    return drama

def get_trailer(tv_id: str) -> Optional[str]:
    """Get YouTube trailer link for a drama"""
    url = f"https://api.themoviedb.org/3/tv/{tv_id}/videos?api_key={TMDB_API_KEY}&language=en-US"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching trailer: {e}")
        return None
    
    for video in data.get("results", []):
        if video["site"] == "YouTube" and video["type"] == "Trailer":
            return f"https://youtu.be/{video['key']}"
    return None

def calculate_days_left(release_date: str) -> str:
    """Calculate days until release"""
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

@Client.on_message(filters.command(["comingsoon", "upcoming"]))
async def comingsoon_list(client, message):
    """Show list of upcoming K-dramas"""
    try:
        dramas = get_coming_soon()
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
            InlineKeyboardButton("📋 My Reminders", callback_data="show_reminders"),
            InlineKeyboardButton("📊 My Stats", callback_data="show_stats")
        ]
        buttons.append(nav_buttons)
        
        # Send as text message to avoid image loading issues
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
async def drama_details(client, query):
    """Show detailed drama information"""
    drama_id = query.data.split("_")[1]
    
    try:
        drama_data = get_drama_details(drama_id)
        if not drama_data:
            await query.answer("❌ Drama not found!", show_alert=True)
            return
        
        trailer = get_trailer(drama_id)
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
        
        user_id = str(query.from_user.id)
        is_reminded = await has_reminder(user_id, drama_id)
        
        # Check if user is currently watching this drama
        active_session = await viewing_sessions_collection.find_one({
            "user_id": user_id,
            "drama_id": drama_id,
            "end_time": None
        })
        
        if active_session:
            buttons.append([InlineKeyboardButton("⏹️ Stop Watching", callback_data=f"stopwatch_{drama_id}")])
        else:
            buttons.append([InlineKeyboardButton("▶️ Start Watching", callback_data=f"startwatch_{drama_id}")])
        
        if is_reminded:
            buttons.append([InlineKeyboardButton("🔕 Remove Reminder", callback_data=f"unremind_{drama_id}")])
        else:
            buttons.append([InlineKeyboardButton("🔔 Set Reminder", callback_data=f"remind_{drama_id}")])
        
        buttons.append([InlineKeyboardButton("⬅️ Back to List", callback_data="refresh_list")])
        
        # Use poster if available, otherwise use default image
        photo_url = drama_data.get("poster") or DEFAULT_POSTER
        
        # Try to send photo with drama details
        try:
            if query.message.photo:
                # Edit existing photo message
                await query.message.edit_media(
                    media=InputMediaPhoto(photo_url, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                # Current message is text, so send new photo message and delete old one
                new_message = await client.send_photo(
                    chat_id=query.message.chat.id,
                    photo=photo_url,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML
                )
                # Try to delete the old message
                try:
                    await query.message.delete()
                except:
                    pass  # Ignore if we can't delete
        
        except Exception as photo_error:
            logger.error(f"Error with photo, falling back to text: {photo_error}")
            # Fallback: edit message as text with poster link
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
                # Last resort - send new message
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

@Client.on_callback_query(filters.regex(r"^startwatch_"))
async def start_watching(client, query):
    """Start watching a drama"""
    drama_id = query.data.split("_")[1]
    user_id = str(query.from_user.id)
    username = query.from_user.username or query.from_user.first_name
    
    try:
        drama_data = get_drama_details(drama_id)
        drama_title = drama_data["title"] if drama_data else f"Drama {drama_id}"
        
        success = await start_viewing_session(user_id, username, drama_id, drama_title)
        
        if success:
            await query.answer(f"▶️ Now watching '{drama_title}'!", show_alert=True)
            # Update the button to show watching is active
            await drama_details(client, query)
        else:
            await query.answer("❌ You already have an active viewing session!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error starting watching: {e}")
        await query.answer("❌ Error starting viewing session!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^stopwatch_"))
async def stop_watching(client, query):
    """Stop watching a drama"""
    drama_id = query.data.split("_")[1]
    user_id = str(query.from_user.id)
    
    try:
        session_data = await end_viewing_session(user_id)
        
        if session_data:
            drama_title = session_data["drama_title"]
            duration = session_data["duration"]
            hours = duration // 60
            minutes = duration % 60
            
            await query.answer(
                f"⏹️ Stopped watching '{drama_title}'!\n\n"
                f"⏱️ Session duration: {hours}h {minutes}m", 
                show_alert=True
            )
            # Update the button to show watching is stopped
            await drama_details(client, query)
        else:
            await query.answer("❌ No active viewing session found!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error stopping watching: {e}")
        await query.answer("❌ Error stopping viewing session!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^remind_"))
async def set_reminder(client, query):
    """Set reminder for a drama"""
    drama_id = query.data.split("_")[1]
    user_id = str(query.from_user.id)
    
    try:
        drama_data = get_drama_details(drama_id)
        drama_title = drama_data["title"] if drama_data else f"Drama {drama_id}"
        
        success = await add_reminder(user_id, drama_id, drama_title)
        
        if success:
            await query.answer(f"🔔 Reminder set for '{drama_title}'!", show_alert=True)
            # Update the button to show reminder is set
            await drama_details(client, query)
        else:
            await query.answer("❌ Error setting reminder!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error setting reminder: {e}")
        await query.answer("❌ Error setting reminder!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^unremind_"))
async def remove_user_reminder(client, query):
    """Remove reminder for a drama"""
    drama_id = query.data.split("_")[1]
    user_id = str(query.from_user.id)
    
    try:
        drama_data = get_drama_details(drama_id)
        drama_title = drama_data["title"] if drama_data else f"Drama {drama_id}"
        
        success = await remove_reminder(user_id, drama_id)
        
        if success:
            await query.answer(f"🔕 Reminder removed for '{drama_title}'!", show_alert=True)
        else:
            await query.answer(f"🔕 Reminder removed for '{drama_title}'!", show_alert=True)  # Show success even if not found
        
        # Update the button to show reminder is removed
        await drama_details(client, query)
        
    except Exception as e:
        logger.error(f"Error removing reminder: {e}")
        await query.answer("❌ Error removing reminder!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^refresh_list$"))
async def refresh_list(client, query):
    """Refresh the drama list"""
    # Clear cache to get fresh data
    drama_cache.clear()
    
    try:
        dramas = get_coming_soon()
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
            InlineKeyboardButton("📋 My Reminders", callback_data="show_reminders"),
            InlineKeyboardButton("📊 My Stats", callback_data="show_stats")
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
            
            # Truncate long titles
            if len(drama_title) > 30:
                drama_title = drama_title[:27] + "..."
            
            buttons.append([InlineKeyboardButton(f"🔔 {drama_title}", callback_data=f"drama_{drama_id}")])
        
        buttons.append([InlineKeyboardButton("⬅️ Back to List", callback_data="refresh_list")])
        
        await query.message.edit_text(
            "📋 <b>Your Reminders</b>\n\n"
            "Click on a drama to view details or manage your reminder:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error showing reminders: {e}")
        await query.answer("❌ Error loading reminders!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^show_stats$"))
async def show_user_stats(client, query):
    """Show user's viewing statistics"""
    user_id = str(query.from_user.id)
    
    try:
        stats = await get_user_viewing_stats(user_id)
        
        if not stats:
            await query.answer("📊 You have no viewing data yet!", show_alert=True)
            return
        
        # Get user's timezone
        user_tz = pytz.timezone(stats.get("timezone", "UTC"))
        
        # Format timestamps
        first_session = stats["first_session"].astimezone(user_tz) if stats["first_session"] else None
        last_session = stats["last_session"].astimezone(user_tz) if stats["last_session"] else None
        
        # Calculate additional metrics
        total_hours = stats["total_minutes"] / 60
        days_active = stats["days_active"]
        daily_avg = stats["daily_avg"]
        
        # Build stats message
        stats_text = (
            f"📊 <b>Your Viewing Statistics</b>\n\n"
            f"⏱️ <b>Total Watch Time:</b> {total_hours:.1f} hours ({stats['total_minutes']} minutes)\n"
            f"🔢 <b>Viewing Sessions:</b> {stats['total_sessions']}\n"
            f"🎬 <b>Dramas Watched:</b> {stats['dramas_watched']}\n"
            f"📈 <b>Average Session:</b> {stats['avg_session']} minutes\n"
        )
        
        if first_session:
            stats_text += f"📅 <b>First Session:</b> {first_session.strftime('%Y-%m-%d %H:%M')}\n"
        
        if last_session:
            stats_text += f"🕐 <b>Last Session:</b> {last_session.strftime('%Y-%m-%d %H:%M')}\n"
        
        if days_active > 0:
            stats_text += f"📆 <b>Days Active:</b> {days_active}\n"
            stats_text += f"📊 <b>Daily Average:</b> {daily_avg:.1f} minutes/day\n"
        
        # Build buttons
        buttons = [
            [InlineKeyboardButton("🏆 Leaderboard", callback_data="show_leaderboard")],
            [InlineKeyboardButton("🌍 Set Timezone", callback_data="set_timezone")],
            [InlineKeyboardButton("⬅️ Back to List", callback_data="refresh_list")]
        ]
        
        await query.message.edit_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error showing user stats: {e}")
        await query.answer("❌ Error loading viewing statistics!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^show_leaderboard$"))
async def show_leaderboard(client, query):
    """Show viewing leaderboard"""
    try:
        leaderboard = await get_viewing_leaderboard(10)
        
        if not leaderboard:
            await query.answer("🏆 No viewing data available for leaderboard!", show_alert=True)
            return
        
        leaderboard_text = "🏆 <b>Top Viewers</b>\n\n"
        
        for i, entry in enumerate(leaderboard, 1):
            username = entry.get("username", f"User {entry['user_id']}")
            total_minutes = entry.get("total_minutes", 0)
            total_sessions = entry.get("total_sessions", 0)
            
            hours = total_minutes // 60
            minutes = total_minutes % 60
            
            leaderboard_text += (
                f"{i}. <b>{username}</b>\n"
                f"   ⏱️ {hours}h {minutes}m | "
                f"🔢 {total_sessions} sessions\n\n"
            )
        
        buttons = [
            [InlineKeyboardButton("📊 My Stats", callback_data="show_stats")],
            [InlineKeyboardButton("⬅️ Back to List", callback_data="refresh_list")]
        ]
        
        await query.message.edit_text(
            leaderboard_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error showing leaderboard: {e}")
        await query.answer("❌ Error loading leaderboard!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^set_timezone$"))
async def set_timezone_prompt(client, query):
    """Prompt user to set timezone"""
    try:
        await query.message.edit_text(
            "🌍 <b>Set Your Timezone</b>\n\n"
            "Enter your timezone (e.g., 'America/New_York', 'Europe/London'):\n\n"
            "Find your timezone: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Stats", callback_data="show_stats")]
            ]),
            parse_mode=ParseMode.HTML
        )
        
        # Store state in user data
        await client.storage.set_user_data(
            query.from_user.id,
            {"state": "setting_timezone"}
        )
        
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error setting timezone prompt: {e}")
        await query.answer("❌ Error setting timezone!", show_alert=True)

@Client.on_message(filters.text & ~filters.command)
async def handle_timezone_input(client, message):
    """Handle timezone input from user"""
    user_id = message.from_user.id
    user_data = await client.storage.get_user_data(user_id)
    
    if not user_data or user_data.get("state") != "setting_timezone":
        return
    
    timezone = message.text.strip()
    
    try:
        success = await set_user_timezone(str(user_id), timezone)
        
        if success:
            await message.reply_text(
                f"✅ Timezone set to {timezone}!\n\n"
                "Your viewing statistics will now be displayed in your local time.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 View My Stats", callback_data="show_stats")]
                ])
            )
        else:
            await message.reply_text(
                "❌ Invalid timezone! Please try again.\n\n"
                "Find your timezone: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Stats", callback_data="show_stats")]
                ])
            )
        
        # Clear state
        await client.storage.set_user_data(user_id, {"state": None})
        
    except Exception as e:
        logger.error(f"Error handling timezone input: {e}")
        await message.reply_text("❌ Error setting timezone!")

@Client.on_message(filters.command(["statsremind"]))
async def database_stats(client, message):
    """Show database statistics (admin only)"""
    try:
        # Get total reminders count
        total_reminders = await reminders_collection.count_documents({})
        
        # Get unique users count
        unique_users = len(await reminders_collection.distinct("user_id"))
        
        # Get most reminded dramas
        pipeline = [
            {"$group": {"_id": "$drama_id", "count": {"$sum": 1}, "title": {"$first": "$drama_title"}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        top_dramas = await reminders_collection.aggregate(pipeline).to_list(length=5)
        
        # Get viewing statistics
        total_viewing_sessions = await viewing_sessions_collection.count_documents({})
        total_viewing_time = await viewing_sessions_collection.aggregate([
            {"$group": {"_id": None, "total": {"$sum": "$duration_minutes"}}}
        ]).to_list(length=1)
        
        total_minutes = total_viewing_time[0]["total"] if total_viewing_time else 0
        total_hours = total_minutes / 60
        
        stats_text = (
            f"📊 <b>Database Statistics</b>\n\n"
            f"👥 Total Users: {unique_users}\n"
            f"🔔 Total Reminders: {total_reminders}\n"
            f"▶️ Viewing Sessions: {total_viewing_sessions}\n"
            f"⏱️ Total Watch Time: {total_hours:.1f} hours\n\n"
            f"<b>🏆 Most Popular Dramas:</b>\n"
        )
        
        for i, drama in enumerate(top_dramas, 1):
            title = drama.get("title", f"Drama {drama['_id']}")
            stats_text += f"{i}. {title} ({drama['count']} reminders)\n"
        
        await message.reply_text(stats_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        await message.reply_text("❌ Error retrieving database statistics!")

@Client.on_message(filters.command(["help"]))
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
        "• Track your viewing time and sessions\n"
        "• See personal viewing statistics and analytics\n"
        "• Compare with other viewers on the leaderboard\n"
        "• Set your timezone for accurate reports\n\n"
        "Just use /comingsoon to get started! 🌟"
    )
    
    await message.reply_text(help_text, parse_mode=ParseMode.HTML)
