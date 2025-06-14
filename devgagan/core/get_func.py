import os
import sys
import math
import time
import asyncio
import logging
import gc
import re
from pyrogram.errors import ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid
from pyrogram.enums import MessageMediaType, ParseMode
from pyrogram.errors import RPCError
from pyrogram.types import Message
from config import LOG_GROUP, OWNER_ID, STRING, API_ID, CONTACT, API_HASH
from devgagan import app
from pyrogram import filters, Client


from typing import Union, AsyncGenerator
from pyrogram import types
from db import db
from pyrogram.errors import FloodWait, MessageNotModified, RPCError
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

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
        bot_data, filters, configs  = await get_user_data(user_id)
        if not bot_data or not bot_data.get('bot_token'):
            await m.edit_text("❌ No bot configured. Please add a bot first! /settings")
            return

        # Validate access
        if is_forwarded_msg and not chat_id == user_id and not bot_data.get('is_userbot', False):
            await m.edit_text("⚠️ For private chats, please use a user bot, /settings or /login")
            return await cleanup(client, user_id)

        client = None
        try:
          # Initialize client
          if is_forwarded_msg and not chat_id == user_id:
            client = await initialize_userbot(user_id,bot_data.get('userbot_session'))

          else:
            client = await start_bot(user_id,bot_data.get('bot_token'))
          active_tasks[user_id] = asyncio.current_task()

        except Exception as e:
          logger.error(f"Initialize client error: {str(e)}")
          await m.edit_text(f"❌ Error: {str(e)}")
          return await cleanup(None, user_id)

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

            if configs.get('forward_tag', False):
                batch.append(msg.id)
                if len(batch) >= 100 or (limit - stats['fetched']) <= 5:
                    await process_batch(client, batch, chat_id, toid, configs, stats, m)
                    batch = []
            else:
                await copy_message(client, msg, toid, configs, stats, m)

            # Update progress periodically
            if stats['fetched'] % 20 == 0 or stats['fetched'] == limit:
                await update_progress(m, stats, limit, 'Forwarding')

        # Process any remaining messages in batch
        if batch and users_loop.get(user_id, False):
            await process_batch(client, batch, chat_id, toid, configs, stats, m)

        status = 'Completed' if users_loop.get(user_id, False) else 'Cancelled'
        await update_progress(m, stats, limit, status)
        
    except Exception as e:
        logger.error(f"Forwarding error: {str(e)}")
        await m.edit_text(f"❌ Error: {str(e)}")
    finally:
        await cleanup(client, user_id)

async def process_batch(client, batch, chat_id, to_id, configs, stats, status_msg):
    try:
        if configs.get('forward_tag', False):
            await client.forward_messages(
                chat_id=to_id,
                from_chat_id=chat_id,
                message_ids=batch,
                protect_content=configs.get('protect', False)
            )
        else:
            for msg_id in batch:
                msg = await client.get_messages(chat_id, msg_id)
                await copy_message(client, msg, to_id, configs, stats, status_msg)
        
        stats['forwarded'] += len(batch)
        await update_progress(status_msg, stats, None, "Waiting 10s")
        await asyncio.sleep(10)
    except FloodWait as e:
        await update_progress(status_msg, stats, None, f"FloodWait Waiting {e.value}s")
        await asyncio.sleep(e.value)
        await process_batch(client, batch, chat_id, to_id, configs, stats, status_msg)
    except Exception as e:
        logger.error(f"Batch error: {str(e)}")

async def copy_message(client, message, to_id, configs, stats, status_msg):
    try:
        caption = custom_caption(message, configs.get('caption', ''))
        if message.media and caption:
            await client.send_cached_media(
                chat_id=to_id,
                file_id=media(message),
                caption=caption,
                reply_markup=configs.get('button'),
                protect_content=configs.get('protect', False)
            )
        else:
            await client.copy_message(
                chat_id=to_id,
                from_chat_id=message.chat.id,
                message_id=message.id,
                caption=caption,
                reply_markup=configs.get('button'),
                protect_content=configs.get('protect', False))
        
        stats['forwarded'] += 1
        await asyncio.sleep(1)
    except FloodWait as e:
        await update_progress(status_msg, stats, None, f"FloodWait Waiting {e.value}s")
        await asyncio.sleep(e.value)
        await copy_message(client, message, to_id, configs, stats, status_msg)
    except Exception as e:
        logger.error(f"Copy error: {str(e)}")

async def update_progress(message, stats, total, status):
    try:
        if not total:
            total = stats['total']
        percentage = math.floor((stats['fetched'] / total) * 100) if total else 0
        progress_bar = "".join(
            "▓" if i < percentage//10 else "░"
            for i in range(10))
        
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
                if msg:  # and not msg.empty:
                    yield msg
                    fetched += 1
                    if fetched >= limit:
                        break
            
            current += batch_size
        except Exception as e:
            logger.error(f"Message fetch error: {str(e)}")
            break

@app.on_callback_query(filters.regex(r'^terminate_frwd$'))
async def handle_terminate(c: Client, cb: CallbackQuery):
    user_id = cb.from_user.id
    if user_id in users_loop:
        users_loop[user_id] = False
        await cb.answer("⏹ Forwarding cancelled")
    else:
        await cb.answer("❌ No active task to cancel")

@app.on_callback_query(filters.regex(r'^fwrdstatus'))
async def handle_status(c: Client, cb: CallbackQuery):
    _, status, _, percentage, _ = cb.data.split('#')
    await cb.answer(
        f"Status: {status}\nProgress: {percentage}%",
        show_alert=True
    )

@app.on_callback_query(filters.regex(r'^close_btn$'))
async def handle_close(c: Client, cb: CallbackQuery):
    await cb.answer()
    await cb.message.delete()








async def get_user_data(user_id):
  bot_data = await db.get_bot(user_id)
  filters = await db.get_filters(user_id)
  configs = await db.get_configs(user_id)
  return bot_data, filters, configs



async def start_bot(user_id, bot_token):
  user_bot = Client(
    f"user_bot_{user_id}",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=bot_token,
    parse_mode=ParseMode.MARKDOWN
  )
  await user_bot.start()
  return user_bot
  


async def initialize_userbot(user_id, userbot_session):
    """Initialize the userbot session for the given user."""
    try:
        device = 'iPhone 16 Pro'
        userbot = Client(
            f"userbot_{user_id}",
            api_id=API_ID,
            api_hash=API_HASH,
            device_model=device,
            session_string=userbot_session
        )
        await userbot.start()
        return userbot
    except Exception:
        return None




def parse_buttons(text, markup=True):
    buttons = []
    if not text:
        return None

    for match in BTN_URL_REGEX.finditer(text):
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        if n_escapes % 2 == 0:
            if bool(match.group(4)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(3).replace(" ", "")))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(3).replace(" ", ""))])
    if markup and buttons:
        buttons = InlineKeyboardMarkup(buttons)
    return buttons if buttons else None



async def update_user_configs(user_id, key, value):
  current = await db.get_configs(user_id)
  if key in ['caption', 'duplicate', 'db_uri', 'forward_tag', 'protect', 'file_size', 'size_limit', 'extension', 'keywords', 'button']:
     current[key] = value
  else: 
     current['filters'][key] = value
  await db.update_configs(user_id, current)

