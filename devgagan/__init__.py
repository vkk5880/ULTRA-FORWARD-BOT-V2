import asyncio
import logging
from pyrogram import Client
from pyrogram.enums import ParseMode 
from config import API_ID, API_HASH, BOT_TOKEN, STRING, MONGO_DB
from motor.motor_asyncio import AsyncIOMotorClient
from devgagan.core.mongo.db import db
import time
import sys
import os

SESSION_DIR = "data/sessions"
os.makedirs(SESSION_DIR, exist_ok=True) # Create the directory if it doesn't exist

pyrogram_session_path = os.path.join(SESSION_DIR, "my_pyrogram_bot")

loop = asyncio.get_event_loop()

logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s',  
    level=logging.INFO, # Set the minimum logging level to capture (e.g., logging.INFO, logging.DEBUG)
    stream=sys.stdout # Direct log output to standard output
)

botStartTime = time.time()
#name=pyrogram_session_path,
app = Client(
    "VkkAutoForwardBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.MARKDOWN
)



# Run the TTL index creation when the bot starts
async def setup_database():
 await db.create_ttl_index()
 print("MongoDB TTL index created.")
 
 

async def restrict_bot():
    global BOT_ID, BOT_NAME, BOT_USERNAME
    await setup_database()
    await app.start()
    
    getme = await app.get_me()
    BOT_ID = getme.id
    BOT_USERNAME = getme.username
    if getme.last_name:
        BOT_NAME = getme.first_name + " " + getme.last_name
    else:
        BOT_NAME = getme.first_name

loop.run_until_complete(restrict_bot())
