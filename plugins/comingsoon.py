import requests
import datetime
import json
import os
from typing import List, Dict, Optional
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.enums import ParseMode
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TMDB_API_KEY = "90dde61a7cf8339a2cff5d805d5597a9"
REMINDERS_FILE = "reminders.json"
DEFAULT_POSTER = "https://via.placeholder.com/500x750/1a1a2e/eee?text=K-Drama"

# Cache for drama data to avoid repeated API calls
drama_cache = {}

def load_reminders():
    """Load reminders from file"""
    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Error reading reminders file")
    return {}

def save_reminders(reminders):
    """Save reminders to file"""
    try:
        with open(REMINDERS_FILE, 'w') as f:
            json.dump(reminders, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving reminders: {e}")

# Load existing reminders
user_reminders = load_reminders()

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
            InlineKeyboardButton("📋 My Reminders", callback_data="show_reminders")
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
        is_reminded = user_reminders.get(user_id, {}).get(drama_id, False)
        
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

@Client.on_callback_query(filters.regex(r"^remind_"))
async def set_reminder(client, query):
    """Set reminder for a drama"""
    drama_id = query.data.split("_")[1]
    user_id = str(query.from_user.id)
    
    try:
        # Initialize user reminders if not exists
        if user_id not in user_reminders:
            user_reminders[user_id] = {}
        
        user_reminders[user_id][drama_id] = True
        save_reminders(user_reminders)
        
        drama_data = get_drama_details(drama_id)
        drama_title = drama_data["title"] if drama_data else f"Drama {drama_id}"
        
        await query.answer(f"🔔 Reminder set for '{drama_title}'!", show_alert=True)
        
        # Update the button to show reminder is set
        await drama_details(client, query)
        
    except Exception as e:
        logger.error(f"Error setting reminder: {e}")
        await query.answer("❌ Error setting reminder!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^unremind_"))
async def remove_reminder(client, query):
    """Remove reminder for a drama"""
    drama_id = query.data.split("_")[1]
    user_id = str(query.from_user.id)
    
    try:
        if user_id in user_reminders and drama_id in user_reminders[user_id]:
            del user_reminders[user_id][drama_id]
            save_reminders(user_reminders)
        
        drama_data = get_drama_details(drama_id)
        drama_title = drama_data["title"] if drama_data else f"Drama {drama_id}"
        
        await query.answer(f"🔕 Reminder removed for '{drama_title}'!", show_alert=True)
        
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
async def show_user_reminders(client, query):
    """Show user's reminders"""
    user_id = str(query.from_user.id)
    
    try:
        if user_id not in user_reminders or not user_reminders[user_id]:
            await query.answer("📋 You have no reminders set!", show_alert=True)
            return
        
        buttons = []
        for drama_id in user_reminders[user_id]:
            drama_data = get_drama_details(drama_id)
            if drama_data:
                title = drama_data["title"]
                if len(title) > 30:
                    title = title[:27] + "..."
                buttons.append([InlineKeyboardButton(f"🔔 {title}", callback_data=f"drama_{drama_id}")])
        
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

@Client.on_message(filters.command(["help"]))
async def help_command(client, message):
    """Show help information"""
    help_text = (
        "🎬 <b>K-Drama Bot Commands</b>\n\n"
        "🔸 /comingsoon or /upcoming - Show upcoming K-Dramas\n"
        "🔸 /help - Show this help message\n\n"
        "<b>Features:</b>\n"
        "• View upcoming Korean dramas with release dates\n"
        "• Watch trailers directly from the bot\n"
        "• Set reminders for dramas you're interested in\n"
        "• See ratings, genres, and detailed information\n"
        "• Navigate easily with interactive buttons\n\n"
        "Just use /comingsoon to get started! 🌟"
    )
    
    await message.reply_text(help_text, parse_mode=ParseMode.HTML)
