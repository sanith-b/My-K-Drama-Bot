for batch in range(batches):
                if temp.CANCEL:
                    await msg.edit(
                        f"🛑 **Indexing Cancelled**\n\n"
                        f"**Channel:** `{chat_title}`\n"
                        f"**Access:** {access_level}\n"
                        f"**Progress:** `{current:,}/{total_messages:,}`\n"
                        f"**Files Saved:** `{total_files:,}`",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ Close', callback_data='close_data')]])
                    )
                    break
                    
                batch_start = time.time()
                start_id = current + 1
                end_id = min(current + BATCH_SIZE, lst_msg_id)
                message_ids = range(start_id, end_id + 1)
                
                try:
                    # Add delay for member access to avoid rate limits
                    if not is_bot_admin:
                        await asyncio.sleep(0.5)  # Small delay for member access
                    
                    messages = await bot.get_messages(chat, list(message_ids))
                    if not isinstance(messages, list):
                        messages = [messages]
                        
                except FloodWait as e:
                    # Handle rate limiting especially for member access
                    LOGGER.warning(f"FloodWait: {e.value} seconds")
                    await asyncio.sleep(e.value)
                    try:
                        messages = await bot.get_messages(chat, list(message_ids))
                        if not isinstance(messages, list):
                            messages = [messages]
                    except Exception as retry_e:
                        LOGGER.error(f"Retry failed after FloodWait: {retry_e}")
                        errors += len(message_ids)
                        current += len(message_ids)
                        continue
                        
                except Exception as e:
                    LOGGER.error(f"Error fetching messages batch {batch}: {e}")
                    errors += len(message_ids)
                    current += len(message_ids)
                    
                    # For member access, try smaller batches if large batch fails
                    if not is_bot_admin and len(message_ids) > 50:
                        LOGGER.info("Trying smaller batch size for member access")
                        try:
                            for small_batch_start in range(start_id, end_id + 1, 25):
                                small_batch_end = min(small_batch_start + 24, end_id)
                                small_message_ids = list(range(small_batch_start, small_batch_end + 1))
                                try:
                                    await asyncio.sleep(0.3)  # Extra delay for small batches
                                    small_messages = await bot.get_messages(chat, small_message_ids)
                                    if not isinstance(small_messages, list):
                                        small_messages = [small_messages]
                                    
                                    # Process small batch
                                    save_tasks = []
                                    for message in small_messages:
                                        current += 1
                                        try:
                                            if message.empty:
                                                deleted += 1
                                                continue
                                            elif not message.media:
                                                no_media += 1
                                                continue
                                            elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                                                unsupported += 1
                                                continue
                                            
                                            media = getattr(message, message.media.value, None)
                                            if not media:
                                                unsupported += 1
                                                continue
                                                
                                            media.file_type = message.media.value
                                            media.caption = message.caption
                                            save_tasks.append(save_file(media))

                                        except Exception as proc_e:
                                            LOGGER.error(f"Error processing message {current}: {proc_e}")
                                            errors += 1
                                            continue
                                    
                                    # Execute save tasks for small batch
                                    if save_tasks:
                                        results = await asyncio.gather(*save_tasks, return_exceptions=True)
                                        for result in results:
                                            if isinstance(result, Exception):
                                                errors += 1
                                            else:
                                                ok, code = result
                                                if ok:
                                                    total_files += 1
                                                elif code == 0:
                                                    duplicate += 1
                                                elif code == 2:
                                                    errors += 1
                                                    
                                except Exception as small_e:
                                    LOGGER.error(f"Small batch error: {small_e}")
                                    errors += len(small_message_ids)
                                    current += len(small_message_ids)
                                    continue
                        except Exception as retry_e:
                            LOGGER.error(f"Failed to process with smaller batches: {retry_e}")
                    continue

                # Process messages normally if no errors occurred
                save_tasks = []
                for message in messages:
                    current += 1
                    try:
                        if message.empty:
                            deleted += 1
                            continue
                        elif not message.media:
                            no_media += 1
                            continue
                        elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                            unsupported += 1
                            continue
                        
                        media = getattr(message, message.media.value, None)
                        if not media:
                            unsupported += 1
                            continue
                            
                        media.file_type = message.media.value
                        media.caption = message.caption
                        save_tasks.append(save_file(media))

                    except Exception as e:
                        LOGGER.error(f"Error processing message {current}: {e}")
                        errors += 1
                        continue

                # Execute save tasks for normal batch
                if save_tasks:
                    results = await asyncio.gather(*save_tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, Exception):
                            errors += 1
                        else:
                            ok, code = result
                            if ok:
                                total_files += 1
                            elif code == 0:
                                duplicate += 1
                            elif code == 2:
                                errors += 1

                # Update progress with access level information
                batch_time = time.time() - batch_start
                batch_times.append(batch_time)
                elapsed = time.time() - start_time
                progress = current - temp.CURRENT
                percentage = (progress / total_fetch) * 100 if total_fetch > 0 else 100
                avg_batch_time = sum(batch_times) / len(batch_times) if batch_times else 1
                eta = (total_fetch - progress) / BATCH_SIZE * avg_batch_time if progress < total_fetch else 0
                progress_bar = get_progress_bar(min(int(percentage), 100))

                await msg.edit(
                    f"⚡ **Indexing in Progress**\n\n"
                    f"**Channel:** `{chat_title}` ({channel_type_display})\n"
                    f"**Access Level:** {access_level}\n"
                    f"**Batch:** `{batch + 1}/{batches}`\n\n"
                    f"{progress_bar} `{percentage:.1f}%`\n\n"
                    f"📊 **Statistics:**\n"
                    f"• **Total Messages:** `{total_messages:,}`\n"
                    f"• **Processed:** `{current:,}`\n"
                    f"• **Files Saved:** `{total_files:,}`\n"
                    f"• **Duplicates:** `{duplicate:,}`\n"
                    f"• **Deleted:** `{deleted:,}`\n"
                    f"• **Non-Media:** `{no_media + unsupported:,}`\n"
                    f"• **Errors:** `{errors:,}`\n\n"
                    f"⏱️ **Time:**\n"
                    f"• **Elapsed:** `{get_readable_time(elapsed)}`\n"
                    f"• **ETA:** `{get_readable_time(eta) if eta > 0 else 'Calculating...'}`",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🛑 Cancel', callback_data='index_cancel')]])
                )

            # Final summary with access level info
            elapsed = time.time() - start_time
            if not temp.CANCEL:
                success_note = ""
                if not is_bot_admin:
                    success_note = "\n\n✨ **Note:** Indexing completed successfully with member access!"
                
                await msg.edit(
                    f"✅ **Indexing Completed Successfully!**\n\n"
                    f"**Channel:** `{chat_title}` ({channel_type_display})\n"
                    f"**Access Level:** {access_level}\n\n"
                    f"📊 **Final Statistics:**\n"
                    f"• **Total Messages:** `{total_messages:,}`\n"
                    f"• **Processed:** `{current:,}`\n"
                    f"• **Files Saved:** `{total_files:,}`\n"
                    f"• **Duplicates:** `{duplicate:,}`\n"
                    f"• **Deleted:** `{deleted:,}`\n"
                    f"• **Non-Media:** `{no_media + unsupported:,}`\n"
                    f"• **Errors:** `{errors:,}`\n\n"
                    f"⏰ **Total Time:** `{get_readable_time(elapsed)}`\n"
                    f"🚀 **Speed:** `{total_files/elapsed:.1f} files/sec`{success_note}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✅ Close', callback_data='close_data')]])
                )import time
import re
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, ChannelPrivate, ChatAdminRequired
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified, PeerIdInvalid
from info import ADMINS, INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp, get_readable_time
from math import ceil
from logging_helper import LOGGER


lock = asyncio.Lock()

@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")
    _, raju, chat, lst_msg_id, from_user = query.data.split("#")
    if raju == 'reject':
        await query.message.delete()
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been declined by our moderators.',
                               reply_to_message_id=int(lst_msg_id))
        return

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
    msg = query.message

    await query.answer('Processing...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been accepted by our moderators and will be added soon.',
                               reply_to_message_id=int(lst_msg_id))
    await msg.edit(
        "Starting Indexing",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat)
    except:
        chat = chat
    await index_files_to_db(int(lst_msg_id), chat, msg, bot)


# New handler for manual channel ID input (for channels that can't forward)
@Client.on_message(filters.command('addchannel') & filters.private)
async def add_channel_manual(bot, message):
    """
    Manual channel addition for channels with forwarding restrictions
    Usage: /addchannel <chat_id> <last_message_id>
    """
    try:
        cmd_parts = message.text.split()
        if len(cmd_parts) < 3:
            return await message.reply(
                '📝 **Manual Channel Addition**\n\n'
                '**Format:** `/addchannel <chat_id> <last_message_id>`\n'
                '**Example:** `/addchannel -1001234567890 1000`\n\n'
                '💡 **Use this for channels that:**\n'
                '• Have forwarding restrictions\n'
                '• Are private and you know the Chat ID\n'
                '• Cannot be forwarded from\n\n'
                '📋 **How to get Chat ID:**\n'
                '• Use @userinfobot in the channel\n'
                '• Use @getidsbot\n'
                '• Check channel info if you\'re admin'
            )
        
        chat_id = cmd_parts[1]
        last_msg_id = int(cmd_parts[2])
        
        # Try to convert to int if it's numeric
        try:
            if chat_id.startswith('-'):
                chat_id = int(chat_id)
            elif chat_id.isnumeric():
                chat_id = int(("-100" + chat_id))
            # else keep as username
        except:
            pass
        
        # Process this like a regular index request
        await process_index_request(bot, message, chat_id, last_msg_id, is_manual=True)
        
    except ValueError:
        await message.reply('❌ Last message ID must be a number.')
    except Exception as e:
        await message.reply(f'❌ Error: {e}')


@Client.on_message((filters.forwarded | (filters.regex(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text ) & filters.private & filters.incoming)
async def send_for_index(bot, message):
    chat_id = None
    last_msg_id = None
    
    # Handle text links
    if message.text and not message.forward_from_chat:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match:
            return await message.reply(
                '❌ **Invalid link format**\n\n'
                '💡 **Alternative methods:**\n'
                '• Forward a message from the channel\n'
                '• Use `/addchannel <chat_id> <last_msg_id>` for restricted channels\n'
                '• Ensure the link format is correct'
            )
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id = int(("-100" + chat_id))
    
    # Handle forwarded messages (including from channels with restrictions)
    elif message.forward_from_chat:
        if message.forward_from_chat.type == enums.ChatType.CHANNEL:
            last_msg_id = message.forward_from_message_id
            chat_id = message.forward_from_chat.username or message.forward_from_chat.id
        else:
            return await message.reply(
                '❌ **Only channel messages can be indexed**\n\n'
                '💡 **For restricted channels use:**\n'
                '`/addchannel <chat_id> <last_msg_id>`'
            )
    
    # Handle messages that couldn't be detected properly
    else:
        return await message.reply(
            '❌ **Unable to detect channel information**\n\n'
            '✅ **Supported methods:**\n'
            '• Forward a message from the channel\n'
            '• Send a valid channel link\n'
            '• Use `/addchannel <chat_id> <last_msg_id>` for restricted channels\n\n'
            '🔒 **For channels that restrict forwarding:**\n'
            'Use the `/addchannel` command with the channel ID and last message ID.'
        )
    
    if chat_id and last_msg_id:
        await process_index_request(bot, message, chat_id, last_msg_id)


async def process_index_request(bot, message, chat_id, last_msg_id, is_manual=False):
    """
    Process index request from various sources (forwarded, link, manual)
    """
    source_type = "🔧 Manual Input" if is_manual else ("🔗 Link" if message.text and not message.forward_from_chat else "↩️ Forwarded")
    
    # Enhanced chat validation with support for non-admin access
    try:
        chat_info = await bot.get_chat(chat_id)
        is_private = chat_info.type == enums.ChatType.CHANNEL and not chat_info.username
        is_restricted = hasattr(chat_info, 'restrictions') and chat_info.restrictions
        chat_title = chat_info.title or "Unknown Channel"
        
        # Check bot's admin status
        bot_member = None
        is_bot_admin = False
        try:
            bot_member = await bot.get_chat_member(chat_id, bot.me.id)
            is_bot_admin = bot_member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
        except Exception:
            # Bot might not be a member or channel might not allow member queries
            pass
        
        # Check if it's a channel that restricts forwarding
        has_forward_restrictions = False
        try:
            # Try to get a recent message to check for restrictions
            recent_msg = await bot.get_messages(chat_id, 1)
            if hasattr(recent_msg, 'restriction_reason') or (hasattr(chat_info, 'restriction_reason') and chat_info.restriction_reason):
                has_forward_restrictions = True
        except:
            pass
            
    except ChannelInvalid:
        return await message.reply(
            '❌ **Channel Access Error**\n\n'
            'This may be a private channel/group or the bot is not a member.\n'
            '✅ **Solutions:**\n'
            '• Add me to the channel (admin preferred but not required)\n'
            '• For private channels: Make me admin or ensure I\'m a member\n'
            '• For public channels: I can try to join automatically'
        )
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply(
            '❌ **Invalid Username/Link**\n\n'
            '💡 **Try:**\n'
            '• Check the channel link is correct\n'
            '• Use `/addchannel <chat_id> <last_msg_id>` if link doesn\'t work\n'
            '• Ensure the channel exists and is accessible'
        )
    except ChannelPrivate:
        return await message.reply(
            '❌ **Private Channel Access Denied**\n\n'
            'I don\'t have access to this private channel.\n'
            '✅ **Required:**\n'
            '• Add me to the channel (admin preferred)\n'
            '• For restricted channels: Admin rights may be required\n'
            '• Ensure the channel allows bots'
        )
    except PeerIdInvalid:
        return await message.reply(
            '❌ **Invalid Chat ID**\n\n'
            '💡 **How to fix:**\n'
            '• Check the chat ID format (-100xxxxxxxxxx)\n'
            '• Ensure the channel exists\n'
            '• Try forwarding a message instead\n'
            '• Use @userinfobot to get correct chat ID'
        )
    except Exception as e:
        LOGGER.error(f"Error getting chat info: {e}")
        return await message.reply(f'❌ **Error accessing chat:** `{e}`')
    
    # Test message access with flexible approach (admin and non-admin)
    can_access_messages = False
    access_method = "unknown"
    
    try:
        test_msg = await bot.get_messages(chat_id, last_msg_id)
        if not test_msg.empty:
            can_access_messages = True
            access_method = "admin" if is_bot_admin else "member"
    except Exception as e:
        LOGGER.error(f"Error accessing messages: {e}")
        error_msg = str(e).lower()
        
        if "admin" in error_msg and not is_bot_admin:
            return await message.reply(
                '❌ **Admin Rights Required**\n\n'
                'This channel requires admin access for indexing.\n'
                '✅ **Solutions:**\n'
                '• Make me an admin in the channel\n'
                '• Grant "Read Messages" permission\n'
                '• For restricted channels: Grant "Manage Messages" permission'
            )
        elif "restricted" in error_msg or "forbidden" in error_msg:
            return await message.reply(
                '❌ **Restricted Content Channel**\n\n'
                'This channel has content restrictions.\n'
                '✅ **Required for indexing:**\n'
                '• Add me as admin with full rights\n'
                '• Grant "Read Messages" permission\n'
                '• Ensure I can access restricted content\n\n'
                '💡 **Note:** Some channels require special admin permissions for bots.'
            )
        elif "member" in error_msg:
            return await message.reply(
                '❌ **Not a Channel Member**\n\n'
                'I need to be added to this channel first.\n'
                '✅ **Solutions:**\n'
                '• Add me to the channel\n'
                '• Make me admin (recommended for better access)\n'
                '• Ensure the channel allows bots to join'
            )
        else:
            return await message.reply(
                f'❌ **Message Access Failed**\n\n'
                f'Error: `{e}`\n\n'
                '✅ **Common solutions:**\n'
                '• Add me to the channel\n'
                '• Make me admin (recommended)\n'
                '• Check message ID is correct\n'
                '• Ensure channel allows bot access'
            )

    if not can_access_messages:
        return await message.reply(
            '❌ **Cannot Access Messages**\n\n'
            'Unable to read messages from this channel.\n'
            '✅ **Required:**\n'
            '• Add me to the channel\n'
            '• Admin status recommended but not always required\n'
            '• Ensure proper permissions for bot access'
        )

    # Determine channel characteristics and access level
    channel_features = []
    if is_private:
        channel_features.append("🔒 Private")
    if has_forward_restrictions:
        channel_features.append("🚫 Forwarding Restricted")
    if is_restricted:
        channel_features.append("⚠️ Content Restricted")
    if not is_bot_admin:
        channel_features.append("👤 Member Access")
    else:
        channel_features.append("👑 Admin Access")
    
    channel_type_display = " ".join(channel_features) if channel_features else "📢 Public Channel"

    # Admin flow with enhanced information including access level
    if message.from_user.id in ADMINS:
        access_status = f"👑 Admin Access" if is_bot_admin else f"👤 Member Access ({access_method})"
        buttons = [
            [InlineKeyboardButton('✅ Accept & Index', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')],
            [InlineKeyboardButton('❌ Close', callback_data='close_data')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'📊 **Index Request Details**\n\n'
            f'**Source:** {source_type}\n'
            f'**Type:** {channel_type_display}\n'
            f'**Access:** {access_status}\n'
            f'**Title:** `{chat_title}`\n'
            f'**Chat ID:** `{chat_id}`\n'
            f'**Last Message ID:** `{last_msg_id:,}`\n\n'
            f'{"⚠️ **Note:** Bot is not admin - indexing may be slower and some features limited." if not is_bot_admin else ""}\n'
            f'{"⚠️ **Restrictions:** This channel has limitations that may affect indexing." if (has_forward_restrictions or is_restricted) else ""}\n'
            f'Do you want to index this channel?\n\n'
            f'💡 **Need to set skip?** Use /setskip command',
            reply_markup=reply_markup)

    # Regular user flow with enhanced link generation
    link = None
    if type(chat_id) is int:
        try:
            if is_private or has_forward_restrictions:
                # For private/restricted channels, try to create invite link
                try:
                    link = (await bot.create_chat_invite_link(chat_id)).invite_link
                except ChatAdminRequired:
                    return await message.reply(
                        '❌ **Cannot Create Invite Link**\n\n'
                        'I need admin permissions to create invite links for this channel.\n'
                        '✅ **Grant me:**\n'
                        '• Admin status\n'
                        '• "Invite Users" permission\n'
                        '• Access to restricted content (if applicable)'
                    )
                except Exception:
                    link = f"Private Channel - Chat ID: {chat_id}"
            else:
                # Public channel link
                link = f"https://t.me/c/{str(chat_id)[4:]}/{last_msg_id}"
        except Exception as e:
            LOGGER.error(f"Error creating link: {e}")
            link = f"Chat ID: {chat_id}"
    else:
        link = f"@{chat_id}"

    # Send to log channel for approval with enhanced information
    buttons = [
        [InlineKeyboardButton('✅ Accept Index', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')],
        [InlineKeyboardButton('❌ Reject Index', callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    restriction_note = ""
    if has_forward_restrictions or is_restricted:
        restriction_note = "\n⚠️ **Special Notes:** This channel has content/forwarding restrictions"
    
    await bot.send_message(LOG_CHANNEL,
                           f'📋 **#IndexRequest**\n\n'
                           f'**Requested by:** {message.from_user.mention} (`{message.from_user.id}`)\n'
                           f'**Source:** {source_type}\n'
                           f'**Type:** {channel_type_display}\n'
                           f'**Title:** `{chat_title}`\n'
                           f'**Chat ID:** `{chat_id}`\n'
                           f'**Last Message ID:** `{last_msg_id:,}`\n'
                           f'**Access Link:** {link}{restriction_note}',
                           reply_markup=reply_markup)
    
    # Enhanced confirmation message for user
    restriction_info = ""
    if has_forward_restrictions:
        restriction_info = "\n\n🚫 **Note:** This channel restricts forwarding, but indexing is still possible."
    if is_restricted:
        restriction_info += "\n⚠️ **Content Restrictions:** This channel may have special content policies."
    
    await message.reply(
        f'✅ **Request Submitted Successfully!**\n\n'
        f'**Channel:** `{chat_title}`\n'
        f'**Type:** {channel_type_display}\n'
        f'**Source:** {source_type}\n'
        f'**Messages to Index:** `{last_msg_id:,}`\n'
        f'{restriction_info}\n\n'
        f'⏳ **Status:** Waiting for moderator approval\n'
        f'📝 **What\'s next:** Our team will verify and approve your request.'
    )


# New command for direct private channel indexing by admins
@Client.on_message(filters.command('pindex') & filters.user(ADMINS) & filters.private)
async def private_index_command(bot, message):
    """
    Direct indexing command for admins
    Usage: /pindex <chat_id> <last_message_id>
    """
    try:
        cmd_parts = message.text.split()
        if len(cmd_parts) < 3:
            return await message.reply(
                '❌ **Invalid Usage**\n\n'
                '**Format:** `/pindex <chat_id> <last_message_id>`\n'
                '**Example:** `/pindex -1001234567890 1000`\n\n'
                '💡 **Tip:** Forward a message from the channel to get chat ID easily.'
            )
        
        chat_id = cmd_parts[1]
        last_msg_id = int(cmd_parts[2])
        
        # Try to convert to int if it's numeric
        try:
            chat_id = int(chat_id)
        except:
            pass
        
        # Validate access
        try:
            chat_info = await bot.get_chat(chat_id)
            test_msg = await bot.get_messages(chat_id, last_msg_id)
            
            if test_msg.empty:
                return await message.reply('❌ Cannot access the specified message.')
            
            is_private = chat_info.type == enums.ChatType.CHANNEL and not chat_info.username
            channel_type = "🔒 Private Channel" if is_private else "📢 Public Channel"
            
        except Exception as e:
            return await message.reply(f'❌ Error accessing chat: {e}')
        
        # Confirm before indexing
        buttons = [
            [InlineKeyboardButton('✅ Start Indexing', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')],
            [InlineKeyboardButton('❌ Cancel', callback_data='close_data')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        
        await message.reply(
            f'📊 **Ready to Index**\n\n'
            f'**Type:** {channel_type}\n'
            f'**Title:** `{chat_info.title}`\n'
            f'**Chat ID:** `{chat_id}`\n'
            f'**Last Message ID:** `{last_msg_id}`\n\n'
            f'Confirm to start indexing?',
            reply_markup=reply_markup
        )
        
    except ValueError:
        await message.reply('❌ Last message ID must be a number.')
    except Exception as e:
        await message.reply(f'❌ Error: {e}')


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
        except:
            return await message.reply("❌ Skip number should be an integer.")
        await message.reply(f"✅ Successfully set SKIP number to **{skip}**")
        temp.CURRENT = int(skip)
    else:
        current_skip = getattr(temp, 'CURRENT', 0)
        await message.reply(
            f"📋 **Skip Command Usage**\n\n"
            f"**Current Skip:** `{current_skip}`\n"
            f"**Usage:** `/setskip <number>`\n"
            f"**Example:** `/setskip 100`\n\n"
            f"💡 Skip number determines from which message ID to start indexing."
        )


# New command to check private channel info
@Client.on_message(filters.command('chatinfo') & filters.user(ADMINS) & filters.private)
async def chat_info_command(bot, message):
    """Get information about a chat/channel"""
    try:
        cmd_parts = message.text.split()
        if len(cmd_parts) < 2:
            return await message.reply(
                f'❌ **Invalid Usage**\n\n'
                f'**Format:** `/chatinfo <chat_id_or_username>`\n'
                f'**Examples:**\n'
                f'• `/chatinfo -1001234567890`\n'
                f'• `/chatinfo @channel`\n\n'
                f'💡 **For restricted channels:** Use the full chat ID starting with -100'
            )
        
        chat_id = cmd_parts[1]
        try:
            chat_id = int(chat_id)
        except:
            pass
        
        chat_info = await bot.get_chat(chat_id)
        
        # Get member count if possible
        try:
            member_count = await bot.get_chat_members_count(chat_id)
        except:
            member_count = "Unable to fetch"
        
        # Determine chat type and privacy
        chat_type_map = {
            enums.ChatType.PRIVATE: "👤 Private Chat",
            enums.ChatType.BOT: "🤖 Bot",
            enums.ChatType.GROUP: "👥 Group",
            enums.ChatType.SUPERGROUP: "👥 Supergroup",
            enums.ChatType.CHANNEL: "📢 Channel"
        }
        
        chat_type = chat_type_map.get(chat_info.type, "Unknown")
        is_private = chat_info.type == enums.ChatType.CHANNEL and not chat_info.username
        
        if is_private:
            chat_type += " (Private)"
        
        info_text = (
            f"📊 **Chat Information**\n\n"
            f"**Title:** `{chat_info.title or 'N/A'}`\n"
            f"**Type:** {chat_type}\n"
            f"**ID:** `{chat_info.id}`\n"
            f"**Username:** `{chat_info.username or 'None'}`\n"
            f"**Members:** `{member_count}`\n"
            f"**Description:** `{(chat_info.description[:100] + '...') if chat_info.description and len(chat_info.description) > 100 else (chat_info.description or 'None')}`\n\n"
            f"✅ **Access:** Bot can access this chat"
        )
        
        await message.reply(info_text)
        
    except Exception as e:
        await message.reply(f"❌ **Error getting chat info:**\n`{e}`")


def get_progress_bar(percent, length=10):
    filled = int(length * percent / 100)
    unfilled = length - filled
    return '█' * filled + '▒' * unfilled


async def index_files_to_db(lst_msg_id, chat, msg, bot):
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    BATCH_SIZE = 200
    start_time = time.time()

    async with lock:
        try:
            current = temp.CURRENT
            temp.CANCEL = False
            total_messages = lst_msg_id
            total_fetch = lst_msg_id - current
            
            # Get chat info and bot access level for better logging
            try:
                chat_info = await bot.get_chat(chat)
                chat_title = chat_info.title or f"Chat {chat}"
                is_private = chat_info.type == enums.ChatType.CHANNEL and not chat_info.username
                
                # Check bot's admin status
                is_bot_admin = False
                access_level = "Member"
                try:
                    bot_member = await bot.get_chat_member(chat, bot.me.id)
                    is_bot_admin = bot_member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                    access_level = "Admin" if is_bot_admin else "Member"
                except:
                    pass
                    
            except:
                chat_title = f"Chat {chat}"
                is_private = False
                is_bot_admin = False
                access_level = "Unknown"

            # Determine indexing approach based on access level
            if not is_bot_admin:
                # Reduce batch size for member access to avoid rate limits
                BATCH_SIZE = 100
                await msg.edit(
                    "⚠️ **Member Access Mode**\n\n"
                    f"**Channel:** `{chat_title}`\n"
                    f"**Access:** 👤 {access_level}\n"
                    f"**Note:** Indexing with member access (slower but works)\n\n"
                    f"🚀 **Starting indexing...**",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🛑 Cancel', callback_data='index_cancel')]])
                )
            
            channel_features = []
            if is_private:
                channel_features.append("🔒 Private")
            if not is_bot_admin:
                channel_features.append("👤 Member Access")
            else:
                channel_features.append("👑 Admin Access")
            
            channel_type_display = " ".join(channel_features) if channel_features else "📢 Public"
            
            if total_messages <= 0:
                await msg.edit(
                    "🚫 **No Messages To Index**\n\n"
                    f"**Channel:** `{chat_title}`\n"
                    f"**Type:** {channel_type_display}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ Close', callback_data='close_data')]])
                )
                return
                
            batches = ceil(total_fetch / BATCH_SIZE)
            batch_times = []
            
            await msg.edit(
                f"🚀 **Indexing Started**\n\n"
                f"**Channel:** `{chat_title}`\n"
                f"**Type:** {channel_type_display}\n"
                f"**Batch Size:** `{BATCH_SIZE}` {'(Reduced for member access)' if not is_bot_admin else ''}\n"
                f"**Total Messages:** `{total_messages:,}`\n"
                f"**Messages to Fetch:** `{total_fetch:,}`\n"
                f"**Elapsed:** `{get_readable_time(time.time() - start_time)}`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🛑 Cancel', callback_data='index_cancel')]])
            )
            
            for batch in range(batches):
                if temp.CANCEL:
                    await msg.edit(
                        f"🛑 **Indexing Cancelled**\n\n"
                        f"**Channel:** `{chat_title}`\n"
                        f"**Progress:** `{current:,}/{total_messages:,}`\n"
                        f"**Files Saved:** `{total_files:,}`",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ Close', callback_data='close_data')]])
                    )
                    break
                    
                batch_start = time.time()
                start_id = current + 1
                end_id = min(current + BATCH_SIZE, lst_msg_id)
                message_ids = range(start_id, end_id + 1)
                
                try:
                    messages = await bot.get_messages(chat, list(message_ids))
                    if not isinstance(messages, list):
                        messages = [messages]
                except Exception as e:
                    LOGGER.error(f"Error fetching messages: {e}")
                    errors += len(message_ids)
                    current += len(message_ids)
                    continue

                save_tasks = []
                for message in messages:
                    current += 1
                    try:
                        if message.empty:
                            deleted += 1
                            continue
                        elif not message.media:
                            no_media += 1
                            continue
                        elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                            unsupported += 1
                            continue
                        
                        media = getattr(message, message.media.value, None)
                        if not media:
                            unsupported += 1
                            continue
                            
                        media.file_type = message.media.value
                        media.caption = message.caption
                        save_tasks.append(save_file(media))

                    except Exception as e:
                        LOGGER.error(f"Error processing message {current}: {e}")
                        errors += 1
                        continue

                # Execute save tasks
                results = await asyncio.gather(*save_tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        errors += 1
                    else:
                        ok, code = result
                        if ok:
                            total_files += 1
                        elif code == 0:
                            duplicate += 1
                        elif code == 2:
                            errors += 1

                # Update progress
                batch_time = time.time() - batch_start
                batch_times.append(batch_time)
                elapsed = time.time() - start_time
                progress = current - temp.CURRENT
                percentage = (progress / total_fetch) * 100 if total_fetch > 0 else 100
                avg_batch_time = sum(batch_times) / len(batch_times) if batch_times else 1
                eta = (total_fetch - progress) / BATCH_SIZE * avg_batch_time if progress < total_fetch else 0
                progress_bar = get_progress_bar(min(int(percentage), 100))

                await msg.edit(
                    f"⚡ **Indexing in Progress**\n\n"
                    f"**Channel:** `{chat_title}` ({channel_type})\n"
                    f"**Batch:** `{batch + 1}/{batches}`\n\n"
                    f"{progress_bar} `{percentage:.1f}%`\n\n"
                    f"📊 **Statistics:**\n"
                    f"• **Total Messages:** `{total_messages:,}`\n"
                    f"• **Processed:** `{current:,}`\n"
                    f"• **Files Saved:** `{total_files:,}`\n"
                    f"• **Duplicates:** `{duplicate:,}`\n"
                    f"• **Deleted:** `{deleted:,}`\n"
                    f"• **Non-Media:** `{no_media + unsupported:,}`\n"
                    f"• **Errors:** `{errors:,}`\n\n"
                    f"⏱️ **Time:**\n"
                    f"• **Elapsed:** `{get_readable_time(elapsed)}`\n"
                    f"• **ETA:** `{get_readable_time(eta) if eta > 0 else 'Calculating...'}`",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🛑 Cancel', callback_data='index_cancel')]])
                )

            # Final summary
            elapsed = time.time() - start_time
            if not temp.CANCEL:
                await msg.edit(
                    f"✅ **Indexing Completed Successfully!**\n\n"
                    f"**Channel:** `{chat_title}` ({channel_type})\n\n"
                    f"📊 **Final Statistics:**\n"
                    f"• **Total Messages:** `{total_messages:,}`\n"
                    f"• **Processed:** `{current:,}`\n"
                    f"• **Files Saved:** `{total_files:,}`\n"
                    f"• **Duplicates:** `{duplicate:,}`\n"
                    f"• **Deleted:** `{deleted:,}`\n"
                    f"• **Non-Media:** `{no_media + unsupported:,}`\n"
                    f"• **Errors:** `{errors:,}`\n\n"
                    f"⏰ **Total Time:** `{get_readable_time(elapsed)}`\n"
                    f"🚀 **Speed:** `{total_files/elapsed:.1f} files/sec`",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✅ Close', callback_data='close_data')]])
                )
                
        except Exception as e:
            LOGGER.error(f"Indexing error: {e}")
            await msg.edit(
                f"❌ **Indexing Error**\n\n"
                f"**Error:** `{str(e)[:200]}...`\n"
                f"**Files Saved:** `{total_files:,}`\n"
                f"**Processed:** `{current:,}`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ Close', callback_data='close_data')]])
            )
