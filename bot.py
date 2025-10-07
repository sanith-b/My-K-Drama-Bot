import sys
import glob
import importlib
from pathlib import Path
from pyrogram import Client, idle, __version__
from pyrogram.raw.all import layer
import time
import asyncio
from datetime import date, datetime, timedelta
import pytz
from aiohttp import web
from database.ia_filterdb import Media, Media2
from database.users_chats_db import db
from info import *
from utils import temp
from Script import script
from plugins import web_server, check_expired_premium 
from Lucia.Bot import SilentX
from Lucia.util.keepalive import ping_server
from Lucia.Bot.clients import initialize_clients
import pyrogram.utils
from PIL import Image
import threading
import requests
import os
import signal
from logging_helper import LOGGER

# ============================================
# NEW: Import API if enabled
# ============================================
try:
    if ENABLE_API:
        from api import run_api
        LOGGER.info("📡 API Module Loaded Successfully")
except ImportError:
    ENABLE_API = False
    LOGGER.warning("⚠️ API module not found. API will be disabled.")
except Exception as e:
    ENABLE_API = False
    LOGGER.error(f"❌ Error loading API module: {e}")

botStartTime = time.time()
ppath = "plugins/*.py"
files = glob.glob(ppath)
pyrogram.utils.MIN_CHANNEL_ID = -1002719012453

def ping_loop():
    """Background thread to ping the server periodically"""
    while True:
        try:
            r = requests.get(URL, timeout=10)
            if r.status_code == 200:
                LOGGER.info("✅ Ping Successful")
            else:
                LOGGER.error(f"⚠️ Ping Failed: {r.status_code}")
        except Exception as e:
            LOGGER.error(f"❌ Exception During Ping: {e}")
        time.sleep(120)

def restart_bot():
    """Restart the bot by terminating current process"""
    LOGGER.info("🔄 Auto-restarting bot after 3 hours...")
    os.execv(sys.executable, ['python'] + sys.argv)

def schedule_restart():
    """Schedule bot restart every 3 hours"""
    while True:
        time.sleep(3 * 60 * 60)  # 3 hours = 3 * 60 * 60 seconds
        restart_bot()

# Start the ping loop in a daemon thread
threading.Thread(target=ping_loop, daemon=True).start()

# Start the auto-restart scheduler in a daemon thread
threading.Thread(target=schedule_restart, daemon=True).start()

# ============================================
# NEW: Start API Server in background thread
# ============================================
if ENABLE_API:
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    LOGGER.info(f"🚀 API Server Started on http://0.0.0.0:{API_PORT}")
    LOGGER.info(f"📖 API Docs: http://0.0.0.0:{API_PORT}/")

async def SilentXBotz_start():
    """Main bot startup function"""
    LOGGER.info('Initializing Your Bot!')
    
    # Start the bot
    await SilentX.start()
    bot_info = await SilentX.get_me()
    SilentX.username = bot_info.username
    
    # Initialize clients
    await initialize_clients()
    
    # Load plugins dynamically
    for name in files:
        with open(name) as a:
            patt = Path(a.name)
            plugin_name = patt.stem.replace(".py", "")
            plugins_dir = Path(f"plugins/{plugin_name}.py")
            import_path = "plugins.{}".format(plugin_name)
            spec = importlib.util.spec_from_file_location(import_path, plugins_dir)
            load = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(load)
            sys.modules["plugins." + plugin_name] = load
            LOGGER.info("Import Plugins - " + plugin_name)
    
    # Start ping server if on Heroku
    if ON_HEROKU:
        asyncio.create_task(ping_server()) 
    
    # Get banned users and chats
    b_users, b_chats = await db.get_banned()
    temp.BANNED_USERS = b_users
    temp.BANNED_CHATS = b_chats
    
    # Ensure database indexes
    await Media.ensure_indexes()
    if MULTIPLE_DB:
        await Media2.ensure_indexes()
        LOGGER.info("Multiple Database Mode On. Now Files Will Be Save In Second DB If First DB Is Full")
    else:
        LOGGER.info("Single DB Mode On ! Files Will Be Save In First Database")
    
    # Set bot information
    me = await SilentX.get_me()
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name
    temp.B_LINK = me.mention
    SilentX.username = '@' + me.username
    
    # Start premium check task
    SilentX.loop.create_task(check_expired_premium(SilentX))
    
    LOGGER.info(f"{me.first_name} with Pyrogram v{__version__} (Layer {layer}) started on {me.username}.")
    LOGGER.info(script.LOGO)
    
    # Send restart notification
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    current_time = now.strftime("%H:%M:%S %p")
    
    # Calculate next restart time
    next_restart = datetime.now(tz) + timedelta(hours=3)
    next_restart_str = next_restart.strftime("%H:%M:%S %p")
    
    # ============================================
    # NEW: Enhanced restart message with API info
    # ============================================
    restart_message = script.RESTART_TXT.format(temp.B_LINK, today, current_time)
    restart_message += f"\n\n⏰ <b>Next Auto-Restart:</b> {next_restart_str}"
    
    if ENABLE_API:
        restart_message += f"\n\n🌐 <b>API Status:</b> ✅ Running"
        restart_message += f"\n📡 <b>API Port:</b> {API_PORT}"
        restart_message += f"\n🔗 <b>API Endpoint:</b> <code>http://0.0.0.0:{API_PORT}</code>"
    else:
        restart_message += f"\n\n🌐 <b>API Status:</b> ❌ Disabled"
    
    await SilentX.send_message(
        chat_id=LOG_CHANNEL, 
        text=restart_message
    )
    
    # Notify admins with restart info
    try:
        for admin in ADMINS:
            admin_message = f"<b>๏[-ิ_•ิ]๏ {me.mention} Restarted ✅</b>\n"
            admin_message += f"⏰ <b>Next Auto-Restart:</b> {next_restart_str}"
            
            if ENABLE_API:
                admin_message += f"\n🌐 <b>API:</b> ✅ Online (Port {API_PORT})"
            
            await SilentX.send_message(chat_id=admin, text=admin_message)
    except Exception as e:
        LOGGER.error(f"Failed to notify admins: {e}")
    
    # Start web server
    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, PORT).start()
    
    LOGGER.info("=" * 50)
    LOGGER.info("✅ Bot Started Successfully!")
    LOGGER.info(f"🤖 Bot: @{me.username}")
    LOGGER.info(f"🌐 Web Server: http://0.0.0.0:{PORT}")
    if ENABLE_API:
        LOGGER.info(f"📡 API Server: http://0.0.0.0:{API_PORT}")
        LOGGER.info(f"📖 API Docs: http://0.0.0.0:{API_PORT}/")
    LOGGER.info("=" * 50)
    
    # Keep the bot running
    await idle()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(SilentXBotz_start())
    except KeyboardInterrupt:
        LOGGER.info('Service Stopped Bye 👋')
    finally:
        loop.close()
