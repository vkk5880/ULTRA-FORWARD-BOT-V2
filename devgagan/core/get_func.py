# ---------------------------------------------------
# File Name: get_func.py
# Description: A Pyrogram bot for downloading files from Telegram channels or groups 
#              and uploading them back to Telegram.
# Author: Gagan
# GitHub: https://github.com/devgaganin/
# Telegram: https://t.me/team_spy_pro
# YouTube: https://youtube.com/@dev_gagan
# Created: 2025-01-11
# Last Modified: 2025-02-01
# Version: 2.0.5
# License: MIT License
# Improved logic handles
# ---------------------------------------------------
import os
import sys
import math
import time
import asyncio
import logging
import gc
import re
from typing import Callable
from telethon import TelegramClient, events, Button, types
from telethon.errors import (
    ChannelInvalidError, 
    ChannelPrivateError, 
    ChatIdInvalidError, 
    ChatInvalidError,
    FileMigrateError,
    AuthBytesInvalidError,
    FloodWaitError
)
from devgagan.core.fasthelper import fast_upload, fast_download, safe_turbo_download
from telethon import functions, types
from telethon.tl.types import DocumentAttributeVideo, Message
from telethon.sessions import StringSession
import pymongo
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid
from pyrogram.enums import MessageMediaType, ParseMode
from pyrogram.errors import RPCError
from pyrogram.types import Message
from config import MONGO_DB as MONGODB_CONNECTION_STRING, LOG_GROUP, OWNER_ID, STRING, API_ID, CONTACT, API_HASH
from devgagan.core.mongo.db import set_session, remove_session, get_data
from devgagantools import fast_upload as fast_uploads
#from devgagantools import fast_download
from devgagan.core.func import *
from devgagan.modules.shrink import is_user_verified, get_pyro_bot, get_tele_bot
from telethon import TelegramClient, events, Button
from devgagan import app
from devgagan import telethon_user_client  as gf
from telethon.tl.types import MessageMediaDocument
from pyrogram import filters, Client

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def thumbnail(sender):
    """Get thumbnail path for user if exists"""
    thumb_path = f'{sender}.jpg'
    return thumb_path if os.path.exists(thumb_path) else None

# MongoDB database name and collection name
DB_NAME = "smart_users"
COLLECTION_NAME = "super_user"

VIDEO_EXTENSIONS = ['mp4', 'mov', 'avi', 'mkv', 'flv', 'wmv', 'webm', 'mpg', 'mpeg', '3gp', 'ts', 'm4v', 'f4v', 'vob']
DOCUMENT_EXTENSIONS = ['pdf', 'docs']

mongo_app = pymongo.MongoClient(MONGODB_CONNECTION_STRING)
db = mongo_app[DB_NAME]
collection = db[COLLECTION_NAME]

if STRING:
    from devgagan import pro
    logger.info("App imported from package.")
else:
    pro = None
    logger.info("STRING is not available. 'app' is set to None.")




#from telethon import types
from telethon.errors import (
    ChannelInvalidError,
    ChannelPrivateError,
    ChatIdInvalidError,
    ChatInvalidError,
)

from typing import Union, AsyncGenerator
from pyrogram import types
from database import db
from .test import CLIENT, start_clone_bot
from config import Config, temp
from pyrogram.errors import FloodWait, MessageNotModified, RPCError
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

CLIENT = CLIENT()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TEXT = """<b><u>Forward Status</u></b>
  
<b>🕵 Fetched:</b> <code>{fetched}</code>/<code>{total}</code>
<b>✅ Forwarded:</b> <code>{forwarded}</code>
<b>🗑 Deleted:</b> <code>{deleted}</code>
<b>📊 Status:</b> <code>{status}</code>
<b>🔥 Progress:</b> <code>{percentage}%</code> {progress_bar}
<b>⏳ ETA:</b> <code>{eta}</code>
"""


users_loop = {}
active_tasks = {}

async def start_forwarding(user_id, chat_id, toid, start_msg_id, limit, is_forwarded_msg, message):
    start_time = time.time()
    
    # Check for existing task
    if user_id in users_loop:
        await message.answer("⏳ Please wait until your previous task completes", show_alert=True)
        return
    
    try:
        m = await message.edit_text("🔍 Verifying your data...")
        
        # Get user data
        user_data = await db.get_user_data(user_id)
        if not user_data or not user_data.get('bot_token'):
            await m.edit_text("❌ No bot configured. Please add a bot first! /settings")
            return

        # Initialize client
        client = await start_clone_bot(CLIENT.client(user_data))
        active_tasks[user_id] = asyncio.current_task()

        # Validate access
        if is_forwarded_msg and not chat_id == user_id and user_data.get('is_bot', True):
            await m.edit_text("⚠️ For private chats, please use a user bot, /settings or /login")
            return await cleanup(client, user_id)

        try:
            await client.get_messages(chat_id, start_msg_id if start_msg_id else 1)
        except Exception as e:
            await m.edit_text(f"❌ Cannot access source chat: {str(e)} ,Use Userbot or Make Your Bot Admin")
            return await cleanup(client, user_id)

        # Test target chat
        try:
            test_msg = await client.send_message(toid, "🔹 Connection test")
            await test_msg.delete()
        except Exception as e:
            await m.edit_text(f"❌ Cannot send to target chat: {str(e)} , Use Userbot or Make Your Bot Admin")
            return await cleanup(client, user_id)

        # Start forwarding
        users_loop[user_id] = True
        await db.add_frwd(user_id)
        
        stats = {
            'forwarded': 0,
            'deleted': 0,
            'fetched': 0,
            'total': limit,
            'start_time': start_time
        }

        batch = []
        async for msg in iter_messages(client, chat_id, limit, start_msg_id):
            if not users_loop.get(user_id, False):
                break

            stats['fetched'] += 1
            
            if msg.empty or msg.service:
                stats['deleted'] += 1
                continue

            if user_data.get('forward_tag', False):
                batch.append(msg.id)
                if len(batch) >= 100 or (limit - stats['fetched']) <= 5:
                    await process_batch(client, batch, chat_id, toid, user_data, stats, m)
                    batch = []
            else:
                await copy_message(client, msg, toid, user_data, stats, m)

            # Update progress periodically
            if stats['fetched'] % 20 == 0 or stats['fetched'] == limit:
                await update_progress(m, stats, limit, 'Forwarding')

        # Process any remaining messages in batch
        if batch and users_loop.get(user_id, False):
            await process_batch(client, batch, chat_id, toid, user_data, stats, m)

        status = 'Completed' if users_loop.get(user_id, False) else 'Cancelled'
        await update_progress(m, stats, limit, status)
        
    except Exception as e:
        logger.error(f"Forwarding error: {str(e)}")
        await m.edit_text(f"❌ Error: {str(e)}")
    finally:
        await cleanup(client, user_id)

async def process_batch(client, batch, chat_id, to_id, user_data, stats, status_msg):
    try:
        if user_data.get('forward_tag', False):
            await client.forward_messages(
                chat_id=to_id,
                from_chat_id=chat_id,
                message_ids=batch,
                protect_content=user_data.get('protect', False)
            )
        else:
            for msg_id in batch:
                msg = await client.get_messages(chat_id, msg_id)
                await copy_message(client, msg, to_id, user_data, stats, status_msg)
        
        stats['forwarded'] += len(batch)
        await update_progress(status_msg, stats, None, "Waiting 10s")
        await asyncio.sleep(10)
    except FloodWait as e:
        await update_progress(status_msg, stats, None, f"Waiting {e.value}s")
        await asyncio.sleep(e.value)
        await process_batch(client, batch, chat_id, to_id, user_data, stats, status_msg)
    except Exception as e:
        logger.error(f"Batch error: {str(e)}")

async def copy_message(client, message, to_id, user_data, stats, status_msg):
    try:
        caption = custom_caption(message, user_data.get('caption', ''))
        if message.media and caption:
            await client.send_cached_media(
                chat_id=to_id,
                file_id=media(message),
                caption=caption,
                reply_markup=user_data.get('button'),
                protect_content=user_data.get('protect', False)
        else:
            await client.copy_message(
                chat_id=to_id,
                from_chat_id=message.chat.id,
                message_id=message.id,
                caption=caption,
                reply_markup=user_data.get('button'),
                protect_content=user_data.get('protect', False))
        
        stats['forwarded'] += 1
    except FloodWait as e:
        await update_progress(status_msg, stats, None, f"Waiting {e.value}s")
        await asyncio.sleep(e.value)
        await copy_message(client, message, to_id, user_data, stats, status_msg)
    except Exception as e:
        logger.error(f"Copy error: {str(e)}")

async def update_progress(message, stats, total, status):
    try:
        if not total:
            total = stats['total']
        percentage = math.floor((stats['fetched'] / total) * 100) if total else 0
        progress_bar = "".join(
            "▓" if i < percentage//10 else "░"
            for i in range(10)
        
        # Calculate ETA
        elapsed = time.time() - stats['start_time']
        if stats['forwarded'] > 0 and elapsed > 0:
            remaining = (total - stats['forwarded']) * (elapsed / stats['forwarded'])
            eta = TimeFormatter(remaining * 1000)
        else:
            eta = "Calculating..."

        text = TEXT.format(
            fetched=stats['fetched'],
            total=total,
            forwarded=stats['forwarded'],
            deleted=stats['deleted'],
            status=status,
            percentage=percentage,
            progress_bar=progress_bar,
            eta=eta
        )

        buttons = []
        if status.lower() not in ['completed', 'cancelled']:
            buttons.append([InlineKeyboardButton('✖ Cancel', 'terminate_frwd')])
        else:
            buttons.extend([
                [InlineKeyboardButton('📢 Channel', url='https://t.me/vijaychoudhary88')],
                [InlineKeyboardButton('💬 Support', url='https://t.me/vijaychoudhary88')]
            ])

        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.error(f"Progress update error: {str(e)}")

async def cleanup(client, user_id):
    try:
        if user_id in active_tasks:
            active_tasks[user_id].cancel()
            del active_tasks[user_id]
        
        if user_id in users_loop:
            del users_loop[user_id]
            
        if client:
            await client.stop()
            
        await db.rmve_frwd(user_id)
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")

def custom_caption(msg, template):
    if not msg or not msg.media:
        return None
        
    media_obj = getattr(msg, msg.media.value, None)
    if not media_obj:
        return None
        
    file_name = getattr(media_obj, 'file_name', '')
    file_size = getattr(media_obj, 'file_size', 0)
    original_caption = getattr(msg, 'caption', '').html if getattr(msg, 'caption', None) else ''
    
    if template:
        return template.format(
            filename=file_name,
            size=get_size(file_size),
            caption=original_caption
        )
    return original_caption

def media(msg):
    if not msg or not msg.media:
        return None
    media_obj = getattr(msg, msg.media.value, None)
    return getattr(media_obj, 'file_id', None) if media_obj else None

def get_size(size):
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size or 0)
    i = 0
    while size >= 1024 and i < len(units)-1:
        i += 1
        size /= 1024
    return f"{size:.2f} {units[i]}"

def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if seconds: parts.append(f"{seconds}s")
    
    return " ".join(parts) if parts else "0s"

async def iter_messages(client, chat_id, limit, offset=0):
    current = offset or 1
    fetched = 0
    
    while fetched < limit:
        batch_size = min(200, limit - fetched)
        try:
            messages = await client.get_messages(
                chat_id,
                message_ids=range(current, current + batch_size)
            )
            
            for msg in messages:
                if msg and not msg.empty:
                    yield msg
                    fetched += 1
                    if fetched >= limit:
                        break
            
            current += batch_size
        except Exception as e:
            logger.error(f"Message fetch error: {str(e)}")
            break

@Client.on_callback_query(filters.regex(r'^terminate_frwd$'))
async def handle_terminate(c: Client, cb: CallbackQuery):
    user_id = cb.from_user.id
    if user_id in users_loop:
        users_loop[user_id] = False
        await cb.answer("⏹ Forwarding cancelled")
    else:
        await cb.answer("❌ No active task to cancel")

@Client.on_callback_query(filters.regex(r'^fwrdstatus'))
async def handle_status(c: Client, cb: CallbackQuery):
    _, status, _, percentage, _ = cb.data.split('#')
    await cb.answer(
        f"Status: {status}\nProgress: {percentage}%",
        show_alert=True
    )

@Client.on_callback_query(filters.regex(r'^close_btn$'))
async def handle_close(c: Client, cb: CallbackQuery):
    await cb.answer()
    await cb.message.delete()












async def iter_messageses(
    bot,
    chat_id: Union[int, str],
    limit: int,
    offset: int = 0,
) -> AsyncGenerator[types.Message, None]:
    """
    Iterate through chat messages by incrementing message IDs.
    Yields valid messages up to the specified limit.
    """
    current_id = max(1, offset)
    yielded = 0

    while yielded < limit:
        batch_size = min(200, limit - yielded)
        msg_ids = range(current_id, current_id + batch_size)

        try:
            messages = await bot.get_messages(chat_id, msg_ids)
        except Exception:
            break

        found_messages = False
        for msg in messages:
            found_messages = True
            yield msg
            yielded += 1
            if yielded >= limit:
                break
                

        current_id += batch_size
        if not found_messages and yielded < limit:
            break




async def initialize_userbot(user_id): # this ensure the single startup .. even if logged in or not
    """Initialize the userbot session for the given user."""
    data = await db.get_data(user_id)
    if data and data.get("session"):
        try:
            device = 'iPhone 16 Pro' # added gareebi text
            userbot = Client(
                "userbot",
                api_id=API_ID,
                api_hash=API_HASH,
                device_model=device,
                session_string=data.get("session")
            )
            await userbot.start()
            return userbot
        except Exception:
            return None
    return None


