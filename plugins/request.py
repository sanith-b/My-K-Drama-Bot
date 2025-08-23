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

# Load environment variables
BOT_OWNER_ID = "1204352805"
MONGODB_URL = "mongodb+srv://kdramabot:Buo0fRGenkOAkgXH@pastppr.ipuyepp.mongodb.net/?retryWrites=true&w=majority&appName=pastppr"

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class KDramaRequestSystem:
    def __init__(self, client: Client):
        self.client = client
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
            logger.info("✅ Connected to MongoDB successfully")

            # Create indexes
            await self.create_indexes()

        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
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

            logger.info("✅ Database indexes created")
        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")

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
            logger.info(f"✅ Admin added: {user_id}")
        except Exception as e:
            logger.error(f"❌ Error adding admin: {e}")

    async def load_admins(self):
        """Load admins from database"""
        try:
            admins = await self.db.admins.find({'is_active': True}).to_list(None)
            self.admin_ids = [admin['user_id'] for admin in admins]
            logger.info(f"✅ Loaded {len(self.admin_ids)} admins")
        except Exception as e:
            logger.error(f"❌ Error loading admins: {e}")

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

    async def request_drama_command(self, client: Client, message: Message):
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
        self.set_user_data(user_id, 'pending_request', {
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

    async def handle_callbacks(self, client: Client, callback_query: CallbackQuery):
        """Handle all callback queries"""
        await callback_query.answer()

        data = callback_query.data
        user_id = callback_query.from_user.id

        if data == "cancel_request":
            await callback_query.edit_message_text("❌ Request cancelled.")
            # Clear pending request
            user_data = self.get_user_data(user_id)
            if 'pending_request' in user_data:
                del user_data['pending_request']
            return

        elif data == "confirm_manual_request":
            # Check if pending request exists
            user_data = self.get_user_data(user_id)
            if 'pending_request' not in user_data:
                await callback_query.edit_message_text("❌ Request expired. Please try again.")
                return

            pending_request = user_data['pending_request']
            await self.create_manual_request(callback_query, pending_request)

        elif data.startswith("admin_"):
            await self.handle_admin_callbacks(callback_query)

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
            await self.notify_admins_new_request(request_doc)

            logger.info(f"✅ Request created: {request_id} by {request_data['username']}")

        except Exception as e:
            logger.error(f"❌ Error creating request: {e}")
            await callback_query.edit_message_text(
                "❌ **Error submitting request**\n\n"
                "Please try again later or contact support."
            )

    async def notify_admins_new_request(self, request_data: Dict):
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
                await self.client.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    async def admin_panel(self, client: Client, message: Message):
        """Show admin control panel with database stats or handle specific request ID"""
        user_id = message.from_user.id

        if not self.is_admin(user_id):
            await message.reply_text("❌ You don't have admin permissions!")
            return

        # Extract command arguments
        command_text = message.text
        args = command_text.split()[1:] if len(command_text.split()) > 1 else []

        # Check if admin provided a specific request ID
        if args:
            request_id = args[0].upper()
            # If it doesn't start with REQ_, add it
            if not request_id.startswith('REQ_'):
                request_id = f'REQ_{request_id.zfill(4)}'

            await self.show_admin_request_actions(message, request_id)
            return

        # Show general admin panel
        # Get statistics from database
        pending_count = await self.db.requests.count_documents({'status': 'pending'})
        approved_count = await self.db.requests.count_documents({'status': 'approved'})
        rejected_count = await self.db.requests.count_documents({'status': 'rejected'})
        total_count = await self.db.requests.count_documents({})

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📋 Pending Requests", callback_data="admin_view_pending"),
                InlineKeyboardButton("✅ Approved", callback_data="admin_view_approved")
            ],
            [
                InlineKeyboardButton("❌ Rejected", callback_data="admin_view_rejected"),
                InlineKeyboardButton("📊 Statistics", callback_data="admin_view_stats")
            ],
            [
                InlineKeyboardButton("👥 Users", callback_data="admin_view_users"),
                InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh_panel")
            ]
        ])

        stats_text = (
            f"🛠️ **K-DRAMA ADMIN PANEL**\n\n"
            f"📊 **Statistics:**\n"
            f"📋 Pending: {pending_count}\n"
            f"✅ Approved: {approved_count}\n"
            f"❌ Rejected: {rejected_count}\n"
            f"📈 Total: {total_count}\n"
            f"👥 Admins: {len(self.admin_ids)}\n\n"
            f"💡 **Quick Actions:**\n"
            f"Use `/admin [Request ID]` to quickly manage specific requests\n"
            f"Example: `/admin REQ_0001` or `/admin 1`"
        )

        await message.reply_text(
            stats_text,
            reply_markup=keyboard
        )

    async def show_admin_request_actions(self, message: Message, request_id: str):
        """Show specific request details with admin action buttons"""
        try:
            # Find the request in database
            request = await self.db.requests.find_one({'request_id': request_id})

            if not request:
                await message.reply_text(
                    f"❌ **Request Not Found**\n\n"
                    f"Request ID `{request_id}` doesn't exist.\n\n"
                    f"💡 **Tips:**\n"
                    f"• Use exact request ID (e.g., REQ_0001)\n"
                    f"• Or just the number (e.g., 1)\n"
                    f"• Check `/admin` panel for valid requests"
                )
                return

            # Determine status and available actions
            status = request['status']
            status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}

            # Create action buttons based on current status
            if status == 'pending':
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{request_id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{request_id}")
                    ],
                    [
                        InlineKeyboardButton("📝 Add Note", callback_data=f"admin_note_{request_id}"),
                        InlineKeyboardButton("📋 Full Details", callback_data=f"admin_details_{request_id}")
                    ],
                    [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")]
                ])
            else:
                # Already processed - show different options
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔄 Revert to Pending", callback_data=f"admin_revert_{request_id}"),
                        InlineKeyboardButton("📋 Full Details", callback_data=f"admin_details_{request_id}")
                    ],
                    [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")]
                ])

            # Format request information
            request_text = (
                f"📋 **ADMIN REQUEST REVIEW**\n\n"
                f"**ID:** `{request['request_id']}`\n"
                f"**Status:** {status_emoji.get(status, '❓')} {status.title()}\n"
                f"**Drama:** {request['drama_name']}\n"
                f"**User:** @{request['username']} ({request['user_id']})\n"
                f"**Submitted:** {request['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
            )

            if request.get('processed_at'):
                request_text += f"**Processed:** {request['processed_at'].strftime('%Y-%m-%d %H:%M')}\n"

            if request.get('processed_by'):
                request_text += f"**Processed by:** {request['processed_by']}\n"

            if request.get('additional_info'):
                request_text += f"**Notes:** {request['additional_info']}\n"

            if status == 'pending':
                request_text += f"\n🎯 **Choose Action:**"
            else:
                request_text += f"\n🔧 **Management Options:**"

            await message.reply_text(
                request_text,
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Error showing admin request actions: {e}")
            await message.reply_text(
                f"❌ **Error Loading Request**\n\n"
                f"Failed to load request `{request_id}`.\n"
                f"Please try again or contact support."
            )

    async def handle_admin_callbacks(self, callback_query: CallbackQuery):
        """Handle admin button callbacks"""
        user_id = callback_query.from_user.id
        if not self.is_admin(user_id):
            await callback_query.edit_message_text("❌ Access denied!")
            return

        data = callback_query.data

        if data.startswith("admin_approve_"):
            request_id = data.replace("admin_approve_", "")
            await self.approve_request(callback_query, request_id)
        elif data.startswith("admin_reject_"):
            request_id = data.replace("admin_reject_", "")
            await self.reject_request(callback_query, request_id)
        elif data.startswith("admin_details_"):
            request_id = data.replace("admin_details_", "")
            await self.show_request_details(callback_query, request_id)
        elif data == "admin_view_pending":
            await self.show_pending_requests_with_actions(callback_query)
        elif data == "admin_view_approved":
            await self.show_approved_requests(callback_query)
        elif data == "admin_view_rejected":
            await self.show_rejected_requests(callback_query)
        elif data == "admin_view_stats":
            await self.show_detailed_stats(callback_query)
        elif data == "admin_view_users":
            await self.show_user_stats(callback_query)
        elif data == "admin_refresh_panel":
            await self.refresh_admin_panel(callback_query)
        elif data.startswith("admin_revert_"):
            request_id = data.replace("admin_revert_", "")
            await self.revert_request_to_pending(callback_query, request_id)

    async def show_request_details(self, callback_query: CallbackQuery, request_id: str):
        """Show detailed information about a specific request"""
        try:
            request = await self.db.requests.find_one({'request_id': request_id})

            if not request:
                await callback_query.edit_message_text("❌ Request not found!")
                return

            status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}

            details = (
                f"📋 **REQUEST DETAILS**\n\n"
                f"**ID:** `{request['request_id']}`\n"
                f"**Status:** {status_emoji.get(request['status'], '❓')} {request['status'].title()}\n"
                f"**Drama:** {request['drama_name']}\n"
                f"**Requested by:** @{request['username']} ({request['user_id']})\n"
                f"**Date:** {request['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
            )

            if request.get('processed_at'):
                details += f"**Processed:** {request['processed_at'].strftime('%Y-%m-%d %H:%M')}\n"
            if request.get('processed_by'):
                details += f"**Processed by:** {request['processed_by']}\n"
            if request.get('additional_info'):
                details += f"**Notes:** {request['additional_info']}\n"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")]
            ])

            await callback_query.edit_message_text(details, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing request details: {e}")
            await callback_query.edit_message_text("❌ Error loading request details.")

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
                await self.client.send_message(
                    chat_id=result['user_id'],
                    text=f"🎉 **Request Approved!**\n\n"
                         f"📋 **Request ID:** `{request_id}`\n"
                         f"🎬 **Drama:** {result['drama_name']}\n\n"
                         f"✨ We'll work on adding this drama to our collection. Thank you for your suggestion!"
                )
            except Exception as e:
                logger.error(f"Failed to notify user {result['user_id']}: {e}")

            await callback_query.edit_message_text(
                f"✅ **Request Approved!**\n\n"
                f"📋 **ID:** {request_id}\n"
                f"🎬 **Drama:** {result['drama_name']}\n"
                f"👤 **User:** @{result['username']}\n\n"
                f"✉️ User has been notified."
            )

        except Exception as e:
            logger.error(f"Error approving request: {e}")
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
                await self.client.send_message(
                    chat_id=result['user_id'],
                    text=f"💔 **Request Update**\n\n"
                         f"📋 **Request ID:** `{request_id}`\n"
                         f"🎬 **Drama:** {result['drama_name']}\n\n"
                         f"Unfortunately, we cannot fulfill this request at this time. "
                         f"This might be due to licensing issues or availability."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {result['user_id']}: {e}")

            await callback_query.edit_message_text(
                f"❌ **Request Rejected**\n\n"
                f"📋 **ID:** {request_id}\n"
                f"🎬 **Drama:** {result['drama_name']}\n"
                f"👤 **User:** @{result['username']}\n\n"
                f"✉️ User has been notified."
            )

        except Exception as e:
            logger.error(f"Error rejecting request: {e}")
            await callback_query.edit_message_text("❌ Error processing request. Please try again.")

    async def show_pending_requests_with_actions(self, callback_query: CallbackQuery):
        """Show pending requests with quick action buttons"""
        try:
            pending_requests = await self.db.requests.find(
                {'status': 'pending'}
            ).sort('created_at', -1).limit(3).to_list(3)

            if not pending_requests:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")]
                ])
                await callback_query.edit_message_text("📋 No pending requests!", reply_markup=keyboard)
                return

            text = "📋 **PENDING REQUESTS - QUICK ACTIONS**\n\n"
            keyboard_buttons = []

            for req in pending_requests:
                text += (
                    f"🆔 `{req['request_id']}`\n"
                    f"👤 @{req['username']}\n"
                    f"🎬 {req['drama_name']}\n"
                    f"📅 {req['created_at'].strftime('%Y-%m-%d')}\n\n"
                )

                # Add quick action buttons for each request
                keyboard_buttons.append([
                    InlineKeyboardButton(f"✅ {req['request_id'][-4:]}", callback_data=f"admin_approve_{req['request_id']}"),
                    InlineKeyboardButton(f"❌ {req['request_id'][-4:]}", callback_data=f"admin_reject_{req['request_id']}"),
                    InlineKeyboardButton(f"📋 {req['request_id'][-4:]}", callback_data=f"admin_details_{req['request_id']}")
                ])

            total_pending = await self.db.requests.count_documents({'status': 'pending'})
            if total_pending > 3:
                text += f"... and {total_pending - 3} more pending requests\n\n"

            text += "💡 Use `/admin [ID]` for individual request management"

            keyboard_buttons.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")])
            keyboard = InlineKeyboardMarkup(keyboard_buttons)

            await callback_query.edit_message_text(text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing pending requests with actions: {e}")
            await callback_query.edit_message_text("❌ Error loading requests.")

    async def show_approved_requests(self, callback_query: CallbackQuery):
        """Show recent approved requests"""
        try:
            approved_requests = await self.db.requests.find(
                {'status': 'approved'}
            ).sort('processed_at', -1).limit(5).to_list(5)

            if not approved_requests:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")]
                ])
                await callback_query.edit_message_text("✅ No approved requests yet!", reply_markup=keyboard)
                return

            text = "✅ **RECENT APPROVED REQUESTS**\n\n"
            for req in approved_requests:
                text += (
                    f"• `{req['request_id']}` - @{req['username']}\n"
                    f"  🎬 {req['drama_name']}\n"
                    f"  📅 {req.get('processed_at', req['created_at']).strftime('%Y-%m-%d')}\n\n"
                )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")]
            ])

            await callback_query.edit_message_text(text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing approved requests: {e}")
            await callback_query.edit_message_text("❌ Error loading requests.")

    async def show_rejected_requests(self, callback_query: CallbackQuery):
        """Show recent rejected requests"""
        try:
            rejected_requests = await self.db.requests.find(
                {'status': 'rejected'}
            ).sort('processed_at', -1).limit(5).to_list(5)

            if not rejected_requests:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")]
                ])
                await callback_query.edit_message_text("❌ No rejected requests yet!", reply_markup=keyboard)
                return

            text = "❌ **RECENT REJECTED REQUESTS**\n\n"
            for req in rejected_requests:
                text += (
                    f"• `{req['request_id']}` - @{req['username']}\n"
                    f"  🎬 {req['drama_name']}\n"
                    f"  📅 {req.get('processed_at', req['created_at']).strftime('%Y-%m-%d')}\n\n"
                )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")]
            ])

            await callback_query.edit_message_text(text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing rejected requests: {e}")
            await callback_query.edit_message_text("❌ Error loading requests.")

    async def show_detailed_stats(self, callback_query: CallbackQuery):
        """Show detailed statistics"""
        try:
            # Get comprehensive statistics
            total_requests = await self.db.requests.count_documents({})
            pending_requests = await self.db.requests.count_documents({'status': 'pending'})
            approved_requests = await self.db.requests.count_documents({'status': 'approved'})
            rejected_requests = await self.db.requests.count_documents({'status': 'rejected'})

            # Get unique user count
            unique_users = len(await self.db.requests.distinct('user_id'))

            # Get requests from last 7 days
            week_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
            recent_requests = await self.db.requests.count_documents({'created_at': {'$gte': week_ago}})

            stats_text = (
                f"📊 **DETAILED STATISTICS**\n\n"
                f"📈 **Total Requests:** {total_requests}\n"
                f"📋 **Pending:** {pending_requests}\n"
                f"✅ **Approved:** {approved_requests}\n"
                f"❌ **Rejected:** {rejected_requests}\n\n"
                f"👥 **Unique Users:** {unique_users}\n"
                f"📅 **Last 7 Days:** {recent_requests}\n"
                f"👮 **Active Admins:** {len(self.admin_ids)}\n\n"
            )

            if total_requests > 0:
                approval_rate = (approved_requests / total_requests) * 100
                stats_text += f"📊 **Approval Rate:** {approval_rate:.1f}%"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")]
            ])

            await callback_query.edit_message_text(stats_text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing detailed stats: {e}")
            await callback_query.edit_message_text("❌ Error loading statistics.")

    async def show_user_stats(self, callback_query: CallbackQuery):
        """Show user statistics"""
        try:
            # Get top requesting users
            pipeline = [
                {"$group": {"_id": "$username", "count": {"$sum": 1}, "user_id": {"$first": "$user_id"}}},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]

            top_users = await self.db.requests.aggregate(pipeline).to_list(5)

            user_text = "👥 **TOP REQUESTING USERS**\n\n"

            if top_users:
                for i, user in enumerate(top_users, 1):
                    user_text += f"{i}. @{user['_id']} - {user['count']} requests\n"
            else:
                user_text += "No user data available yet."

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")]
            ])

            await callback_query.edit_message_text(user_text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing user stats: {e}")
            await callback_query.edit_message_text("❌ Error loading user statistics.")

    async def revert_request_to_pending(self, callback_query: CallbackQuery, request_id: str):
        """Revert an approved/rejected request back to pending status"""
        try:
            # Find and update request in database
            result = await self.db.requests.find_one_and_update(
                {'request_id': request_id, 'status': {'$in': ['approved', 'rejected']}},
                {
                    '$set': {
                        'status': 'pending',
                        'processed_by': None,
                        'processed_at': None
                    }
                }
            )

            if not result:
                await callback_query.edit_message_text("❌ Request not found or already pending!")
                return

            old_status = result['status']

            # Notify the user about status change
            try:
                await self.client.send_message(
                    chat_id=result['user_id'],
                    text=f"🔄 **Request Status Updated**\n\n"
                         f"📋 **Request ID:** `{request_id}`\n"
                         f"🎬 **Drama:** {result['drama_name']}\n\n"
                         f"Your request has been moved back to pending for re-review.\n"
                         f"You'll be notified once it's reviewed again."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {result['user_id']}: {e}")

            # Update admin message
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{request_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{request_id}")
                ],
                [
                    InlineKeyboardButton("📝 Add Note", callback_data=f"admin_note_{request_id}"),
                    InlineKeyboardButton("📋 Full Details", callback_data=f"admin_details_{request_id}")
                ],
                [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_refresh_panel")]
            ])

            await callback_query.edit_message_text(
                f"🔄 **Request Reverted to Pending**\n\n"
                f"📋 **ID:** {request_id}\n"
                f"🎬 **Drama:** {result['drama_name']}\n"
                f"👤 **User:** @{result['username']}\n"
                f"📊 **Previous Status:** {old_status.title()}\n\n"
                f"✉️ User has been notified.\n"
                f"🎯 **Choose new action:**",
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Error reverting request: {e}")
            await callback_query.edit_message_text("❌ Error reverting request. Please try again.")

    async def refresh_admin_panel(self, callback_query: CallbackQuery):
        """Refresh the admin panel with updated stats"""
        try:
            # Get fresh statistics from database
            pending_count = await self.db.requests.count_documents({'status': 'pending'})
            approved_count = await self.db.requests.count_documents({'status': 'approved'})
            rejected_count = await self.db.requests.count_documents({'status': 'rejected'})
            total_count = await self.db.requests.count_documents({})

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📋 Pending Requests", callback_data="admin_view_pending"),
                    InlineKeyboardButton("✅ Approved", callback_data="admin_view_approved")
                ],
                [
                    InlineKeyboardButton("❌ Rejected", callback_data="admin_view_rejected"),
                    InlineKeyboardButton("📊 Statistics", callback_data="admin_view_stats")
                ],
                [
                    InlineKeyboardButton("👥 Users", callback_data="admin_view_users"),
                    InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh_panel")
                ]
            ])

            stats_text = (
                f"🛠️ **K-DRAMA ADMIN PANEL**\n\n"
                f"📊 **Statistics:**\n"
                f"📋 Pending: {pending_count}\n"
                f"✅ Approved: {approved_count}\n"
                f"❌ Rejected: {rejected_count}\n"
                f"📈 Total: {total_count}\n"
                f"👥 Admins: {len(self.admin_ids)}\n"
            )

            await callback_query.edit_message_text(stats_text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error refreshing admin panel: {e}")

    async def status_command(self, client: Client, message: Message):
        """Handle /status command to show user's requests"""
        user_id = message.from_user.id

        try:
            # Get user's requests from database
            user_requests = await self.db.requests.find(
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
            logger.error(f"Error showing user status: {e}")
            await message.reply_text(
                "❌ Error loading your request status. Please try again later."
            )

    async def add_admin_command(self, client: Client, message: Message):
        """Handle /addadmin command"""
        user_id = message.from_user.id
        bot_owner_id = int(os.getenv('BOT_OWNER_ID', BOT_OWNER_ID))

        if user_id == bot_owner_id:
            command_text = message.text
            args = command_text.split()[1:] if len(command_text.split()) > 1 else []
            
            if args:
                try:
                    new_admin_id = int(args[0])
                    await self.add_admin(new_admin_id)
                    await message.reply_text(f"✅ Added admin: {new_admin_id}")
                except ValueError:
                    await message.reply_text("❌ Invalid user ID!")
            else:
                await message.reply_text("Usage: /addadmin [user_id]")
        else:
            await message.reply_text("❌ Only bot owner can add admins!")

    async def remove_admin_command(self, client: Client, message: Message):
        """Handle /removeadmin command"""
        user_id = message.from_user.id
        bot_owner_id = int(os.getenv('BOT_OWNER_ID', BOT_OWNER_ID))

        if user_id == bot_owner_id:
            command_text = message.text
            args = command_text.split()[1:] if len(command_text.split()) > 1 else []
            
            if args:
                try:
                    remove_admin_id = int(args[0])

                    # Remove from database
                    await self.db.admins.update_one(
                        {'user_id': remove_admin_id},
                        {'$set': {'is_active': False}}
                    )

                    # Remove from memory
                    if remove_admin_id in self.admin_ids:
                        self.admin_ids.remove(remove_admin_id)

                    await message.reply_text(f"✅ Removed admin: {remove_admin_id}")
                except ValueError:
                    await message.reply_text("❌ Invalid user ID!")
                except Exception as e:
                    logger.error(f"Error removing admin: {e}")
                    await message.reply_text("❌ Error removing admin!")
            else:
                await message.reply_text("Usage: /removeadmin [user_id]")
        else:
            await message.reply_text("❌ Only bot owner can remove admins!")


def setup_handlers(client: Client, drama_system: KDramaRequestSystem):
    """Set up all the handlers for the bot - Pyrogram Client version"""

    # Command handlers
    @client.on_message(filters.command("request"))
    async def request_handler(client, message):
        await drama_system.request_drama_command(client, message)

    @client.on_message(filters.command("status"))
    async def status_handler(client, message):
        await drama_system.status_command(client, message)

    @client.on_message(filters.command("admin"))
    async def admin_handler(client, message):
        await drama_system.admin_panel(client, message)

    @client.on_message(filters.command("addadmin"))
    async def add_admin_handler(client, message):
        await drama_system.add_admin_command(client, message)

    @client.on_message(filters.command("removeadmin"))
    async def remove_admin_handler(client, message):
        await drama_system.remove_admin_command(client, message)

    # Callback query handler
    @client.on_callback_query()
    async def callback_handler(client, callback_query):
        await drama_system.handle_callbacks(client, callback_query)


