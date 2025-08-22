import datetime
import logging
from typing import List, Dict, Optional
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_NAME = "pastppr"
DATABASE_URI = "mongodb+srv://kdramabot:Buo0fRGenkOAkgXH@pastppr.ipuyepp.mongodb.net/?retryWrites=true&w=majority&appName=pastppr"

# Initialize MongoDB client
mongo_client = AsyncIOMotorClient(DATABASE_URI)
db = mongo_client[DATABASE_NAME]
requests_collection = db.drama_requests
admins_collection = db.admins

# Admin configuration - Add your admin user IDs here
ADMIN_IDS = [123456789, 987654321]  # Replace with actual admin user IDs
ADMIN_CHANNEL_ID = -1001234567890   # Replace with your admin channel/group ID (optional)

# Request status constants
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved" 
STATUS_REJECTED = "rejected"
STATUS_PROCESSING = "processing"

# User data storage for conversation flow
user_states = {}
USER_STATE_REQUESTING = "requesting_drama"

async def safe_edit_message(message, text, reply_markup=None, parse_mode=None):
    """Safely edit a message, handling MESSAGE_NOT_MODIFIED errors"""
    try:
        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" in str(e):
            return False  # Message wasn't modified, but that's okay
        else:
            logger.error(f"Error editing message: {e}")
            return False

async def safe_send_message(client, user_id, text, reply_markup=None, parse_mode=None):
    """Safely send a message, handling various errors"""
    try:
        await client.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True
    except Exception as e:
        logger.error(f"Error sending message to {user_id}: {e}")
        return False

async def handle_callback_error(callback, error):
    """Handle callback errors globally"""
    if "MESSAGE_NOT_MODIFIED" in str(error):
        await callback.answer("✅ Content is already up to date!")
        return True
    elif "QUERY_ID_INVALID" in str(error):
        # Query too old, just ignore
        return True
    else:
        logger.error(f"Callback error: {error}")
        await callback.answer("❌ An error occurred!", show_alert=True)
        return False

async def init_admin_db():
    """Initialize admin database with predefined admin IDs"""
    try:
        for admin_id in ADMIN_IDS:
            await admins_collection.update_one(
                {"user_id": admin_id},
                {
                    "$set": {
                        "user_id": admin_id,
                        "added_date": datetime.datetime.utcnow(),
                        "is_active": True
                    }
                },
                upsert=True
            )
        logger.info(f"Initialized {len(ADMIN_IDS)} admins in database")
    except Exception as e:
        logger.error(f"Error initializing admin database: {e}")

async def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    return user_id in ADMIN_IDS

async def create_request(user_id: int, username: str, first_name: str, drama_name: str, description: str = "") -> str:
    """Create a new drama request"""
    try:
        request_data = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "drama_name": drama_name,
            "description": description,
            "request_date": datetime.datetime.utcnow(),
            "status": STATUS_PENDING,
            "admin_response": None,
            "response_date": None,
            "admin_id": None
        }
        
        result = await requests_collection.insert_one(request_data)
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"Error creating request: {e}")
        return None

async def get_user_requests(user_id: int, limit: int = 10) -> List[Dict]:
    """Get user's drama requests"""
    try:
        cursor = requests_collection.find(
            {"user_id": user_id}
        ).sort("request_date", -1).limit(limit)
        
        requests = await cursor.to_list(length=limit)
        return requests
    except Exception as e:
        logger.error(f"Error getting user requests: {e}")
        return []

async def get_pending_requests(limit: int = 20) -> List[Dict]:
    """Get all pending requests"""
    try:
        cursor = requests_collection.find(
            {"status": STATUS_PENDING}
        ).sort("request_date", 1).limit(limit)
        
        requests = await cursor.to_list(length=limit)
        return requests
    except Exception as e:
        logger.error(f"Error getting pending requests: {e}")
        return []

async def update_request_status(request_id: str, status: str, admin_id: int, admin_response: str = None) -> bool:
    """Update request status"""
    try:
        from bson import ObjectId
        update_data = {
            "status": status,
            "admin_id": admin_id,
            "response_date": datetime.datetime.utcnow()
        }
        
        if admin_response:
            update_data["admin_response"] = admin_response
        
        result = await requests_collection.update_one(
            {"_id": ObjectId(request_id)},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating request status: {e}")
        return False

async def get_request_by_id(request_id: str) -> Optional[Dict]:
    """Get request by ID"""
    try:
        from bson import ObjectId
        request = await requests_collection.find_one({"_id": ObjectId(request_id)})
        return request
    except Exception as e:
        logger.error(f"Error getting request by ID: {e}")
        return None

async def get_requests_stats() -> Dict:
    """Get request statistics"""
    try:
        pipeline = [
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        stats_cursor = requests_collection.aggregate(pipeline)
        stats_list = await stats_cursor.to_list(length=None)
        
        stats = {stat["_id"]: stat["count"] for stat in stats_list}
        
        total_requests = await requests_collection.count_documents({})
        unique_users = len(await requests_collection.distinct("user_id"))
        
        return {
            "total": total_requests,
            "unique_users": unique_users,
            "pending": stats.get(STATUS_PENDING, 0),
            "approved": stats.get(STATUS_APPROVED, 0),
            "rejected": stats.get(STATUS_REJECTED, 0),
            "processing": stats.get(STATUS_PROCESSING, 0)
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {}

@Client.on_message(filters.command(["start"]))
async def start_command(client, message):
    """Start command with main menu"""
    try:
        user_id = message.from_user.id
        first_name = message.from_user.first_name or "User"
        
        buttons = [
            [InlineKeyboardButton("🎭 Request Drama", callback_data="request_drama")],
            [InlineKeyboardButton("📋 My Requests", callback_data="my_requests")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help_info")]
        ]
        
        # Add admin panel for admins
        if await is_admin(user_id):
            buttons.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel")])
        
        # Add timestamp to ensure content is different
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        welcome_text = (
            f"🎬 <b>Welcome to K-Drama Request Bot, {first_name}!</b>\n\n"
            "Can't find your favorite K-Drama in our collection? "
            "Request it from our admins and we'll try to add it!\n\n"
            "Choose an option below to get started:\n"
            f"<i>Last updated: {timestamp}</i>"
        )
        
        await message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.reply_text("❌ Something went wrong! Please try again.")

@Client.on_message(filters.command(["request"]))
async def request_command(client, message):
    """Direct request command"""
    user_id = message.from_user.id
    user_states[user_id] = USER_STATE_REQUESTING
    
    instructions_text = (
        "🎭 <b>Request a K-Drama</b>\n\n"
        "Please send your drama request in this format:\n\n"
        "<b>Drama Name:</b> [Drama Title]\n"
        "<b>Description:</b> [Year, actors, or any specific details]\n\n"
        "<b>Example:</b>\n"
        "<b>Drama Name:</b> Business Proposal\n"
        "<b>Description:</b> 2022 romantic comedy with Ahn Hyo-seop and Kim Sejeong\n\n"
        "Or just send the drama name and any details you know.\n"
        "Send your request now:"
    )
    
    await message.reply_text(instructions_text, parse_mode=ParseMode.HTML)

@Client.on_callback_query(filters.regex(r"^request_drama$"))
async def request_drama_callback(client, query):
    """Handle request drama button"""
    user_id = query.from_user.id
    user_states[user_id] = USER_STATE_REQUESTING
    
    instructions_text = (
        "🎭 <b>Request a K-Drama</b>\n\n"
        "Please send your drama request in this format:\n\n"
        "<b>Drama Name:</b> [Drama Title]\n"
        "<b>Description:</b> [Year, actors, or any specific details]\n\n"
        "<b>Example:</b>\n"
        "<b>Drama Name:</b> Business Proposal\n"
        "<b>Description:</b> 2022 romantic comedy with Ahn Hyo-seop and Kim Sejeong\n\n"
        "Or just send the drama name and any details you know.\n"
        "Send your request now:"
    )
    
    await safe_edit_message(query.message, instructions_text, parse_mode=ParseMode.HTML)
    await query.answer()

@Client.on_message(filters.text & ~filters.command([]))
async def handle_text_messages(client, message):
    """Handle text messages for drama requests"""
    user_id = message.from_user.id
    
    # Check if user is in requesting state
    if user_states.get(user_id) != USER_STATE_REQUESTING:
        return
    
    try:
        user = message.from_user
        username = user.username or ""
        first_name = user.first_name or "User"
        message_text = message.text.strip()
        
        # Validate input
        if not message_text or len(message_text) < 3:
            await message.reply_text(
                "❌ Please provide a valid drama name (at least 3 characters).\n"
                "Try again:"
            )
            return
        
        # Parse the request
        drama_name = ""
        description = ""
        
        # Try to parse structured format first
        name_match = re.search(r"(?i)(drama name|title):\s*(.+)", message_text)
        desc_match = re.search(r"(?i)(description|details):\s*(.+)", message_text)
        
        if name_match:
            drama_name = name_match.group(2).strip()
            # Extract description if available
            if desc_match:
                description = desc_match.group(2).strip()
            else:
                # Try to extract description from the rest of the text
                remaining_text = message_text.replace(name_match.group(0), "").strip()
                if remaining_text:
                    description = remaining_text
        else:
            # If no structured format, use first line as drama name and rest as description
            lines = message_text.split('\n', 1)
            drama_name = lines[0].strip()
            if len(lines) > 1:
                description = lines[1].strip()
        
        # If drama_name is still empty, use the whole message
        if not drama_name:
            drama_name = message_text[:100]  # Limit drama name length
        
        # Create the request
        request_id = await create_request(user_id, username, first_name, drama_name, description)
        
        if request_id:
            # Clear user state
            user_states.pop(user_id, None)
            
            # Send confirmation to user
            buttons = [
                [InlineKeyboardButton("📋 View My Requests", callback_data="my_requests")],
                [InlineKeyboardButton("🎭 Request Another", callback_data="request_drama")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            
            confirmation_text = (
                "✅ <b>Request Submitted Successfully!</b>\n\n"
                f"🆔 <b>Request ID:</b> {request_id[-8:]}\n"  # Show last 8 chars
                f"🎭 <b>Drama:</b> {drama_name}\n"
                f"📝 <b>Description:</b> {description or 'None provided'}\n\n"
                "Your request has been sent to our admins. "
                "You'll be notified once it's reviewed!"
            )
            
            await message.reply_text(
                confirmation_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )
            
            # Notify admins
            await notify_admins(client, request_id, user, drama_name, description)
            
        else:
            await message.reply_text(
                "❌ Sorry, there was an error submitting your request. Please try again!"
            )
            
    except Exception as e:
        logger.error(f"Error handling drama request: {e}")
        await message.reply_text(
            "❌ Something went wrong! Please try again or contact support."
        )

async def notify_admins(client, request_id: str, user, drama_name: str, description: str):
    """Notify admins about new request"""
    try:
        admin_text = (
            "🆕 <b>New Drama Request</b>\n\n"
            f"🆔 <b>Request ID:</b> {request_id[-8:]}\n"
            f"👤 <b>User:</b> {user.first_name} (@{user.username or 'no_username'})\n"
            f"🆔 <b>User ID:</b> {user.id}\n"
            f"🎭 <b>Drama:</b> {drama_name}\n"
            f"📝 <b>Description:</b> {description or 'None provided'}\n"
            f"📅 <b>Date:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        buttons = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{request_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{request_id}")
            ],
            [InlineKeyboardButton("🔄 Processing", callback_data=f"admin_process_{request_id}")],
            [InlineKeyboardButton("💬 Send Custom Reply", callback_data=f"admin_reply_{request_id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        # Send to admin channel if configured
        if ADMIN_CHANNEL_ID:
            try:
                await client.send_message(
                    chat_id=ADMIN_CHANNEL_ID,
                    text=admin_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send to admin channel: {e}")
        
        # Send to individual admins
        for admin_id in ADMIN_IDS:
            try:
                await client.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
                
    except Exception as e:
        logger.error(f"Error notifying admins: {e}")

@Client.on_callback_query(filters.regex(r"^my_requests$"))
async def show_user_requests(client, query):
    """Show user's requests with MESSAGE_NOT_MODIFIED handling"""
    try:
        user_id = query.from_user.id
        requests = await get_user_requests(user_id)
        
        if not requests:
            no_requests_text = (
                "📋 <b>Your Requests</b>\n\n"
                "You haven't made any drama requests yet.\n"
                "Click the button below to submit your first request!"
            )
            
            buttons = [
                [InlineKeyboardButton("🎭 Request Drama", callback_data="request_drama")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            
            await safe_edit_message(
                query.message,
                no_requests_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )
            await query.answer()
            return
        
        # Build requests text
        requests_text = "📋 <b>Your Recent Requests</b>\n\n"
        
        for request in requests[:10]:  # Show last 10 requests
            req_id = str(request["_id"])[-8:]  # Last 8 characters
            drama = request["drama_name"]
            status = request["status"]
            date = request["request_date"].strftime("%Y-%m-%d")
            
            status_emoji = {
                STATUS_PENDING: "⏳",
                STATUS_APPROVED: "✅", 
                STATUS_REJECTED: "❌",
                STATUS_PROCESSING: "🔄"
            }.get(status, "❓")
            
            requests_text += f"🆔 <b>#{req_id}</b> {status_emoji}\n"
            requests_text += f"🎭 {drama}\n"
            requests_text += f"📅 {date}\n"
            
            if request.get("admin_response"):
                responses = request['admin_response']
                if len(responses) > 50:
                    responses = responses[:47] + "..."
                requests_text += f"💬 <i>{responses}</i>\n"
            
            requests_text += "\n"
        
        buttons = [
            [InlineKeyboardButton("🎭 Request New Drama", callback_data="request_drama")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="my_requests")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        
        # Use safe edit to handle MESSAGE_NOT_MODIFIED
        was_modified = await safe_edit_message(
            query.message,
            requests_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        
        if not was_modified:
            await query.answer("✅ List is already up to date!")
        else:
            await query.answer()
        
    except Exception as e:
        if not await handle_callback_error(query, e):
            logger.error(f"Error showing user requests: {e}")

@Client.on_callback_query(filters.regex(r"^admin_panel$"))
async def admin_panel(client, query):
    """Show admin panel with timestamp to prevent MESSAGE_NOT_MODIFIED"""
    if not await is_admin(query.from_user.id):
        await query.answer("❌ You don't have admin permissions!", show_alert=True)
        return
    
    try:
        stats = await get_requests_stats()
        
        # Add timestamp to ensure content is always different
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        panel_text = (
            "🛠 <b>Admin Panel</b>\n\n"
            f"📊 <b>Statistics:</b>\n"
            f"• Total Requests: {stats.get('total', 0)}\n"
            f"• Unique Users: {stats.get('unique_users', 0)}\n"
            f"• ⏳ Pending: {stats.get('pending', 0)}\n"
            f"• ✅ Approved: {stats.get('approved', 0)}\n"
            f"• ❌ Rejected: {stats.get('rejected', 0)}\n"
            f"• 🔄 Processing: {stats.get('processing', 0)}\n"
            f"\n🕒 <i>Last updated: {timestamp}</i>"
        )
        
        buttons = [
            [InlineKeyboardButton(f"⏳ View Pending ({stats.get('pending', 0)})", callback_data="admin_pending_list")],
            [InlineKeyboardButton("📊 Full Statistics", callback_data="admin_stats")],
            [InlineKeyboardButton("🔍 Search Request", callback_data="admin_search")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        
        await safe_edit_message(
            query.message,
            panel_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        await query.answer()
        
    except Exception as e:
        if not await handle_callback_error(query, e):
            logger.error(f"Error showing admin panel: {e}")

@Client.on_callback_query(filters.regex(r"^admin_pending_list$"))
async def show_pending_requests(client, query):
    """Show pending requests to admin"""
    if not await is_admin(query.from_user.id):
        await query.answer("❌ Access denied!", show_alert=True)
        return
    
    try:
        pending_requests = await get_pending_requests(10)
        
        if not pending_requests:
            await safe_edit_message(
                query.message,
                "✅ <b>No Pending Requests</b>\n\nAll requests have been processed!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
                ]),
                parse_mode=ParseMode.HTML
            )
            await query.answer()
            return
        
        # Add timestamp to ensure content is different
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        pending_text = f"⏳ <b>Pending Requests</b> - Updated: {timestamp}\n\n"
        
        for request in pending_requests:
            req_id = str(request["_id"])[-8:]
            user_name = request["first_name"]
            username = request.get("username", "no_username")
            drama = request["drama_name"]
            date = request["request_date"].strftime("%m-%d")
            
            pending_text += (
                f"🆔 <b>#{req_id}</b>\n"
                f"👤 {user_name} (@{username})\n"
                f"🎭 {drama}\n"
                f"📅 {date}\n\n"
            )
        
        buttons = [
            [InlineKeyboardButton("🔄 Refresh List", callback_data="admin_pending_list")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
        ]
        
        was_modified = await safe_edit_message(
            query.message,
            pending_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        
        if not was_modified:
            await query.answer("✅ List is already up to date!")
        else:
            await query.answer()
        
    except Exception as e:
        if not await handle_callback_error(query, e):
            logger.error(f"Error showing pending requests: {e}")

@Client.on_callback_query(filters.regex(r"^admin_(approve|reject|process)_"))
async def handle_admin_actions(client, query):
    """Handle admin actions on requests"""
    if not await is_admin(query.from_user.id):
        await query.answer("❌ Access denied!", show_alert=True)
        return
    
    try:
        action = query.data.split("_")[1]  # approve, reject, or process
        request_id = query.data.split("_")[2]
        
        # Get request details
        request_data = await get_request_by_id(request_id)
        if not request_data:
            await query.answer("❌ Request not found!", show_alert=True)
            return
        
        user_id = request_data["user_id"]
        drama_name = request_data["drama_name"]
        
        if action == "approve":
            status = STATUS_APPROVED
            admin_response = "Your request has been approved! The drama will be uploaded soon."
            success_msg = f"✅ Request approved for '{drama_name}'"
            user_msg = (
                f"✅ <b>Request Approved!</b>\n\n"
                f"🎭 <b>Drama:</b> {drama_name}\n"
                f"🎉 Great news! Your requested drama has been approved and will be uploaded soon.\n\n"
                f"Thank you for your request!"
            )
        elif action == "reject":
            status = STATUS_REJECTED
            admin_response = "Your request couldn't be fulfilled at this time due to availability constraints."
            success_msg = f"❌ Request rejected for '{drama_name}'"
            user_msg = (
                f"❌ <b>Request Update</b>\n\n"
                f"🎭 <b>Drama:</b> {drama_name}\n"
                f"Unfortunately, we couldn't fulfill your request at this time. "
                f"This might be due to licensing or availability issues.\n\n"
                f"Feel free to request other dramas!"
            )
        else:  # process
            status = STATUS_PROCESSING
            admin_response = "Your request is being processed. We'll update you soon!"
            success_msg = f"🔄 Request marked as processing for '{drama_name}'"
            user_msg = (
                f"🔄 <b>Request Update</b>\n\n"
                f"🎭 <b>Drama:</b> {drama_name}\n"
                f"Good news! We're currently working on your request. "
                f"We'll notify you once it's ready!\n\n"
                f"Thanks for your patience!"
            )
        
        # Update request status
        success = await update_request_status(request_id, status, query.from_user.id, admin_response)
        
        if success:
            # Notify user
            try:
                await safe_send_message(
                    client,
                    user_id,
                    user_msg,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")
            
            await query.answer(success_msg, show_alert=True)
            
            # Update the admin message to show it's been processed
            try:
                # Try to edit the original admin message to show it's been processed
                processed_text = query.message.text + f"\n\n✅ Processed by {query.from_user.first_name} at {datetime.datetime.now().strftime('%H:%M:%S')}"
                await safe_edit_message(
                    query.message,
                    processed_text,
                    parse_mode=ParseMode.HTML
                )
            except:
                pass  # If we can't edit the message, it's not critical
            
        else:
            await query.answer("❌ Error updating request status!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error handling admin action: {e}")
        await query.answer("❌ Error processing request!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^help_info$"))
async def show_help(client, query):
    """Show help information"""
    # Add timestamp to ensure content is different
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    
    help_text = (
        "ℹ️ <b>K-Drama Request Bot Help</b>\n\n"
        "🎭 <b>How to Request:</b>\n"
        "1. Click 'Request Drama' button\n"
        "2. Send drama name and details\n"
        "3. Wait for admin review\n"
        "4. Get notified of the result\n\n"
        "📋 <b>Request Status:</b>\n"
        "• ⏳ Pending - Under review\n"
        "• 🔄 Processing - Being worked on\n"
        "• ✅ Approved - Will be uploaded\n"
        "• ❌ Rejected - Cannot fulfill\n\n"
        "💡 <b>Tips for Better Requests:</b>\n"
        "• Be specific with drama names\n"
        "• Include release year if known\n"
        "• Mention main actors if helpful\n"
        "• Provide English and Korean titles\n"
        "• Be patient for admin response\n\n"
        "📞 <b>Commands:</b>\n"
        "• /start - Main menu\n"
        "• /request - Quick request\n"
        "• /help - This help message\n\n"
        f"<i>Last updated: {timestamp}</i>"
    )
    
    buttons = [
        [InlineKeyboardButton("🎭 Request Drama Now", callback_data="request_drama")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    
    await safe_edit_message(
        query.message,
        help_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )
    await query.answer()

@Client.on_callback_query(filters.regex(r"^main_menu$"))
async def main_menu(client, query):
    """Return to main menu with MESSAGE_NOT_MODIFIED handling"""
    try:
        # Clear any user states
        user_states.pop(query.from_user.id, None)
        
        user_id = query.from_user.id
        first_name = query.from_user.first_name or "User"
        
        buttons = [
            [InlineKeyboardButton("🎭 Request Drama", callback_data="request_drama")],
            [InlineKeyboardButton("📋 My Requests", callback_data="my_requests")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help_info")]
        ]
        
        # Add admin panel for admins
        if await is_admin(user_id):
            buttons.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel")])
        
        # Add timestamp to ensure content is different
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        welcome_text = (
            f"🎬 <b>Welcome to K-Drama Request Bot, {first_name}!</b>\n\n"
            "Can't find your favorite K-Drama in our collection? "
            "Request it from our admins and we'll try to add it!\n\n"
            "Choose an option below to get started:\n"
            f"<i>Last updated: {timestamp}</i>"
        )
        
        was_modified = await safe_edit_message(
            query.message,
            welcome_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        
        if not was_modified:
            await query.answer("✅ Menu is already up to date!")
        else:
            await query.answer()
            
    except Exception as e:
        if not await handle_callback_error(query, e):
            logger.error(f"Error in main menu: {e}")

@Client.on_message(filters.command(["stats"]) & filters.user(ADMIN_IDS))
async def admin_stats_command(client, message):
    """Show detailed statistics (admin only)"""
    try:
        stats = await get_requests_stats()
        
        # Get recent activity
        recent_requests = await requests_collection.find().sort("request_date", -1).limit(5).to_list(length=5)
        
        # Add timestamp to ensure content is different
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        stats_text = (
            f"📊 <b>Detailed Statistics</b> - Updated: {timestamp}\n\n"
            f"👥 <b>Users & Requests:</b>\n"
            f"• Total Requests: {stats.get('total', 0)}\n"
            f"• Unique Users: {stats.get('unique_users', 0)}\n\n"
            f"📋 <b>Request Status:</b>\n"
            f"• ⏳ Pending: {stats.get('pending', 0)}\n"
            f"• 🔄 Processing: {stats.get('processing', 0)}\n"
            f"• ✅ Approved: {stats.get('approved', 0)}\n"
            f"• ❌ Rejected: {stats.get('rejected', 0)}\n\n"
        )
        
        if recent_requests:
            stats_text += "🕒 <b>Recent Activity:</b>\n"
            for req in recent_requests:
                date = req["request_date"].strftime("%m-%d")
                status_emoji = {
                    STATUS_PENDING: "⏳",
                    STATUS_APPROVED: "✅",
                    STATUS_REJECTED: "❌",
                    STATUS_PROCESSING: "🔄"
                }.get(req["status"], "❓")
                
                stats_text += f"{status_emoji} {req['drama_name'][:20]}... ({date})\n"
        
        await message.reply_text(stats_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error showing stats: {e}")
        await message.reply_text("❌ Error retrieving statistics!")

# Initialize admin database on startup
asyncio.create_task(init_admin_db())

logger.info("K-Drama Request Bot handlers loaded successfully!")
