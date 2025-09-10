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
DB_SIZE_LIMIT_MB = 512  # Change this as needed
DB_SIZE = DB_SIZE_LIMIT_MB * 1024 * 1024
"""-----------------------------------------https://t.me/SilentXBotz--------------------------------------"""

@Client.on_message(filters.new_chat_members & filters.group)
async def save_group(bot, message):
    r_j_check = [u.id for u in message.new_chat_members]
    if temp.ME in r_j_check:
        if not await db.get_chat(message.chat.id):
            total=await bot.get_chat_members_count(message.chat.id)
            r_j = message.from_user.mention if message.from_user else "Anonymous" 
            await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, r_j))       
            await db.add_chat(message.chat.id, message.chat.title)
        if message.chat.id in temp.BANNED_CHATS:
            
            buttons = [[
                InlineKeyboardButton('📌 ᴄᴏɴᴛᴀᴄᴛ ꜱᴜᴘᴘᴏʀᴛ 📌', url=OWNER_LNK)
            ]]
            reply_markup=InlineKeyboardMarkup(buttons)
            k = await message.reply(
                text='<b>ᴄʜᴀᴛ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ 🐞\n\nᴍʏ ᴀᴅᴍɪɴꜱ ʜᴀꜱ ʀᴇꜱᴛʀɪᴄᴛᴇᴅ ᴍᴇ ꜰʀᴏᴍ ᴡᴏʀᴋɪɴɢ ʜᴇʀᴇ ! ɪꜰ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴋɴᴏᴡ ᴍᴏʀᴇ ᴀʙᴏᴜᴛ ɪᴛ ᴄᴏɴᴛᴀᴄᴛ ꜱᴜᴘᴘᴏʀᴛ.</b>',
                reply_markup=reply_markup,
            )

            try:
                await k.pin()
            except:
                pass
            await bot.leave_chat(message.chat.id)
            return
        buttons = [[
                    InlineKeyboardButton("📌 ᴄᴏɴᴛᴀᴄᴛ ꜱᴜᴘᴘᴏʀᴛ 📌", url=OWNER_LNK)
                  ]]
        reply_markup=InlineKeyboardMarkup(buttons)
        await message.reply_text(
            text=f"<b>Thankyou For Adding Me In {message.chat.title} ❣️\n\nIf you have any questions & doubts about using me contact support.</b>",
            reply_markup=reply_markup)
        try:
            await db.connect_group(message.chat.id, message.from_user)
        except Exception as e:
            LOGGER.error(f"DB error connecting group: {e}")
    else:
        settings = await get_settings(message.chat.id)
        if settings["welcome"]:
            for u in message.new_chat_members:
                if (temp.MELCOW).get('welcome') is not None:
                    try:
                        await (temp.MELCOW['welcome']).delete()
                    except:
                        pass
                temp.MELCOW['welcome'] = await message.reply_video(
                                                 video=(MELCOW_VID),
                                                 caption=(script.MELCOW_ENG.format(u.mention, message.chat.title)),
                                                 reply_markup=InlineKeyboardMarkup(
                                                                         [[
                                                                           InlineKeyboardButton("📌 ᴄᴏɴᴛᴀᴄᴛ ꜱᴜᴘᴘᴏʀᴛ 📌", url=OWNER_LNK)
                                                                         ]]
                                                 ),
                                                 parse_mode=enums.ParseMode.HTML
                )
                
        if settings["auto_delete"]:
            await asyncio.sleep(600)
            await (temp.MELCOW['welcome']).delete()
                

@Client.on_message(filters.command('leave') & filters.user(ADMINS))
async def leave_a_chat(bot, message):
    if len(message.command) == 1:
        return await message.reply('Give me a chat id')
    chat = message.command[1]
    try:
        chat = int(chat)
    except:
        chat = chat
    try:
        buttons = [[
                  InlineKeyboardButton("📌 ᴄᴏɴᴛᴀᴄᴛ ꜱᴜᴘᴘᴏʀᴛ 📌", url=OWNER_LNK)
                  ]]
        reply_markup=InlineKeyboardMarkup(buttons)
        await bot.send_message(
            chat_id=chat,
            text='<b>ʜᴇʟʟᴏ ꜰʀɪᴇɴᴅꜱ, \nᴍʏ ᴀᴅᴍɪɴ ʜᴀꜱ ᴛᴏʟᴅ ᴍᴇ ᴛᴏ ʟᴇᴀᴠᴇ ꜰʀᴏᴍ ɢʀᴏᴜᴘ, ꜱᴏ ɪ ʜᴀᴠᴇ ᴛᴏ ɢᴏ !/nɪꜰ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴀᴅᴅ ᴍᴇ ᴀɢᴀɪɴ ᴄᴏɴᴛᴀᴄᴛ ꜱᴜᴘᴘᴏʀᴛ.</b>',
            reply_markup=reply_markup,
        )

        await bot.leave_chat(chat)
        await message.reply(f"left the chat `{chat}`")
    except Exception as e:
        await message.reply(f'Error - {e}')

@Client.on_message(filters.command('disable') & filters.user(ADMINS))
async def disable_chat(bot, message):
    if len(message.command) == 1:
        return await message.reply('Give me a chat id')
    r = message.text.split(None)
    if len(r) > 2:
        reason = message.text.split(None, 2)[2]
        chat = message.text.split(None, 2)[1]
    else:
        chat = message.command[1]
        reason = "No reason Provided"
    try:
        chat_ = int(chat)
    except:
        return await message.reply('Give Me A Valid Chat ID')
    cha_t = await db.get_chat(int(chat_))
    if not cha_t:
        return await message.reply("Chat Not Found In DB")
    if cha_t['is_disabled']:
        return await message.reply(f"This chat is already disabled:\nReason-<code> {cha_t['reason']} </code>")
    await db.disable_chat(int(chat_), reason)
    temp.BANNED_CHATS.append(int(chat_))
    await message.reply('Chat Successfully Disabled')
    try:
        buttons = [[
            InlineKeyboardButton('📌 ᴄᴏɴᴛᴀᴄᴛ ꜱᴜᴘᴘᴏʀᴛ 📌', url=OWNER_LNK)
        ]]
        reply_markup=InlineKeyboardMarkup(buttons)
        await bot.send_message(
            chat_id=chat_, 
            text=f'<b>ʜᴇʟʟᴏ ꜰʀɪᴇɴᴅꜱ, \nᴍʏ ᴀᴅᴍɪɴ ʜᴀꜱ ᴛᴏʟᴅ ᴍᴇ ᴛᴏ ʟᴇᴀᴠᴇ ꜰʀᴏᴍ ɢʀᴏᴜᴘ, ꜱᴏ ɪ ʜᴀᴠᴇ ᴛᴏ ɢᴏ ! \nɪꜰ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴀᴅᴅ ᴍᴇ ᴀɢᴀɪɴ ᴄᴏɴᴛᴀᴄᴛ ꜱᴜᴘᴘᴏʀᴛ..</b> \nReason : <code>{reason}</code>',
            reply_markup=reply_markup)
        await bot.leave_chat(chat_)
    except Exception as e:
        await message.reply(f"Error - {e}")


@Client.on_message(filters.command('enable') & filters.user(ADMINS))
async def re_enable_chat(bot, message):
    if len(message.command) == 1:
        return await message.reply('Give me a chat id')
    chat = message.command[1]
    try:
        chat_ = int(chat)
    except:
        return await message.reply('Give Me A Valid Chat ID')
    sts = await db.get_chat(int(chat))
    if not sts:
        return await message.reply("Chat Not Found In DB !")
    if not sts.get('is_disabled'):
        return await message.reply('This chat is not yet disabled.')
    await db.re_enable_chat(int(chat_))
    temp.BANNED_CHATS.remove(int(chat_))
    await message.reply("Chat Successfully re-enabled")

@Client.on_message(filters.command('stats') & filters.user(ADMINS))
async def get_stats(bot, message):
    """Enhanced stats command with better error handling and features"""
    status_msg = None
    try:
        # Send initial status message
        status_msg = await message.reply('📊 **Fetching System Statistics...**\n⏳ Please wait...')
        
        # Initialize variables with defaults
        total_users = total_chats = premium_count = 0
        file1 = file2 = 0
        db_size = db2_size = 0
        free = free2 = 0
        
        # Database size constants
        DB_SIZE = 512 * 1024 * 1024  # 512 MB
        
        # Fetch user and chat statistics
        try:
            total_users = await db.total_users_count()
            total_chats = await db.total_chat_count()
            premium_users = await db.all_premium_users()
            premium_count = len(premium_users) if isinstance(premium_users, list) else premium_users
        except Exception as e:
            LOGGER.error(f"Error fetching user/chat stats: {e}")
            # Continue with default values
        
        # Fetch primary database statistics
        try:
            file1 = await Media.count_documents()
            dbstats = await db_stats.command("dbStats")
            db_size = dbstats.get('dataSize', 0) + dbstats.get('indexSize', 0)
            free = max(0, DB_SIZE - db_size)
        except Exception as e:
            LOGGER.error(f"Error fetching primary DB stats: {e}")
        
        # System information
        uptime = get_readable_time(time() - botStartTime)
        
        try:
            ram_usage = psutil.virtual_memory().percent
            cpu_usage = psutil.cpu_percent(interval=1)  # 1 second interval for accuracy
            disk_usage = psutil.disk_usage('/').percent
        except Exception as e:
            LOGGER.error(f"Error fetching system stats: {e}")
            ram_usage = cpu_usage = disk_usage = 0
        
        # Handle multiple database scenario
        if MULTIPLE_DB:
            try:
                file2 = await Media2.count_documents()
                db2stats = await db2_stats.command("dbStats")
                db2_size = db2stats.get('dataSize', 0) + db2stats.get('indexSize', 0)
                free2 = max(0, DB_SIZE - db2_size)
                
                total_files = file1 + file2
                await status_msg.edit(script.MULTI_STATUS_TXT.format(
                    total_users, total_chats, premium_count, file1, get_size(db_size), get_size(free),
                    file2, get_size(db2_size), get_size(free2), uptime, ram_usage, cpu_usage, total_files
                ))
            except Exception as e:
                LOGGER.error(f"Error fetching secondary DB stats: {e}")
                # Fallback to single DB display
                await status_msg.edit(script.STATUS_TXT.format(
                    total_users, total_chats, premium_count, file1, get_size(db_size), 
                    get_size(free), uptime, ram_usage, cpu_usage
                ))
        else:
            # Single database scenario
            await status_msg.edit(script.STATUS_TXT.format(
                total_users, total_chats, premium_count, file1, get_size(db_size), 
                get_size(free), uptime, ram_usage, cpu_usage
            ))
            
    except Exception as e:
        LOGGER.error(f"Critical error in get_stats: {e}")
        error_msg = "❌ **Error Fetching Statistics**\n\nUnable to retrieve system statistics. Please check logs for details."
        
        if status_msg:
            try:
                await status_msg.edit(error_msg)
            except Exception as edit_error:
                LOGGER.error(f"Error editing status message: {edit_error}")
                await message.reply(error_msg)
        else:
            await message.reply(error_msg)


# Alternative enhanced version with additional features
@Client.on_message(filters.command('detailedstats') & filters.user(ADMINS))
async def get_detailed_stats(bot, message):
    """Detailed stats command with comprehensive system information"""
    try:
        status_msg = await message.reply('📊 **Generating Detailed Statistics...**')
        
        # Collect all statistics
        stats_data = {}
        
        # User & Chat Statistics
        try:
            stats_data.update({
                'total_users': await db.total_users_count(),
                'total_chats': await db.total_chat_count(),
                'premium_users': len(await db.all_premium_users()) if await db.all_premium_users() else 0
            })
        except Exception as e:
            LOGGER.error(f"User stats error: {e}")
            stats_data.update({'total_users': 0, 'total_chats': 0, 'premium_users': 0})
        
        # Database Statistics
        try:
            file1 = await Media.count_documents()
            dbstats = await db_stats.command("dbStats")
            db_size = dbstats.get('dataSize', 0) + dbstats.get('indexSize', 0)
            
            stats_data.update({
                'files_db1': file1,
                'db1_size': db_size,
                'db1_free': max(0, 512 * 1024 * 1024 - db_size)
            })
            
            if MULTIPLE_DB:
                file2 = await Media2.count_documents()
                db2stats = await db2_stats.command("dbStats")
                db2_size = db2stats.get('dataSize', 0) + db2stats.get('indexSize', 0)
                
                stats_data.update({
                    'files_db2': file2,
                    'db2_size': db2_size,
                    'db2_free': max(0, 512 * 1024 * 1024 - db2_size),
                    'total_files': file1 + file2
                })
            else:
                stats_data['total_files'] = file1
                
        except Exception as e:
            LOGGER.error(f"Database stats error: {e}")
        
        # System Statistics
        try:
            memory = psutil.virtual_memory()
            stats_data.update({
                'uptime': get_readable_time(time() - botStartTime),
                'ram_percent': memory.percent,
                'ram_used': get_size(memory.used),
                'ram_total': get_size(memory.total),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'cpu_count': psutil.cpu_count(),
                'disk_percent': psutil.disk_usage('/').percent,
                'boot_time': datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            LOGGER.error(f"System stats error: {e}")
            stats_data.update({
                'uptime': 'Unknown', 'ram_percent': 0, 'cpu_percent': 0,
                'ram_used': '0 B', 'ram_total': '0 B', 'cpu_count': 0,
                'disk_percent': 0, 'boot_time': 'Unknown'
            })
        
        # Format the detailed message
        detailed_msg = f"""📊 **DETAILED SYSTEM STATISTICS**

👥 **User Statistics:**
├ Total Users: `{stats_data.get('total_users', 0):,}`
├ Total Chats: `{stats_data.get('total_chats', 0):,}`
└ Premium Users: `{stats_data.get('premium_users', 0):,}`

🗃️ **Database Statistics:**
├ Total Files: `{stats_data.get('total_files', 0):,}`
├ DB1 Files: `{stats_data.get('files_db1', 0):,}`
├ DB1 Size: `{get_size(stats_data.get('db1_size', 0))}`
├ DB1 Free: `{get_size(stats_data.get('db1_free', 0))}`"""

        if MULTIPLE_DB and 'files_db2' in stats_data:
            detailed_msg += f"""
├ DB2 Files: `{stats_data.get('files_db2', 0):,}`
├ DB2 Size: `{get_size(stats_data.get('db2_size', 0))}`
└ DB2 Free: `{get_size(stats_data.get('db2_free', 0))}`"""
        
        detailed_msg += f"""

💻 **System Statistics:**
├ Uptime: `{stats_data.get('uptime', 'Unknown')}`
├ CPU Usage: `{stats_data.get('cpu_percent', 0):.1f}%`
├ CPU Cores: `{stats_data.get('cpu_count', 0)}`
├ RAM Usage: `{stats_data.get('ram_percent', 0):.1f}%`
├ RAM Used: `{stats_data.get('ram_used', '0 B')}`
├ RAM Total: `{stats_data.get('ram_total', '0 B')}`
├ Disk Usage: `{stats_data.get('disk_percent', 0):.1f}%`
└ Boot Time: `{stats_data.get('boot_time', 'Unknown')}`

🕐 **Last Updated:** `{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`"""
        
        await status_msg.edit(detailed_msg)
        
    except Exception as e:
        LOGGER.error(f"Error in detailed stats: {e}")
        await message.reply("❌ **Error generating detailed statistics**\nPlease check logs for more information.")


# Add comprehensive user statistics commands
@Client.on_message(filters.command(['userstats', 'users']) & filters.user(ADMINS))
async def get_user_stats(bot, message):
    """Detailed user statistics command"""
    try:
        status_msg = await message.reply('👥 **Analyzing User Data...**')
        
        # Fetch comprehensive user data
        user_data = {}
        
        try:
            # Basic counts
            user_data['total_users'] = await db.total_users_count()
            user_data['total_chats'] = await db.total_chat_count()
            user_data['premium_users'] = len(await db.all_premium_users())
            
            # Activity metrics
            user_data['active_today'] = await db.get_active_users(days=1)
            user_data['active_week'] = await db.get_active_users(days=7)
            user_data['active_month'] = await db.get_active_users(days=30)
            user_data['inactive_30days'] = await db.get_inactive_users(days=30)
            
            # Growth metrics
            user_data['joined_today'] = await db.get_new_users_count(days=1)
            user_data['joined_week'] = await db.get_new_users_count(days=7)
            user_data['joined_month'] = await db.get_new_users_count(days=30)
            
            # Status categories
            user_data['banned_users'] = await db.get_banned_users_count()
            user_data['verified_users'] = await db.get_verified_users_count()
            user_data['warning_users'] = await db.get_users_with_warnings()
            
            # Engagement metrics
            user_data['total_requests'] = await db.get_total_requests_count()
            user_data['requests_today'] = await db.get_total_requests_count(days=1)
            user_data['avg_requests_per_user'] = user_data['total_requests'] / max(user_data['total_users'], 1)
            
            # User retention
            user_data['retention_7day'] = await db.get_user_retention(days=7)
            user_data['retention_30day'] = await db.get_user_retention(days=30)
            
            # Geographic data
            user_data['top_countries'] = await db.get_top_countries(limit=10)
            user_data['top_languages'] = await db.get_top_languages(limit=10)
            
        except Exception as e:
            LOGGER.error(f"Error fetching user data: {e}")
            # Set defaults
            for key in ['total_users', 'total_chats', 'premium_users', 'active_today', 
                       'active_week', 'active_month', 'joined_today', 'joined_week', 
                       'joined_month', 'banned_users', 'verified_users']:
                user_data[key] = 0
        
        # Calculate percentages and ratios
        total = max(user_data.get('total_users', 1), 1)
        premium_rate = (user_data.get('premium_users', 0) / total) * 100
        activity_rate = (user_data.get('active_month', 0) / total) * 100
        growth_rate = (user_data.get('joined_month', 0) / max(total - user_data.get('joined_month', 0), 1)) * 100
        
        # Format comprehensive user stats message
        user_stats_msg = f"""👥 **COMPREHENSIVE USER ANALYTICS**

📊 **Overview:**
├ **Total Users:** `{user_data.get('total_users', 0):,}`
├ **Premium Users:** `{user_data.get('premium_users', 0):,}` ({premium_rate:.1f}%)
├ **Verified Users:** `{user_data.get('verified_users', 0):,}`
├ **Banned Users:** `{user_data.get('banned_users', 0):,}`
└ **Users with Warnings:** `{user_data.get('warning_users', 0):,}`

📈 **Activity Metrics:**
├ **Active Today:** `{user_data.get('active_today', 0):,}` ({(user_data.get('active_today', 0)/total*100):.1f}%)
├ **Active This Week:** `{user_data.get('active_week', 0):,}` ({(user_data.get('active_week', 0)/total*100):.1f}%)
├ **Active This Month:** `{user_data.get('active_month', 0):,}` ({activity_rate:.1f}%)
└ **Inactive (30d):** `{user_data.get('inactive_30days', 0):,}`

🆕 **Growth Statistics:**
├ **Joined Today:** `{user_data.get('joined_today', 0):,}`
├ **Joined This Week:** `{user_data.get('joined_week', 0):,}`
├ **Joined This Month:** `{user_data.get('joined_month', 0):,}`
└ **Growth Rate:** `{growth_rate:.1f}%`

🔄 **Retention Rates:**
├ **7-Day Retention:** `{user_data.get('retention_7day', 0):.1f}%`
└ **30-Day Retention:** `{user_data.get('retention_30day', 0):.1f}%`

💬 **Usage Analytics:**
├ **Total Requests:** `{user_data.get('total_requests', 0):,}`
├ **Requests Today:** `{user_data.get('requests_today', 0):,}`
├ **Avg Requests/User:** `{user_data.get('avg_requests_per_user', 0):.1f}`
└ **Daily Active Rate:** `{(user_data.get('active_today', 0)/max(user_data.get('active_month', 1), 1)*100):.1f}%`"""

        # Add top countries if available
        if user_data.get('top_countries'):
            user_stats_msg += "\n\n🌍 **Top Countries:**"
            for i, (country, count) in enumerate(user_data['top_countries'][:5], 1):
                percentage = (count / total) * 100
                user_stats_msg += f"\n{i}. **{country}:** `{count:,}` ({percentage:.1f}%)"

        # Add top languages if available
        if user_data.get('top_languages'):
            user_stats_msg += "\n\n🗣️ **Top Languages:**"
            for i, (language, count) in enumerate(user_data['top_languages'][:5], 1):
                percentage = (count / total) * 100
                user_stats_msg += f"\n{i}. **{language}:** `{count:,}` ({percentage:.1f}%)"

        user_stats_msg += f"\n\n🕐 **Report Generated:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        
        await status_msg.edit(user_stats_msg)
        
    except Exception as e:
        LOGGER.error(f"Error in user stats: {e}")
        await message.reply("❌ **Error generating user statistics**\nPlease check logs for details.")


@Client.on_message(filters.command(['topusers', 'leaderboard']) & filters.user(ADMINS))
async def get_top_users(bot, message):
    """Show top users leaderboard"""
    try:
        status_msg = await message.reply('🏆 **Generating User Leaderboard...**')
        
        # Get different top user categories
        top_active = await db.get_top_active_users(limit=10)
        top_requests = await db.get_top_users_by_requests(limit=10)
        recent_premium = await db.get_recent_premium_users(limit=5)
        top_referrers = await db.get_top_referrers(limit=5)
        
        leaderboard_msg = f"""🏆 **USER LEADERBOARD**

🔥 **Most Active Users (Last 30 Days):**"""
        
        for i, user in enumerate(top_active[:10], 1):
            name = user.get('name', 'Unknown User')[:25]
            activity_score = user.get('activity_score', 0)
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            leaderboard_msg += f"\n{medal} `{name}`: {activity_score:,} pts"

        leaderboard_msg += f"\n\n📊 **Most Requests:**"
        for i, user in enumerate(top_requests[:5], 1):
            name = user.get('name', 'Unknown User')[:25]
            requests = user.get('requests', 0)
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            leaderboard_msg += f"\n{medal} `{name}`: {requests:,} requests"

        if recent_premium:
            leaderboard_msg += f"\n\n💎 **Recent Premium Users:**"
            for user in recent_premium:
                name = user.get('name', 'Unknown User')[:25]
                date = user.get('premium_date', 'Unknown')
                leaderboard_msg += f"\n💎 `{name}` - {date}"

        if top_referrers:
            leaderboard_msg += f"\n\n👥 **Top Referrers:**"
            for i, user in enumerate(top_referrers, 1):
                name = user.get('name', 'Unknown User')[:25]
                referrals = user.get('referrals', 0)
                leaderboard_msg += f"\n{i}. `{name}`: {referrals:,} referrals"

        leaderboard_msg += f"\n\n🕐 **Updated:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        
        await status_msg.edit(leaderboard_msg)
        
    except Exception as e:
        LOGGER.error(f"Error generating leaderboard: {e}")
        await message.reply("❌ **Error generating leaderboard**\nPlease check logs for details.")


@Client.on_message(filters.command(['analytics', 'insights']) & filters.user(ADMINS))
async def get_user_analytics(bot, message):
    """Advanced user analytics and insights"""
    try:
        status_msg = await message.reply('📊 **Generating Advanced Analytics...**')
        
        # Fetch advanced analytics data
        analytics_data = {}
        
        try:
            # Time-based analysis
            analytics_data['hourly_activity'] = await db.get_hourly_activity_pattern()
            analytics_data['daily_activity'] = await db.get_daily_activity_pattern()
            analytics_data['monthly_growth'] = await db.get_monthly_growth_data(months=6)
            
            # User behavior analysis
            analytics_data['avg_session_duration'] = await db.get_average_session_duration()
            analytics_data['bounce_rate'] = await db.get_bounce_rate()
            analytics_data['feature_usage'] = await db.get_feature_usage_stats()
            
            # Cohort analysis
            analytics_data['user_cohorts'] = await db.get_user_cohort_analysis()
            analytics_data['churn_rate'] = await db.get_churn_rate()
            
        except Exception as e:
            LOGGER.error(f"Error fetching analytics data: {e}")
            analytics_data = {}
        
        # Peak activity hours
        peak_hours = analytics_data.get('hourly_activity', {})
        peak_hour = max(peak_hours, key=peak_hours.get) if peak_hours else "Unknown"
        
        # Most active day
        daily_data = analytics_data.get('daily_activity', {})
        peak_day = max(daily_data, key=daily_data.get) if daily_data else "Unknown"
        
        analytics_msg = f"""📊 **ADVANCED USER ANALYTICS**

🕐 **Activity Patterns:**
├ **Peak Hour:** `{peak_hour}:00` ({peak_hours.get(peak_hour, 0):,} users)
├ **Most Active Day:** `{peak_day}` ({daily_data.get(peak_day, 0):,} users)
├ **Avg Session Duration:** `{analytics_data.get('avg_session_duration', 0):.1f} minutes`
└ **Bounce Rate:** `{analytics_data.get('bounce_rate', 0):.1f}%`

📈 **User Behavior:**
├ **Churn Rate:** `{analytics_data.get('churn_rate', 0):.1f}%`
├ **Return Rate:** `{100 - analytics_data.get('churn_rate', 0):.1f}%`
└ **Engagement Score:** `{analytics_data.get('engagement_score', 0):.1f}/10`

🎯 **Feature Usage (Top 5):**"""

        # Add feature usage if available
        feature_usage = analytics_data.get('feature_usage', {})
        if feature_usage:
            sorted_features = sorted(feature_usage.items(), key=lambda x: x[1], reverse=True)
            for i, (feature, usage) in enumerate(sorted_features[:5], 1):
                analytics_msg += f"\n{i}. **{feature}:** `{usage:,}` uses"
        
        # Add monthly growth trend
        monthly_growth = analytics_data.get('monthly_growth', [])
        if monthly_growth:
            analytics_msg += f"\n\n📅 **6-Month Growth Trend:**"
            for month_data in monthly_growth[-6:]:
                month = month_data.get('month', 'Unknown')
                growth = month_data.get('growth_percentage', 0)
                new_users = month_data.get('new_users', 0)
                trend_emoji = "📈" if growth > 0 else "📉" if growth < 0 else "➡️"
                analytics_msg += f"\n{trend_emoji} **{month}:** +{new_users:,} users ({growth:+.1f}%)"
        
        analytics_msg += f"\n\n🕐 **Analysis Generated:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        
        await status_msg.edit(analytics_msg)
        
    except Exception as e:
        LOGGER.error(f"Error generating analytics: {e}")
        await message.reply("❌ **Error generating analytics**\nPlease check logs for details.")


# Database helper functions that you'll need to implement
# These are example function signatures - implement based on your database structure

async def get_active_users(days=30):
    """Get count of users active in last N days"""
    # Implementation depends on your database schema
    pass

async def get_new_users_count(days=30):
    """Get count of users who joined in last N days"""
    pass

async def get_banned_users_count():
    """Get count of banned users"""
    pass

async def get_verified_users_count():
    """Get count of verified users"""
    pass

async def get_private_chats_count():
    """Get count of private chats"""
    pass

async def get_group_chats_count():
    """Get count of group chats"""
    pass

async def get_top_active_users(limit=10):
    """Get list of most active users"""
    pass

async def get_users_by_language():
    """Get user distribution by language"""
    pass

async def get_users_by_country():
    """Get user distribution by country"""
    pass
        

@Client.on_message(filters.command('invite') & filters.user(ADMINS))
async def gen_invite(bot, message):
    if len(message.command) == 1:
        return await message.reply('Give me a chat id')
    chat = message.command[1]
    try:
        chat = int(chat)
    except:
        return await message.reply('Give Me A Valid Chat ID')
    try:
        link = await bot.create_chat_invite_link(chat)
    except ChatAdminRequired:
        return await message.reply("Invite Link Generation Failed, Iam Not Having Sufficient Rights")
    except Exception as e:
        return await message.reply(f'Error {e}')
    await message.reply(f'Here is your Invite Link {link.invite_link}')

@Client.on_message(filters.command('ban') & filters.user(ADMINS))
async def ban_a_user(bot, message):
    if len(message.command) == 1:
        return await message.reply('Give me a user id / username')
    r = message.text.split(None)
    if len(r) > 2:
        reason = message.text.split(None, 2)[2]
        chat = message.text.split(None, 2)[1]
    else:
        chat = message.command[1]
        reason = "No reason Provided"
    try:
        chat = int(chat)
    except:
        pass
    try:
        k = await bot.get_users(chat)
    except PeerIdInvalid:
        return await message.reply("This is an invalid user, make sure I have met him before.")
    except IndexError:
        return await message.reply("This might be a channel, make sure its a user.")
    except Exception as e:
        return await message.reply(f'Error - {e}')
    else:
        jar = await db.get_ban_status(k.id)
        if jar['is_banned']:
            return await message.reply(f"{k.mention} is already banned\nReason: {jar['ban_reason']}")
        await db.ban_user(k.id, reason)
        temp.BANNED_USERS.append(k.id)
        await message.reply(f"Successfully banned {k.mention}")
    
@Client.on_message(filters.command('unban') & filters.user(ADMINS))
async def unban_a_user(bot, message):
    if len(message.command) == 1:
        return await message.reply('Give me a user id / username')
    r = message.text.split(None)
    if len(r) > 2:
        reason = message.text.split(None, 2)[2]
        chat = message.text.split(None, 2)[1]
    else:
        chat = message.command[1]
        reason = "No reason Provided"
    try:
        chat = int(chat)
    except:
        pass
    try:
        k = await bot.get_users(chat)
    except PeerIdInvalid:
        return await message.reply("This is an invalid user, make sure ia have met him before.")
    except IndexError:
        return await message.reply("Thismight be a channel, make sure its a user.")
    except Exception as e:
        return await message.reply(f'Error - {e}')
    else:
        jar = await db.get_ban_status(k.id)
        if not jar['is_banned']:
            return await message.reply(f"{k.mention} is not yet banned.")
        await db.remove_ban(k.id)
        temp.BANNED_USERS.remove(k.id)
        await message.reply(f"Successfully unbanned {k.mention}")
 
@Client.on_message(filters.command('users') & filters.user(ADMINS))
async def list_users(bot, message):
    raju = await message.reply('Getting List Of Users')
    users = await db.get_all_users()
    out = "Users Saved In DB Are:\n\n"
    async for user in users:
        out += f"<a href=tg://user?id={user['id']}>{user['name']}</a>"
        if user['ban_status']['is_banned']:
            out += '( Banned User )'
        out += '\n'
    try:
        await raju.edit_text(out)
    except MessageTooLong:
        with open('users.txt', 'w+') as outfile:
            outfile.write(out)
        await message.reply_document('users.txt', caption="List Of Users")

@Client.on_message(filters.command('chats') & filters.user(ADMINS))
async def list_chats(bot, message):
    raju = await message.reply('Getting List Of chats')
    chats = await db.get_all_chats()
    out = "Chats Saved In DB Are:\n\n"
    async for chat in chats:
        out += f"**Title:** `{chat['title']}`\n**- ID:** `{chat['id']}`"
        if chat['chat_status']['is_disabled']:
            out += '( Disabled Chat )'
        out += '\n'
    try:
        await raju.edit_text(out)
    except MessageTooLong:
        with open('chats.txt', 'w+') as outfile:
            outfile.write(out)
        await message.reply_document('chats.txt', caption="List Of Chats")
        
#user status
