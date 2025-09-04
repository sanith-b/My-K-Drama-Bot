import os
import datetime
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient

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
