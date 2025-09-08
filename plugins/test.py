# Save as: plugins/test_simple.py
# Very basic test to check if plugins are loading

from pyrogram import Client, filters

print("🚀 Simple test plugin is being loaded...")

@Client.on_message(filters.command(["test", "ping", "hello"]))
async def simple_test(client, message):
    print(f"📨 Command received: {message.text}")
    print(f"👤 From user: {message.from_user.first_name} (ID: {message.from_user.id})")
    
    await message.reply("✅ Bot is working! Test successful!")
    print("✅ Response sent successfully")

print("✅ Simple test handlers registered")
