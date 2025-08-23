#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K-Drama Request System Plugin for Auto-Filter-Bot
File: plugins/kdrama_requests.py

This plugin adds K-Drama request functionality to the Auto-Filter-Bot
Compatible with pyrogram-based bot architecture
"""

import logging
import asyncio
import datetime
from typing import Dict, List, Optional
import re

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, User
)
from motor.motor_asyncio import AsyncIOMotorClient
from info import *

# Plugin Configuration
KDRAMA_CONFIG = {
    'MONGODB_URL': DATABASE_URI,  # Use existing bot's database
    'DATABASE_NAME': 'autofilter_bot',
    'COLLECTION_PREFIX': 'kdrama_',
    'MAX_REQUESTS_PER_DAY': 5,
    'REQUEST_COOLDOWN_MINUTES': 10,
    'ENABLE_USER_RATINGS': True,
    'AUTO_DELETE_TIMEOUT': 300,  # 5 minutes
}

# Initialize logger
logger = logging.getLogger(__name__)

class KDramaDatabase:
    """Database handler for K-Drama requests"""
    
    def __init__(self):
        self.client = None
        self.db = None
        self._initialized = False
    
    async def connect(self):
        """Connect to MongoDB database"""
        if self._initialized:
            return
        
        try:
            self.client = AsyncIOMotorClient(KDRAMA_CONFIG['MONGODB_URL'])
            self.db = self.client[KDRAMA_CONFIG['DATABASE_NAME']]
            
            # Test connection
            await self.client.admin.command('ping')
            
            # Create indexes
            await self.create_indexes()
            self._initialized = True
            
            logger.info("✅ K-Drama database initialized")
            
        except Exception as e:
            logger.error(f"❌ K-Drama database connection failed: {e}")
            raise
    
    async def create_indexes(self):
        """Create necessary database indexes"""
        collections = {
            f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests': [
                'request_id', 'user_id', 'status', 'created_at'
            ],
            f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}admins': ['user_id'],
            f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}stats': ['user_id'],
        }
        
        for collection_name, indexes in collections.items():
            collection = self.db[collection_name]
            for index in indexes:
                try:
                    await collection.create_index(index)
                except Exception as e:
                    logger.debug(f"Index {index} already exists or error: {e}")

# Initialize database
kdrama_db = KDramaDatabase()

class KDramaRequestManager:
    """Manages K-Drama requests and user interactions"""
    
    def __init__(self):
        self.admin_ids = set()
        self.user_cooldowns = {}
    
    async def ensure_db_connected(self):
        """Ensure database is connected"""
        if not kdrama_db._initialized:
            await kdrama_db.connect()
    
    async def load_admins(self):
        """Load admin IDs from database"""
        await self.ensure_db_connected()
        
        try:
            # Load from K-Drama admin collection
            admins_cursor = kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}admins'].find(
                {'is_active': True}
            )
            async for admin in admins_cursor:
                self.admin_ids.add(admin['user_id'])
            
            # Also add bot admins from main bot config
            if ADMINS:
                for admin_id in ADMINS:
                    self.admin_ids.add(admin_id)
                    # Add to K-Drama admins if not exists
                    await self.add_admin(admin_id)
            
            logger.info(f"✅ Loaded {len(self.admin_ids)} K-Drama admins")
            
        except Exception as e:
            logger.error(f"❌ Error loading admins: {e}")
    
    async def add_admin(self, user_id: int):
        """Add admin to database"""
        await self.ensure_db_connected()
        
        try:
            admin_data = {
                'user_id': user_id,
                'added_at': datetime.datetime.utcnow(),
                'is_active': True,
                'added_by': 'system'
            }
            
            await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}admins'].update_one(
                {'user_id': user_id},
                {'$set': admin_data},
                upsert=True
            )
            
            self.admin_ids.add(user_id)
            
        except Exception as e:
            logger.error(f"❌ Error adding admin {user_id}: {e}")
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.admin_ids
    
    async def check_rate_limit(self, user_id: int) -> tuple[bool, str]:
        """Check if user can make a request"""
        await self.ensure_db_connected()
        
        now = datetime.datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Check daily limit
        daily_count = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents({
            'user_id': user_id,
            'created_at': {'$gte': today_start}
        })
        
        if daily_count >= KDRAMA_CONFIG['MAX_REQUESTS_PER_DAY']:
            return False, f"❌ Daily limit reached! You can make {KDRAMA_CONFIG['MAX_REQUESTS_PER_DAY']} requests per day."
        
        # Check cooldown
        if user_id in self.user_cooldowns:
            time_diff = (now - self.user_cooldowns[user_id]).total_seconds()
            cooldown_seconds = KDRAMA_CONFIG['REQUEST_COOLDOWN_MINUTES'] * 60
            
            if time_diff < cooldown_seconds:
                remaining_minutes = int((cooldown_seconds - time_diff) / 60) + 1
                return False, f"⏱️ Please wait {remaining_minutes} minutes before making another request."
        
        return True, ""
    
    async def create_request(self, user: User, drama_name: str, additional_details: str = None) -> Dict:
        """Create a new K-Drama request"""
        await self.ensure_db_connected()
        
        # Generate request ID
        request_count = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents({}) + 1
        request_id = f"KDRAMA_{request_count:04d}"
        
        request_data = {
            'request_id': request_id,
            'user_id': user.id,
            'username': user.username or user.first_name,
            'first_name': user.first_name,
            'drama_name': drama_name,
            'additional_details': additional_details,
            'status': 'pending',
            'created_at': datetime.datetime.utcnow(),
            'processed_at': None,
            'processed_by': None,
            'admin_notes': None
        }
        
        # Insert into database
        await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].insert_one(request_data)
        
        # Update user cooldown
        self.user_cooldowns[user.id] = datetime.datetime.utcnow()
        
        return request_data
    
    async def get_user_requests(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's requests"""
        await self.ensure_db_connected()
        
        cursor = kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].find(
            {'user_id': user_id}
        ).sort('created_at', -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_pending_requests(self, limit: int = 10) -> List[Dict]:
        """Get pending requests for admins"""
        await self.ensure_db_connected()
        
        cursor = kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].find(
            {'status': 'pending'}
        ).sort('created_at', 1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def update_request_status(self, request_id: str, status: str, admin_id: int, notes: str = None) -> bool:
        """Update request status"""
        await self.ensure_db_connected()
        
        update_data = {
            'status': status,
            'processed_at': datetime.datetime.utcnow(),
            'processed_by': admin_id
        }
        
        if notes:
            update_data['admin_notes'] = notes
        
        result = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].update_one(
            {'request_id': request_id},
            {'$set': update_data}
        )
        
        return result.modified_count > 0
    
    async def get_request_by_id(self, request_id: str) -> Optional[Dict]:
        """Get request by ID"""
        await self.ensure_db_connected()
        
        return await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].find_one(
            {'request_id': request_id}
        )

# Initialize manager
kdrama_manager = KDramaRequestManager()

# Helper functions
def get_status_emoji(status: str) -> str:
    """Get emoji for request status"""
    return {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌',
        'processing': '🔄'
    }.get(status, '❓')

async def delete_message_later(client: Client, chat_id: int, message_id: int, delay: int = 300):
    """Delete message after delay"""
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
    except:
        pass

# Command Handlers
@Client.on_message(filters.command(["kdrama", "request", "req"]) & filters.private)
async def kdrama_request_command(client: Client, message: Message):
    """Handle K-Drama request command"""
    user = message.from_user
    
    # Initialize if needed
    if not kdrama_manager.admin_ids:
        await kdrama_manager.load_admins()
    
    # Check rate limits
    can_request, limit_msg = await kdrama_manager.check_rate_limit(user.id)
    if not can_request:
        sent_msg = await message.reply_text(
            f"🚫 **Rate Limited**\n\n{limit_msg}",
            quote=True
        )
        # Auto-delete after 30 seconds
        asyncio.create_task(delete_message_later(client, message.chat.id, sent_msg.id, 30))
        return
    
    # Parse command arguments
    command_text = message.text.split(maxsplit=1)
    
    if len(command_text) < 2:
        # Show help
        help_text = (
            "🎬 **K-Drama Request System**\n\n"
            "**Usage:**\n"
            "`/kdrama [drama name]`\n"
            "`/request_kdrama [drama name]`\n\n"
            "**Examples:**\n"
            "• `/kdrama Squid Game`\n"
            "• `/kdrama Crash Landing on You (2019)`\n"
            "• `/kdrama Kingdom Season 2`\n\n"
            "**Features:**\n"
            f"• {KDRAMA_CONFIG['MAX_REQUESTS_PER_DAY']} requests per day\n"
            f"• {KDRAMA_CONFIG['REQUEST_COOLDOWN_MINUTES']} minute cooldown\n"
            "• Real-time status updates\n"
            "• Admin review system\n\n"
            "**Tips:**\n"
            "✅ Include year for accuracy\n"
            "✅ Specify season numbers\n"
            "✅ Be descriptive but concise"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 My Requests", callback_data="kdrama_my_status")],
            [InlineKeyboardButton("📊 Statistics", callback_data="kdrama_stats")]
        ])
        
        await message.reply_text(help_text, reply_markup=keyboard, quote=True)
        return
    
    drama_name = command_text[1].strip()
    
    # Validate drama name
    if len(drama_name) < 2:
        await message.reply_text(
            "❌ **Invalid Request**\n\n"
            "Drama name is too short. Please provide a valid K-Drama name.",
            quote=True
        )
        return
    
    # Check for offensive content (basic filter)
    offensive_words = ['fuck', 'shit', 'damn']  # Add more as needed
    if any(word in drama_name.lower() for word in offensive_words):
        await message.reply_text(
            "❌ **Invalid Content**\n\n"
            "Please keep your requests appropriate and family-friendly.",
            quote=True
        )
        return
    
    # Show confirmation
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data=f"kdrama_confirm|{drama_name}"),
            InlineKeyboardButton("❌ Cancel", callback_data="kdrama_cancel")
        ],
        [InlineKeyboardButton("📝 Add Details", callback_data=f"kdrama_details|{drama_name}")]
    ])
    
    confirmation_text = (
        f"🎬 **Confirm K-Drama Request**\n\n"
        f"**Drama:** {drama_name}\n"
        f"**Requested by:** {user.first_name}\n\n"
        f"📋 **Next Steps:**\n"
        f"• Request will be reviewed by admins\n"
        f"• You'll be notified of status changes\n"
        f"• Processing usually takes 24-48 hours\n\n"
        f"Proceed with this request?"
    )
    
    await message.reply_text(confirmation_text, reply_markup=keyboard, quote=True)

@Client.on_message(filters.command("kdrama_status") & filters.private)
async def kdrama_status_command(client: Client, message: Message):
    """Show user's K-Drama request status"""
    user = message.from_user
    
    try:
        # Get user's requests
        requests = await kdrama_manager.get_user_requests(user.id, limit=5)
        
        if not requests:
            await message.reply_text(
                "📋 **Your K-Drama Requests**\n\n"
                "You haven't made any requests yet!\n\n"
                "Use `/kdrama [drama name]` to make your first request.",
                quote=True
            )
            return
        
        status_text = "📋 **Your Recent K-Drama Requests**\n\n"
        
        for req in requests:
            emoji = get_status_emoji(req['status'])
            status_text += (
                f"{emoji} `{req['request_id']}`\n"
                f"🎬 **{req['drama_name']}**\n"
                f"📅 {req['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
                f"📊 Status: {req['status'].title()}\n"
            )
            
            if req.get('admin_notes'):
                status_text += f"💬 Note: {req['admin_notes']}\n"
            
            status_text += "\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="kdrama_my_status")],
            [InlineKeyboardButton("🎬 New Request", callback_data="kdrama_new_request")]
        ])
        
        await message.reply_text(status_text, reply_markup=keyboard, quote=True)
        
    except Exception as e:
        logger.error(f"Error showing status: {e}")
        await message.reply_text(
            "❌ **Error Loading Status**\n\n"
            "Unable to load your requests. Please try again later.",
            quote=True
        )

# Admin Commands
# Admin Commands
@Client.on_message(filters.command("kdrama_admin") & filters.private)
async def kdrama_admin_command(client: Client, message: Message):
    """K-Drama admin panel or specific request review"""
    user = message.from_user
    
    # Initialize if needed
    if not kdrama_manager.admin_ids:
        await kdrama_manager.load_admins()
    
    if not kdrama_manager.is_admin(user.id):
        await message.reply_text("❌ You don't have admin permissions for K-Drama requests.", quote=True)
        return
    
    # Parse command arguments
    command_parts = message.text.split()
    
    # If specific request ID is provided
    if len(command_parts) > 1:
        request_id = command_parts[1].strip().upper()
        await handle_specific_request_review(client, message, request_id)
        return
    
    try:
        # Show general admin panel
        await kdrama_manager.ensure_db_connected()
        
        total_requests = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents({})
        pending_requests = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents({'status': 'pending'})
        approved_requests = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents({'status': 'approved'})
        rejected_requests = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents({'status': 'rejected'})
        
        admin_text = (
            f"🛠️ **K-Drama Admin Panel**\n\n"
            f"📊 **Statistics:**\n"
            f"• Total Requests: {total_requests}\n"
            f"• Pending: {pending_requests}\n"
            f"• Approved: {approved_requests}\n"
            f"• Rejected: {rejected_requests}\n\n"
            f"👥 **Admins:** {len(kdrama_manager.admin_ids)}\n\n"
            f"💡 **Usage:**\n"
            f"• `/kdrama_admin` - Show this panel\n"
            f"• `/kdrama_admin [REQUEST_ID]` - Review specific request\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📋 Pending", callback_data="kdrama_admin_pending"),
                InlineKeyboardButton("✅ Approved", callback_data="kdrama_admin_approved")
            ],
            [
                InlineKeyboardButton("❌ Rejected", callback_data="kdrama_admin_rejected"),
                InlineKeyboardButton("📊 Stats", callback_data="kdrama_admin_stats")
            ]
        ])
        
        await message.reply_text(admin_text, reply_markup=keyboard, quote=True)
        
    except Exception as e:
        logger.error(f"Error in admin command: {e}")
        await message.reply_text("❌ Error loading admin panel.", quote=True)

async def handle_specific_request_review(client: Client, message: Message, request_id: str):
    """Handle review of a specific request by ID"""
    try:
        # Get request details
        request = await kdrama_manager.get_request_by_id(request_id)
        
        if not request:
            await message.reply_text(
                f"❌ **Request Not Found**\n\n"
                f"No request found with ID: `{request_id}`\n\n"
                f"Please check the ID and try again.",
                quote=True
            )
            return
        
        # Format request details
        status_emoji = get_status_emoji(request['status'])
        
        request_text = (
            f"📋 **Request Review: {request_id}**\n\n"
            f"🆔 **ID:** `{request['request_id']}`\n"
            f"👤 **User:** @{request['username']} ({request['user_id']})\n"
            f"🎬 **Drama:** {request['drama_name']}\n"
            f"📅 **Requested:** {request['created_at'].strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"📊 **Status:** {status_emoji} {request['status'].title()}\n"
        )
        
        # Add additional details if present
        if request.get('additional_details'):
            request_text += f"📝 **Details:** {request['additional_details']}\n"
        
        # Add processing info if processed
        if request.get('processed_at'):
            request_text += f"⚡ **Processed:** {request['processed_at'].strftime('%Y-%m-%d %H:%M UTC')}\n"
            if request.get('processed_by'):
                request_text += f"👨‍💼 **Processed by:** {request['processed_by']}\n"
        
        # Add admin notes if present
        if request.get('admin_notes'):
            request_text += f"💬 **Admin Notes:** {request['admin_notes']}\n"
        
        # Create action buttons based on current status
        keyboard_buttons = []
        
        if request['status'] == 'pending':
            # Show approve/reject buttons for pending requests
            keyboard_buttons.extend([
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"kdrama_quick_approve_{request_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"kdrama_quick_reject_{request_id}")
                ],
                [InlineKeyboardButton("📝 Approve with Note", callback_data=f"kdrama_approve_note_{request_id}")],
                [InlineKeyboardButton("📝 Reject with Note", callback_data=f"kdrama_reject_note_{request_id}")]
            ])
        else:
            # Show status change options for processed requests
            if request['status'] != 'approved':
                keyboard_buttons.append([InlineKeyboardButton("✅ Mark as Approved", callback_data=f"kdrama_quick_approve_{request_id}")])
            
            if request['status'] != 'rejected':
                keyboard_buttons.append([InlineKeyboardButton("❌ Mark as Rejected", callback_data=f"kdrama_quick_reject_{request_id}")])
            
            if request['status'] != 'pending':
                keyboard_buttons.append([InlineKeyboardButton("⏳ Mark as Pending", callback_data=f"kdrama_mark_pending_{request_id}")])
        
        # Add general action buttons
        keyboard_buttons.extend([
            [InlineKeyboardButton("👤 View User History", callback_data=f"kdrama_user_history_{request['user_id']}")],
            [InlineKeyboardButton("🛠️ Admin Panel", callback_data="kdrama_admin_panel")]
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await message.reply_text(request_text, reply_markup=keyboard, quote=True)
        
    except Exception as e:
        logger.error(f"Error reviewing request {request_id}: {e}")
        await message.reply_text(
            f"❌ **Error Loading Request**\n\n"
            f"Failed to load request `{request_id}`. Please try again later.",
            quote=True
        )
# Callback Query Handlers
@Client.on_callback_query(filters.regex(r"^kdrama_"))
async def kdrama_callback_handler(client: Client, callback_query: CallbackQuery):
    """Handle K-Drama callback queries"""
    user = callback_query.from_user
    data = callback_query.data
    
    try:
        await callback_query.answer()
        
        # Initialize manager if needed
        if not kdrama_manager.admin_ids:
            await kdrama_manager.load_admins()
        
        # Parse callback data
        if data == "kdrama_cancel":
            await callback_query.edit_message_text("❌ Request cancelled.")
            return
        
        elif data.startswith("kdrama_confirm|"):
            drama_name = data.split("|", 1)[1]
            await handle_request_confirmation(client, callback_query, drama_name)
        
        elif data.startswith("kdrama_details|"):
            drama_name = data.split("|", 1)[1]
            await callback_query.edit_message_text(
                f"📝 **Add Details for: {drama_name}**\n\n"
                f"Please reply to this message with additional details like:\n"
                f"• Year of release\n"
                f"• Genre preferences\n"
                f"• Specific season/episode\n"
                f"• Any other relevant information\n\n"
                f"Or use `/kdrama {drama_name}` again to submit without details."
            )
        
        elif data == "kdrama_my_status":
            await handle_status_callback(client, callback_query)
        
        elif data == "kdrama_stats":
            await handle_stats_callback(client, callback_query)
        
        # Admin callbacks
        elif data.startswith("kdrama_admin_") and kdrama_manager.is_admin(user.id):
            await handle_admin_callbacks(client, callback_query)
        
        else:
            await callback_query.edit_message_text("❌ Invalid or expired action.")
    
    except Exception as e:
        logger.error(f"Error handling callback {data}: {e}")
        await callback_query.edit_message_text("❌ An error occurred. Please try again.")

async def handle_request_confirmation(client: Client, callback_query: CallbackQuery, drama_name: str):
    """Handle request confirmation"""
    user = callback_query.from_user
    
    # Check rate limits again
    can_request, limit_msg = await kdrama_manager.check_rate_limit(user.id)
    if not can_request:
        await callback_query.edit_message_text(f"🚫 **Rate Limited**\n\n{limit_msg}")
        return
    
    try:
        # Create request
        request_data = await kdrama_manager.create_request(user, drama_name)
        
        # Success message
        success_text = (
            f"✅ **Request Submitted Successfully!**\n\n"
            f"📋 **Details:**\n"
            f"• ID: `{request_data['request_id']}`\n"
            f"• Drama: {drama_name}\n"
            f"• Status: Pending Review\n"
            f"• Submitted: {request_data['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
            f"🔔 **What's Next?**\n"
            f"• Admins will review your request\n"
            f"• You'll be notified of any updates\n"
            f"• Use `/kdrama_status` to check progress\n\n"
            f"Thank you for your request! 🎬"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 My Requests", callback_data="kdrama_my_status")],
            [InlineKeyboardButton("🎬 Request Another", callback_data="kdrama_new_request")]
        ])
        
        await callback_query.edit_message_text(success_text, reply_markup=keyboard)
        
        # Notify admins
        await notify_admins_new_request(client, request_data)
        
    except Exception as e:
        logger.error(f"Error confirming request: {e}")
        await callback_query.edit_message_text(
            "❌ **Error Creating Request**\n\n"
            "There was a technical issue. Please try again later."
        )

async def handle_status_callback(client: Client, callback_query: CallbackQuery):
    """Handle status callback"""
    user = callback_query.from_user
    
    try:
        requests = await kdrama_manager.get_user_requests(user.id, limit=5)
        
        if not requests:
            await callback_query.edit_message_text(
                "📋 **Your K-Drama Requests**\n\n"
                "No requests found. Use `/kdrama [name]` to make your first request!"
            )
            return
        
        status_text = "📋 **Your Recent Requests**\n\n"
        
        for req in requests:
            emoji = get_status_emoji(req['status'])
            status_text += (
                f"{emoji} `{req['request_id']}`\n"
                f"🎬 {req['drama_name']}\n"
                f"📅 {req['created_at'].strftime('%m-%d %H:%M')}\n\n"
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="kdrama_my_status")],
            [InlineKeyboardButton("🎬 New Request", callback_data="kdrama_new_request")]
        ])
        
        await callback_query.edit_message_text(status_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error showing status: {e}")
        await callback_query.edit_message_text("❌ Error loading status.")

async def handle_stats_callback(client: Client, callback_query: CallbackQuery):
    """Handle stats callback"""
    try:
        await kdrama_manager.ensure_db_connected()
        
        total_requests = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents({})
        total_users = len(await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].distinct('user_id'))
        
        # Get popular dramas
        pipeline = [
            {"$group": {"_id": "$drama_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        popular_dramas = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].aggregate(pipeline).to_list(5)
        
        stats_text = (
            f"📊 **K-Drama Statistics**\n\n"
            f"📈 **Overall:**\n"
            f"• Total Requests: {total_requests}\n"
            f"• Active Users: {total_users}\n"
            f"• Active Admins: {len(kdrama_manager.admin_ids)}\n\n"
        )
        
        if popular_dramas:
            stats_text += "🏆 **Most Requested:**\n"
            for i, drama in enumerate(popular_dramas, 1):
                stats_text += f"{i}. {drama['_id']} ({drama['count']})\n"
        
        await callback_query.edit_message_text(stats_text)
        
    except Exception as e:
        logger.error(f"Error showing stats: {e}")
        await callback_query.edit_message_text("❌ Error loading statistics.")

async def handle_admin_callbacks(client: Client, callback_query: CallbackQuery):
    """Handle admin callback queries"""
    data = callback_query.data
    
    try:
        if data == "kdrama_admin_pending":
            await show_pending_requests(client, callback_query)
        elif data == "kdrama_admin_approved":
            await show_approved_requests(client, callback_query)
        elif data == "kdrama_admin_rejected":
            await show_rejected_requests(client, callback_query)
        elif data == "kdrama_admin_stats":
            await show_admin_stats(client, callback_query)
        elif data.startswith("kdrama_approve_"):
            request_id = data.split("_", 2)[2]
            await approve_request(client, callback_query, request_id)
        elif data.startswith("kdrama_reject_"):
            request_id = data.split("_", 2)[2]
            await reject_request(client, callback_query, request_id)
            
    except Exception as e:
        logger.error(f"Error in admin callback {data}: {e}")
        await callback_query.edit_message_text("❌ Error processing admin action.")

async def show_pending_requests(client: Client, callback_query: CallbackQuery):
    """Show pending requests to admin"""
    try:
        pending_requests = await kdrama_manager.get_pending_requests(limit=5)
        
        if not pending_requests:
            await callback_query.edit_message_text("📋 **No Pending Requests**\n\nAll caught up! 🎉")
            return
        
        text = "📋 **Pending K-Drama Requests**\n\n"
        
        for req in pending_requests:
            text += (
                f"🆔 `{req['request_id']}`\n"
                f"🎬 **{req['drama_name']}**\n"
                f"👤 @{req['username']} ({req['user_id']})\n"
                f"📅 {req['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
            )
        
        # Create action buttons for first request
        first_request = pending_requests[0]
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"kdrama_approve_{first_request['request_id']}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"kdrama_reject_{first_request['request_id']}")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="kdrama_admin_panel")]
        ])
        
        await callback_query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error showing pending requests: {e}")
        await callback_query.edit_message_text("❌ Error loading pending requests.")

async def approve_request(client: Client, callback_query: CallbackQuery, request_id: str):
    """Approve a request"""
    try:
        success = await kdrama_manager.update_request_status(
            request_id, 'approved', callback_query.from_user.id
        )
        
        if success:
            # Get request details
            request = await kdrama_manager.get_request_by_id(request_id)
            
            if request:
                # Notify user
                try:
                    await client.send_message(
                        request['user_id'],
                        f"🎉 **Request Approved!**\n\n"
                        f"📋 ID: `{request_id}`\n"
                        f"🎬 Drama: **{request['drama_name']}**\n\n"
                        f"Your request has been approved! We'll work on adding this drama to our collection."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {request['user_id']}: {e}")
            
            await callback_query.edit_message_text(
                f"✅ **Request Approved**\n\n"
                f"📋 ID: `{request_id}`\n"
                f"🎬 Drama: **{request['drama_name']}**\n"
                f"👤 User: @{request['username']}\n\n"
                f"✉️ User has been notified."
            )
        else:
            await callback_query.edit_message_text("❌ Failed to approve request.")
            
    except Exception as e:
        logger.error(f"Error approving request: {e}")
        await callback_query.edit_message_text("❌ Error approving request.")

async def reject_request(client: Client, callback_query: CallbackQuery, request_id: str):
    """Reject a request"""
    try:
        success = await kdrama_manager.update_request_status(
            request_id, 'rejected', callback_query.from_user.id
        )
        
        if success:
            # Get request details
            request = await kdrama_manager.get_request_by_id(request_id)
            
            if request:
                # Notify user
                try:
                    await client.send_message(
                        request['user_id'],
                        f"💔 **Request Update**\n\n"
                        f"📋 ID: `{request_id}`\n"
                        f"🎬 Drama: **{request['drama_name']}**\n\n"
                        f"Unfortunately, we cannot fulfill this request at this time. "
                        f"This might be due to licensing issues or availability constraints."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {request['user_id']}: {e}")
            
            await callback_query.edit_message_text(
                f"❌ **Request Rejected**\n\n"
                f"📋 ID: `{request_id}`\n"
                f"🎬 Drama: **{request['drama_name']}**\n"
                f"👤 User: @{request['username']}\n\n"
                f"✉️ User has been notified."
            )
        else:
            await callback_query.edit_message_text("❌ Failed to reject request.")
            
    except Exception as e:
        logger.error(f"Error rejecting request: {e}")
        await callback_query.edit_message_text("❌ Error rejecting request.")

async def show_approved_requests(client: Client, callback_query: CallbackQuery):
    """Show recent approved requests"""
    try:
        await kdrama_manager.ensure_db_connected()
        
        cursor = kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].find(
            {'status': 'approved'}
        ).sort('processed_at', -1).limit(5)
        
        approved_requests = await cursor.to_list(length=5)
        
        if not approved_requests:
            await callback_query.edit_message_text("✅ **No Approved Requests**\n\nNo approved requests yet.")
            return
        
        text = "✅ **Recent Approved Requests**\n\n"
        
        for req in approved_requests:
            text += (
                f"🆔 `{req['request_id']}`\n"
                f"🎬 **{req['drama_name']}**\n"
                f"👤 @{req['username']}\n"
                f"📅 {req.get('processed_at', req['created_at']).strftime('%Y-%m-%d')}\n\n"
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Panel", callback_data="kdrama_admin_panel")]
        ])
        
        await callback_query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error showing approved requests: {e}")
        await callback_query.edit_message_text("❌ Error loading approved requests.")

async def show_rejected_requests(client: Client, callback_query: CallbackQuery):
    """Show recent rejected requests"""
    try:
        await kdrama_manager.ensure_db_connected()
        
        cursor = kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].find(
            {'status': 'rejected'}
        ).sort('processed_at', -1).limit(5)
        
        rejected_requests = await cursor.to_list(length=5)
        
        if not rejected_requests:
            await callback_query.edit_message_text("❌ **No Rejected Requests**\n\nNo rejected requests yet.")
            return
        
        text = "❌ **Recent Rejected Requests**\n\n"
        
        for req in rejected_requests:
            text += (
                f"🆔 `{req['request_id']}`\n"
                f"🎬 **{req['drama_name']}**\n"
                f"👤 @{req['username']}\n"
                f"📅 {req.get('processed_at', req['created_at']).strftime('%Y-%m-%d')}\n\n"
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Panel", callback_data="kdrama_admin_panel")]
        ])
        
        await callback_query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error showing rejected requests: {e}")
        await callback_query.edit_message_text("❌ Error loading rejected requests.")

async def show_admin_stats(client: Client, callback_query: CallbackQuery):
    """Show detailed admin statistics"""
    try:
        await kdrama_manager.ensure_db_connected()
        
        # Get comprehensive statistics
        total_requests = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents({})
        pending_requests = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents({'status': 'pending'})
        approved_requests = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents({'status': 'approved'})
        rejected_requests = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents({'status': 'rejected'})
        
        # Get unique user count
        unique_users = len(await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].distinct('user_id'))
        
        # Get requests from last 7 days
        week_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        recent_requests = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].count_documents(
            {'created_at': {'$gte': week_ago}}
        )
        
        # Get top requesting users
        pipeline = [
            {"$group": {"_id": "$username", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]
        top_users = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].aggregate(pipeline).to_list(3)
        
        stats_text = (
            f"📊 **Detailed K-Drama Statistics**\n\n"
            f"📈 **Request Overview:**\n"
            f"• Total: {total_requests}\n"
            f"• Pending: {pending_requests}\n"
            f"• Approved: {approved_requests}\n"
            f"• Rejected: {rejected_requests}\n\n"
            f"👥 **User Activity:**\n"
            f"• Unique Users: {unique_users}\n"
            f"• Last 7 Days: {recent_requests}\n"
            f"• Active Admins: {len(kdrama_manager.admin_ids)}\n\n"
        )
        
        if total_requests > 0:
            approval_rate = (approved_requests / total_requests) * 100
            stats_text += f"📊 **Approval Rate:** {approval_rate:.1f}%\n\n"
        
        if top_users:
            stats_text += "🏆 **Top Requesters:**\n"
            for i, user in enumerate(top_users, 1):
                stats_text += f"{i}. @{user['_id']}: {user['count']} requests\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Panel", callback_data="kdrama_admin_panel")]
        ])
        
        await callback_query.edit_message_text(stats_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error showing admin stats: {e}")
        await callback_query.edit_message_text("❌ Error loading statistics.")

async def notify_admins_new_request(client: Client, request_data: Dict):
    """Notify all admins about a new request"""
    notification_text = (
        f"🆕 **NEW K-DRAMA REQUEST**\n\n"
        f"📋 **ID:** `{request_data['request_id']}`\n"
        f"👤 **User:** @{request_data['username']} ({request_data['user_id']})\n"
        f"🎬 **Drama:** {request_data['drama_name']}\n"
        f"⏰ **Time:** {request_data['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
    )
    
    if request_data.get('additional_details'):
        notification_text += f"📝 **Details:** {request_data['additional_details']}\n"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"kdrama_approve_{request_data['request_id']}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"kdrama_reject_{request_data['request_id']}")
        ],
        [InlineKeyboardButton("🛠️ Admin Panel", callback_data="kdrama_admin_panel")]
    ])
    
    # Send notification to all admins
    for admin_id in kdrama_manager.admin_ids:
        try:
            await client.send_message(
                admin_id,
                notification_text,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

# Additional utility functions
async def cleanup_old_requests():
    """Clean up old processed requests (optional maintenance)"""
    try:
        await kdrama_manager.ensure_db_connected()
        
        # Delete requests older than 30 days that are processed
        thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        
        result = await kdrama_db.db[f'{KDRAMA_CONFIG["COLLECTION_PREFIX"]}requests'].delete_many({
            'processed_at': {'$lt': thirty_days_ago},
            'status': {'$in': ['approved', 'rejected']}
        })
        
        if result.deleted_count > 0:
            logger.info(f"Cleaned up {result.deleted_count} old requests")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# Initialize the plugin when imported
async def init_kdrama_plugin():
    """Initialize the K-Drama plugin"""
    try:
        await kdrama_manager.load_admins()
        logger.info("✅ K-Drama Request Plugin initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize K-Drama plugin: {e}")

# Auto-initialize when module is imported
asyncio.create_task(init_kdrama_plugin())

# Plugin Information
PLUGIN_INFO = {
    "name": "K-Drama Request System",
    "version": "1.0.0",
    "description": "Advanced K-Drama request system for Auto-Filter-Bot",
    "author": "Auto-Filter-Bot Community",
    "commands": [
        "/kdrama - Request a K-Drama",
        "/request_kdrama - Alternative request command", 
        "/kdrama_status - Check your request status",
        "/kdrama_admin - Admin panel (admins only)"
    ],
    "features": [
        "Rate limiting and spam protection",
        "Admin approval system",
        "User statistics and analytics",
        "Real-time notifications",
        "Database integration with Auto-Filter-Bot"
    ]
}
