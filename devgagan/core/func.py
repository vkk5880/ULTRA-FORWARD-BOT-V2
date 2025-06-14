import os
import re
import math
import time
import asyncio
import subprocess
from datetime import datetime as dt

import cv2
from pyrogram import enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait, InviteHashInvalid, InviteHashExpired, UserAlreadyParticipant, UserNotParticipant

from config import CHANNEL_ID, OWNER_ID 
from devgagan.core.mongo.plans_db import premium_users

# Constants
PROGRESS_BAR = """\n
│ **__Completed:__** {1}/{2}
│ **__Bytes:__** {0}%
│ **__Speed:__** {3}/s
│ **__ETA:__** {4}
╰─────────────────────╯
"""
last_update_time = time.time()

# ---------------------- User Check ----------------------

async def chk_user(message, user_id):
    user = await premium_users()
    return 0 if user_id in user or user_id in OWNER_ID else 1

# ---------------------- Channel Join & Subscribe ----------------------

async def gen_link(app, chat_id):
    return await app.export_chat_invite_link(chat_id)

async def subscribe(app, message):
    update_channel = CHANNEL_ID
    url = await gen_link(app, update_channel)
    if update_channel:
        try:
            user = await app.get_chat_member(update_channel, message.from_user.id)
            if user.status == "kicked":
                await message.reply_text("You are Banned. Contact -- @Contact_xbot")
                return 1
        except UserNotParticipant:
            caption = "Join our channel to use the bot"
            await message.reply_photo(
                photo="https://tecolotito.elsiglocoahuila.mx/i/2023/12/2131463.jpeg",
                caption=caption,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Join Now...", url=url)]
                ])
            )
            return 1
        except Exception:
            await message.reply_text("Something Went Wrong. Contact us @Contact_xbot...")
            return 1

# ---------------------- Time & Format Utilities ----------------------

async def get_seconds(time_string):
    match = re.match(r"(\d+)([a-zA-Z]+)", time_string.strip())
    if not match:
        return 0

    value, unit = int(match.group(1)), match.group(2).lower()
    unit_map = {
        's': 1, 'sec': 1,
        'min': 60,
        'hour': 3600,
        'day': 86400,
        'month': 86400 * 30,
        'year': 86400 * 365
    }
    return value * unit_map.get(unit, 0)

def TimeFormatter(milliseconds: int) -> str:
    seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    result = []
    if days: result.append(f"{days}d")
    if hours: result.append(f"{hours}h")
    if minutes: result.append(f"{minutes}m")
    if seconds: result.append(f"{seconds}s")
    if ms: result.append(f"{ms}ms")
    return ', '.join(result)

def convert(seconds):
    seconds %= (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return "%d:%02d:%02d" % (hour, minutes, seconds)

# ---------------------- Byte Conversion ----------------------

def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < 4:
        size /= power
        n += 1
    return f"{round(size, 2)} {Dic_powerN[n]}B"

# ---------------------- Progress Display ----------------------

async def progress_bar(current, total, ud_type, message, start):
    now = time.time()
    diff = now - start
    if round(diff % 10) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed = round(diff) * 1000
        eta = round((total - current) / speed) * 1000
        total_time = elapsed + eta

        elapsed_fmt = TimeFormatter(milliseconds=elapsed)
        eta_fmt = TimeFormatter(milliseconds=total_time)

        bar = ''.join(["♦" for _ in range(math.floor(percentage / 10))])
        bar += ''.join(["◇" for _ in range(10 - math.floor(percentage / 10))])

        text = f"{bar}{PROGRESS_BAR.format(round(percentage, 2), humanbytes(current), humanbytes(total), humanbytes(speed), eta_fmt)}"
        try:
            await message.edit(f"{ud_type}\n│ {text}")
        except:
            pass

# Optional alt-progress bar
async def progress_callback(current, total, progress_message):
    global last_update_time
    percent = (current / total) * 100
    now = time.time()

    if now - last_update_time >= 10 or percent % 10 == 0:
        blocks = int(percent // 10)
        progress = "♦" * blocks + "◇" * (10 - blocks)
        uploaded = current / (1024 * 1024)
        total_size = total / (1024 * 1024)

        msg = (
            f"╭──────────────────╮\n"
            f"│        **__Uploading...__**       \n"
            f"├──────────\n"
            f"│ {progress}\n\n"
            f"│ **__Progress:__** {percent:.2f}%\n"
            f"│ **__Uploaded:__** {uploaded:.2f} MB / {total_size:.2f} MB\n"
            f"╰──────────────────╯\n\n"
            f"**__Please wait__**"
        )
        await progress_message.edit(msg)
        last_update_time = now

# ---------------------- Link & Metadata ----------------------

def get_link(string):
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+\.[a-z]{2,4}/)(?:[^\s()<>]+|\([^\s()<>]+\))*)"
    try:
        return re.findall(regex, string)[0]
    except IndexError:
        return False

def video_metadata(file):
    try:
        vcap = cv2.VideoCapture(file)
        if not vcap.isOpened():
            return {'width': 1, 'height': 1, 'duration': 1}

        width = round(vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = round(vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = vcap.get(cv2.CAP_PROP_FPS)
        frames = vcap.get(cv2.CAP_PROP_FRAME_COUNT)

        if fps <= 0:
            return {'width': 1, 'height': 1, 'duration': 1}

        duration = round(frames / fps)
        vcap.release()
        return {'width': width, 'height': height, 'duration': max(duration, 1)}
    except Exception as e:
        print(f"Error in video_metadata: {e}")
        return {'width': 1, 'height': 1, 'duration': 1}

# ---------------------- Screenshot ----------------------

def hhmmss(seconds):
    return time.strftime('%H:%M:%S', time.gmtime(seconds))

async def screenshot(video, duration, sender):
    output = f"{sender}.jpg"
    if os.path.exists(output):
        return output

    time_stamp = hhmmss(duration // 2)
    out_file = dt.now().isoformat("_", "seconds") + ".jpg"

    cmd = ["ffmpeg", "-ss", time_stamp, "-i", video, "-frames:v", "1", out_file, "-y"]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()

    return out_file if os.path.isfile(out_file) else None

# ---------------------- Pyrogram Join ----------------------

async def userbot_join(userbot, invite_link):
    try:
        await userbot.join_chat(invite_link)
        return "Successfully joined the Channel"
    except UserAlreadyParticipant:
        return "User is already a participant."
    except (InviteHashInvalid, InviteHashExpired):
        return "Could not join. Maybe your link is expired or Invalid."
    except FloodWait:
        return "Too many requests"
