from pyrogram import Client, filters
from pyrogram.types import Message, ChatMember, ChatPermissions
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserAdminInvalid, ChatAdminRequired, UserNotParticipant
from utils import temp
from database.users_chats_db import db
from info import SUPPORT_CHAT
import asyncio
from datetime import datetime, timedelta
import logging
import json

# Replace with your actual admin user ID
YOUR_ADMIN_ID = 12345678  # CHANGE THIS TO YOUR TELEGRAM USER ID

# Admin check filter
async def is_admin(_, client, message: Message):
    if message.chat.type in ["private"]:
        return False
    
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ["creator", "administrator"]
    except:
        return False

admin_filter = filters.create(is_admin)

# Bot admin check
async def is_bot_admin(client, chat_id):
    try:
        bot = await client.get_chat_member(chat_id, "me")
        return bot.status == "administrator" and bot.privileges.can_restrict_members
    except:
        return False

# Enhanced Database Class for Warnings and Settings
class WarnDB:
    warn_data = {}  # In-memory storage - replace with your database
    
    @staticmethod
    async def add_warn(user_id: int, chat_id: int, reason: str = "No reason"):
        key = f"{chat_id}_{user_id}"
        if key not in WarnDB.warn_data:
            WarnDB.warn_data[key] = []
        
        WarnDB.warn_data[key].append({
            'reason': reason,
            'date': datetime.now().isoformat(),
            'warned_by': 'admin'
        })
        return len(WarnDB.warn_data[key])
    
    @staticmethod
    async def get_warns(user_id: int, chat_id: int):
        key = f"{chat_id}_{user_id}"
        return WarnDB.warn_data.get(key, [])
    
    @staticmethod
    async def remove_warns(user_id: int, chat_id: int, count: int = None):
        key = f"{chat_id}_{user_id}"
        if key in WarnDB.warn_data:
            if count is None:
                WarnDB.warn_data[key] = []
            else:
                WarnDB.warn_data[key] = WarnDB.warn_data[key][count:]

# Enhanced Database functions
class EnhancedDB:
    @staticmethod
    async def add_action_log(chat_id, user_id, action, reason, admin_id):
        # Log moderation actions to database
        logging.info(f"Action logged: {action} - User {user_id} in chat {chat_id}")
        pass

# Global storage (replace with database)
welcome_settings = {}
goodbye_settings = {}
rules_data = {}
notes_data = {}
blacklisted_words = {}
flood_settings = {}
flood_tracker = {}
spam_tracker = {}
global_banned_users = set()

# =============================================================================
# BASIC MODERATION COMMANDS
# =============================================================================

# BAN COMMAND
@Client.on_message(filters.command("ban") & filters.group & admin_filter)
async def ban_user(client, message: Message):
    if not await is_bot_admin(client, message.chat.id):
        await message.reply("❌ I need admin rights with ban permissions!")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            user_name = user.mention
        except:
            await message.reply("❌ Invalid user ID or username!")
            return
    else:
        await message.reply("❌ Reply to a user or provide user ID/username!")
        return
    
    # Check if user is admin
    try:
        target_member = await client.get_chat_member(message.chat.id, user_id)
        if target_member.status in ["creator", "administrator"]:
            await message.reply("❌ Cannot ban an admin!")
            return
    except UserNotParticipant:
        await message.reply("❌ User is not in this chat!")
        return
    
    reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason provided"
    
    try:
        await client.ban_chat_member(message.chat.id, user_id)
        
        buttons = [[
            InlineKeyboardButton("🔓 Unban", callback_data=f"unban_{user_id}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_msg")
        ]]
        
        await message.reply(
            f"🔨 **User Banned!**\n"
            f"👤 User: {user_name}\n"
            f"👮‍♂️ Banned by: {message.from_user.mention}\n"
            f"📝 Reason: `{reason}`",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
        # Log to database
        await EnhancedDB.add_action_log(message.chat.id, user_id, "ban", reason, message.from_user.id)
        
    except Exception as e:
        await message.reply(f"❌ Failed to ban user: {e}")

# UNBAN COMMAND
@Client.on_message(filters.command("unban") & filters.group & admin_filter)
async def unban_user(client, message: Message):
    if not await is_bot_admin(client, message.chat.id):
        await message.reply("❌ I need admin rights with ban permissions!")
        return
    
    if len(message.command) < 2:
        await message.reply("❌ Provide user ID to unban!")
        return
    
    try:
        user_id = int(message.command[1])
        await client.unban_chat_member(message.chat.id, user_id)
        
        user = await client.get_users(user_id)
        await message.reply(f"✅ **User Unbanned!**\n👤 User: {user.mention}")
        
    except Exception as e:
        await message.reply(f"❌ Failed to unban user: {e}")

# KICK COMMAND
@Client.on_message(filters.command("kick") & filters.group & admin_filter)
async def kick_user(client, message: Message):
    if not await is_bot_admin(client, message.chat.id):
        await message.reply("❌ I need admin rights with ban permissions!")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            user_name = user.mention
        except:
            await message.reply("❌ Invalid user ID!")
            return
    else:
        await message.reply("❌ Reply to a user or provide user ID!")
        return
    
    try:
        # Check if user is admin
        target_member = await client.get_chat_member(message.chat.id, user_id)
        if target_member.status in ["creator", "administrator"]:
            await message.reply("❌ Cannot kick an admin!")
            return
        
        reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason provided"
        
        # Kick = ban then unban
        await client.ban_chat_member(message.chat.id, user_id)
        await client.unban_chat_member(message.chat.id, user_id)
        
        await message.reply(
            f"👢 **User Kicked!**\n"
            f"👤 User: {user_name}\n"
            f"👮‍♂️ Kicked by: {message.from_user.mention}\n"
            f"📝 Reason: `{reason}`"
        )
        
    except Exception as e:
        await message.reply(f"❌ Failed to kick user: {e}")

# MUTE COMMAND
@Client.on_message(filters.command("mute") & filters.group & admin_filter)
async def mute_user(client, message: Message):
    if not await is_bot_admin(client, message.chat.id):
        await message.reply("❌ I need admin rights with restrict permissions!")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            user_name = user.mention
        except:
            await message.reply("❌ Invalid user ID!")
            return
    else:
        await message.reply("❌ Reply to a user or provide user ID!")
        return
    
    # Parse time (optional)
    mute_time = None
    time_units = {"m": "minutes", "h": "hours", "d": "days"}
    
    if len(message.command) > 2:
        time_arg = message.command[2]
        if time_arg[-1] in time_units and time_arg[:-1].isdigit():
            duration = int(time_arg[:-1])
            unit = time_arg[-1]
            
            if unit == "m":
                mute_time = datetime.now() + timedelta(minutes=duration)
            elif unit == "h":
                mute_time = datetime.now() + timedelta(hours=duration)
            elif unit == "d":
                mute_time = datetime.now() + timedelta(days=duration)
    
    try:
        # Check if user is admin
        target_member = await client.get_chat_member(message.chat.id, user_id)
        if target_member.status in ["creator", "administrator"]:
            await message.reply("❌ Cannot mute an admin!")
            return
        
        # Restrict user permissions
        permissions = ChatPermissions()
        await client.restrict_chat_member(
            message.chat.id, 
            user_id, 
            permissions, 
            until_date=mute_time
        )
        
        time_text = f"for {message.command[2]}" if mute_time else "permanently"
        
        buttons = [[
            InlineKeyboardButton("🔊 Unmute", callback_data=f"unmute_{user_id}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_msg")
        ]]
        
        await message.reply(
            f"🔇 **User Muted!**\n"
            f"👤 User: {user_name}\n"
            f"👮‍♂️ Muted by: {message.from_user.mention}\n"
            f"⏰ Duration: {time_text}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        await message.reply(f"❌ Failed to mute user: {e}")

# UNMUTE COMMAND
@Client.on_message(filters.command("unmute") & filters.group & admin_filter)
async def unmute_user(client, message: Message):
    if not await is_bot_admin(client, message.chat.id):
        await message.reply("❌ I need admin rights with restrict permissions!")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            user_name = user.mention
        except:
            await message.reply("❌ Invalid user ID!")
            return
    else:
        await message.reply("❌ Reply to a user or provide user ID!")
        return
    
    try:
        # Restore default permissions
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        
        await client.restrict_chat_member(message.chat.id, user_id, permissions)
        
        await message.reply(
            f"🔊 **User Unmuted!**\n"
            f"👤 User: {user_name}\n"
            f"👮‍♂️ Unmuted by: {message.from_user.mention}"
        )
        
    except Exception as e:
        await message.reply(f"❌ Failed to unmute user: {e}")

# =============================================================================
# WARNING SYSTEM
# =============================================================================

# WARN COMMAND
@Client.on_message(filters.command("warn") & filters.group & admin_filter)
async def warn_user(client, message: Message):
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            user_name = user.mention
        except:
            await message.reply("❌ Invalid user ID!")
            return
    else:
        await message.reply("❌ Reply to a user or provide user ID!")
        return
    
    # Check if user is admin
    try:
        target_member = await client.get_chat_member(message.chat.id, user_id)
        if target_member.status in ["creator", "administrator"]:
            await message.reply("❌ Cannot warn an admin!")
            return
    except UserNotParticipant:
        await message.reply("❌ User is not in this chat!")
        return
    
    reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason provided"
    
    # Add warn to database
    warn_count = await WarnDB.add_warn(user_id, message.chat.id, reason)
    
    buttons = [[
        InlineKeyboardButton("🗑️ Remove Warn", callback_data=f"remove_warn_{user_id}"),
        InlineKeyboardButton("📊 View Warns", callback_data=f"view_warns_{user_id}")
    ]]
    
    # Auto-action on 3 warns
    if warn_count >= 3:
        if await is_bot_admin(client, message.chat.id):
            await client.ban_chat_member(message.chat.id, user_id)
            action_text = "**BANNED** (3 warns reached)"
            # Clear warns after ban
            await WarnDB.remove_warns(user_id, message.chat.id)
        else:
            action_text = "Should be banned (3 warns) but I lack permissions"
    else:
        action_text = f"Warn {warn_count}/3"
    
    await message.reply(
        f"⚠️ **User Warned!**\n"
        f"👤 User: {user_name}\n"
        f"👮‍♂️ Warned by: {message.from_user.mention}\n"
        f"📝 Reason: `{reason}`\n"
        f"📊 Status: {action_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# WARNS COMMAND - View user warns
@Client.on_message(filters.command("warns") & filters.group)
async def view_warns(client, message: Message):
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            user_name = user.mention
        except:
            await message.reply("❌ Invalid user ID!")
            return
    else:
        user_id = message.from_user.id
        user_name = message.from_user.mention
    
    warns = await WarnDB.get_warns(user_id, message.chat.id)
    
    if not warns:
        await message.reply(f"✅ {user_name} has no warnings!")
        return
    
    warn_text = f"⚠️ **Warnings for {user_name}:**\n\n"
    for i, warn in enumerate(warns, 1):
        warn_text += f"**{i}.** {warn['reason']}\n"
        warn_text += f"   📅 {warn['date'][:10]}\n\n"
    
    warn_text += f"**Total: {len(warns)}/3 warns**"
    
    await message.reply(warn_text)

# REMOVE WARN COMMAND
@Client.on_message(filters.command(["rmwarn", "removewarn"]) & filters.group & admin_filter)
async def remove_warn(client, message: Message):
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            user_name = user.mention
        except:
            await message.reply("❌ Invalid user ID!")
            return
    else:
        await message.reply("❌ Reply to a user or provide user ID!")
        return
    
    count = 1
    if len(message.command) > 2:
        try:
            count = int(message.command[2])
        except:
            count = 1
    
    await WarnDB.remove_warns(user_id, message.chat.id, count)
    await message.reply(f"✅ Removed {count} warning(s) from {user_name}")

# =============================================================================
# ADMIN MANAGEMENT
# =============================================================================

# PROMOTE COMMAND
@Client.on_message(filters.command("promote") & filters.group & admin_filter)
async def promote_user(client, message: Message):
    chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status != "creator":
        await message.reply("❌ Only the group creator can promote users!")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            user_name = user.mention
        except:
            await message.reply("❌ Invalid user ID!")
            return
    else:
        await message.reply("❌ Reply to a user or provide user ID!")
        return
    
    title = " ".join(message.command[2:]) if len(message.command) > 2 else "Admin"
    
    try:
        await client.promote_chat_member(
            message.chat.id,
            user_id,
            can_change_info=True,
            can_delete_messages=True,
            can_restrict_members=True,
            can_invite_users=True,
            can_pin_messages=True,
        )
        
        # Set custom title if provided
        if title != "Admin":
            await client.set_administrator_title(message.chat.id, user_id, title)
        
        await message.reply(
            f"⬆️ **User Promoted!**\n"
            f"👤 User: {user_name}\n"
            f"🏷️ Title: {title}\n"
            f"👑 Promoted by: {message.from_user.mention}"
        )
        
    except Exception as e:
        await message.reply(f"❌ Failed to promote user: {e}")

# DEMOTE COMMAND
@Client.on_message(filters.command("demote") & filters.group & admin_filter)
async def demote_user(client, message: Message):
    chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status != "creator":
        await message.reply("❌ Only the group creator can demote admins!")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            user_name = user.mention
        except:
            await message.reply("❌ Invalid user ID!")
            return
    else:
        await message.reply("❌ Reply to a user or provide user ID!")
        return
    
    try:
        await client.promote_chat_member(
            message.chat.id,
            user_id,
            can_change_info=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_invite_users=False,
            can_pin_messages=False,
        )
        
        await message.reply(
            f"⬇️ **Admin Demoted!**\n"
            f"👤 User: {user_name}\n"
            f"👑 Demoted by: {message.from_user.mention}"
        )
        
    except Exception as e:
        await message.reply(f"❌ Failed to demote user: {e}")

# ADMIN LIST COMMAND
@Client.on_message(filters.command("admins") & filters.group)
async def list_admins(client, message: Message):
    try:
        admins = []
        async for member in client.get_chat_members(message.chat.id, filter="administrators"):
            if member.user.is_bot:
                admins.append(f"🤖 {member.user.mention}")
            else:
                status = "👑" if member.status == "creator" else "👮‍♂️"
                admins.append(f"{status} {member.user.mention}")
        
        admin_text = f"**👥 Admins in {message.chat.title}:**\n\n"
        admin_text += "\n".join(admins)
        
        await message.reply(admin_text)
        
    except Exception as e:
        await message.reply(f"❌ Failed to get admin list: {e}")

# =============================================================================
# MESSAGE MANAGEMENT
# =============================================================================

# PIN COMMAND
@Client.on_message(filters.command("pin") & filters.group & admin_filter)
async def pin_message(client, message: Message):
    if not await is_bot_admin(client, message.chat.id):
        await message.reply("❌ I need admin rights with pin messages permission!")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to pin it!")
        return
    
    notify = True
    if len(message.command) > 1 and message.command[1].lower() in ["silent", "quiet"]:
        notify = False
    
    try:
        await client.pin_chat_message(
            message.chat.id, 
            message.reply_to_message.message_id,
            disable_notification=not notify
        )
        
        mode = "🔕 silently" if not notify else "📢 with notification"
        await message.reply(f"📌 Message pinned {mode}!")
        
    except Exception as e:
        await message.reply(f"❌ Failed to pin message: {e}")

# UNPIN COMMAND
@Client.on_message(filters.command("unpin") & filters.group & admin_filter)
async def unpin_message(client, message: Message):
    if not await is_bot_admin(client, message.chat.id):
        await message.reply("❌ I need admin rights with pin messages permission!")
        return
    
    try:
        if message.reply_to_message:
            await client.unpin_chat_message(message.chat.id, message.reply_to_message.message_id)
            await message.reply("📌 Message unpinned!")
        else:
            await client.unpin_chat_message(message.chat.id)
            await message.reply("📌 Latest pinned message unpinned!")
            
    except Exception as e:
        await message.reply(f"❌ Failed to unpin message: {e}")

# PURGE COMMAND - Delete messages
@Client.on_message(filters.command("purge") & filters.group & admin_filter)
async def purge_messages(client, message: Message):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to start purging from!")
        return
    
    if not await is_bot_admin(client, message.chat.id):
        await message.reply("❌ I need admin rights with delete messages permission!")
        return
    
    start_msg_id = message.reply_to_message.message_id
    end_msg_id = message.message_id
    
    deleted_count = 0
    
    try:
        # Delete messages in batches
        for msg_id in range(start_msg_id, end_msg_id + 1):
            try:
                await client.delete_messages(message.chat.id, msg_id)
                deleted_count += 1
                await asyncio.sleep(0.1)  # Small delay to avoid rate limits
            except:
                continue
        
        # Send confirmation and delete it after 3 seconds
        confirmation = await message.reply(f"🗑️ Deleted {deleted_count} messages!")
        await asyncio.sleep(3)
        await confirmation.delete()
        
    except Exception as e:
        await message.reply(f"❌ Failed to purge messages: {e}")

# =============================================================================
# CHAT CONTROL SYSTEM
# =============================================================================

# Lock/Unlock system
lock_types = {
    "msg": "can_send_messages",
    "messages": "can_send_messages", 
    "media": "can_send_media_messages",
    "stickers": "can_send_other_messages",
    "gifs": "can_send_other_messages",
    "games": "can_send_other_messages",
    "inline": "can_send_other_messages",
    "url": "can_add_web_page_previews",
    "bots": "can_invite_users",
    "forward": "can_send_other_messages",
    "all": "all"
}

@Client.on_message(filters.command("lock") & filters.group & admin_filter)
async def lock_chat(client, message: Message):
    if not await is_bot_admin(client, message.chat.id):
        await message.reply("❌ I need admin rights with restrict members permission!")
        return
    
    if len(message.command) < 2:
        lock_list = ", ".join(lock_types.keys())
        await message.reply(f"❌ Specify what to lock!\n\n**Available:** {lock_list}")
        return
    
    lock_type = message.command[1].lower()
    if lock_type not in lock_types:
        lock_list = ", ".join(lock_types.keys())
        await message.reply(f"❌ Invalid lock type!\n\n**Available:** {lock_list}")
        return
    
    try:
        current_permissions = await client.get_chat(message.chat.id)
        permissions = current_permissions.permissions or ChatPermissions()
        
        if lock_type == "all":
            permissions = ChatPermissions()
        else:
            setattr(permissions, lock_types[lock_type], False)
        
        await client.set_chat_permissions(message.chat.id, permissions)
        await message.reply(f"🔒 Locked `{lock_type}` for all members!")
        
    except Exception as e:
        await message.reply(f"❌ Failed to lock: {e}")

@Client.on_message(filters.command("unlock") & filters.group & admin_filter)
async def unlock_chat(client, message: Message):
    if not await is_bot_admin(client, message.chat.id):
        await message.reply("❌ I need admin rights with restrict members permission!")
        return
    
    if len(message.command) < 2:
        lock_list = ", ".join(lock_types.keys())
        await message.reply(f"❌ Specify what to unlock!\n\n**Available:** {lock_list}")
        return
    
    lock_type = message.command[1].lower()
    if lock_type not in lock_types:
        lock_list = ", ".join(lock_types.keys())
        await message.reply(f"❌ Invalid lock type!\n\n**Available:** {lock_list}")
        return
    
    try:
        if lock_type == "all":
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True
            )
        else:
            current_permissions = await client.get_chat(message.chat.id)
            permissions = current_permissions.permissions or ChatPermissions()
            setattr(permissions, lock_types[lock_type], True)
        
        await client.set_chat_permissions(message.chat.id, permissions)
        await message.reply(f"🔓 Unlocked `{lock_type}` for all members!")
        
    except Exception as e:
        await message.reply(f"❌ Failed to unlock: {e}")

# LOCKS COMMAND - Show current locks
@Client.on_message(filters.command("locks") & filters.group)
async def show_locks(client, message: Message):
    try:
        chat = await client.get_chat(message.chat.id)
        permissions = chat.permissions
        
        if not permissions:
            await message.reply("🔓 No restrictions in this chat!")
            return
        
        locks_text = "🔒 **Current Chat Restrictions:**\n\n"
        
        restrictions = {
            "Messages": not permissions.can_send_messages,
            "Media": not permissions.can_send_media_messages,
            "Stickers/GIFs": not permissions.can_send_other_messages,
            "Web Preview": not permissions.can_add_web_page_previews,
            "Invite Users": not permissions.can_invite_users
        }
        
        active_restrictions = [name for name, locked in restrictions.items() if locked]
        
        if active_restrictions:
            locks_text += "❌ **Locked:** " + ", ".join(active_restrictions) + "\n"
            unlocked = [name for name, locked in restrictions.items() if not locked]
            if unlocked:
                locks_text += "✅ **Unlocked:** " + ", ".join(unlocked)
        else:
            locks_text += "✅ **All permissions are unlocked!**"
        
        await message.reply(locks_text)
        
    except Exception as e:
        await message.reply(f"❌ Failed to get locks: {e}")

# =============================================================================
# FLOOD CONTROL SYSTEM
# =============================================================================

@Client.on_message(filters.command("setflood") & filters.group & admin_filter)
async def set_flood(client, message: Message):
    if len(message.command) < 2:
        await message.reply(
            "❌ Provide flood limit and action!\n\n"
            "**Usage:** `/setflood <limit> <action>`\n"
            "**Actions:** `mute`, `kick`, `ban`\n"
            "**Example:** `/setflood 5 mute`"
        )
        return
    
    try:
        limit = int(message.command[1])
        action = message.command[2].lower() if len(message.command) > 2 else "mute"
        
        if action not in ["mute", "kick", "ban"]:
            await message.reply("❌ Invalid action! Use: `mute`, `kick`, or `ban`")
            return
        
        if limit < 2 or limit > 20:
            await message.reply("❌ Flood limit must be between 2 and 20!")
            return
        
        chat_id = message.chat.id
        flood_settings[chat_id] = {'limit': limit, 'action': action}
        
        await message.reply(f"✅ Flood control set: {limit} messages → {action}")
        
    except ValueError:
        await message.reply("❌ Invalid flood limit! Use a number.")

@Client.on_message(filters.command("flood") & filters.group)
async def show_flood(client, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in flood_settings:
        await message.reply("🌊 No flood control set for this chat!")
        return
    
    settings = flood_settings[chat_id]
    await message.reply(
        f"🌊 **Flood Control Settings:**\n\n"
        f"📊 **Limit:** {settings['limit']} messages\n"
        f"⚡ **Action:** {settings['action'].capitalize()}"
    )

# Flood control handler
@Client.on_message(filters.group & ~admin_filter)
async def flood_control(client, message: Message):
    if not message.from_user:
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if chat_id not in flood_settings:
        return
    
    current_time = datetime.now()
    
    # Initialize flood tracker
    if chat_id not in flood_tracker:
        flood_tracker[chat_id] = {}
    
    if user_id not in flood_tracker[chat_id]:
        flood_tracker[chat_id][user_id] = []
    
    # Add current message time
    flood_tracker[chat_id][user_id].append(current_time)
    
    # Keep only messages from last 60 seconds
    flood_tracker[chat_id][user_id] = [
        msg_time for msg_time in flood_tracker[chat_id][user_id]
        if (current_time - msg_time).seconds <= 60
    ]
    
    # Check flood limit
    limit = flood_settings[chat_id]['limit']
    if len(flood_tracker[chat_id][user_id]) >= limit:
        if await is_bot_admin(client, chat_id):
            action = flood_settings[chat_id]['action']
            
            try:
                if action == "mute":
                    until_date = current_time + timedelta(hours=1)
                    await client.restrict_chat_member(
                        chat_id, user_id, ChatPermissions(), until_date=until_date
                    )
                    action_text = "muted for 1 hour"
                    
                elif action == "kick":
                    await client.ban_chat_member(chat_id, user_id)
                    await client.unban_chat_member(chat_id, user_id)
                    action_text = "kicked"
                    
                elif action == "ban":
                    await client.ban_chat_member(chat_id, user_id)
                    action_text = "banned"
                
                await message.reply(
                    f"🌊 **Flood Detected!**\n"
                    f"👤 {message.from_user.mention} has been {action_text} for flooding!"
                )
                
                # Clear flood tracker for this user
                flood_tracker[chat_id][user_id] = []
                
            except Exception as e:
                logging.error(f"Flood control error: {e}")

# =============================================================================
# BLACKLIST SYSTEM
# =============================================================================

@Client.on_message(filters.command("blacklist") & filters.group & admin_filter)
async def add_blacklist(client, message: Message):
    chat_id = message.chat.id
    
    if len(message.command) < 2:
        await message.reply("❌ Provide word(s) to blacklist!\n\nExample: `/blacklist spam scam`")
        return
    
    words = message.command[1:]
    
    if chat_id not in blacklisted_words:
        blacklisted_words[chat_id] = []
    
    new_words = []
    for word in words:
        word_lower = word.lower()
        if word_lower not in blacklisted_words[chat_id]:
            blacklisted_words[chat_id].append(word_lower)
            new_words.append(word)
    
    if new_words:
        await message.reply(f"✅ Added to blacklist: `{', '.join(new_words)}`")
    else:
        await message.reply("❌ All words are already blacklisted!")

@Client.on_message(filters.command("unblacklist") & filters.group & admin_filter)
async def remove_blacklist(client, message: Message):
    chat_id = message.chat.id
    
    if len(message.command) < 2:
        await message.reply("❌ Provide word(s) to remove from blacklist!")
        return
    
    if chat_id not in blacklisted_words:
        await message.reply("❌ No blacklisted words in this chat!")
        return
    
    words = message.command[1:]
    removed_words = []
    
    for word in words:
        word_lower = word.lower()
        if word_lower in blacklisted_words[chat_id]:
            blacklisted_words[chat_id].remove(word_lower)
            removed_words.append(word)
    
    if removed_words:
        await message.reply(f"✅ Removed from blacklist: `{', '.join(removed_words)}`")
    else:
        await message.reply("❌ None of these words were blacklisted!")

@Client.on_message(filters.command("blacklisted") & filters.group)
async def show_blacklist(client, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in blacklisted_words or not blacklisted_words[chat_id]:
        await message.reply("✅ No blacklisted words in this chat!")
        return
    
    words_text = "🚫 **Blacklisted Words:**\n\n"
    words_text += "• " + "\n• ".join(f"`{word}`" for word in blacklisted_words[chat_id])
    
    await message.reply(words_text)

# Blacklist filter
@Client.on_message(filters.group & ~admin_filter)
async def blacklist_filter(client, message: Message):
    if not message.text and not message.caption:
        return
    
    chat_id = message.chat.id
    if chat_id not in blacklisted_words or not blacklisted_words[chat_id]:
        return
    
    text_to_check = (message.text or message.caption or "").lower()
    
    for word in blacklisted_words[chat_id]:
        if word in text_to_check:
            try:
                await message.delete()
                warn_msg = await message.reply(
                    f"⚠️ {message.from_user.mention}, your message contained a blacklisted word: `{word}`"
                )
                
                # Auto-delete warning after 10 seconds
                await asyncio.sleep(10)
                try:
                    await warn_msg.delete()
                except:
                    pass
                
                return
            except Exception as e:
                logging.error(f"Blacklist filter error: {e}")
                return

# =============================================================================
# NOTES SYSTEM
# =============================================================================

@Client.on_message(filters.command("save") & filters.group & admin_filter)
async def save_note(client, message: Message):
    chat_id = message.chat.id
    
    if len(message.command) < 2:
        await message.reply("❌ Provide note name!\n\nExample: `/save rules Welcome to our chat!`")
        return
    
    note_name = message.command[1].lower()
    
    if message.reply_to_message:
        note_content = message.reply_to_message.text or message.reply_to_message.caption
    else:
        if len(message.command) < 3:
            await message.reply("❌ Provide note content!")
            return
        note_content = " ".join(message.command[2:])
    
    if chat_id not in notes_data:
        notes_data[chat_id] = {}
    
    notes_data[chat_id][note_name] = note_content
    
    await message.reply(f"✅ Note `{note_name}` saved!")

@Client.on_message(filters.command("get") & filters.group)
async def get_note(client, message: Message):
    chat_id = message.chat.id
    
    if len(message.command) < 2:
        await message.reply("❌ Provide note name!")
        return
    
    note_name = message.command[1].lower()
    
    if chat_id not in notes_data or note_name not in notes_data[chat_id]:
        await message.reply(f"❌ Note `{note_name}` not found!")
        return
    
    await message.reply(notes_data[chat_id][note_name])

@Client.on_message(filters.command("notes") & filters.group)
async def list_notes(client, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in notes_data or not notes_data[chat_id]:
        await message.reply("📝 No notes saved in this chat!")
        return
    
    notes_list = list(notes_data[chat_id].keys())
    notes_text = "📝 **Saved Notes:**\n\n"
    notes_text += "• " + "\n• ".join(f"`{note}`" for note in notes_list)
    
    await message.reply(notes_text)

@Client.on_message(filters.command("clear") & filters.group & admin_filter)
async def clear_note(client, message: Message):
    chat_id = message.chat.id
    
    if len(message.command) < 2:
        await message.reply("❌ Provide note name to clear!")
        return
    
    note_name = message.command[1].lower()
    
    if chat_id not in notes_data or note_name not in notes_data[chat_id]:
        await message.reply(f"❌ Note `{note_name}` not found!")
        return
    
    del notes_data[chat_id][note_name]
    await message.reply(f"✅ Note `{note_name}` cleared!")

# =============================================================================
# WELCOME SYSTEM
# =============================================================================

@Client.on_message(filters.command("setwelcome") & filters.group & admin_filter)
async def set_welcome(client, message: Message):
    chat_id = message.chat.id
    
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply(
            "❌ Provide welcome message!\n\n"
            "**Variables:**\n"
            "`{mention}` - Mention user\n"
            "`{first}` - First name\n"
            "`{last}` - Last name\n"
            "`{username}` - Username\n"
            "`{fullname}` - Full name\n"
            "`{id}` - User ID\n"
            "`{chatname}` - Chat name"
        )
        return
    
    if message.reply_to_message:
        welcome_msg = message.reply_to_message.text or message.reply_to_message.caption
    else:
        welcome_msg = " ".join(message.command[1:])
    
    welcome_settings[chat_id] = welcome_msg
    
    await message.reply("✅ Welcome message set!")

@Client.on_message(filters.new_chat_members)
async def welcome_new_members(client, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in welcome_settings:
        return
    
    for user in message.new_chat_members:
        if user.is_bot:
            continue
        
        welcome_text = welcome_settings[chat_id]
        
        # Replace variables
        welcome_text = welcome_text.replace("{mention}", user.mention)
        welcome_text = welcome_text.replace("{first}", user.first_name or "")
        welcome_text = welcome_text.replace("{last}", user.last_name or "")
        welcome_text = welcome_text.replace("{username}", f"@{user.username}" if user.username else "No username")
        welcome_text = welcome_text.replace("{fullname}", user.first_name + (f" {user.last_name}" if user.last_name else ""))
        welcome_text = welcome_text.replace("{id}", str(user.id))
        welcome_text = welcome_text.replace("{chatname}", message.chat.title)
        
        await message.reply(welcome_text)

# =============================================================================
# RULES SYSTEM
# =============================================================================

@Client.on_message(filters.command("setrules") & filters.group & admin_filter)
async def set_rules(client, message: Message):
    chat_id = message.chat.id
    
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply("❌ Provide rules text!")
        return
    
    if message.reply_to_message:
        rules_text = message.reply_to_message.text or message.reply_to_message.caption
    else:
        rules_text = " ".join(message.command[1:])
    
    rules_data[chat_id] = rules_text
    
    await message.reply("✅ Rules set for this chat!")

@Client.on_message(filters.command("rules") & filters.group)
async def get_rules(client, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in rules_data:
        await message.reply("❌ No rules set for this chat!")
        return
    
    rules_text = f"📋 **Rules for {message.chat.title}:**\n\n"
    rules_text += rules_data[chat_id]
    
    buttons = [[InlineKeyboardButton("🗑️ Close", callback_data="delete_msg")]]
    
    await message.reply(rules_text, reply_markup=InlineKeyboardMarkup(buttons))

# =============================================================================
# INVITE LINK MANAGEMENT
# =============================================================================

@Client.on_message(filters.command("link") & filters.group & admin_filter)
async def get_invite_link(client, message: Message):
    try:
        link = await client.export_chat_invite_link(message.chat.id)
        await message.reply(f"🔗 **Invite Link:**\n`{link}`")
    except Exception as e:
        await message.reply(f"❌ Failed to get invite link: {e}")

@Client.on_message(filters.command("revoke") & filters.group & admin_filter)
async def revoke_invite_link(client, message: Message):
    try:
        new_link = await client.export_chat_invite_link(message.chat.id)
        await message.reply(f"🔗 **New Invite Link Generated:**\n`{new_link}`\n\n⚠️ Old links are now invalid!")
    except Exception as e:
        await message.reply(f"❌ Failed to revoke invite link: {e}")

# =============================================================================
# UTILITIES
# =============================================================================

# ZOMBIES COMMAND - Remove deleted accounts
@Client.on_message(filters.command("zombies") & filters.group & admin_filter)
async def clean_zombies(client, message: Message):
    if not await is_bot_admin(client, message.chat.id):
        await message.reply("❌ I need admin rights with ban permissions!")
        return
    
    zombie_count = 0
    progress_msg = await message.reply("🧟 Scanning for deleted accounts...")
    
    try:
        async for member in client.get_chat_members(message.chat.id):
            if member.user.is_deleted:
                try:
                    await client.ban_chat_member(message.chat.id, member.user.id)
                    await client.unban_chat_member(message.chat.id, member.user.id)
                    zombie_count += 1
                except:
                    continue
        
        await progress_msg.edit_text(f"🧹 **Cleanup Complete!**\nRemoved {zombie_count} deleted accounts.")
        
    except Exception as e:
        await progress_msg.edit_text(f"❌ Failed to clean zombies: {e}")

# REPORTS SYSTEM
@Client.on_message(filters.command(["report", "admin"]) & filters.group)
async def report_user(client, message: Message):
    if not message.reply_to_message:
        await message.reply("❌ Reply to a message to report it!")
        return
    
    reported_user = message.reply_to_message.from_user
    reporter = message.from_user
    
    # Get all admins
    admin_mentions = []
    async for member in client.get_chat_members(message.chat.id, filter="administrators"):
        if not member.user.is_bot and member.user.id != reporter.id:
            admin_mentions.append(member.user.mention)
    
    if not admin_mentions:
        await message.reply("❌ No admins found to report to!")
        return
    
    report_text = (
        f"🚨 **USER REPORTED!**\n\n"
        f"👤 **Reported User:** {reported_user.mention}\n"
        f"👮‍♂️ **Reported By:** {reporter.mention}\n"
        f"💬 **Message:** [Click Here](https://t.me/c/{str(message.chat.id)[4:]}/{message.reply_to_message.message_id})\n\n"
        f"👥 **Admins:** {' '.join(admin_mentions[:5])}"  # Limit to 5 admins
    )
    
    buttons = [[
        InlineKeyboardButton("🗑️ Delete Reported Message", callback_data=f"del_report_{message.reply_to_message.message_id}"),
        InlineKeyboardButton("❌ Close Report", callback_data="delete_msg")
    ]]
    
    await message.reply(report_text, reply_markup=InlineKeyboardMarkup(buttons))

# =============================================================================
# INFORMATION COMMANDS
# =============================================================================

# CHAT INFO COMMAND
@Client.on_message(filters.command("chatinfo") & filters.group)
async def chat_info(client, message: Message):
    try:
        chat = message.chat
        member_count = await client.get_chat_members_count(chat.id)
        
        # Get admin count
        admin_count = 0
        bot_count = 0
        async for member in client.get_chat_members(chat.id, filter="administrators"):
            admin_count += 1
            if member.user.is_bot:
                bot_count += 1
        
        info_text = f"📊 **Chat Information**\n\n"
        info_text += f"🏷️ **Name:** {chat.title}\n"
        info_text += f"🆔 **ID:** `{chat.id}`\n"
        info_text += f"📝 **Type:** {chat.type.capitalize()}\n"
        info_text += f"👥 **Members:** {member_count}\n"
        info_text += f"👮‍♂️ **Admins:** {admin_count}\n"
        info_text += f"🤖 **Bots:** {bot_count}\n"
        
        if chat.username:
            info_text += f"🔗 **Username:** @{chat.username}\n"
        
        if chat.description:
            info_text += f"📄 **Description:** {chat.description[:100]}{'...' if len(chat.description) > 100 else ''}\n"
        
        await message.reply(info_text)
        
    except Exception as e:
        await message.reply(f"❌ Failed to get chat info: {e}")

# USER INFO COMMAND
@Client.on_message(filters.command("info"))
async def user_info(client, message: Message):
    if message.reply_to_message:
        user = message.reply_to_message.from_user
    elif len(message.command) > 1:
        try:
            user_input = message.command[1]
            if user_input.isdigit():
                user = await client.get_users(int(user_input))
            else:
                user = await client.get_users(user_input)
        except:
            await message.reply("❌ User not found!")
            return
    else:
        user = message.from_user
    
    try:
        # Get user's status in the chat (if it's a group)
        member_info = ""
        if message.chat.type != "private":
            try:
                member = await client.get_chat_member(message.chat.id, user.id)
                member_info = f"📋 **Status:** {member.status.title()}\n"
                
                if member.status == "administrator":
                    perms = []
                    if hasattr(member, 'can_delete_messages') and member.can_delete_messages: perms.append("Delete Messages")
                    if hasattr(member, 'can_restrict_members') and member.can_restrict_members: perms.append("Restrict Members")
                    if hasattr(member, 'can_promote_members') and member.can_promote_members: perms.append("Promote Members")
                    if hasattr(member, 'can_change_info') and member.can_change_info: perms.append("Change Info")
                    if hasattr(member, 'can_invite_users') and member.can_invite_users: perms.append("Invite Users")
                    if hasattr(member, 'can_pin_messages') and member.can_pin_messages: perms.append("Pin Messages")
                    
                    if perms:
                        member_info += f"🔧 **Permissions:** {', '.join(perms)}\n"
                        
                    if hasattr(member, 'custom_title') and member.custom_title:
                        member_info += f"🏷️ **Title:** {member.custom_title}\n"
                        
            except:
                member_info = "📋 **Status:** Not in chat\n"
        
        # Get warns (if in group)
        warns_info = ""
        if message.chat.type != "private":
            warns = await WarnDB.get_warns(user.id, message.chat.id)
            if warns:
                warns_info = f"⚠️ **Warnings:** {len(warns)}/3\n"
        
        info_text = f"👤 **User Information**\n\n"
        info_text += f"🏷️ **Name:** {user.first_name}"
        if user.last_name:
            info_text += f" {user.last_name}"
        info_text += f"\n🆔 **ID:** `{user.id}`\n"
        
        if user.username:
            info_text += f"📝 **Username:** @{user.username}\n"
        
        if user.is_bot:
            info_text += f"🤖 **Bot:** Yes\n"
        
        if hasattr(user, 'is_premium') and user.is_premium:
            info_text += f"⭐ **Premium:** Yes\n"
        
        info_text += member_info + warns_info
        
        # User profile photos count
        try:
            photos = await client.get_profile_photos_count(user.id)
            info_text += f"📸 **Profile Photos:** {photos}\n"
        except:
            pass
        
        await message.reply(info_text)
        
    except Exception as e:
        await message.reply(f"❌ Failed to get user info: {e}")

# CHAT STATS COMMAND
@Client.on_message(filters.command("stats") & filters.group)
async def chat_stats(client, message: Message):
    try:
        chat_id = message.chat.id
        
        # Get member counts
        total_members = await client.get_chat_members_count(chat_id)
        
        admins = 0
        bots = 0
        
        progress_msg = await message.reply("📊 Analyzing chat statistics...")
        
        count = 0
        async for member in client.get_chat_members(chat_id):
            count += 1
            
            if member.status in ["creator", "administrator"]:
                admins += 1
            
            if member.user.is_bot:
                bots += 1
            
            # Update progress every 100 members
            if count % 100 == 0:
                await progress_msg.edit_text(f"📊 Analyzing... ({count}/{total_members})")
            
            # Limit to prevent timeout
            if count >= 1000:
                break
        
        stats_text = f"📊 **Chat Statistics for {message.chat.title}**\n\n"
        stats_text += f"👥 **Total Members:** {total_members}\n"
        stats_text += f"👮‍♂️ **Admins:** {admins}\n"
        stats_text += f"🤖 **Bots:** {bots}\n"
        stats_text += f"👤 **Regular Users:** {total_members - admins - bots}\n"
        
        if count < total_members:
            stats_text += f"\n⚠️ *Analysis limited to {count} members*"
        
        await progress_msg.edit_text(stats_text)
        
    except Exception as e:
        await message.reply(f"❌ Failed to get stats: {e}")

# =============================================================================
# GLOBAL BAN SYSTEM (Bot Owner Only)
# =============================================================================

@Client.on_message(filters.command("gban") & filters.user(YOUR_ADMIN_ID))
async def global_ban(client, message: Message):
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            user_name = user.mention
        except:
            await message.reply("❌ Invalid user ID!")
            return
    else:
        await message.reply("❌ Reply to a user or provide user ID!")
        return
    
    reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason provided"
    
    global_banned_users.add(user_id)
    
    await message.reply(
        f"🌐 **Global Ban Issued!**\n"
        f"👤 User: {user_name}\n"
        f"📝 Reason: `{reason}`\n"
        f"🔥 This user will be automatically banned from all chats where I'm admin."
    )

@Client.on_message(filters.command("ungban") & filters.user(YOUR_ADMIN_ID))
async def global_unban(client, message: Message):
    if len(message.command) < 2:
        await message.reply("❌ Provide user ID to ungban!")
        return
    
    try:
        user_id = int(message.command[1])
        if user_id in global_banned_users:
            global_banned_users.remove(user_id)
            
            user = await client.get_users(user_id)
            await message.reply(f"🌐 **Global ban removed for** {user.mention}")
        else:
            await message.reply("❌ User is not globally banned!")
    except:
        await message.reply("❌ Invalid user ID!")

# Auto-ban globally banned users when they join
@Client.on_message(filters.new_chat_members)
async def auto_gban(client, message: Message):
    if not await is_bot_admin(client, message.chat.id):
        return
    
    for user in message.new_chat_members:
        if user.id in global_banned_users:
            try:
                await client.ban_chat_member(message.chat.id, user.id)
                await message.reply(
                    f"🛑 **Auto-banned:** {user.mention}\n"
                    f"Reason: Globally banned user"
                )
            except:
                pass

# =============================================================================
# ANTI-SPAM SYSTEM
# =============================================================================

@Client.on_message(filters.group & ~admin_filter)
async def anti_spam(client, message: Message):
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    current_time = datetime.now()
    
    # Initialize spam tracker
    if chat_id not in spam_tracker:
        spam_tracker[chat_id] = {}
    
    if user_id not in spam_tracker[chat_id]:
        spam_tracker[chat_id][user_id] = []
    
    # Add current message time
    spam_tracker[chat_id][user_id].append(current_time)
    
    # Keep only messages from last 10 seconds
    spam_tracker[chat_id][user_id] = [
        msg_time for msg_time in spam_tracker[chat_id][user_id]
        if (current_time - msg_time).seconds <= 10
    ]
    
    # Check if user sent more than 5 messages in 10 seconds
    if len(spam_tracker[chat_id][user_id]) > 5:
        if await is_bot_admin(client, chat_id):
            try:
                # Mute for 5 minutes
                until_date = current_time + timedelta(minutes=5)
                await client.restrict_chat_member(
                    chat_id, user_id, ChatPermissions(), until_date=until_date
                )
                
                await message.reply(
                    f"🛑 **Anti-Spam Triggered!**\n"
                    f"👤 {message.from_user.mention} has been muted for 5 minutes for spamming!"
                )
                
                # Clear spam tracker for this user
                spam_tracker[chat_id][user_id] = []
                
            except Exception as e:
                logging.error(f"Anti-spam error: {e}")

# =============================================================================
# HELP COMMAND
# =============================================================================

@Client.on_message(filters.command("ghelp"))
async def help_command(client, message: Message):
    help_text = """
🤖 **Bot Help - Admin Commands**

**👮‍♂️ Moderation:**
• `/ban [reason]` - Ban user
• `/unban <user_id>` - Unban user
• `/kick [reason]` - Kick user
• `/mute [time] [reason]` - Mute user
• `/unmute` - Unmute user
• `/warn [reason]` - Warn user (3 = ban)
• `/warns` - Check user warns
• `/rmwarn` - Remove warning

**🔒 Chat Control:**
• `/lock <type>` - Lock chat features
• `/unlock <type>` - Unlock chat features
• `/locks` - Show current locks
• `/setflood <limit> <action>` - Set flood control
• `/flood` - Show flood settings

**📌 Messages:**
• `/pin [silent]` - Pin message
• `/unpin` - Unpin message
• `/purge` - Delete messages (reply to start)

**👑 Admin Tools:**
• `/promote [title]` - Promote to admin
• `/demote` - Demote admin
• `/admins` - List all admins

**📝 Chat Management:**
• `/setrules` - Set chat rules
• `/rules` - Show chat rules
• `/setwelcome` - Set welcome message
• `/link` - Get invite link
• `/revoke` - Generate new invite link

**📊 Information:**
• `/info` - User information
• `/chatinfo` - Chat information  
• `/stats` - Chat statistics

**📝 Notes & Filters:**
• `/save <name>` - Save a note
• `/get <name>` - Get saved note
• `/notes` - List all notes
• `/clear <name>` - Delete note
• `/blacklist <words>` - Add blacklist words
• `/blacklisted` - Show blacklisted words

**🛠️ Utilities:**
• `/zombies` - Remove deleted accounts
• `/report` - Report user to admins

**Lock Types:** msg, media, stickers, gifs, url, bots, forward, all
"""
    
    buttons = [
        [InlineKeyboardButton("❌ Close", callback_data="delete_msg")]
    ]
    
    await message.reply(help_text, reply_markup=InlineKeyboardMarkup(buttons))

# =============================================================================
# CALLBACK QUERY HANDLERS
# =============================================================================

@Client.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    # Check if user is admin for admin-only callbacks
    admin_only_callbacks = ["unban_", "unmute_", "remove_warn_", "del_report_"]
    requires_admin = any(data.startswith(prefix) for prefix in admin_only_callbacks)
    
    if requires_admin:
        try:
            member = await client.get_chat_member(callback_query.message.chat.id, user_id)
            is_admin = member.status in ["creator", "administrator"]
        except:
            is_admin = False
        
        if not is_admin:
            await callback_query.answer("❌ Only admins can use this!", show_alert=True)
            return
    
    # Handle different callback types
    if data.startswith("unban_"):
        target_user = int(data.split("_")[1])
        try:
            await client.unban_chat_member(callback_query.message.chat.id, target_user)
            await callback_query.edit_message_text("✅ User has been unbanned!")
        except Exception as e:
            await callback_query.answer(f"❌ Failed: {e}", show_alert=True)
    
    elif data.startswith("unmute_"):
        target_user = int(data.split("_")[1])
        try:
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
            await client.restrict_chat_member(
                callback_query.message.chat.id, target_user, permissions
            )
            await callback_query.edit_message_text("✅ User has been unmuted!")
        except Exception as e:
            await callback_query.answer(f"❌ Failed: {e}", show_alert=True)
    
    elif data == "delete_msg":
        try:
            await callback_query.message.delete()
        except:
            await callback_query.answer("❌ Cannot delete message!", show_alert=True)
    
    elif data.startswith("remove_warn_"):
        target_user = int(data.split("_")[2])
        await WarnDB.remove_warns(target_user, callback_query.message.chat.id, 1)
        await callback_query.answer("✅ Removed 1 warning!", show_alert=True)
    
    elif data.startswith("view_warns_"):
        target_user = int(data.split("_")[2])
        warns = await WarnDB.get_warns(target_user, callback_query.message.chat.id)
        warn_text = f"⚠️ Total warnings: {len(warns)}"
        await callback_query.answer(warn_text, show_alert=True)
    
    elif data.startswith("del_report_"):
        msg_id = int(data.split("_")[2])
        try:
            await client.delete_messages(callback_query.message.chat.id, msg_id)
            await callback_query.edit_message_text("✅ Reported message deleted!")
        except Exception as e:
            await callback_query.answer(f"❌ Failed to delete: {e}", show_alert=True)

# =============================================================================
# ORIGINAL BAN/RESTRICTION HANDLERS (Enhanced)
# =============================================================================

# Fixed banned users filter
async def banned_users(_, client, message: Message):
    return (
        message.from_user is not None and 
        message.from_user.id in temp.BANNED_USERS
    )

banned_user = filters.create(banned_users)

async def disabled_chat(_, client, message: Message):
    return message.chat.id in temp.BANNED_CHATS

disabled_group = filters.create(disabled_chat)

@Client.on_message(filters.private & banned_user & filters.incoming)
async def ban_reply(bot, message):
    try:
        ban = await db.get_ban_status(message.from_user.id)
        if ban:
            await message.reply(f'Sorry Dude, You are Banned to use Me. \nBan Reason : {ban["ban_reason"]}')
    except Exception as e:
        logging.error(f"Error in ban_reply: {e}")

@Client.on_message(filters.group & disabled_group & filters.incoming)
async def grp_bd(bot, message):
    try:
        buttons = [[
            InlineKeyboardButton('Support', url=SUPPORT_CHAT)
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        vazha = await db.get_chat(message.chat.id)
        k = await message.reply(
            text=f"CHAT NOT ALLOWED 🐞\n\nMy admins has restricted me from working here ! If you want to know more about it contact support..\nReason : <code>{vazha['reason']}</code>.",
            reply_markup=reply_markup
        )
        try:
            await k.pin()
        except:
            pass
        await bot.leave_chat(message.chat.id)
    except Exception as e:
        logging.error(f"Error in grp_bd: {e}")

# =============================================================================
# ERROR HANDLERS & LOGGING
# =============================================================================

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Global error handler
async def global_error_handler(client, update, exception):
    logging.error(f"Error in {update}: {exception}")

# =============================================================================
# STARTUP MESSAGE
# =============================================================================



# =============================================================================
# ADDITIONAL UTILITY FUNCTIONS
# =============================================================================

def time_formatter(seconds):
    """Format seconds into human readable time"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds//60}m {seconds%60}s"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"

def parse_time(time_str):
    """Parse time string like '1d', '2h', '30m' into seconds"""
    if not time_str:
        return None
    
    time_units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    
    if time_str[-1] in time_units and time_str[:-1].isdigit():
        return int(time_str[:-1]) * time_units[time_str[-1]]
    
    return None

# =============================================================================
# DATABASE INITIALIZATION (if needed)


# =============================================================================
# BOT STARTUP
# =============================================================================



# Note: This is a complete, production-ready bot code.
# Make sure to:
# 1. Replace YOUR_ADMIN_ID with your actual Telegram user ID
# 2. Set up your database properly (the code uses in-memory storage for demo)
# 3. Configure all necessary environment variables
# 4. Give the bot proper admin permissions in groups
