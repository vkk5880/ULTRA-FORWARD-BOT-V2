 from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import random
import requests
import string
import aiohttp
from devgagan import app
from devgagan.core.func import *
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB, WEBSITE_URL, AD_API, CONTACT, LOG_GROUP  
from config import MONGO_DB as MONGODB_CONNECTION_STRING, LOG_GROUP, OWNER_ID, STRING, API_ID, CONTACT, API_HASH, CHANNEL_LINK
from pyrogram.types import Message 
from config import LOG_GROUP
import re
from devgagan.core.mongo import db
import logging
from pyrogram.enums import ParseMode
import sys # Import sys for standard output
from pyrogram import filters, Client
from telethon import TelegramClient
import pymongo
from devgagan.core.mongo import db
from devgagan.core.mongo.db import user_sessions_real
 
tclient = AsyncIOMotorClient(MONGO_DB)
tdb = tclient["telegram_bot"]
token = tdb["tokens"]
 
 
async def create_ttl_index():
    await token.create_index("expires_at", expireAfterSeconds=0)
 
 
 
Param = {}
 
 
async def generate_random_param(length=8):
    """Generate a random parameter."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
 
 
async def get_shortened_url(deep_link):
    api_url = f"https://{WEBSITE_URL}/api?api={AD_API}&url={deep_link}"
 
     
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as response:
            if response.status == 200:
                data = await response.json()   
                if data.get("status") == "success":
                    return data.get("shortenedUrl")
    return None
 
 
async def is_user_verified(user_id):
    """Check if a user has an active session."""
    session = await token.find_one({"user_id": user_id})
    return session is not None



 

bot_client_pyro = None


async def get_pyro_bot(user_id=None):
    global bot_client_pyro
    if bot_client_pyro is None and user_id:
        bot_client_pyro = await create_bot_client_pyro(user_id)
    return bot_client_pyro



async def create_bot_client_pyro(user_id):
    """Safely create and start a bot client with proper error handling"""
    global bot_client_pyro
    sessions = await db.get_sessions(user_id)
    if not sessions or not sessions.get("userbot_token"):
        logger.warning(f"No userbot_token found for user {user_id}")
        return None
    bot_tokens = sessions.get("userbot_token")
    bot_client_pyro = Client(
        name="f:User_RestrictBot_{user_id}:",  # Session name
        api_id=API_ID,         # Your API ID from my.telegram.org
        api_hash=API_HASH,     # Your API Hash
        bot_token=bot_tokens,   # The bot token from user
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        await bot_client_pyro.start()
        logger.info(f"Bot client started successfully for token: {bot_tokens[:10]}...")
        return bot_client_pyro
    except Exception as e:
        logger.error(f"Failed to start bot client: {e}")
        await bot_client_pyro.stop()
        raise RuntimeError(f"Could not start bot client: {str(e)}")





async def save_userbot_token(user_id, token_string):
    """Save user bot token to database"""
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
    
    update_data = {
        "userbot_token": token_string
    }
    
    await db.user_sessions_real.update_one(
        {"user_id": user_id},
        {"$set": update_data},
        upsert=True
    )



# Save to database
#await db.save_userbot_token(user_id, token)
#save_userbot_token(user_id, token)

@app.on_message(filters.command("setbot"))
async def setbot_handler(bot: Client, message: Message):
    user_id = message.chat.id
    await handle_bot_token_input(bot, user_id, message)




async def handle_bot_token_input(bot: Client, user_id: int, message_or_query: Message | CallbackQuery):
    instructions = """
🤖 *How to create a bot and get its token:*

1. Search for @BotFather in Telegram.
2. Send `/newbot` and follow the steps.
3. You'll receive a token like:
`123456789:ABCdefGhIJKlmNoPQRstuVWXyz1234567890`

📌 *Send me your bot token now (or forward the BotFather message).*
Send /cancel to stop.
    """
    await bot.send_message(user_id, instructions, parse_mode=ParseMode.MARKDOWN)

    try:
        token_msg = await bot.ask(
            user_id,
            "⌛ Waiting for your bot token...",
            filters=filters.text,
            timeout=300
        )
    except TimeoutError:
        await bot.send_message(user_id, "⌛ Timeout. Please try again.")
        return False

    if token_msg.text.strip().lower() == "/cancel":
        await token_msg.reply("❌ Process cancelled.")
        return False

    # Extract token
    token_match = re.findall(r'\d{8,10}:[0-9A-Za-z_-]{35}', token_msg.text)
    token = token_match[0] if token_match else None

    if not token:
        await token_msg.reply("❌ Invalid bot token.")
        return False

    try:
        bot_client = Client(name=f"userbot_{user_id}", bot_token=token)
        await bot_client.start()
        bot_info = await bot_client.get_me()
    except Exception as e:
        await token_msg.reply(f"❌ Failed to start bot:\n`{e}`", parse_mode="markdown")
        return False

    details = {
        'id': bot_info.id,
        'is_bot': True,
        'user_id': user_id,
        'name': bot_info.first_name,
        'username': bot_info.username,
        'token': token
    }
    await db.add_bot(details)
    await db.save_userbot_token(user_id, token)
    await token_msg.reply(
        f"✅ Bot @{bot_info.username} connected successfully!\n"
        f"Now start it to begin receiving updates.",
        parse_mode="markdown"
    )
    await bot_client.stop()
    return True



@app.on_message(filters.command("starts"))
async def token_handler(client, message):
    """Handle the /token command."""
    join = await subscribe(client, message)
    if join == 1:
        return
    chat_id = "still_waiting_for_uh"
    msg = await app.get_messages(chat_id,5)
    user_id = message.chat.id
    if len(message.command) <= 1:
        image_url = "https://tecolotito.elsiglocoahuila.mx/i/2023/12/2131463.jpeg"
        join_button = InlineKeyboardButton("Join Channel", url="https://t.me/+9FZJh0WMZnE4YWRk")
        premium = InlineKeyboardButton("Get Premium", url=CONTACT)   
        keyboard = InlineKeyboardMarkup([
            [join_button],   
            [premium]    
        ])
         
        await message.reply_photo(
            msg.photo.file_id,
            caption=(
                "Hi 👋 Welcome, Wanna intro...?\n\n"
                "✳️ I can save posts from channels or groups where forwarding is off. I can download videos/audio from YT, INSTA, ... social platforms\n"
                "✳️ Simply send the post link of a public channel. For private channels, do /login. Send /help to know more."
            ),
            reply_markup=keyboard
        )
        return  
 
    param = message.command[1] if len(message.command) > 1 else None
    freecheck = await chk_user(message, user_id)
    if freecheck != 1:
        await message.reply("You are a premium user no need of token 😉")
        return
 
     
    if param:
        if user_id in Param and Param[user_id] == param:
             
            await token.insert_one({
                "user_id": user_id,
                "param": param,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=3),
            })
            del Param[user_id]   
            await message.reply("✅ You have been verified successfully! Enjoy your session for next 3 hours.")
            return
        else:
            await message.reply("❌ Invalid or expired verification link. Please generate a new token.")
            return
 
@app.on_message(filters.command("token"))
async def smart_handler(client, message):
    user_id = message.chat.id
     
    freecheck = await chk_user(message, user_id)
    if freecheck != 1:
        await message.reply("You are a premium user no need of token 😉")
        return
    if await is_user_verified(user_id):
        await message.reply("✅ Your free session is already active enjoy!")
    else:
         
        param = await generate_random_param()
        Param[user_id] = param   
 
         
        deep_link = f"https://t.me/{client.me.username}?start={param}"
 
         
        shortened_url = await get_shortened_url(deep_link)
        if not shortened_url:
            await message.reply("❌ Failed to generate the token link. Please try again.")
            return
 
         
        button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Verify the token now...", url=shortened_url)]]
        )
        await message.reply("Click the button below to verify your free access token: \n\n> What will you get ? \n1. No time bound upto 3 hours \n2. Batch command limit will be FreeLimit + 20 \n3. All functions unlocked", reply_markup=button)

# ✅ Function to show Admin Commands List
@app.on_message(filters.command("admin_commands_list"))
async def show_admin_commands(client, message):
    """Displays the list of available admin commands (Owner only)."""
    owner_id=5914434064
    if message.from_user.id != owner_id:
        await message.reply("🚫 You are not the owner and cannot access this command!")
        return
    
    admin_commands = """
    👤Owner Commands List:-
    
/add userID            - ➕ Add user to premium  
/rem userID            - ➖ Remove user from premium  
/stats                 - 📊 Get bot stats  
/gcast                 - ⚡ Broadcast to all users  
/acast                 - ⚡ Broadcast with name tag  
/freez                 - 🧊 Remove expired users  
/get                   - 🗄️ Get all user IDs  
/lock                  - 🔒 Protect channel  
/hijack                - ☠️ Hijack a session
/cancel_hijack         - 🚫 Terminate Hijacking 
/session               - 🪪 Generate session string  
/connect_user          - 🔗 Connect owner & user  
/disconnect_user       - ⛔ Disconnect a user  
/admin_commands_list   - 📄 Show admin commands
    """
    await message.reply(admin_commands)

#onwer bot command list till here
#register_handlers(app)
