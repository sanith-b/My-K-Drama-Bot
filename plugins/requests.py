# plugins/requests.py
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
import os

# === MongoDB setup ===
MONGO_URI = os.getenv(""mongodb+srv://kdramabot:Buo0fRGenkOAkgXH@pastppr.ipuyepp.mongodb.net/?retryWrites=true&w=majority&appName=pastppr")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["pastppr"]
requests_col = db["requests"]

# === Admin IDs ===
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "1204352805").split(",") if x]

# === User: Submit request ===
@Client.on_message(filters.private & filters.command("request"))
async def request_start(client, message):
    await message.reply_text(
        "📌 Please send me the drama name you want to request."
    )
    # Next message will be handled below


@Client.on_message(filters.private & ~filters.command(["request", "pending"]))
async def save_request(client, message):
    if not message.text:
        return
    drama_name = message.text.strip()

    req_data = {
        "user_id": message.from_user.id,
        "username": message.from_user.username or "",
        "drama_name": drama_name,
        "status": "pending",
        "notes": [],
    }
    await requests_col.insert_one(req_data)

    await message.reply_text(
        f"✅ Your request for **{drama_name}** has been submitted!"
    )


# === Admin: View pending requests with inline pagination ===
@Client.on_message(filters.command("pending") & filters.user(ADMIN_IDS))
async def pending_requests(client, message):
    req = await requests_col.find_one({"status": "pending"})
    if not req:
        return await message.reply_text("🎉 No pending requests right now.")
    await send_request_card(client, message.chat.id, req, 0)


async def send_request_card(client, chat_id, req, index):
    total = await requests_col.count_documents({"status": "pending"})
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{req['_id']}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject:{req['_id']}"),
            ],
            [
                InlineKeyboardButton("📌 Complete", callback_data=f"complete:{req['_id']}"),
                InlineKeyboardButton("📝 Add Note", callback_data=f"note:{req['_id']}"),
            ],
            [
                InlineKeyboardButton("⬅️ Prev", callback_data=f"prev:{index}"),
                InlineKeyboardButton("➡️ Next", callback_data=f"next:{index}"),
            ]
        ]
    )

    text = (
        f"🎬 **Request:** {req['drama_name']}\n"
        f"👤 User: {req.get('username','')} ({req['user_id']})\n"
        f"📌 Status: {req['status']}\n"
        f"📝 Notes: {', '.join(req.get('notes', [])) or 'None'}\n\n"
        f"({index+1}/{total})"
    )

    await client.send_message(chat_id, text, reply_markup=keyboard)


# === Handle Inline Buttons ===
@Client.on_callback_query()
async def callback_handler(client, query):
    data = query.data.split(":")
    action = data[0]

    if action in ["approve", "reject", "complete"]:
        req_id = data[1]
        new_status = {"approve": "approved", "reject": "rejected", "complete": "completed"}[action]
        await requests_col.update_one({"_id": {"$eq": req_id}}, {"$set": {"status": new_status}})
        await query.answer(f"Marked as {new_status}")
        await query.message.edit_text(f"✅ Request updated: {new_status}")

    elif action == "note":
        await query.answer("Send me the note text in chat.", show_alert=True)
        # Next message from admin will be saved as a note for this request
        client.add_handler(
            filters.private & filters.user(ADMIN_IDS),
            note_handler(req_id=data[1], message_id=query.message.id),
            group=1
        )

    elif action in ["prev", "next"]:
        index = int(data[1])
        total = await requests_col.count_documents({"status": "pending"})
        if total == 0:
            return await query.answer("No more requests.")
        if action == "prev":
            index = (index - 1) % total
        else:
            index = (index + 1) % total
        req = await requests_col.find({"status": "pending"}).skip(index).to_list(1)
        if req:
            await query.message.delete()
            await send_request_card(client, query.message.chat.id, req[0], index)


# === Dynamic Note Handler Factory ===
def note_handler(req_id, message_id):
    async def _handler(client, message):
        note_text = message.text.strip()
        await requests_col.update_one(
            {"_id": {"$eq": req_id}},
            {"$push": {"notes": note_text}}
        )
        await message.reply_text(f"📝 Note added to request: {note_text}")
        client.remove_handler(_handler, group=1)
    return _handler
