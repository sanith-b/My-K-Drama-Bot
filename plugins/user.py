from pyrogram import Client, filters

@Client.on_message(filters.command("test"))
async def test_command(client, message):
    """Simple test command that replies with success message"""
    await message.reply_text("test success")

# Alternative with more detailed response
@Client.on_message(filters.command("test2"))
async def test_command_detailed(client, message):
    """Test command with more details"""
    await message.reply_text(
        "✅ <b>Test Success!</b>\n\n"
        f"👤 User: {message.from_user.first_name}\n"
        f"💬 Command executed successfully",
        parse_mode="HTML"
    )

# Test command with inline button
@Client.on_message(filters.command("testbutton"))
async def test_with_button(client, message):
    """Test command with inline button"""
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    button = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Test Passed", callback_data="test_success")]
    ])
    
    await message.reply_text(
        "🧪 Test command executed!",
        reply_markup=button
    )

# Callback handler for the button
@Client.on_callback_query(filters.regex("^test_success$"))
async def test_callback(client, callback_query):
    """Handle test button click"""
    await callback_query.answer("Test successful! ✅", show_alert=True)
