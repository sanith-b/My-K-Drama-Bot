# request.py
import os
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# ----------------------
# CONFIG
# ----------------------


DATABASE_URI = os.environ["DATABASE_URI"]
DB_NAME = "kdrama"
REQ_COLLECTION = "requests"
ADMIN_IDS = [123456789]  # Replace with your admin user IDs

mongo_client = AsyncIOMotorClient(DATABASE_URI)
db = mongo_client[DB_NAME]
req_col = db[REQ_COLLECTION]

# ----------------------
# HELPERS
# ----------------------
def format_user_request(request):
    status_emoji = {"approved": "✅", "rejected": "❌", "pending": "📋"}
    return f"{status_emoji.get(request['status'], '📋')} {request['req_id']} - {request['status'].capitalize()}\n   🎬 {request['drama_name']}\n   📅 {request['date']}"

def user_inline_keyboard(requests):
    buttons = []
    for req in requests:
        buttons.append([
            InlineKeyboardButton(req['drama_name'], callback_data=f"view_{req['req_id']}")
        ])
    return InlineKeyboardMarkup(buttons) if buttons else None

def admin_inline_keyboard(requests):
    buttons = []
    for req in requests:
        buttons.append([
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{req['req_id']}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{req['req_id']}"),
            InlineKeyboardButton("↩️ Revert", callback_data=f"revert_{req['req_id']}")
        ])
    return InlineKeyboardMarkup(buttons) if buttons else None

# ----------------------
# COMMANDS
# ----------------------
@Client.on_message(filters.command("myrequests") & filters.private)
async def my_requests(client, message):
    user_id = message.from_user.id
    requests = await req_col.find({"user_id": user_id}).to_list(length=100)
    if not requests:
        await message.reply_text("You have no K-Drama requests yet.")
        return
    text = "📋 **Your K-Drama Requests**\n\n"
    text += "\n\n".join([format_user_request(r) for r in requests])
    await message.reply_text(text, reply_markup=user_inline_keyboard(requests))

@Client.on_message(filters.command("adminpanel") & filters.user(ADMIN_IDS))
async def admin_panel(client, message):
    requests = await req_col.find({}).to_list(length=100)
    total = len(requests)
    approved = len([r for r in requests if r['status'] == "approved"])
    rejected = len([r for r in requests if r['status'] == "rejected"])
    pending = len([r for r in requests if r['status'] == "pending"])
    admin_count = len(ADMIN_IDS)
    
    text = (
        "🛠️ **K-DRAMA ADMIN PANEL**\n\n"
        "📊 Statistics:\n"
        f"📋 Pending: {pending}\n"
        f"✅ Approved: {approved}\n"
        f"❌ Rejected: {rejected}\n"
        f"📈 Total: {total}\n"
        f"👥 Admins: {admin_count}"
    )
    await message.reply_text(text, reply_markup=admin_inline_keyboard(requests))

# ----------------------
# CALLBACK QUERIES
# ----------------------
@Client.on_callback_query()
async def handle_callback(client, callback: CallbackQuery):
    data = callback.data
    if data.startswith("approve_") or data.startswith("reject_") or data.startswith("revert_"):
        req_id = data.split("_")[1]
        action = data.split("_")[0]
        new_status = {"approve": "approved", "reject": "rejected", "revert": "pending"}[action]
        await req_col.update_one({"req_id": req_id}, {"$set": {"status": new_status}})
        await callback.answer(f"Request {req_id} set to {new_status.capitalize()}")
        # Update admin panel
        requests = await req_col.find({}).to_list(length=100)
        total = len(requests)
        approved = len([r for r in requests if r['status'] == "approved"])
        rejected = len([r for r in requests if r['status'] == "rejected"])
        pending = len([r for r in requests if r['status'] == "pending"])
        admin_count = len(ADMIN_IDS)
        text = (
            "🛠️ **K-DRAMA ADMIN PANEL**\n\n"
            "📊 Statistics:\n"
            f"📋 Pending: {pending}\n"
            f"✅ Approved: {approved}\n"
            f"❌ Rejected: {rejected}\n"
            f"📈 Total: {total}\n"
            f"👥 Admins: {admin_count}"
        )
        await callback.message.edit_text(text, reply_markup=admin_inline_keyboard(requests))

# ----------------------
# NEW REQUEST
# ----------------------
@Client.on_message(filters.command("request") & filters.private)
async def new_request(client, message):
    user_id = message.from_user.id
    if len(message.command) < 2:
        await message.reply_text("Usage: /request <Drama Name>")
        return
    drama_name = " ".join(message.command[1:])
    req_id = f"REQ_{int(datetime.utcnow().timestamp())}"  # simple unique ID
    request_doc = {
        "req_id": req_id,
        "user_id": user_id,
        "drama_name": drama_name,
        "status": "pending",
        "date": datetime.utcnow().strftime("%Y-%m-%d")
    }
    await req_col.insert_one(request_doc)
    await message.reply_text(f"Your request for **{drama_name}** has been submitted!\nID: {req_id}")

# ----------------------
# RUN BOT
# ----------------------
if __name__ == "__main__":
    print("Bot is running...")
    BOT.run()
