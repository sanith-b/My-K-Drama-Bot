import pymongo
import requests
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

DATABASE_URI = "mongodb+srv://kdramabot:Buo0fRGenkOAkgXH@pastppr.ipuyepp.mongodb.net/?retryWrites=true&w=majority&appName=pastppr" 
DATABASE_NAME = "pastppr" 
TMDB_API_KEY = "90dde61a7cf8339a2cff5d805d5597a9"
# --- MongoDB setup ---
mongo_client = pymongo.MongoClient(DATABASE_URI)
db = mongo_client[DATABASE_NAME]
watchlist_col = db["watchlist"]
favorites_col = db["favorites"]

# --- TMDB API ---
SEARCH_URL = "https://api.themoviedb.org/3/search/tv?api_key={}&query={}&language=en-US&page={}"
DETAIL_URL = "https://api.themoviedb.org/3/tv/{}?api_key={}&language=en-US"
IMG_URL = "https://image.tmdb.org/t/p/w500"

# --- Helpers ---
def search_drama(query: str, page: int = 1):
    r = requests.get(SEARCH_URL.format(TMDB_API_KEY, query, page))
    if r.status_code == 200:
        data = r.json()
        return data.get("results", []), data.get("total_pages", 1)
    return [], 1

def get_drama_details(drama_id: int):
    r = requests.get(DETAIL_URL.format(drama_id, TMDB_API_KEY))
    if r.status_code == 200:
        return r.json()
    return None

def add_to_collection(user_id, drama_id, collection):
    if collection.find_one({"user_id": user_id, "drama_id": drama_id}):
        return False
    collection.insert_one({"user_id": user_id, "drama_id": drama_id})
    return True

def remove_from_collection(user_id, drama_id, collection):
    result = collection.delete_one({"user_id": user_id, "drama_id": drama_id})
    return result.deleted_count > 0

def list_collection(user_id, collection):
    """Returns list of dicts: {'id': drama_id, 'details': tmdb_details}"""
    docs = list(collection.find({"user_id": user_id}))
    dramas = []
    for entry in docs:
        details = get_drama_details(entry["drama_id"])
        if details:
            dramas.append({"id": entry["drama_id"], "details": details})
    return dramas

# --- /drama command ---
@Client.on_message(filters.command("drama"))
async def drama_search(client, message):
    if len(message.command) < 2:
        return await message.reply("⚠️ Usage: `/drama <name>`", quote=True)

    query = " ".join(message.command[1:])
    results, total_pages = search_drama(query, 1)

    if not results:
        return await message.reply("❌ No dramas found.")

    for drama in results[:5]:
        title = drama.get("name")
        year = drama.get("first_air_date", "N/A")[:4]
        drama_id = drama["id"]
        overview = drama.get("overview", "No description available.")[:300]

        text = f"🎬 <b>{title}</b> ({year})\n\n📖 {overview}"

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Watchlist", callback_data=f"watch_{drama_id}"),
                InlineKeyboardButton("💖 Favorite", callback_data=f"fav_{drama_id}")
            ],
            [
                InlineKeyboardButton("📜 More Info", callback_data=f"info_{drama_id}")
            ]
        ])

        poster_path = drama.get("poster_path")
        if poster_path:
            await message.reply_photo(IMG_URL + poster_path, caption=text, reply_markup=buttons)
        else:
            await message.reply(text, reply_markup=buttons)

# --- Callback Handlers ---
@Client.on_callback_query(filters.regex("^(watch|fav|info)_"))
async def drama_callbacks(client, query: CallbackQuery):
    action, drama_id = query.data.split("_")
    drama_id = int(drama_id)
    user_id = query.from_user.id
    drama = get_drama_details(drama_id)

    if action == "watch":
        added = add_to_collection(user_id, drama_id, watchlist_col)
        await query.answer(f"✅ {drama['name']} added to Watchlist!" if added else "⚠️ Already in Watchlist!", show_alert=True)
    elif action == "fav":
        added = add_to_collection(user_id, drama_id, favorites_col)
        await query.answer(f"💖 {drama['name']} added to Favorites!" if added else "⚠️ Already in Favorites!", show_alert=True)
    elif action == "info":
        text = (
            f"🎬 <b>{drama['name']}</b> ({drama.get('first_air_date','N/A')[:4]})\n"
            f"⭐ Rating: {drama.get('vote_average','N/A')}/10\n"
            f"📅 First Air: {drama.get('first_air_date','N/A')}\n\n"
            f"📖 {drama.get('overview','No description')}"
        )
        await query.message.reply(text)

# --- Show Watchlist / Favorites ---
async def show_collection(client, message, collection, collection_name):
    user_id = message.from_user.id
    dramas = list_collection(user_id, collection)
    if not dramas:
        return await message.reply(f"📭 Your {collection_name} is empty.")

    for drama in dramas:
        d = drama["details"]
        text = f"🎬 <b>{d['name']}</b> ({d.get('first_air_date','N/A')[:4]})"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🗑 Remove from {collection_name}", callback_data=f"remove_{collection_name}_{drama['id']}")]
        ])
        poster_path = d.get("poster_path")
        if poster_path:
            await message.reply_photo(IMG_URL + poster_path, caption=text, reply_markup=buttons)
        else:
            await message.reply(text, reply_markup=buttons)

@Client.on_message(filters.command("mywatchlist"))
async def my_watchlist(client, message):
    await show_collection(client, message, watchlist_col, "Watchlist")

@Client.on_message(filters.command("myfavorites"))
async def my_favorites(client, message):
    await show_collection(client, message, favorites_col, "Favorites")

# --- Remove from Watchlist / Favorites ---
@Client.on_callback_query(filters.regex("^remove_"))
async def remove_callback(client, query: CallbackQuery):
    _, collection_name, drama_id = query.data.split("_")
    drama_id = int(drama_id)
    user_id = query.from_user.id
    collection = watchlist_col if collection_name == "Watchlist" else favorites_col

    removed = remove_from_collection(user_id, drama_id, collection)
    drama = get_drama_details(drama_id)
    await query.answer(f"🗑 {drama['name']} removed from {collection_name}" if removed else "❌ Already removed.", show_alert=True)
    await query.message.delete()
