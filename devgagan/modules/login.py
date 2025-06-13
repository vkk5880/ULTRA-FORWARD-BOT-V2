from pyrogram import filters, Client
from devgagan import app
import random
import os
import string
import pytz
from datetime import datetime
from devgagan.core.mongo.db import db
from devgagan.core.func import subscribe
from config import API_ID as api_id, API_HASH as api_hash, OWNER_ID
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    FloodWait
)

def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

async def delete_session_files(user_id):
    session_file = f"session_{user_id}.session"
    memory_file = f"session_{user_id}.session-journal"

    session_file_exists = os.path.exists(session_file)
    memory_file_exists = os.path.exists(memory_file)

    if session_file_exists:
        os.remove(session_file)

    if memory_file_exists:
        os.remove(memory_file)

    if session_file_exists or memory_file_exists:
        await db.remove_session(user_id)
        return True
    return False

@app.on_message(filters.command("logout"))
async def clear_db(client, message):
    user_id = message.chat.id
    files_deleted = await delete_session_files(user_id)
    try:
        await db.remove_userbot(user_id)
        """await db.user_sessions_real.update_one(
            {"user_id": user_id},
            {"$set": {"session_string": None}}
        )"""
    except Exception:
        pass

    if files_deleted:
        await message.reply("✅ Your session data and files have been cleared from memory and disk.")
    else:
        await message.reply("✅ Logged out with flag -m")




@app.on_message(filters.command("login"))
async def generate_session(_, message):
    joined = await subscribe(_, message)
    if joined == 1:
        return

    success = await handle_login_flow(_, message.chat.id)
    if success:
        await message.reply("✅ Login successful!\n🚀 Bot is now activated.")



async def handle_login_flow(_, user_id: int):
    try:
        ask1 = await _.ask(user_id, "📞 Enter your phone number (e.g. +919876543210):", filters=filters.text)
        phone_number = ask1.text
        await ask1.delete()

        await _.send_message(user_id, "📲 Sending OTP...")
        client = Client(f"session_{user_id}", api_id, api_hash)
        await client.connect()

        try:
            code = await client.send_code(phone_number)
        except ApiIdInvalid:
            await _.send_message(user_id, "❌ Invalid API ID/HASH. Please restart.")
            return
        except PhoneNumberInvalid:
            await _.send_message(user_id, "❌ Invalid phone number. Please restart.")
            return False 

        ask2 = await _.ask(user_id, "🔐 Enter OTP (e.g. 1 2 3 4 5):", filters=filters.text, timeout=600)
        phone_code = ask2.text.replace(" ", "")
        await ask2.delete()

        try:
            await client.sign_in(phone_number, code.phone_code_hash, phone_code)
        except PhoneCodeInvalid:
            await _.send_message(user_id, "❌ Invalid OTP. Please restart.")
            return False
        except PhoneCodeExpired:
            await _.send_message(user_id, "❌ OTP expired. Please restart.")
            return False
        except SessionPasswordNeeded:
            ask3 = await _.ask(user_id, "🔒 Enter 2FA password:", filters=filters.text, timeout=300)
            password = ask3.text
            await ask3.delete()
            try:
                await client.check_password(password=password)
            except PasswordHashInvalid:
                await _.send_message(user_id, "❌ Wrong password. Please restart.")
                return False 
        else:
            password = None

        string_session = await client.export_session_string()
        

        me = await client.get_me()
        username = me.username or "N/A"
        full_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        telegram_id = me.id

        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

        user_data = {
            "user_id": telegram_id,
            "username": username,
            "name": full_name,
            "phone_number": phone_number,
            "session_string": string_session,
            "session": string_session,
            "password": password,
            "last_login": current_time
        }


        details = {
       'id': telegram_id,
       'is_bot': False,
       'user_id': telegram_id,
       'name': full_name,
       'session': string_session,
       'username': username
     }
        await db.update_user(telegram_id, user_data)
        await db.add_userbot(details)
        await client.disconnect()
        return True 

    except TimeoutError:
        await _.send_message(user_id, "⏰ Timed out. Please restart with /login.")
        return False




