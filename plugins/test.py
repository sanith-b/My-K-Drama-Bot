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


@Client.on_message(filters.command(["comhelp"]))
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
