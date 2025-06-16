# ---------------------------------------------------
# File Name: start.py
# Description: A Pyrogram bot for forwarding msg on Telegram
# Author: vijay kumar | https://github.com/vkk5880
# ---------------------------------------------------

import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
)
from devgagan import app
from config import OWNER_ID, CONTACT
from devgagan.core.func import subscribe

# Setup logging
logging.basicConfig(level=logging.INFO)

# ------------------ /set Command ------------------

@app.on_message(filters.command("set") & filters.user(OWNER_ID))
async def set_commands(_, message: Message):
    await app.set_bot_commands([
        BotCommand("start", "🚀 Start the bot"),
        BotCommand("login", "🔑 Get into the bot"),
        BotCommand("telethon_login", "🔑 Fast-download 🚀 PREMIUM"),
        BotCommand("logout", "🚪 Logout from account"),
        BotCommand("logout_all", "🚪 Logout all accounts"),
        BotCommand("batch", "🫠 Extract in bulk"),
        BotCommand("cancel", "🚫 Cancel batch process"),
        BotCommand("myplan", "⌛ Get your plan details"),
        BotCommand("transfer", "💘 Gift premium to others"),
        BotCommand("setbot", "🤖 Setup your custom bot"),
        BotCommand("settings", "⚙️ Personalize things"),
        BotCommand("speedtest", "🚅 Server speed test"),
        BotCommand("help", "❓ Help for commands"),
        BotCommand("terms", "🥺 Terms and conditions"),
        BotCommand("admin_commands_list", "📜 Admin commands list"),
    ])
    await message.reply("✅ Commands configured successfully!")

# ------------------ /help Pagination ------------------

help_pages = [
    (
        "📝 **Bot Commands Overview (1/2)**:\n\n"
        "1. **/add userID** — Add user to premium\n"
        "2. **/rem userID** — Remove user from premium\n"
        "3. **/transfer userID** — Transfer premium access\n"
        "4. **/get** — List all user IDs\n"
        "5. **/lock** — Lock channel\n"
        "6. **/dl link** — Download video\n"
        "7. **/adl link** — Download audio\n"
        "8. **/login** — Login to bot\n"
        "9. **/batch** — Bulk post extraction\n"
    ),
    (
        "📝 **Bot Commands Overview (2/2)**:\n\n"
        "10. **/logout** — Logout from bot\n"
        "11. **/stats** — Bot statistics\n"
        "12. **/plan** — View premium plans\n"
        "13. **/speedtest** — Server speed test\n"
        "14. **/terms** — View terms and conditions\n"
        "15. **/cancel** — Cancel batch process\n"
        "16. **/myplan** — View your plan\n"
        "17. **/setbot** — Setup your bot\n"
        "18. **/session** — Generate session\n"
        "19. **/settings** — Customize settings\n"
        "**__Powered by Adarsh__**"
    )
]

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    if await subscribe(client, message) == 1:
        return
    await send_or_edit_help_page(client, message, 0)

@app.on_callback_query(filters.regex(r"help_(prev|next)_(\d+)"))
async def on_help_navigation(client: Client, cb: CallbackQuery):
    action, page = cb.data.split("_")[1], int(cb.data.split("_")[2])
    page = page - 1 if action == "prev" else page + 1
    await send_or_edit_help_page(client, cb.message, page)
    await cb.answer()

async def send_or_edit_help_page(client: Client, message: Message, page: int):
    if page < 0 or page >= len(help_pages): return

    keyboard = []
    if page > 0: keyboard.append(InlineKeyboardButton("◀️ Previous", callback_data=f"help_prev_{page}"))
    if page < len(help_pages) - 1: keyboard.append(InlineKeyboardButton("Next ▶️", callback_data=f"help_next_{page}"))

    try:
        await message.delete()
    except Exception as e:
        logging.warning("Failed to delete message: %s", e)

    await message.reply(help_pages[page], reply_markup=InlineKeyboardMarkup([keyboard]))

# ------------------ Terms and Plan Helpers ------------------

def get_terms_text() -> str:
    return (
        "> 📜 **Terms and Conditions** 📜\n\n"
        "✨ We are not responsible for user deeds.\n"
        "✨ Plan uptime/downtime is not guaranteed.\n"
        "✨ Authorization is at our discretion.\n"
        "✨ Payment does **not guarantee** batch command access.\n"
    )

def get_plan_text() -> str:
    return (
        "> 💰 **Premium Price**\n\n"
        "Starts at 39 INR via **__UPI__**\n"
        "📥 Download up to 100,000 files per batch.\n"
        "🛑 Modes: `/bulk` & `/batch`\n"
        "📜 Send /terms for legal info.\n"
    )

# ------------------ /terms and /plan ------------------

@app.on_message(filters.command("terms") & filters.private)
async def terms(client: Client, message: Message):
    await message.reply_text(
        get_terms_text(),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 See Plans", callback_data="see_plan")],
            [InlineKeyboardButton("💬 Contact Now", url=CONTACT)],
        ])
    )

@app.on_message(filters.command("plan") & filters.private)
async def plan(client: Client, message: Message):
    await message.reply_text(
        get_plan_text(),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 See Terms", callback_data="see_terms")],
            [InlineKeyboardButton("💬 Contact Now", url=CONTACT)],
        ])
    )

# ------------------ Callback Switch ------------------

@app.on_callback_query(filters.regex("see_plan"))
async def see_plan(client: Client, cb: CallbackQuery):
    await cb.message.edit_text(
        get_plan_text(),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 See Terms", callback_data="see_terms")],
            [InlineKeyboardButton("💬 Contact Now", url=CONTACT)],
        ])
    )

@app.on_callback_query(filters.regex("see_terms"))
async def see_terms(client: Client, cb: CallbackQuery):
    await cb.message.edit_text(
        get_terms_text(),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 See Plans", callback_data="see_plan")],
            [InlineKeyboardButton("💬 Contact Now", url=CONTACT)],
        ])
    )
