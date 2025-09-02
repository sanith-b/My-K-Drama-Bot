from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors.exceptions.bad_request_400 import MessageTooLong, PeerIdInvalid
from info import *
from database.users_chats_db import db, db2
from database.ia_filterdb import Media, Media2, db as db_stats, db2 as db2_stats
from utils import get_size, temp, get_settings, get_readable_time
from Script import script
from pyrogram.errors import ChatAdminRequired
import asyncio
import psutil
import time
from time import time
from bot import botStartTime
from logging_helper import LOGGER

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
    try:
        SilentXBotz = await message.reply('ᴀᴄᴄᴇꜱꜱɪɴɢ ꜱᴛᴀᴛᴜꜱ ᴅᴇᴛᴀɪʟꜱ...')
        total_users = await db.total_users_count()
        totl_chats = await db.total_chat_count()
        premium = await db.all_premium_users()
        file1 = await Media.count_documents()
        DB_SIZE = 512 * 1024 * 1024
        dbstats = await db_stats.command("dbStats")
        db_size = dbstats['dataSize'] + dbstats['indexSize']
        free = DB_SIZE - db_size
        uptime = get_readable_time(time() - botStartTime)
        ram = psutil.virtual_memory().percent
        cpu = psutil.cpu_percent()
        if MULTIPLE_DB == False:
            await SilentXBotz.edit(script.STATUS_TXT.format(
                total_users, totl_chats, premium, file1, get_size(db_size), get_size(free), uptime, ram, cpu))                                               
            return
        file2 = await Media2.count_documents()
        db2stats = await db2_stats.command("dbStats")
        db2_size = db2stats['dataSize'] + db2stats['indexSize']
        free2 = DB_SIZE - db2_size
        await SilentXBotz.edit(script.MULTI_STATUS_TXT.format(
            total_users, totl_chats, premium, file1, get_size(db_size), get_size(free),
            file2, get_size(db2_size), get_size(free2), uptime, ram, cpu, (int(file1) + int(file2))
        ))
    except Exception as e:
        LOGGER.error(e)
        

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
@Client.on_message(filters.command('status') & filters.user(ADMINS))
async def get_stats(bot, message):
    try:
        SilentXBotz = await message.reply('ᴀᴄᴄᴇꜱꜱɪɴɢ ꜱᴛᴀᴛᴜꜱ ᴅᴇᴛᴀɪʟꜱ...')
        
        # Basic stats
        total_users = await db.total_users_count()
        totl_chats = await db.total_chat_count()
        premium = await db.all_premium_users()
        
        # Live and activity stats
        live_users = await db.get_live_users_count() if hasattr(db, 'get_live_users_count') else 0
        active_users_7d = await db.active_users_week() if hasattr(db, 'active_users_week') else 0
        banned_users = await db.banned_users_count() if hasattr(db, 'banned_users_count') else 0
        
        # New user registration stats
        new_users_today = await db.new_users_today() if hasattr(db, 'new_users_today') else 0
        new_users_week = await db.new_users_this_week() if hasattr(db, 'new_users_this_week') else 0
        new_users_month = await db.new_users_this_month() if hasattr(db, 'new_users_this_month') else 0
        new_users_year = await db.new_users_this_year() if hasattr(db, 'new_users_this_year') else 0
        
        # File and media stats
        file1 = await Media.count_documents()
        
        # Database configuration and limits
        DB_SIZE = getattr(config, 'DB_SIZE_LIMIT', 512) * 1024 * 1024  # Make configurable
        
        # Database stats with error handling
        try:
            dbstats = await db_stats.command("dbStats")
            db_size = dbstats.get('dataSize', 0) + dbstats.get('indexSize', 0)
            collections_count = dbstats.get('collections', 0)
            indexes_count = dbstats.get('indexes', 0)
        except Exception as db_error:
            LOGGER.warning(f"Database stats error: {db_error}")
            db_size = 0
            collections_count = 0
            indexes_count = 0
            
        free = max(0, DB_SIZE - db_size)  # Prevent negative values
        db_usage_percent = (db_size / DB_SIZE * 100) if DB_SIZE > 0 else 0
        
        # System metrics with enhanced details
        uptime = get_readable_time(time() - botStartTime)
        ram = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)  # 1 second interval for accuracy
        disk = psutil.disk_usage('/')
        
        # Network stats (if available)
        try:
            network = psutil.net_io_counters()
            bytes_sent = get_size(network.bytes_sent)
            bytes_recv = get_size(network.bytes_recv)
        except:
            bytes_sent = bytes_recv = "N/A"
        
        # Bot-specific metrics
        bot_info = await bot.get_me()
        
        # Enhanced status text with more details
        enhanced_stats = f"""
📊 **BOT STATISTICS**

👥 **User Statistics:**
• Total Users: `{total_users:,}`
• Live Users: `{live_users:,}` 🟢
• Total Chats: `{totl_chats:,}`
• Premium Users: `{premium:,}` ⭐
• Active (7 days): `{active_users_7d:,}`
• Banned Users: `{banned_users:,}` 🚫

📈 **New User Growth:**
• Today: `{new_users_today:,}`
• This Week: `{new_users_week:,}`
• This Month: `{new_users_month:,}`
• This Year: `{new_users_year:,}`

📁 **Database Statistics:**
• Files in DB1: `{file1:,}`
• DB Size: `{get_size(db_size)}` ({db_usage_percent:.1f}%)
• Free Space: `{get_size(free)}`
• Collections: `{collections_count}`
• Indexes: `{indexes_count}`

🖥️ **System Performance:**
• Uptime: `{uptime}`
• CPU Usage: `{cpu:.1f}%`
• RAM Usage: `{ram.percent:.1f}%` ({get_size(ram.used)}/{get_size(ram.total)})
• Disk Usage: `{disk.percent:.1f}%` ({get_size(disk.used)}/{get_size(disk.total)})

🌐 **Network Stats:**
• Data Sent: `{bytes_sent}`
• Data Received: `{bytes_recv}`

🤖 **Bot Information:**
• Bot Username: @{bot_info.username}
• Bot ID: `{bot_info.id}`
• Python Version: `{sys.version.split()[0]}`
• Pyrogram Version: `{pyrogram.__version__}`
"""

        if MULTIPLE_DB:
            try:
                file2 = await Media2.count_documents()
                db2stats = await db2_stats.command("dbStats")
                db2_size = db2stats.get('dataSize', 0) + db2stats.get('indexSize', 0)
                free2 = max(0, DB_SIZE - db2_size)
                db2_usage_percent = (db2_size / DB_SIZE * 100) if DB_SIZE > 0 else 0
                
                enhanced_stats += f"""
📁 **Secondary Database:**
• Files in DB2: `{file2:,}`
• DB2 Size: `{get_size(db2_size)}` ({db2_usage_percent:.1f}%)
• DB2 Free: `{get_size(free2)}`
• Total Files: `{file1 + file2:,}`
"""
            except Exception as db2_error:
                LOGGER.warning(f"DB2 stats error: {db2_error}")
                enhanced_stats += "\n📁 **Secondary Database:** `Error fetching stats`"
        
        # Performance warnings
        warnings = []
        if ram.percent > 80:
            warnings.append("⚠️ High RAM usage")
        if cpu > 80:
            warnings.append("⚠️ High CPU usage")
        if db_usage_percent > 90:
            warnings.append("⚠️ Database nearly full")
        if disk.percent > 90:
            warnings.append("⚠️ Disk space low")
            
        if warnings:
            enhanced_stats += f"\n\n🚨 **Warnings:**\n" + "\n".join(f"• {w}" for w in warnings)
        
        # Add refresh timestamp
        enhanced_stats += f"\n\n🔄 **Last Updated:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}`"
        
        await SilentXBotz.edit(enhanced_stats, disable_web_page_preview=True)
        
    except Exception as e:
        error_msg = f"❌ **Error fetching stats:**\n`{str(e)}`"
        try:
            await SilentXBotz.edit(error_msg)
        except:
            await message.reply(error_msg)
        LOGGER.error(f"Stats command error: {e}", exc_info=True)


# Additional helper function for better error handling
async def safe_db_query(query_func, default_value=0):
    """Safely execute database queries with fallback"""
    try:
        result = await query_func()
        return result if result is not None else default_value
    except Exception as e:
        LOGGER.warning(f"Database query failed: {e}")
        return default_value


# Database methods to implement in your database class
class Database:
    
    async def get_live_users_count(self):
        """Count users who were active in the last 5 minutes"""
        from datetime import datetime, timedelta
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)
        return await self.col.count_documents({
            "last_active": {"$gte": cutoff_time}
        })
    
    async def new_users_today(self):
        """Count users who joined today"""
        from datetime import datetime, timedelta
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.col.count_documents({
            "date": {"$gte": today_start}
        })
    
    async def new_users_this_week(self):
        """Count users who joined this week"""
        from datetime import datetime, timedelta
        week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.col.count_documents({
            "date": {"$gte": week_start}
        })
    
    async def new_users_this_month(self):
        """Count users who joined this month"""
        from datetime import datetime
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return await self.col.count_documents({
            "date": {"$gte": month_start}
        })
    
    async def new_users_this_year(self):
        """Count users who joined this year"""
        from datetime import datetime
        year_start = datetime.utcnow().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return await self.col.count_documents({
            "date": {"$gte": year_start}
        })
    
    async def active_users_week(self):
        """Count users who were active in the last 7 days"""
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        return await self.col.count_documents({
            "last_active": {"$gte": week_ago}
        })
    
    async def banned_users_count(self):
        """Count banned users"""
        return await self.col.count_documents({
            "banned": True
        })
    
    async def update_user_activity(self, user_id):
        """Update user's last activity timestamp"""
        from datetime import datetime
        await self.col.update_one(
            {"id": user_id},
            {"$set": {"last_active": datetime.utcnow()}},
            upsert=True
        )


# User activity tracker - Add this to your main bot file
@Client.on_message()
async def track_user_activity(client, message):
    """Track user activity for live users count"""
    if message.from_user:
        try:
            await db.update_user_activity(message.from_user.id)
        except Exception as e:
            LOGGER.error(f"Failed to update user activity: {e}")
    
    # Continue with your existing message handlers
    # This should be placed before other message handlers


# Alternative optimized version with batching
class UserActivityTracker:
    def __init__(self):
        self.activity_queue = set()
        self.last_batch_update = time()
        
    async def track_activity(self, user_id):
        """Add user to activity queue"""
        self.activity_queue.add(user_id)
        
        # Batch update every 30 seconds
        if time() - self.last_batch_update > 30:
            await self.flush_activity_queue()
    
    async def flush_activity_queue(self):
        """Batch update user activities"""
        if not self.activity_queue:
            return
            
        try:
            from datetime import datetime
            current_time = datetime.utcnow()
            
            # Bulk update all users at once
            await db.col.update_many(
                {"id": {"$in": list(self.activity_queue)}},
                {"$set": {"last_active": current_time}}
            )
            
            self.activity_queue.clear()
            self.last_batch_update = time()
            
        except Exception as e:
            LOGGER.error(f"Failed to batch update activities: {e}")


# Initialize the tracker
activity_tracker = UserActivityTracker()

@Client.on_message()
async def optimized_activity_tracker(client, message):
    """Optimized user activity tracking"""
    if message.from_user:
        await activity_tracker.track_activity(message.from_user.id)


# Enhanced version with caching (optional)
import asyncio
from functools import wraps

def cache_stats(duration=60):  # Cache for 60 seconds
    def decorator(func):
        cache = {"data": None, "timestamp": 0}
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_time = time()
            if current_time - cache["timestamp"] > duration:
                cache["data"] = await func(*args, **kwargs)
                cache["timestamp"] = current_time
            return cache["data"]
        return wrapper
    return decorator


@cache_stats(duration=30)  # Cache system stats for 30 seconds
async def get_system_stats():
    """Get system statistics with caching"""
    return {
        'ram': psutil.virtual_memory(),
        'cpu': psutil.cpu_percent(interval=1),
        'disk': psutil.disk_usage('/'),
        'network': psutil.net_io_counters()
    }
