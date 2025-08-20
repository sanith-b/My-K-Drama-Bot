import requests
import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TMDB_API_KEY = "90dde61a7cf8339a2cff5d805d5597a9"

# Fetch upcoming dramas
def get_coming_soon():
    today = datetime.date.today().strftime("%Y-%m-%d")
    url = (
        f"https://api.themoviedb.org/3/discover/tv"
        f"?api_key={TMDB_API_KEY}"
        f"&with_origin_country=KR"
        f"&sort_by=first_air_date.asc"
        f"&first_air_date.gte={today}"
        f"&language=en-US&page=1"
    )
    response = requests.get(url).json()
    dramas = []
    for item in response.get("results", []):
        dramas.append({
            "id": item["id"],
            "title": item["name"],
            "release_date": item.get("first_air_date", "TBA"),
            "overview": item.get("overview", "No description available."),
            "poster": f"https://image.tmdb.org/t/p/w500{item['poster_path']}" if item.get("poster_path") else None
        })
    return dramas

# Get trailer link
def get_trailer(tv_id):
    url = f"https://api.themoviedb.org/3/tv/{tv_id}/videos?api_key={TMDB_API_KEY}&language=en-US"
    response = requests.get(url).json()
    for video in response.get("results", []):
        if video["site"] == "YouTube" and video["type"] == "Trailer":
            return f"https://youtu.be/{video['key']}"
    return None

# Show list of upcoming dramas
@Client.on_message(filters.command("comingsoon"))
async def comingsoon_list(client, message):
    dramas = get_coming_soon()
    if not dramas:
        await message.reply_text("🌸 No upcoming K-Dramas found!")
        return

    buttons = []
    for drama in dramas[:10]:  # show first 10 dramas
        buttons.append([InlineKeyboardButton(drama["title"], callback_data=f"drama_{drama['id']}")])

    await message.reply_text(
        "🎬 Upcoming K-Dramas:\nClick a drama to see details",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Show drama details when user clicks a button
@Client.on_callback_query(filters.regex(r"^drama_"))
async def drama_details(client, query):
    drama_id = query.data.split("_")[1]
    drama_data = None

    for drama in get_coming_soon():
        if str(drama['id']) == drama_id:
            drama_data = drama
            break

    if not drama_data:
        await query.answer("Drama not found!", show_alert=True)
        return

    trailer = get_trailer(drama_id)
    release_date = drama_data.get("release_date", "TBA")
    days_left = ""
    if release_date != "TBA":
        try:
            rd = datetime.datetime.strptime(release_date, "%Y-%m-%d").date()
            diff = (rd - datetime.date.today()).days
            if diff >= 0:
                days_left = f"\n⏳ {diff} days left!"
        except:
            pass

    caption = (
        f"🎬 <b>{drama_data['title']}</b>\n"
        f"📅 Release Date: {release_date}{days_left}\n\n"
        f"✨ {drama_data['overview']}"
    )

    buttons = []
    if trailer:
        buttons.append([InlineKeyboardButton("▶️ Watch Trailer", url=trailer)])
    buttons.append([InlineKeyboardButton("🔔 Remind Me", callback_data=f"remind_{drama_id}")])

    await query.message.edit_media(
        media=drama_data["poster"] if drama_data["poster"] else "https://i.ibb.co/6NfYQ7c/kdrama.jpg",
        caption=caption,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Callback for Remind Me
@Client.on_callback_query(filters.regex(r"^remind_"))
async def remind_me(client, query):
    drama_id = query.data.split("_")[1]
    await query.answer(f"🔔 Reminder set for drama ID {drama_id}!", show_alert=True)
