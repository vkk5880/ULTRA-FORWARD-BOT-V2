import asyncio
import logging
import traceback
from pyrogram import filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from pyrogram.types import Message
from config import OWNER_ID
from devgagan import app
from devgagan.core.mongo.users_db import get_users

logging.basicConfig(level=logging.INFO)

# Send and pin message
async def send_msg(user_id: int, message: Message):
    try:
        x = await message.copy(chat_id=user_id)
        try:
            await x.pin()
        except Exception:
            await x.pin(both_sides=True)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await send_msg(user_id, message)
    except InputUserDeactivated:
        return 400, f"{user_id} : deactivated"
    except UserIsBlocked:
        return 400, f"{user_id} : blocked the bot"
    except PeerIdInvalid:
        return 400, f"{user_id} : user id invalid"
    except Exception:
        return 500, f"{user_id} : {traceback.format_exc()}"
    return 200, f"{user_id} : success"


# GCAST command
@app.on_message(filters.command("copycast") & filters.user(OWNER_ID))
async def broadcast(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Please reply to a message to broadcast it.")

    exmsg = await message.reply_text("📢 Broadcasting started...")
    all_users = await get_users() or []

    done_users, failed_users = 0, 0

    for user_id in all_users:
        status, _ = await send_msg(user_id, message.reply_to_message)
        if status == 200:
            done_users += 1
        else:
            failed_users += 1
        await asyncio.sleep(0.1)

    summary = (
        f"✅ **Broadcast finished**\n\n"
        f"📬 Message sent to: `{done_users}` users\n"
    )
    if failed_users:
        summary += f"⚠️ Failed to send to: `{failed_users}` users"

    await exmsg.edit_text(summary)


# ACAST command
@app.on_message(filters.command("fcast") & filters.user(OWNER_ID))
async def announce(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Please reply to a message to broadcast.")

    users = await get_users() or []
    to_send = message.reply_to_message.id
    from_chat = message.chat.id
    exmsg = await message.reply_text("📢 Announcement broadcast started...")

    done_users, failed_users = 0, 0

    for user_id in users:
        try:
            await _.forward_messages(chat_id=int(user_id), from_chat_id=from_chat, message_ids=to_send)
            done_users += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            failed_users += 1
            logging.warning(f"Failed to send to {user_id}: {e}")

    summary = (
        f"✅ **Announcement finished**\n\n"
        f"📬 Message sent to: `{done_users}` users\n"
    )
    if failed_users:
        summary += f"⚠️ Failed to send to: `{failed_users}` users"

    await exmsg.edit_text(summary)
