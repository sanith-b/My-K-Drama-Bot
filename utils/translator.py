from motor.motor_asyncio import AsyncIOMotorClient
from translations import translations
import os

# Load DB config from env or info.py
DATABASE_URI = os.getenv("DATABASE_URI", "mongodb+srv://kdramabot:Buo0fRGenkOAkgXH@pastppr.ipuyepp.mongodb.net/?retryWrites=true&w=majority&appName=pastppr")
DATABASE_NAME = os.getenv("DATABASE_NAME", "pastppr")

# Init MongoDB
client = AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]
users = db["users"]


# ─────────────── DB Functions ─────────────── #
async def set_language(user_id: int, lang: str):
    """Save or update user language in DB"""
    await users.update_one(
        {"user_id": user_id},
        {"$set": {"language": lang}},
        upsert=True
    )


async def get_language(user_id: int) -> str:
    """Get user language from DB. Defaults to English"""
    user = await users.find_one({"user_id": user_id})
    if user and "language" in user:
        return user["language"]
    return "en"  # default language


# ─────────────── Translator ─────────────── #
async def t(user_id: int, key: str, **kwargs) -> str:
    """
    Get translated text for the user.
    Example: await t(user_id, "ping", time="123")
    """
    lang = await get_language(user_id)
    text = translations.get(lang, translations["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text
