import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from pyrogram.types import Message, User, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserIsBlocked, PeerIdInvalid, UserDeactivated
import logging
from collections import defaultdict
import time
from info import DATABASE_URI, ADMINS, DATABASE_NAME
from utils import temp
from logging_helper import LOGGER

# Use existing logger
logger = LOGGER

class UserAnalytics:
    def __init__(self, bot: Client, database_uri: str = DATABASE_URI, database_name: str = DATABASE_NAME):
        """
        Initialize User Analytics Module
        
        Args:
            bot: Pyrogram Client instance
            database_uri: MongoDB connection string
            database_name: Database name
        """
        self.bot = bot
        self.db_client = AsyncIOMotorClient(database_uri)
        self.db = self.db_client[database_name]
        self.users_collection = self.db.users
        self.analytics_collection = self.db.analytics
        
        # Cache for quick access
        self.active_users_cache = set()
        self.blocked_users_cache = set()
        self.cache_last_updated = 0
        self.cache_ttl = 300  # 5 minutes cache TTL
    
    async def init_database(self):
        """Initialize database indexes for better performance"""
        try:
            # Create indexes for better query performance
            await self.users_collection.create_index("user_id", unique=True)
            await self.users_collection.create_index("first_seen")
            await self.users_collection.create_index("last_seen")
            await self.users_collection.create_index("is_blocked")
            await self.users_collection.create_index("is_active")
            
            await self.analytics_collection.create_index("date")
            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating database indexes: {e}")
    
    async def add_user(self, user: User, source: str = "unknown"):
        """
        Add or update user in database
        
        Args:
            user: Pyrogram User object
            source: Source of user addition (start, group_join, etc.)
        """
        try:
            current_time = datetime.utcnow()
            
            user_data = {
                "user_id": user.id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username or "",
                "is_bot": user.is_bot,
                "language_code": getattr(user, 'language_code', 'en'),
                "last_seen": current_time,
                "is_active": True,
                "is_blocked": False,
                "source": source,
                "total_interactions": 1
            }
            
            # Check if user exists
            existing_user = await self.users_collection.find_one({"user_id": user.id})
            
            if existing_user:
                # Update existing user
                update_data = {
                    "first_name": user.first_name or "",
                    "last_name": user.last_name or "",
                    "username": user.username or "",
                    "last_seen": current_time,
                    "is_active": True,
                    "is_blocked": False,
                    "$inc": {"total_interactions": 1}
                }
                await self.users_collection.update_one(
                    {"user_id": user.id}, 
                    {"$set": update_data}
                )
            else:
                # Add new user
                user_data["first_seen"] = current_time
                await self.users_collection.insert_one(user_data)
                
                # Update daily analytics
                await self.update_daily_analytics("new_users", 1)
                logger.info(f"New user added: {user.id} ({user.first_name})")
            
            # Update cache
            if user.id in self.blocked_users_cache:
                self.blocked_users_cache.remove(user.id)
            self.active_users_cache.add(user.id)
            
        except Exception as e:
            logger.error(f"Error adding/updating user {user.id}: {e}")
    
    async def mark_user_blocked(self, user_id: int):
        """Mark user as blocked"""
        try:
            await self.users_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_blocked": True,
                        "is_active": False,
                        "blocked_at": datetime.utcnow()
                    }
                }
            )
            
            # Update cache
            if user_id in self.active_users_cache:
                self.active_users_cache.remove(user_id)
            self.blocked_users_cache.add(user_id)
            
            # Update daily analytics
            await self.update_daily_analytics("blocked_users", 1)
            logger.info(f"User {user_id} marked as blocked")
            
        except Exception as e:
            logger.error(f"Error marking user {user_id} as blocked: {e}")
    
    async def update_user_activity(self, user_id: int):
        """Update user's last seen timestamp"""
        try:
            current_time = datetime.utcnow()
            await self.users_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "last_seen": current_time,
                        "is_active": True
                    },
                    "$inc": {"total_interactions": 1}
                }
            )
            
            # Update cache
            self.active_users_cache.add(user_id)
            
        except Exception as e:
            logger.error(f"Error updating activity for user {user_id}: {e}")
    
    async def get_new_users_stats(self) -> Dict[str, int]:
        """Get new users statistics"""
        try:
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today - timedelta(days=today.weekday())
            month_start = today.replace(day=1)
            
            # Today's new users
            today_count = await self.users_collection.count_documents({
                "first_seen": {"$gte": today}
            })
            
            # This week's new users
            week_count = await self.users_collection.count_documents({
                "first_seen": {"$gte": week_start}
            })
            
            # This month's new users
            month_count = await self.users_collection.count_documents({
                "first_seen": {"$gte": month_start}
            })
            
            return {
                "today": today_count,
                "week": week_count,
                "month": month_count
            }
            
        except Exception as e:
            logger.error(f"Error getting new users stats: {e}")
            return {"today": 0, "week": 0, "month": 0}
    
    async def get_active_users_count(self) -> int:
        """Get count of active users (interacted in last 30 days)"""
        try:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            count = await self.users_collection.count_documents({
                "last_seen": {"$gte": thirty_days_ago},
                "is_blocked": {"$ne": True}
            })
            return count
        except Exception as e:
            logger.error(f"Error getting active users count: {e}")
            return 0
    
    async def get_blocked_users_count(self) -> int:
        """Get count of blocked users"""
        try:
            count = await self.users_collection.count_documents({
                "is_blocked": True
            })
            return count
        except Exception as e:
            logger.error(f"Error getting blocked users count: {e}")
            return 0
    
    async def get_live_users_count(self) -> int:
        """
        Get count of live users by attempting to send test messages
        Note: This is resource-intensive and should be used carefully
        """
        try:
            # Get sample of recent users to test
            recent_users = await self.users_collection.find({
                "is_blocked": {"$ne": True},
                "last_seen": {"$gte": datetime.utcnow() - timedelta(days=7)}
            }).limit(100).to_list(length=100)
            
            live_count = 0
            for user_doc in recent_users:
                try:
                    user_id = user_doc["user_id"]
                    # Try to get user info (lightweight check)
                    await self.bot.get_users(user_id)
                    live_count += 1
                except (UserIsBlocked, PeerIdInvalid, UserDeactivated):
                    # Mark user as blocked if we can't reach them
                    await self.mark_user_blocked(user_id)
                except Exception:
                    # Other errors, skip this user
                    continue
                
                # Add small delay to avoid rate limiting
                await asyncio.sleep(0.1)
            
            # Estimate total live users based on sample
            total_users = await self.users_collection.count_documents({
                "is_blocked": {"$ne": True}
            })
            
            if len(recent_users) > 0:
                live_ratio = live_count / len(recent_users)
                estimated_live = int(total_users * live_ratio)
            else:
                estimated_live = 0
            
            return estimated_live
            
        except Exception as e:
            logger.error(f"Error getting live users count: {e}")
            return 0
    
    async def update_daily_analytics(self, metric: str, increment: int = 1):
        """Update daily analytics"""
        try:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            await self.analytics_collection.update_one(
                {"date": today},
                {
                    "$inc": {metric: increment},
                    "$set": {"updated_at": datetime.utcnow()}
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating daily analytics: {e}")
    
    async def get_user_analytics(self) -> Dict:
        """Get comprehensive user analytics"""
        try:
            # Get all stats
            new_users = await self.get_new_users_stats()
            active_users = await self.get_active_users_count()
            blocked_users = await self.get_blocked_users_count()
            
            # Total users
            total_users = await self.users_collection.count_documents({})
            
            # Get live users count (this might take time)
            live_users = await self.get_live_users_count()
            
            return {
                "total_users": total_users,
                "new_users_today": new_users["today"],
                "new_users_week": new_users["week"],
                "new_users_month": new_users["month"],
                "active_users": active_users,
                "blocked_users": blocked_users,
                "live_users": live_users,
                "inactive_users": total_users - active_users - blocked_users
            }
            
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {}
    
    async def get_detailed_analytics(self) -> Dict:
        """Get detailed analytics including hourly/daily breakdowns"""
        try:
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday = today - timedelta(days=1)
            
            # Basic stats
            basic_stats = await self.get_user_analytics()
            
            # Hourly new users today
            hourly_pipeline = [
                {
                    "$match": {
                        "first_seen": {
                            "$gte": today,
                            "$lt": today + timedelta(days=1)
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {"$hour": "$first_seen"},
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"_id": 1}}
            ]
            
            hourly_data = await self.users_collection.aggregate(hourly_pipeline).to_list(length=24)
            hourly_users = {item["_id"]: item["count"] for item in hourly_data}
            
            # Yesterday vs today comparison
            yesterday_count = await self.users_collection.count_documents({
                "first_seen": {
                    "$gte": yesterday,
                    "$lt": today
                }
            })
            
            # Top user sources
            source_pipeline = [
                {
                    "$group": {
                        "_id": "$source",
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            
            source_data = await self.users_collection.aggregate(source_pipeline).to_list(length=5)
            
            # Most active users (top 5)
            active_pipeline = [
                {
                    "$match": {
                        "is_blocked": {"$ne": True}
                    }
                },
                {"$sort": {"total_interactions": -1}},
                {"$limit": 5}
            ]
            
            active_users = await self.users_collection.aggregate(active_pipeline).to_list(length=5)
            
            return {
                **basic_stats,
                "yesterday_new_users": yesterday_count,
                "hourly_new_users": hourly_users,
                "top_sources": source_data,
                "most_active_users": active_users
            }
            
        except Exception as e:
            logger.error(f"Error getting detailed analytics: {e}")
            return await self.get_user_analytics()  # Fallback to basic stats
    
    def format_detailed_analytics_message(self, stats: Dict) -> str:
        """Format detailed analytics data into a readable message"""
        if not stats:
            return "❌ Unable to fetch detailed analytics data"
        
        # Basic info
        message = f"""
📊 **DETAILED USER ANALYTICS**

👥 **Total Users:** {stats.get('total_users', 0):,}

🆕 **New Users:**
   • Today: {stats.get('new_users_today', 0):,}
   • Yesterday: {stats.get('yesterday_new_users', 0):,}
   • Growth: {((stats.get('new_users_today', 0) - stats.get('yesterday_new_users', 1)) / max(stats.get('yesterday_new_users', 1), 1) * 100):+.1f}%
   • This Week: {stats.get('new_users_week', 0):,}
   • This Month: {stats.get('new_users_month', 0):,}

📈 **Activity Status:**
   • 🟢 Active: {stats.get('active_users', 0):,} ({(stats.get('active_users', 0) / max(stats.get('total_users', 1), 1) * 100):.1f}%)
   • 🚫 Blocked: {stats.get('blocked_users', 0):,} ({(stats.get('blocked_users', 0) / max(stats.get('total_users', 1), 1) * 100):.1f}%)
   • 📡 Live: {stats.get('live_users', 0):,} ({(stats.get('live_users', 0) / max(stats.get('total_users', 1), 1) * 100):.1f}%)
   • 😴 Inactive: {stats.get('inactive_users', 0):,}

🕐 **Today's Hourly Breakdown:**"""
        
        # Hourly breakdown
        hourly_data = stats.get('hourly_new_users', {})
        current_hour = datetime.utcnow().hour
        for hour in range(24):
            count = hourly_data.get(hour, 0)
            if hour == current_hour:
                message += f"\n   • {hour:02d}:00 - {count} users ⬅️"
            else:
                message += f"\n   • {hour:02d}:00 - {count} users"
        
        # Top sources
        top_sources = stats.get('top_sources', [])
        if top_sources:
            message += f"\n\n🎯 **Top User Sources:**"
            for source in top_sources:
                source_name = source['_id'] or 'Unknown'
                message += f"\n   • {source_name.title()}: {source['count']:,} users"
        
        # Most active users
        active_users = stats.get('most_active_users', [])
        if active_users:
            message += f"\n\n👑 **Most Active Users:**"
            for i, user in enumerate(active_users, 1):
                name = user.get('first_name', 'Unknown')[:20]
                interactions = user.get('total_interactions', 0)
                message += f"\n   {i}. {name}: {interactions:,} interactions"
        
        message += f"\n\n⏰ **Last Updated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
    def format_analytics_message(self, stats: Dict) -> str:
        """Format analytics data into a readable message"""
        if not stats:
            return "❌ Unable to fetch analytics data"
        
        message = f"""
📊 **USER ANALYTICS**

👥 **Total Users:** {stats.get('total_users', 0):,}

🆕 **New Users:**
   • Today: {stats.get('new_users_today', 0):,}
   • This Week: {stats.get('new_users_week', 0):,}
   • This Month: {stats.get('new_users_month', 0):,}

🟢 **Active Users:** {stats.get('active_users', 0):,}
🚫 **Blocked Users:** {stats.get('blocked_users', 0):,}
📡 **Live Users:** {stats.get('live_users', 0):,}
😴 **Inactive Users:** {stats.get('inactive_users', 0):,}

📈 **User Distribution:**
   • Active: {(stats.get('active_users', 0) / max(stats.get('total_users', 1), 1) * 100):.1f}%
   • Blocked: {(stats.get('blocked_users', 0) / max(stats.get('total_users', 1), 1) * 100):.1f}%
   • Live: {(stats.get('live_users', 0) / max(stats.get('total_users', 1), 1) * 100):.1f}%

⏰ **Updated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
        """
        
        return message.strip()

# Handler functions for integration with existing bot
class AnalyticsHandlers:
    def __init__(self, analytics: UserAnalytics, admin_ids: List[int]):
        self.analytics = analytics
        self.admin_ids = admin_ids
    
    def register_handlers(self, app: Client):
        """Register all analytics handlers"""
        
        @app.on_message(filters.command("analytics", "status") & filters.private)
        async def analytics_command(client: Client, message: Message):
            """Handle /analytics command"""
            if message.from_user.id not in self.admin_ids:
                await message.reply("❌ You are not authorized to use this command.")
                return
            
            # Send loading message
            loading_msg = await message.reply("📊 Fetching analytics data...")
            
            try:
                # Get analytics data
                stats = await self.analytics.get_user_analytics()
                
                # Format and send analytics
                analytics_text = self.analytics.format_analytics_message(stats)
                
                # Create refresh button
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_analytics")],
                    [InlineKeyboardButton("📈 Detailed Stats", callback_data="detailed_analytics")]
                ])
                
                await loading_msg.edit_text(analytics_text, reply_markup=keyboard)
                
            except Exception as e:
                logger.error(f"Error in analytics command: {e}")
                await loading_msg.edit_text("❌ Error fetching analytics data.")
        
        @app.on_callback_query(filters.regex("^refresh_analytics$"))
        async def refresh_analytics_callback(client: Client, callback_query: CallbackQuery):
            """Handle refresh analytics callback"""
            if callback_query.from_user.id not in self.admin_ids:
                await callback_query.answer("❌ Not authorized!", show_alert=True)
                return
            
            await callback_query.answer("🔄 Refreshing analytics...")
            
            try:
                # Get fresh analytics data
                stats = await self.analytics.get_user_analytics()
                analytics_text = self.analytics.format_analytics_message(stats)
                
                # Create refresh button
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_analytics")],
                    [InlineKeyboardButton("📈 Detailed Stats", callback_data="detailed_analytics")]
                ])
                
                await callback_query.edit_message_text(analytics_text, reply_markup=keyboard)
                
            except Exception as e:
                logger.error(f"Error refreshing analytics: {e}")
                await callback_query.edit_message_text("❌ Error refreshing analytics data.")
        
        @app.on_callback_query(filters.regex("^detailed_analytics$"))
        async def detailed_analytics_callback(client: Client, callback_query: CallbackQuery):
            """Handle detailed analytics callback"""
            if callback_query.from_user.id not in self.admin_ids:
                await callback_query.answer("❌ Not authorized!", show_alert=True)
                return
            
            await callback_query.answer("📊 Loading detailed stats...")
            
            try:
                # Get detailed analytics
                stats = await self.analytics.get_detailed_analytics()
                detailed_text = self.analytics.format_detailed_analytics_message(stats)
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="refresh_analytics")]
                ])
                
                await callback_query.edit_message_text(detailed_text, reply_markup=keyboard)
                
            except Exception as e:
                logger.error(f"Error getting detailed analytics: {e}")
                await callback_query.edit_message_text("❌ Error fetching detailed analytics.")
        
        @app.on_message(filters.command("start"))
        async def start_handler(client: Client, message: Message):
            """Track users on start command - this will be called from your existing start handler"""
            try:
                await self.analytics.add_user(message.from_user, "start_command")
            except Exception as e:
                logger.error(f"Error tracking start command: {e}")
        
        # Note: Don't override existing private message handler, just call update_user_activity from existing handlers

# Global analytics instance
analytics_instance = None

async def track_user_activity(user_id: int):
    """Helper function to track user activity from anywhere in the bot"""
    global analytics_instance
    if analytics_instance:
        try:
            await analytics_instance.update_user_activity(user_id)
        except Exception as e:
            logger.error(f"Error tracking user activity: {e}")

async def track_new_user(user: User, source: str = "unknown"):
    """Helper function to track new users from anywhere in the bot"""
    global analytics_instance
    if analytics_instance:
        try:
            await analytics_instance.add_user(user, source)
        except Exception as e:
            logger.error(f"Error tracking new user: {e}")

async def mark_user_blocked(user_id: int):
    """Helper function to mark user as blocked from anywhere in the bot"""
    global analytics_instance
    if analytics_instance:
        try:
            await analytics_instance.mark_user_blocked(user_id)
        except Exception as e:
            logger.error(f"Error marking user as blocked: {e}")

# Integration function for your main bot
async def initialize_analytics(bot: Client):
    """Initialize analytics module for integration with existing bot"""
    global analytics_instance
    try:
        # Create analytics instance
        analytics_instance = UserAnalytics(bot)
        
        # Initialize database
        await analytics_instance.init_database()
        
        # Create handlers
        handlers = AnalyticsHandlers(analytics_instance, ADMINS)
        
        # Register handlers
        handlers.register_handlers(bot)
        
        logger.info("✅ User Analytics Module Initialized Successfully")
        return analytics_instance
        
    except Exception as e:
        logger.error(f"❌ Error Initializing Analytics: {e}")
        return None

# Example integration in main bot file:
"""
from user_analytics import initialize_analytics

# In your main bot initialization:
async def main():
    bot = Client("autofilter_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    
    # Initialize analytics
    admin_ids = [123456789, 987654321]  # Your admin IDs
    analytics = await initialize_analytics(bot, DATABASE_URI, admin_ids)
    
    # Start the bot
    await bot.start()
    print("Bot started with analytics!")
    
    # Keep the bot running
    await asyncio.sleep(float('inf'))

if __name__ == "__main__":
    asyncio.run(main())
"""
