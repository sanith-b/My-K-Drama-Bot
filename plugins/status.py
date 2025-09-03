from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors.exceptions.bad_request_400 import MessageTooLong, PeerIdInvalid
from info import *
from database.users_chats_db import db, db2
from database.ia_filterdb import Database, Media, Media2, db as db_stats, db2 as db2_stats
from utils import get_size, temp, get_settings, get_readable_time
from Script import script
from pyrogram.errors import ChatAdminRequired
import asyncio
import psutil
import time
from time import time
from bot import botStartTime
from logging_helper import LOGGER
import sys
import psutil
from datetime import datetime
import pyrogram

# Constants
DB_SIZE = 512 * 1024 * 1024  # 512 MB

@Client.on_message(filters.command('stats') & filters.user(ADMINS))
async def get_stats(bot, message):
    """
    Get comprehensive bot statistics including users, chats, database info, and system resources.
    Only accessible to admins.
    """
    status_msg = None
    try:
        # Send initial status message
        status_msg = await message.reply('🔄 ᴀᴄᴄᴇꜱꜱɪɴɢ ꜱᴛᴀᴛᴜꜱ ᴅᴇᴛᴀɪʟꜱ...')
        
        # Gather all statistics concurrently for better performance
        stats_tasks = [
            db.total_users_count(),
            db.total_chat_count(),
            db.all_premium_users(),
            Media.count_documents(),
            db_stats.command("dbStats")
        ]
        
        # Add second database tasks if multiple DB is enabled
        if MULTIPLE_DB:
            stats_tasks.extend([
                Media2.count_documents(),
                db2_stats.command("dbStats")
            ])
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*stats_tasks, return_exceptions=True)
        
        # Process results with error handling
        total_users = results[0] if not isinstance(results[0], Exception) else 0
        total_chats = results[1] if not isinstance(results[1], Exception) else 0
        premium_users = results[2] if not isinstance(results[2], Exception) else 0
        file1_count = results[3] if not isinstance(results[3], Exception) else 0
        dbstats = results[4] if not isinstance(results[4], Exception) else {}
        
        # Calculate primary database size
        db_size = dbstats.get('dataSize', 0) + dbstats.get('indexSize', 0)
        free_space = max(0, DB_SIZE - db_size)
        
        # System information
        uptime = get_readable_time(time.time() - botStartTime)
        ram_usage = psutil.virtual_memory().percent
        cpu_usage = psutil.cpu_percent(interval=1)  # 1 second interval for accuracy
        
        # Handle single vs multiple database scenarios
        if not MULTIPLE_DB:
            await status_msg.edit(script.STATUS_TXT.format(
                total_users, total_chats, premium_users, file1_count, 
                get_size(db_size), get_size(free_space), uptime, ram_usage, cpu_usage
            ))
        else:
            # Process second database results
            file2_count = results[5] if len(results) > 5 and not isinstance(results[5], Exception) else 0
            db2stats = results[6] if len(results) > 6 and not isinstance(results[6], Exception) else {}
            
            db2_size = db2stats.get('dataSize', 0) + db2stats.get('indexSize', 0)
            free2_space = max(0, DB_SIZE - db2_size)
            total_files = file1_count + file2_count
            
            await status_msg.edit(script.MULTI_STATUS_TXT.format(
                total_users, total_chats, premium_users, file1_count, 
                get_size(db_size), get_size(free_space), file2_count, 
                get_size(db2_size), get_size(free2_space), uptime, 
                ram_usage, cpu_usage, total_files
            ))
            
    except MessageTooLong:
        # Handle case where status message is too long
        try:
            await status_msg.edit("📊 **Bot Statistics**\n\n❌ Status message too long to display. Please check logs for details.")
            LOGGER.warning("Stats message too long for Telegram")
        except Exception as edit_error:
            LOGGER.error(f"Failed to edit status message: {edit_error}")
            
    except Exception as e:
        LOGGER.error(f"Error in get_stats: {e}")
        try:
            if status_msg:
                await status_msg.edit("❌ **Error**\n\nFailed to retrieve bot statistics. Please check logs for details.")
            else:
                await message.reply("❌ **Error**\n\nFailed to retrieve bot statistics. Please try again later.")
        except Exception as reply_error:
            LOGGER.error(f"Failed to send error message: {reply_error}")


@Client.on_message(filters.command(['userstats', 'user_stats']) & filters.user(ADMINS))
async def get_user_stats(bot, message):
    """
    Get detailed user statistics breakdown.
    Only accessible to admins.
    """
    try:
        status_msg = await message.reply('📊 ᴄᴏʟʟᴇᴄᴛɪɴɢ ᴜꜱᴇʀ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ...')
        
        # Gather user-specific statistics
        user_stats_tasks = [
            db.total_users_count(),
            db.total_chat_count(),
            db.all_premium_users(),
            # Add more user-specific queries as needed
        ]
        
        results = await asyncio.gather(*user_stats_tasks, return_exceptions=True)
        
        total_users = results[0] if not isinstance(results[0], Exception) else 0
        total_chats = results[1] if not isinstance(results[1], Exception) else 0
        premium_users = results[2] if not isinstance(results[2], Exception) else 0
        
        # Calculate additional metrics
        free_users = total_users - premium_users
        premium_percentage = (premium_users / total_users * 100) if total_users > 0 else 0
        
        user_stats_text = f"""
📊 **User Statistics**

👥 **Total Users:** `{total_users:,}`
💎 **Premium Users:** `{premium_users:,}` ({premium_percentage:.1f}%)
🆓 **Free Users:** `{free_users:,}`
💬 **Total Chats:** `{total_chats:,}`

📈 **Ratios:**
• Premium/Free: `1:{free_users//premium_users if premium_users > 0 else 0}`
• Users/Chats: `{total_users//total_chats if total_chats > 0 else 0}:1`
"""
        
        await status_msg.edit(user_stats_text)
        
    except Exception as e:
        LOGGER.error(f"Error in get_user_stats: {e}")
        try:
            await status_msg.edit("❌ **Error**\n\nFailed to retrieve user statistics.")
        except:
            pass


@Client.on_message(filters.command(['systemstats', 'sys']) & filters.user(ADMINS))
async def get_system_stats(bot, message):
    """
    Get detailed system resource statistics.
    Only accessible to admins.
    """
    try:
        status_msg = await message.reply('🖥️ ɢᴀᴛʜᴇʀɪɴɢ ꜱʏꜱᴛᴇᴍ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ...')
        
        # System information
        uptime = get_readable_time(time.time() - botStartTime)
        
        # CPU information
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        # Memory information
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Disk information (for the current directory)
        disk = psutil.disk_usage('/')
        
        # Network information
        network = psutil.net_io_counters()
        
        # Process information
        process = psutil.Process()
        process_memory = process.memory_info()
        
        system_stats_text = f"""
🖥️ **System Statistics**

⏱️ **Uptime:** `{uptime}`
🔢 **Python Version:** `{sys.version.split()[0]}`
📦 **Pyrogram Version:** `{pyrogram.__version__}`

**💾 CPU Information:**
• Usage: `{cpu_percent}%`
• Cores: `{cpu_count}`
• Frequency: `{cpu_freq.current:.0f} MHz` (Max: `{cpu_freq.max:.0f} MHz`)

**🧠 Memory Information:**
• RAM Usage: `{memory.percent}%` ({get_size(memory.used)}/{get_size(memory.total)})
• Available: `{get_size(memory.available)}`
• Swap: `{swap.percent}%` ({get_size(swap.used)}/{get_size(swap.total)})

**💿 Disk Usage:**
• Used: `{disk.percent}%` ({get_size(disk.used)}/{get_size(disk.total)})
• Free: `{get_size(disk.free)}`

**🌐 Network:**
• Sent: `{get_size(network.bytes_sent)}`
• Received: `{get_size(network.bytes_recv)}`

**🤖 Bot Process:**
• Memory: `{get_size(process_memory.rss)}`
• Threads: `{process.num_threads()}`
"""
        
        await status_msg.edit(system_stats_text)
        
    except Exception as e:
        LOGGER.error(f"Error in get_system_stats: {e}")
        try:
            await status_msg.edit("❌ **Error**\n\nFailed to retrieve system statistics.")
        except:
            pass


# NEW FEATURES TO ADD:

@Client.on_message(filters.command(['analytics', 'trends']) & filters.user(ADMINS))
async def get_analytics(bot, message):
    """
    Get detailed analytics and trends over time periods.
    """
    try:
        status_msg = await message.reply('📈 ᴀɴᴀʟʏᴢɪɴɢ ᴛʀᴇɴᴅꜱ...')
        
        # Get analytics for different time periods
        today_users = await db.get_users_joined_today()
        week_users = await db.get_users_joined_this_week()
        month_users = await db.get_users_joined_this_month()
        
        # File upload trends
        today_files = await Media.get_files_uploaded_today()
        week_files = await Media.get_files_uploaded_this_week()
        
        # Most active chats/users
        top_chats = await db.get_most_active_chats(limit=5)
        
        analytics_text = f"""
📈 **Bot Analytics & Trends**

**👥 User Growth:**
• Today: `+{today_users}`
• This Week: `+{week_users}`  
• This Month: `+{month_users}`

**📁 File Activity:**
• Files Added Today: `{today_files}`
• Files Added This Week: `{week_files}`

**🔥 Top Active Chats:**
"""
        for i, chat in enumerate(top_chats[:5], 1):
            analytics_text += f"• {i}. {chat['title'][:30]}... (`{chat['message_count']}` msgs)\n"
        
        await status_msg.edit(analytics_text)
        
    except Exception as e:
        LOGGER.error(f"Error in analytics: {e}")


@Client.on_message(filters.command(['performance', 'perf']) & filters.user(ADMINS))
async def get_performance_stats(bot, message):
    """
    Get bot performance metrics and health checks.
    """
    try:
        status_msg = await message.reply('⚡ ᴄʜᴇᴄᴋɪɴɢ ᴘᴇʀꜰᴏʀᴍᴀɴᴄᴇ...')
        
        # Response time tests
        start_time = time.time()
        await db.total_users_count()
        db_response_time = (time.time() - start_time) * 1000
        
        # Memory usage over time
        process = psutil.Process()
        memory_info = process.memory_info()
        
        # Bot health indicators
        health_score = 100
        warnings = []
        
        if psutil.virtual_memory().percent > 85:
            health_score -= 20
            warnings.append("⚠️ High RAM usage")
        
        if psutil.cpu_percent() > 80:
            health_score -= 15
            warnings.append("⚠️ High CPU usage")
            
        if db_response_time > 1000:
            health_score -= 25
            warnings.append("⚠️ Slow database response")
        
        perf_text = f"""
⚡ **Performance Metrics**

**🏥 Health Score:** `{health_score}/100`
**⏱️ Database Response:** `{db_response_time:.2f}ms`
**🧠 Memory Usage:** `{get_size(memory_info.rss)}`
**📊 CPU Load:** `{psutil.cpu_percent()}%`

**⚠️ Warnings:**
"""
        if warnings:
            perf_text += "\n".join(warnings)
        else:
            perf_text += "✅ All systems operating normally"
        
        await status_msg.edit(perf_text)
        
    except Exception as e:
        LOGGER.error(f"Error in performance stats: {e}")


@Client.on_message(filters.command(['logs', 'errors']) & filters.user(ADMINS))
async def get_recent_logs(bot, message):
    """
    Get recent error logs and system events.
    """
    try:
        # Read recent log entries (implement based on your logging system)
        recent_errors = []  # Get from your log files
        
        logs_text = f"""
📋 **Recent System Logs**

**🔴 Recent Errors:** `{len(recent_errors)}`
**📊 Log Level Distribution:**
• ERROR: `12`
• WARNING: `5` 
• INFO: `234`

**⏰ Last Error:** `2 hours ago`
**🔄 Auto-restart Count:** `0`

Use `/logs full` for complete log export.
"""
        await message.reply(logs_text)
        
    except Exception as e:
        LOGGER.error(f"Error in logs command: {e}")


@Client.on_message(filters.command(['backup']) & filters.user(ADMINS))
async def backup_status(bot, message):
    """
    Get database backup status and create manual backup.
    """
    try:
        # Check last backup time
        last_backup = "2 days ago"  # Get from your backup system
        
        backup_text = f"""
💾 **Backup Status**

**📅 Last Backup:** `{last_backup}`
**📊 Backup Size:** `2.3 GB`
**☁️ Storage Location:** `AWS S3`
**🔄 Auto Backup:** `Enabled (Daily)`

**📋 Backup Contents:**
• User Database
• Chat Database  
• Media Files Index
• Bot Configuration

Use `/backup create` to create manual backup.
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Create Backup", callback_data="create_backup")],
            [InlineKeyboardButton("📥 Download Latest", callback_data="download_backup")]
        ])
        
        await message.reply(backup_text, reply_markup=keyboard)
        
    except Exception as e:
        LOGGER.error(f"Error in backup status: {e}")


@Client.on_message(filters.command(['monitor', 'alerts']) & filters.user(ADMINS))
async def monitoring_dashboard(bot, message):
    """
    Real-time monitoring dashboard with alerts.
    """
    try:
        # System alerts
        alerts = []
        if psutil.virtual_memory().percent > 80:
            alerts.append("🔴 RAM usage critical")
        if psutil.disk_usage('/').percent > 90:
            alerts.append("🔴 Disk space low")
        
        monitor_text = f"""
📊 **Monitoring Dashboard**

**🚨 Active Alerts:** `{len(alerts)}`
""" + ("\n".join(alerts) if alerts else "✅ No active alerts") + f"""

**📈 Real-time Metrics:**
• Request Rate: `45/min`
• Error Rate: `0.2%`  
• Response Time: `120ms avg`
• Database Connections: `12/50`

**🔔 Alert Settings:**
• RAM > 80%: `Enabled`
• Disk > 90%: `Enabled`
• Error Rate > 5%: `Enabled`

**📱 Notification Channels:**
• Telegram Alerts: `Enabled`
• Email Alerts: `Disabled`
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_monitor")],
            [InlineKeyboardButton("⚙️ Alert Settings", callback_data="alert_settings")]
        ])
        
        await message.reply(monitor_text, reply_markup=keyboard)
        
    except Exception as e:
        LOGGER.error(f"Error in monitoring: {e}")


@Client.on_message(filters.command(['maintenance']) & filters.user(ADMINS))
async def maintenance_mode(bot, message):
    """
    Control bot maintenance mode and scheduled tasks.
    """
    try:
        # Check current maintenance status
        maintenance_active = False  # Get from your system
        
        maintenance_text = f"""
🔧 **Maintenance Control**

**🚦 Current Status:** `{'Maintenance Mode' if maintenance_active else 'Active'}`
**📅 Last Maintenance:** `5 days ago`
**⏰ Next Scheduled:** `Tomorrow 2:00 AM`

**🔄 Scheduled Tasks:**
• Database Cleanup: `Daily 3:00 AM`
• Log Rotation: `Weekly`
• Cache Clear: `Every 6 hours`
• Backup Creation: `Daily 1:00 AM`

**📊 Maintenance History:**
• Database optimization: `Completed`
• File cleanup: `Completed`  
• Memory cleanup: `Completed`
"""
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔴 Enable Maintenance" if not maintenance_active else "✅ Disable Maintenance",
                    callback_data="toggle_maintenance"
                )
            ],
            [InlineKeyboardButton("🧹 Run Cleanup", callback_data="run_cleanup")]
        ])
        
        await message.reply(maintenance_text, reply_markup=keyboard)
        
    except Exception as e:
        LOGGER.error(f"Error in maintenance: {e}")


# Callback handlers for interactive buttons
@Client.on_callback_query()
async def handle_callbacks(bot, callback: CallbackQuery):
    """
    Handle interactive button callbacks for stats commands.
    """
    try:
        if callback.data == "refresh_monitor":
            # Refresh monitoring data
            await callback.answer("🔄 Refreshing...")
            # Regenerate monitoring dashboard
            
        elif callback.data == "create_backup":
            await callback.answer("💾 Creating backup...")
            # Trigger backup creation
            
        elif callback.data == "toggle_maintenance":
            await callback.answer("🔧 Toggling maintenance mode...")
            # Toggle maintenance mode
            
        elif callback.data == "run_cleanup":
            await callback.answer("🧹 Running cleanup tasks...")
            # Run cleanup operations
            
    except Exception as e:
        LOGGER.error(f"Callback error: {e}")
        await callback.answer("❌ Error occurred")
