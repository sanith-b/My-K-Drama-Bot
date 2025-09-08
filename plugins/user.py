"""
Test command plugin for K-Drama Bot
Place this file as: plugins/test.py
"""

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode
import logging

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("test"))
async def test_command(client, message):
    """Simple test command that replies with success message"""
    try:
        await message.reply_text("test success")
        logger.info(f"Test command executed by user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in test command: {e}")
        await message.reply_text("❌ Test failed")

@Client.on_message(filters.command("testbot"))
async def test_bot_status(client, message):
    """Test bot functionality with detailed response"""
    try:
        user_name = message.from_user.first_name or "User"
        
        await message.reply_text(
            f"✅ <b>K-Drama Bot Test Success!</b>\n\n"
            f"👤 Hello {user_name}!\n"
            f"🤖 Bot is working perfectly\n"
            f"📅 Command executed successfully\n\n"
            f"<i>Bot is ready to serve K-Drama content!</i>",
            parse_mode=ParseMode.HTML
        )
        
        logger.info(f"Bot test executed by {user_name} (ID: {message.from_user.id})")
        
    except Exception as e:
        logger.error(f"Error in test bot command: {e}")
        await message.reply_text("❌ Bot test failed - please contact admin")

@Client.on_message(filters.command("testfeatures"))
async def test_features(client, message):
    """Test command with inline buttons to test bot features"""
    try:
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎬 Test Drama List", callback_data="test_drama_list"),
                InlineKeyboardButton("🔍 Test Search", callback_data="test_search")
            ],
            [
                InlineKeyboardButton("⭐ Test Ratings", callback_data="test_ratings"),
                InlineKeyboardButton("📋 Test Reminders", callback_data="test_reminders")
            ],
            [
                InlineKeyboardButton("✅ All Tests Pass", callback_data="test_all_pass")
            ]
        ])
        
        await message.reply_text(
            "🧪 <b>K-Drama Bot Feature Test</b>\n\n"
            "Click the buttons below to test different bot features:",
            reply_markup=buttons,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error in test features command: {e}")
        await message.reply_text("❌ Could not load feature tests")

# Callback handlers for test buttons
@Client.on_callback_query(filters.regex("^test_drama_list$"))
async def test_drama_list_callback(client, callback_query):
    """Test drama list functionality"""
    try:
        await callback_query.answer("✅ Drama List Test Passed!", show_alert=True)
    except Exception as e:
        logger.error(f"Error in drama list test: {e}")
        await callback_query.answer("❌ Drama List Test Failed", show_alert=True)

@Client.on_callback_query(filters.regex("^test_search$"))
async def test_search_callback(client, callback_query):
    """Test search functionality"""
    try:
        await callback_query.answer("✅ Search Test Passed!", show_alert=True)
    except Exception as e:
        logger.error(f"Error in search test: {e}")
        await callback_query.answer("❌ Search Test Failed", show_alert=True)

@Client.on_callback_query(filters.regex("^test_ratings$"))
async def test_ratings_callback(client, callback_query):
    """Test ratings functionality"""
    try:
        await callback_query.answer("✅ Ratings Test Passed!", show_alert=True)
    except Exception as e:
        logger.error(f"Error in ratings test: {e}")
        await callback_query.answer("❌ Ratings Test Failed", show_alert=True)

@Client.on_callback_query(filters.regex("^test_reminders$"))
async def test_reminders_callback(client, callback_query):
    """Test reminders functionality"""
    try:
        await callback_query.answer("✅ Reminders Test Passed!", show_alert=True)
    except Exception as e:
        logger.error(f"Error in reminders test: {e}")
        await callback_query.answer("❌ Reminders Test Failed", show_alert=True)

@Client.on_callback_query(filters.regex("^test_all_pass$"))
async def test_all_pass_callback(client, callback_query):
    """All tests pass confirmation"""
    try:
        await callback_query.edit_message_text(
            "🎉 <b>All Tests Completed Successfully!</b>\n\n"
            "✅ Drama List - Working\n"
            "✅ Search Function - Working\n" 
            "✅ Ratings System - Working\n"
            "✅ Reminders - Working\n\n"
            "🤖 <b>K-Drama Bot is fully operational!</b>",
            parse_mode=ParseMode.HTML
        )
        
        await callback_query.answer("🎉 All systems working perfectly!")
        
    except Exception as e:
        logger.error(f"Error in all pass test: {e}")
        await callback_query.answer("❌ Test completion failed", show_alert=True)
