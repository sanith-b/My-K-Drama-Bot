import logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    User
)
import json
import datetime
from typing import Dict, List, Optional
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from logging_helper import LOGGER

# Load environment variables - adjust these based on your config
BOT_OWNER_ID = os.getenv('BOT_OWNER_ID', "1204352805")
MONGODB_URL = os.getenv('MONGODB_URL', "mongodb+srv://kdramabot:Buo0fRGenkOAkgXH@pastppr.ipuyepp.mongodb.net/?retryWrites=true&w=majority&appName=pastppr")

class KDramaRequestSystem:
    def __init__(self):
        self.admin_ids = []
        self.db_client = None
        self.db = None
        self.user_data = {}  # Store user session data

    async def init_database(self):
        """Initialize MongoDB connection"""
        try:
            mongodb_url = os.getenv('MONGODB_URL', MONGODB_URL)
            self.db_client = AsyncIOMotorClient(mongodb_url)
            self.db = self.db_client.kdrama_bot

            # Test connection
            await self.db_client.admin.command('ping')
            LOGGER.info("K-Drama Plugin: Connected to MongoDB successfully")

            # Create indexes
            await self.create_indexes()

        except Exception as e:
            LOGGER.error(f"K-Drama Plugin: MongoDB connection failed: {e}")
            raise

    async def create_indexes(self):
        """Create database indexes for better performance"""
        try:
            # Index for requests collection
            await self.db.requests.create_index("request_id", unique=True)
            await self.db.requests.create_index("user_id")
            await self.db.requests.create_index("status")
            await self.db.requests.create_index("created_at")

            # Index for admins collection
            await self.db.admins.create_index("user_id", unique=True)

            LOGGER.info("K-Drama Plugin: Database indexes created")
        except Exception as e:
            LOGGER.error(f"K-Drama Plugin: Error creating indexes: {e}")

    async def add_admin(self, user_id: int):
        """Add a new admin to database"""
        try:
            admin_data = {
                'user_id': user_id,
                'added_at': datetime.datetime.utcnow(),
                'is_active': True
            }
            await self.db.admins.update_one(
                {'user_id': user_id},
                {'$set': admin_data},
                upsert=True
            )
            if user_id not in self.admin_ids:
                self.admin_ids.append(user_id)
            LOGGER.info(f"K-Drama Plugin: Admin added: {user_id}")
        except Exception as e:
            LOGGER.error(f"K-Drama Plugin: Error adding admin: {e}")

    async def load_admins(self):
        """Load admins from database"""
        try:
            admins = await self.db.admins.find({'is_active': True}).to_list(None)
            self.admin_ids = [admin['user_id'] for admin in admins]
            LOGGER.info(f"K-Drama Plugin: Loaded {len(self.admin_ids)} admins")
        except Exception as e:
            LOGGER.error(f"K-Drama Plugin: Error loading admins: {e}")

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin"""
        return user_id in self.admin_ids

    def get_user_data(self, user_id: int) -> dict:
        """Get user session data"""
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        return self.user_data[user_id]

    def set_user_data(self, user_id: int, key: str, value):
        """Set user session data"""
        user_data = self.get_user_data(user_id)
        user_data[key] = value

    async def create_manual_request(self, callback_query: CallbackQuery, request_data: Dict):
        """Create a manual drama request in the database"""
        try:
            # Generate unique request ID
            request_count = await self.db.requests.count_documents({}) + 1
            request_id = f"REQ_{request_count:04d}"

            # Create request document
            request_doc = {
                'request_id': request_id,
                'user_id': request_data['user_id'],
                'username': request_data['username'],
                'drama_name': request_data['drama_name'],
                'request_type': 'manual',
                'status': 'pending',
                'created_at': datetime.datetime.utcnow(),
                'processed_at': None,
                'processed_by': None,
                'additional_info': None
            }

            # Insert into database
            await self.db.requests.insert_one(request_doc)

            # Send confirmation to user
            await callback_query.edit_message_text(
                f"✅ **Request Submitted Successfully!**\n\n"
                f"📋 **Request ID:** `{request_id}`\n"
                f"🎬 **Drama:** {request_data['drama_name']}\n\n"
                f"🔔 You'll be notified when admins review your request!\n"
                f"📞 Admins will contact you if they need more details."
            )

            # Clear pending request
            user_data = self.get_user_data(request_data['user_id'])
            if 'pending_request' in user_data:
                del user_data['pending_request']

            # Notify admins
            await self.notify_admins_new_request(callback_query._client, request_doc)

            LOGGER.info(f"K-Drama Plugin: Request created: {request_id} by {request_data['username']}")

        except Exception as e:
            LOGGER.error(f"K-Drama Plugin: Error creating request: {e}")
            await callback_query.edit_message_text(
                "❌ **Error submitting request**\n\n"
                "Please try again later or contact support."
            )

    async def notify_admins_new_request(self, client: Client, request_data: Dict):
        """Notify all admins about a new request"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{request_data['request_id']}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{request_data['request_id']}")
            ],
            [
                InlineKeyboardButton("📝 Add Note", callback_data=f"admin_note_{request_data['request_id']}"),
                InlineKeyboardButton("📋 View Details", callback_data=f"admin_details_{request_data['request_id']}")
            ]
        ])

        admin_message = (
            f"🆕 **NEW K-DRAMA REQUEST**\n\n"
            f"📋 **ID:** `{request_data['request_id']}`\n"
            f"👤 **User:** @{request_data['username']} ({request_data['user_id']})\n"
            f"🎬 **Drama:** {request_data['drama_name']}\n"
            f"🔤 **Type:** Manual Request\n"
            f"⏰ **Requested:** {request_data['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
        )

        for admin_id in self.admin_ids:
            try:
                await client.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    reply_markup=keyboard
                )
            except Exception as e:
                LOGGER.error(f"K-Drama Plugin: Failed to notify admin {admin_id}: {e}")

    async def approve_request(self, callback_query: CallbackQuery, request_id: str):
        """Approve a drama request"""
        try:
            # Find and update request in database
            result = await self.db.requests.find_one_and_update(
                {'request_id': request_id, 'status': 'pending'},
                {
                    '$set': {
                        'status': 'approved',
                        'processed_by': callback_query.from_user.id,
                        'processed_at': datetime.datetime.utcnow()
                    }
                }
            )

            if not result:
                await callback_query.edit_message_text("❌ Request not found or already processed!")
                return

            # Notify the user
            try:
                await callback_query._client.send_message(
                    chat_id=result['user_id'],
                    text=f"🎉 **Request Approved!**\n\n"
                         f"📋 **Request ID:** `{request_id}`\n"
                         f"🎬 **Drama:** {result['drama_name']}\n\n"
                         f"✨ We'll work on adding this drama to our collection. Thank you for your suggestion!"
                )
            except Exception as e:
                LOGGER.error(f"K-Drama Plugin: Failed to notify user {result['user_id']}: {e}")

            await callback_query.edit_message_text(
                f"✅ **Request Approved!**\n\n"
                f"📋 **ID:** {request_id}\n"
                f"🎬 **Drama:** {result['drama_name']}\n"
                f"👤 **User:** @{result['username']}\n\n"
                f"✉️ User has been notified."
            )

        except Exception as e:
            LOGGER.error(f"K-Drama Plugin: Error approving request: {e}")
            await callback_query.edit_message_text("❌ Error processing request. Please try again.")

    async def reject_request(self, callback_query: CallbackQuery, request_id: str):
        """Reject a drama request"""
        try:
            # Find and update request in database
            result = await self.db.requests.find_one_and_update(
                {'request_id': request_id, 'status': 'pending'},
                {
                    '$set': {
                        'status': 'rejected',
                        'processed_by': callback_query.from_user.id,
                        'processed_at': datetime.datetime.utcnow()
                    }
                }
            )

            if not result:
                await callback_query.edit_message_text("❌ Request not found or already processed!")
                return

            # Notify the user
            try:
                await callback_query._client.send_message(
                    chat_id=result['user_id'],
                    text=f"💔 **Request Update**\n\n"
                         f"📋 **Request ID:** `{request_id}`\n"
                         f"🎬 **Drama:** {result['drama_name']}\n\n"
                         f"Unfortunately, we cannot fulfill this request at this time. "
                         f"This might be due to licensing issues or availability."
                )
            except Exception as e:
                LOGGER.error(f"K-Drama Plugin: Failed to notify user {result['user_id']}: {e}")

            await callback_query.edit_message_text(
                f"❌ **Request Rejected**\n\n"
                f"📋 **ID:** {request_id}\n"
                f"🎬 **Drama:** {result['drama_name']}\n"
                f"👤 **User:** @{result['username']}\n\n"
                f"✉️ User has been notified."
            )

        except Exception as e:
            LOGGER.error(f"K-Drama Plugin: Error rejecting request: {e}")
            await callback_query.edit_message_text("❌ Error processing request. Please try again.")

# Initialize the drama system
drama_system = KDramaRequestSystem()

# Plugin handlers using decorators similar to your existing structure
@Client.on_message(filters.command("request"))
async def request_drama_handler(client: Client, message: Message):
    """Handle /request command for manual drama requests"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Extract command arguments
    command_text = message.text
    args = command_text.split()[1:] if len(command_text.split()) > 1 else []

    if not args:
        await message.reply_text(
            "🎬 **Request K-Drama**\n\n"
            "Usage: `/request [drama name]`\n\n"
            "Examples:\n"
            "`/request Squid Game`\n"
            "`/request Crash Landing on You`\n"
            "`/request Kingdom Season 3`\n\n"
            "💡 Please provide as much detail as possible including:\n"
            "• Full drama name\n"
            "• Year (if known)\n"
            "• Any additional details"
        )
        return

    # Get the drama request from user input
    drama_request = " ".join(args)

    # Show confirmation dialog
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Submit Request", callback_data=f"confirm_manual_request"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_request")
        ]
    ])

    # Store request data temporarily in user data
    drama_system.set_user_data(user_id, 'pending_request', {
        'drama_name': drama_request,
        'user_id': user_id,
        'username': username
    })

    await message.reply_text(
        f"🎬 **Confirm Your K-Drama Request**\n\n"
        f"**Drama:** {drama_request}\n\n"
        f"📋 Submit this request?",
        reply_markup=keyboard
    )

@Client.on_message(filters.command("status"))
async def status_handler(client: Client, message: Message):
    """Handle /status command to show user's requests"""
    user_id = message.from_user.id

    try:
        # Get user's requests from database
        user_requests = await drama_system.db.requests.find(
            {'user_id': user_id}
        ).sort('created_at', -1).limit(10).to_list(10)

        if not user_requests:
            await message.reply_text(
                "📋 **Your Request Status**\n\n"
                "You haven't made any requests yet!\n\n"
                "Use `/request [drama name]` to submit your first request."
            )
            return

        status_text = "📋 **Your K-Drama Requests**\n\n"

        status_emoji = {
            'pending': '⏳',
            'approved': '✅', 
            'rejected': '❌'
        }

        for req in user_requests:
            emoji = status_emoji.get(req['status'], '❓')
            status_text += (
                f"{emoji} `{req['request_id']}` - **{req['status'].title()}**\n"
                f"   🎬 {req['drama_name']}\n"
                f"   📅 {req['created_at'].strftime('%Y-%m-%d')}\n\n"
            )

        total_requests = len(user_requests)
        if total_requests >= 10:
            status_text += f"... (showing latest 10 requests)"

        await message.reply_text(status_text)

    except Exception as e:
        LOGGER.error(f"K-Drama Plugin: Error showing user status: {e}")
        await message.reply_text(
            "❌ Error loading your request status. Please try again later."
        )

@Client.on_message(filters.command("admin"))
async def admin_panel_handler(client: Client, message: Message):
    """Show admin control panel"""
    user_id = message.from_user.id

    if not drama_system.is_admin(user_id):
        await message.reply_text("❌ You don't have admin permissions!")
        return

    # Get statistics from database
    pending_count = await drama_system.db.requests.count_documents({'status': 'pending'})
    approved_count = await drama_system.db.requests.count_documents({'status': 'approved'})
    rejected_count = await drama_system.db.requests.count_documents({'status': 'rejected'})
    total_count = await drama_system.db.requests.count_documents({})

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Pending Requests", callback_data="admin_view_pending"),
            InlineKeyboardButton("✅ Approved", callback_data="admin_view_approved")
        ],
        [
            InlineKeyboardButton("❌ Rejected", callback_data="admin_view_rejected"),
            InlineKeyboardButton("📊 Statistics", callback_data="admin_view_stats")
        ]
    ])

    stats_text = (
        f"🛠️ **K-DRAMA ADMIN PANEL**\n\n"
        f"📊 **Statistics:**\n"
        f"📋 Pending: {pending_count}\n"
        f"✅ Approved: {approved_count}\n"
        f"❌ Rejected: {rejected_count}\n"
        f"📈 Total: {total_count}\n"
        f"👥 Admins: {len(drama_system.admin_ids)}\n"
    )

    await message.reply_text(stats_text, reply_markup=keyboard)

@Client.on_message(filters.command("addadmin"))
async def add_admin_handler(client: Client, message: Message):
    """Handle /addadmin command"""
    user_id = message.from_user.id
    bot_owner_id = int(os.getenv('BOT_OWNER_ID', BOT_OWNER_ID))

    if user_id == bot_owner_id:
        command_text = message.text
        args = command_text.split()[1:] if len(command_text.split()) > 1 else []
        
        if args:
            try:
                new_admin_id = int(args[0])
                await drama_system.add_admin(new_admin_id)
                await message.reply_text(f"✅ Added admin: {new_admin_id}")
            except ValueError:
                await message.reply_text("❌ Invalid user ID!")
        else:
            await message.reply_text("Usage: /addadmin [user_id]")
    else:
        await message.reply_text("❌ Only bot owner can add admins!")

@Client.on_callback_query(filters.regex("^(confirm_manual_request|cancel_request|admin_)"))
async def callback_handler(client: Client, callback_query: CallbackQuery):
    """Handle callback queries for K-Drama plugin"""
    await callback_query.answer()

    data = callback_query.data
    user_id = callback_query.from_user.id

    if data == "cancel_request":
        await callback_query.edit_message_text("❌ Request cancelled.")
        # Clear pending request
        user_data = drama_system.get_user_data(user_id)
        if 'pending_request' in user_data:
            del user_data['pending_request']
        return

    elif data == "confirm_manual_request":
        # Check if pending request exists
        user_data = drama_system.get_user_data(user_id)
        if 'pending_request' not in user_data:
            await callback_query.edit_message_text("❌ Request expired. Please try again.")
            return

        pending_request = user_data['pending_request']
        await drama_system.create_manual_request(callback_query, pending_request)

    elif data.startswith("admin_approve_"):
        if not drama_system.is_admin(user_id):
            await callback_query.edit_message_text("❌ Access denied!")
            return
        request_id = data.replace("admin_approve_", "")
        await drama_system.approve_request(callback_query, request_id)

    elif data.startswith("admin_reject_"):
        if not drama_system.is_admin(user_id):
            await callback_query.edit_message_text("❌ Access denied!")
            return
        request_id = data.replace("admin_reject_", "")
        await drama_system.reject_request(callback_query, request_id)

    elif data == "admin_view_pending":
        if not drama_system.is_admin(user_id):
            await callback_query.edit_message_text("❌ Access denied!")
            return
        
        # Show pending requests
        pending_requests = await drama_system.db.requests.find(
            {'status': 'pending'}
        ).sort('created_at', -1).limit(5).to_list(5)

        if not pending_requests:
            await callback_query.edit_message_text("📋 No pending requests!")
            return

        text = "📋 **PENDING REQUESTS**\n\n"
        for req in pending_requests:
            text += (
                f"• `{req['request_id']}` - @{req['username']}\n"
                f"  🎬 {req['drama_name']}\n"
                f"  📅 {req['created_at'].strftime('%Y-%m-%d')}\n\n"
            )

        await callback_query.edit_message_text(text)

# Initialize plugin when module is loaded
async def init_kdrama_plugin():
    """Initialize K-Drama plugin"""
    try:
        await drama_system.init_database()
        await drama_system.load_admins()
        
        # Add bot owner as admin if specified
        bot_owner_id = os.getenv('BOT_OWNER_ID', BOT_OWNER_ID)
        if bot_owner_id:
            try:
                await drama_system.add_admin(int(bot_owner_id))
                LOGGER.info(f"K-Drama Plugin: Bot owner ({bot_owner_id}) added as admin")
            except ValueError:
                LOGGER.warning("K-Drama Plugin: Invalid BOT_OWNER_ID")
        
        LOGGER.info("K-Drama Plugin: Initialized successfully")
        return True
    except Exception as e:
        LOGGER.error(f"K-Drama Plugin: Initialization failed: {e}")
        return False
