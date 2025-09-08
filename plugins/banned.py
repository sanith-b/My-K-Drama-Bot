from pyrogram import Client, filters
from pyrogram.types import Message, ChatMember, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import ChatAdminRequired, UserNotParticipant, FloodWait
from utils import temp
from database.users_chats_db import db
from info import SUPPORT_CHAT, ADMINS
import asyncio
from datetime import datetime, timedelta
import re

# Existing filters
async def banned_users(_, client, message: Message):
    return (
        message.from_user is not None or not message.sender_chat
    ) and message.from_user.id in temp.BANNED_USERS

banned_user = filters.create(banned_users)

async def disabled_chat(_, client, message: Message):
    return message.chat.id in temp.BANNED_CHATS

disabled_group = filters.create(disabled_chat)

# New filter for admin-only commands
async def admin_filter(_, client, message: Message):
    if not message.from_user:
        return False
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ["creator", "administrator"]
    except:
        return False

admin_only = filters.create(admin_filter)

# Filter for bot admins
def bot_admin_filter(_, __, message):
    return message.from_user.id in ADMINS

bot_admin = filters.create(bot_admin_filter)

# Existing handlers
@Client.on_message(filters.private & banned_user & filters.incoming)
async def ban_reply(bot, message):
    ban = await db.get_ban_status(message.from_user.id)
    await message.reply(f'Sorry Dude, You are Banned to use Me. \nBan Reason : {ban["ban_reason"]}')

@Client.on_message(filters.group & disabled_group & filters.incoming)
async def grp_bd(bot, message):
    buttons = [[
        InlineKeyboardButton('Support', url=SUPPORT_CHAT)
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    vazha = await db.get_chat(message.chat.id)
    k = await message.reply(
        text=f"CHAT NOT ALLOWED 🐞\n\nMy admins has restricted me from working here ! If you want to know more about it contact support..\nReason : <code>{vazha['reason']}</code>.",
        reply_markup=reply_markup)
    try:
        await k.pin()
    except:
        pass
    await bot.leave_chat(message.chat.id)

# =============================================================================
# NEW GROUP MANAGEMENT FEATURES
# =============================================================================

# Kick/Ban Members
@Client.on_message(filters.group & admin_only & filters.command(["kick", "ban"]))
async def kick_ban_user(bot, message):
    command = message.command[0].lower()
    
    if not message.reply_to_message and len(message.command) < 2:
        await message.reply(f"Reply to a user or provide username/ID to {command}")
        return
    
    try:
        if message.reply_to_message:
            user_id = message.reply_to_message.from_user.id
            user_name = message.reply_to_message.from_user.first_name
        else:
            user_input = message.command[1]
            if user_input.isdigit():
                user_id = int(user_input)
            else:
                user_id = user_input.replace("@", "")
            
            user = await bot.get_users(user_id)
            user_id = user.id
            user_name = user.first_name
        
        if command == "kick":
            await bot.ban_chat_member(message.chat.id, user_id)
            await bot.unban_chat_member(message.chat.id, user_id)
            await message.reply(f"✅ {user_name} has been kicked from the group!")
        else:  # ban
            await bot.ban_chat_member(message.chat.id, user_id)
            await message.reply(f"✅ {user_name} has been banned from the group!")
    
    except Exception as e:
        await message.reply(f"❌ Failed to {command} user: {str(e)}")

# Unban Members
@Client.on_message(filters.group & admin_only & filters.command("unban"))
async def unban_user(bot, message):
    if len(message.command) < 2:
        await message.reply("Provide username or user ID to unban")
        return
    
    try:
        user_input = message.command[1]
        if user_input.isdigit():
            user_id = int(user_input)
        else:
            user_id = user_input.replace("@", "")
        
        user = await bot.get_users(user_id)
        await bot.unban_chat_member(message.chat.id, user.id)
        await message.reply(f"✅ {user.first_name} has been unbanned!")
    
    except Exception as e:
        await message.reply(f"❌ Failed to unban user: {str(e)}")

# Mute/Unmute Members
@Client.on_message(filters.group & admin_only & filters.command(["mute", "unmute"]))
async def mute_unmute_user(bot, message):
    command = message.command[0].lower()
    
    if not message.reply_to_message and len(message.command) < 2:
        await message.reply(f"Reply to a user or provide username/ID to {command}")
        return
    
    try:
        if message.reply_to_message:
            user_id = message.reply_to_message.from_user.id
            user_name = message.reply_to_message.from_user.first_name
        else:
            user_input = message.command[1]
            if user_input.isdigit():
                user_id = int(user_input)
            else:
                user_id = user_input.replace("@", "")
            
            user = await bot.get_users(user_id)
            user_id = user.id
            user_name = user.first_name
        
        if command == "mute":
            from pyrogram.types import ChatPermissions
            await bot.restrict_chat_member(
                message.chat.id, 
                user_id, 
                ChatPermissions(can_send_messages=False)
            )
            await message.reply(f"🔇 {user_name} has been muted!")
        else:  # unmute
            from pyrogram.types import ChatPermissions
            await bot.restrict_chat_member(
                message.chat.id, 
                user_id, 
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            await message.reply(f"🔊 {user_name} has been unmuted!")
    
    except Exception as e:
        await message.reply(f"❌ Failed to {command} user: {str(e)}")

# Temporary Mute
@Client.on_message(filters.group & admin_only & filters.command("tmute"))
async def temp_mute(bot, message):
    if not message.reply_to_message or len(message.command) < 2:
        await message.reply("Reply to a user and provide time (e.g., 5m, 1h, 1d)")
        return
    
    try:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.first_name
        time_str = message.command[1]
        
        # Parse time
        time_units = {'m': 60, 'h': 3600, 'd': 86400}
        time_match = re.match(r'(\d+)([mhd])', time_str.lower())
        
        if not time_match:
            await message.reply("Invalid time format. Use: 5m, 1h, 2d")
            return
        
        duration = int(time_match.group(1)) * time_units[time_match.group(2)]
        until_date = datetime.now() + timedelta(seconds=duration)
        
        from pyrogram.types import ChatPermissions
        await bot.restrict_chat_member(
            message.chat.id, 
            user_id, 
            ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        
        await message.reply(f"🔇 {user_name} has been muted for {time_str}!")
    
    except Exception as e:
        await message.reply(f"❌ Failed to temporarily mute user: {str(e)}")

# Promote/Demote Members
@Client.on_message(filters.group & admin_only & filters.command(["promote", "demote"]))
async def promote_demote_user(bot, message):
    command = message.command[0].lower()
    
    if not message.reply_to_message and len(message.command) < 2:
        await message.reply(f"Reply to a user or provide username/ID to {command}")
        return
    
    try:
        if message.reply_to_message:
            user_id = message.reply_to_message.from_user.id
            user_name = message.reply_to_message.from_user.first_name
        else:
            user_input = message.command[1]
            if user_input.isdigit():
                user_id = int(user_input)
            else:
                user_id = user_input.replace("@", "")
            
            user = await bot.get_users(user_id)
            user_id = user.id
            user_name = user.first_name
        
        if command == "promote":
            await bot.promote_chat_member(
                message.chat.id, 
                user_id,
                can_delete_messages=True,
                can_restrict_members=True,
                can_invite_users=True,
                can_pin_messages=True
            )
            await message.reply(f"⬆️ {user_name} has been promoted to admin!")
        else:  # demote
            await bot.promote_chat_member(
                message.chat.id, 
                user_id,
                can_delete_messages=False,
                can_restrict_members=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_promote_members=False,
                can_change_info=False
            )
            await message.reply(f"⬇️ {user_name} has been demoted!")
    
    except Exception as e:
        await message.reply(f"❌ Failed to {command} user: {str(e)}")

# Delete Messages
@Client.on_message(filters.group & admin_only & filters.command("del"))
async def delete_message(bot, message):
    if not message.reply_to_message:
        await message.reply("Reply to a message to delete it")
        return
    
    try:
        await message.reply_to_message.delete()
        await message.delete()
    except Exception as e:
        await message.reply(f"❌ Failed to delete message: {str(e)}")

# Purge Messages
@Client.on_message(filters.group & admin_only & filters.command("purge"))
async def purge_messages(bot, message):
    if not message.reply_to_message:
        await message.reply("Reply to a message to start purging from")
        return
    
    try:
        start_msg_id = message.reply_to_message.message_id
        end_msg_id = message.message_id
        
        deleted_count = 0
        for msg_id in range(start_msg_id, end_msg_id):
            try:
                await bot.delete_messages(message.chat.id, msg_id)
                deleted_count += 1
                await asyncio.sleep(0.1)  # Prevent flood
            except:
                continue
        
        status_msg = await message.reply(f"🗑️ Deleted {deleted_count} messages!")
        await asyncio.sleep(5)
        await status_msg.delete()
        await message.delete()
    
    except Exception as e:
        await message.reply(f"❌ Failed to purge messages: {str(e)}")

# Pin/Unpin Messages
@Client.on_message(filters.group & admin_only & filters.command(["pin", "unpin"]))
async def pin_unpin_message(bot, message):
    command = message.command[0].lower()
    
    if not message.reply_to_message:
        await message.reply(f"Reply to a message to {command} it")
        return
    
    try:
        if command == "pin":
            await message.reply_to_message.pin()
            await message.reply("📌 Message pinned!")
        else:  # unpin
            await message.reply_to_message.unpin()
            await message.reply("📌 Message unpinned!")
    
    except Exception as e:
        await message.reply(f"❌ Failed to {command} message: {str(e)}")

# Group Settings
@Client.on_message(filters.group & admin_only & filters.command("lock"))
async def lock_group(bot, message):
    if len(message.command) < 2:
        await message.reply("Specify what to lock: messages, media, stickers, links, forwards")
        return
    
    lock_type = message.command[1].lower()
    
    try:
        from pyrogram.types import ChatPermissions
        
        if lock_type == "messages":
            permissions = ChatPermissions(can_send_messages=False)
        elif lock_type == "media":
            permissions = ChatPermissions(can_send_media_messages=False)
        elif lock_type == "stickers":
            permissions = ChatPermissions(can_send_other_messages=False)
        elif lock_type == "links":
            permissions = ChatPermissions(can_add_web_page_previews=False)
        elif lock_type == "forwards":
            permissions = ChatPermissions(can_send_messages=True, can_send_media_messages=False)
        else:
            await message.reply("Invalid lock type. Use: messages, media, stickers, links, forwards")
            return
        
        await bot.set_chat_permissions(message.chat.id, permissions)
        await message.reply(f"🔒 Locked {lock_type} for all members!")
    
    except Exception as e:
        await message.reply(f"❌ Failed to lock {lock_type}: {str(e)}")

@Client.on_message(filters.group & admin_only & filters.command("unlock"))
async def unlock_group(bot, message):
    try:
        from pyrogram.types import ChatPermissions
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        
        await bot.set_chat_permissions(message.chat.id, permissions)
        await message.reply("🔓 Unlocked all restrictions!")
    
    except Exception as e:
        await message.reply(f"❌ Failed to unlock: {str(e)}")

# Group Info
@Client.on_message(filters.group & admin_only & filters.command("info"))
async def group_info(bot, message):
    try:
        chat = await bot.get_chat(message.chat.id)
        admins = []
        async for member in bot.iter_chat_members(message.chat.id, filter="administrators"):
            admins.append(f"• {member.user.first_name}")
        
        info_text = f"""
📊 **Group Information**

**Name:** {chat.title}
**ID:** `{chat.id}`
**Type:** {chat.type}
**Members:** {await bot.get_chat_members_count(message.chat.id)}
**Description:** {chat.description or 'No description'}

**Administrators ({len(admins)}):**
{chr(10).join(admins)}
        """
        
        await message.reply(info_text)
    
    except Exception as e:
        await message.reply(f"❌ Failed to get group info: {str(e)}")

# Warn System (requires database implementation)
@Client.on_message(filters.group & admin_only & filters.command("warn"))
async def warn_user(bot, message):
    if not message.reply_to_message:
        await message.reply("Reply to a user to warn them")
        return
    
    try:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.first_name
        reason = " ".join(message.command[1:]) if len(message.command) > 1 else "No reason provided"
        
        # This would need database implementation
        # warn_count = await db.add_warn(message.chat.id, user_id, reason)
        
        await message.reply(f"⚠️ {user_name} has been warned!\nReason: {reason}")
        
    except Exception as e:
        await message.reply(f"❌ Failed to warn user: {str(e)}")

# Bot Admin Commands
@Client.on_message(filters.private & bot_admin & filters.command("gban"))
async def global_ban(bot, message):
    if len(message.command) < 2:
        await message.reply("Provide user ID to globally ban")
        return
    
    try:
        user_id = int(message.command[1])
        reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason provided"
        
        # Add to banned users
        temp.BANNED_USERS.add(user_id)
        await db.ban_user(user_id, reason)
        
        await message.reply(f"✅ User {user_id} has been globally banned!\nReason: {reason}")
        
    except Exception as e:
        await message.reply(f"❌ Failed to globally ban user: {str(e)}")

@Client.on_message(filters.private & bot_admin & filters.command("ungban"))
async def global_unban(bot, message):
    if len(message.command) < 2:
        await message.reply("Provide user ID to globally unban")
        return
    
    try:
        user_id = int(message.command[1])
        
        # Remove from banned users
        temp.BANNED_USERS.discard(user_id)
        await db.unban_user(user_id)
        
        await message.reply(f"✅ User {user_id} has been globally unbanned!")
        
    except Exception as e:
        await message.reply(f"❌ Failed to globally unban user: {str(e)}")

@Client.on_message(filters.private & bot_admin & filters.command("disable"))
async def disable_chat(bot, message):
    if len(message.command) < 2:
        await message.reply("Provide chat ID to disable")
        return
    
    try:
        chat_id = int(message.command[1])
        reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason provided"
        
        # Add to banned chats
        temp.BANNED_CHATS.add(chat_id)
        await db.disable_chat(chat_id, reason)
        
        await message.reply(f"✅ Chat {chat_id} has been disabled!\nReason: {reason}")
        
    except Exception as e:
        await message.reply(f"❌ Failed to disable chat: {str(e)}")

@Client.on_message(filters.private & bot_admin & filters.command("enable"))
async def enable_chat(bot, message):
    if len(message.command) < 2:
        await message.reply("Provide chat ID to enable")
        return
    
    try:
        chat_id = int(message.command[1])
        
        # Remove from banned chats
        temp.BANNED_CHATS.discard(chat_id)
        await db.enable_chat(chat_id)
        
        await message.reply(f"✅ Chat {chat_id} has been enabled!")
        
    except Exception as e:
        await message.reply(f"❌ Failed to enable chat: {str(e)}")

# Help Command
@Client.on_message(filters.command("help"))
async def help_command(bot, message):
    help_text = """
🤖 **Group Management Commands**

**Member Management:**
• `/kick` - Kick a member
• `/ban` - Ban a member
• `/unban` - Unban a member
• `/mute` - Mute a member
• `/unmute` - Unmute a member
• `/tmute` - Temporarily mute (e.g., 5m, 1h, 1d)
• `/promote` - Promote to admin
• `/demote` - Demote admin
• `/warn` - Warn a member

**Message Management:**
• `/del` - Delete replied message
• `/purge` - Delete messages from replied to current
• `/pin` - Pin replied message
• `/unpin` - Unpin replied message

**Group Settings:**
• `/lock` - Lock group features
• `/unlock` - Unlock all restrictions
• `/info` - Show group information

**Bot Admin Only:**
• `/gban` - Global ban user
• `/ungban` - Global unban user
• `/disable` - Disable bot in chat
• `/enable` - Enable bot in chat

*Note: Most commands require admin rights*
    """
    
    await message.reply(help_text)
