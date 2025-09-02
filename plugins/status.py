import asyncio
import logging
import psutil
from datetime import datetime, timedelta
from pyrogram import Client, filters
from time import time
from pymongo import MongoClient
from info import DATABASE_URI, DATABASE_NAME, ADMINS
from utils import get_readable_time, get_size  # your helper functions


# Logging
LOGGER = logging.getLogger(__name__)

# MongoDB setup
mongo_client = MongoClient(DATABASE_URI)
db = mongo_client[DATABASE_NAME]
users_col = db.users
requests_col = db.requests
Media = db.media

# Track bot uptime
botStartTime = time()

@Client.on_message(filters.command("status"))
async def get_stats(bot, message):
    try:
        status_msg = await message.reply("📊 Accessing status details...")

        # Core stats
        total_users = await users_col.count_documents({})
        total_chats = await db.chats.count_documents({})
        premium_users = await users_col.count_documents({"is_premium": True})
        total_files = await Media.count_documents({})

        # Database size
        DB_SIZE = 512 * 1024 * 1024  # Example fixed quota
        dbstats = db.command("dbStats")
        db_size = dbstats["dataSize"] + dbstats["indexSize"]
        free = DB_SIZE - db_size

        # Time-based stats
        now = datetime.utcnow()
        today = now - timedelta(days=1)
        week = now - timedelta(weeks=1)
        month = now - timedelta(days=30)
        year = now - timedelta(days=365)

        new_today = await users_col.count_documents({"joined_at": {"$gte": today}})
        new_week = await users_col.count_documents({"joined_at": {"$gte": week}})
        new_month = await users_col.count_documents({"joined_at": {"$gte": month}})
        new_year = await users_col.count_documents({"joined_at": {"$gte": year}})

        # Requests served
        total_requests = await requests_col.count_documents({})
        requests_today = await requests_col.count_documents({"time": {"$gte": today}})
        requests_week = await requests_col.count_documents({"time": {"$gte": week}})

        # Blocked users
        blocked_users = await users_col.count_documents({"is_blocked": True})

        # Online users = last_active < 5 min
        online_users = await users_col.count_documents({
            "last_active": {"$gte": now - timedelta(minutes=5)}
        })

        # System stats
        uptime = get_readable_time(time() - botStartTime)
        ram = psutil.virtual_memory().percent
        cpu = psutil.cpu_percent()

        # Final output
        text = f"""
📊 **Bot Statistics**

👥 **Users**
   • Total: `{total_users}`
   • New Today: `{new_today}`
   • This Week: `{new_week}`
   • This Month: `{new_month}`
   • This Year: `{new_year}`
   • Premium: `{premium_users}`
   • Blocked: `{blocked_users}`
   • 🟢 Online Now: `{online_users}`

💬 **Chats**
   • Total Chats: `{total_chats}`

📌 **Requests**
   • Total Served: `{total_requests}`
   • Today: `{requests_today}`
   • This Week: `{requests_week}`
"""
        await status_msg.edit(text)

    except Exception as e:
        LOGGER.error(e)
        await message.reply(f"⚠️ Error: `{e}`")
