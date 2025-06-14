import re
import asyncio
import time
from devgagan import app
from devgagan.core.mongo.db import db
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate as PrivateChat
from pyrogram.errors.exceptions.bad_request_400 import (
    ChannelInvalid,
    ChatAdminRequired,
    UsernameInvalid,
    UsernameNotModified,
    PeerIdInvalid
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from devgagan.core.get_func import start_forwarding


@app.on_message(filters.private & filters.command(["fwd", "forward"]))
async def run(bot, message):
    user_id = message.from_user.id
    bot_data = await db.get_bot(user_id)

    if not bot_data or not bot_data.get('bot_token'): # or userbot_session for userbot
        initial_msg = await message.reply("You haven't added any bots yet. Please add a bot using /settings or /addbot before trying to forward messages.")
        await asyncio.sleep(5)
        await initial_msg.delete()
        return

    channels = await db.get_user_channels(user_id)
    if not channels:
        initial_msg = await message.reply_text("Please set a **target channel** in /settings before you can start forwarding messages.")
        await asyncio.sleep(5)
        await initial_msg.delete()
        return

    # --- Step 1: Select Target Channel ---
    toid = None
    to_title = None
    if len(channels) > 1:
        buttons = []
        btn_data = {}
        for channel in channels:
            buttons.append([KeyboardButton(f"{channel['title']}")])
            btn_data[channel['title']] = channel['chat_id']
        buttons.append([KeyboardButton("cancel")])

        choose_target_msg = await message.reply_text(
            Translation.TO_MSG.format(_bot['name'], _bot['username']),
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        )
        try:
            _toid_response = await bot.listen(
                message.chat.id,
                filters.text & filters.user(user_id),
                timeout=120
            )
            await choose_target_msg.delete()
            await _toid_response.delete()

            if _toid_response.text.lower() == 'cancel' or _toid_response.text.startswith('/'):
                cancel_msg = await message.reply_text(Translation.CANCEL, reply_markup=ReplyKeyboardRemove())
                await asyncio.sleep(3)
                await cancel_msg.delete()
                return

            to_title = _toid_response.text
            toid = btn_data.get(to_title)
            if not toid:
                invalid_channel_msg = await message.reply_text("That's not a valid channel. Please choose from the provided options!", reply_markup=ReplyKeyboardRemove())
                await asyncio.sleep(3)
                await invalid_channel_msg.delete()
                return
        except asyncio.exceptions.TimeoutError:
            await choose_target_msg.delete()
            timeout_msg = await message.reply_text("Operation timed out. Please try again.", reply_markup=ReplyKeyboardRemove())
            await asyncio.sleep(3)
            await timeout_msg.delete()
            return
        except Exception as e:
            await choose_target_msg.delete()
            error_msg = await message.reply_text(f"An error occurred: {e}", reply_markup=ReplyKeyboardRemove())
            await asyncio.sleep(3)
            await error_msg.delete()
            return
    else:
        toid = channels[0]['chat_id']
        to_title = channels[0]['title']

    # --- Step 2: Get Source Chat Information ---
    chat_id = None
    start_msg_id = None
    last_msg_id = None
    source_chat_title = "Unknown Chat"
    is_forwarded_msg = False

    instruction_text = await message.reply_text(
        "**To start, please send the start link or forward a message.**\n\n"
        "You can either:\n"
        "1. **Forward a message from the source chat** (from a bot or user).\n"
        "2. **Send a link to the message within the chat** (e.g., `https://t.me/my_public_channel/123`).\n\n"
        "**Important for Private Channels/Groups/User Forwards:**\n"
        "- If it's a **private chat**, the bot you added in /settings **must be an admin** in that chat.\n"
        "- If you're forwarding from a **user or bot**, you must have **login**  using /login or go to /settings to add user bot\n\n"
        "Type `/cancel` to stop this process.",
        reply_markup=ReplyKeyboardRemove()
    )

    try:
        source_input_msg = await bot.listen(
            message.chat.id,
            filters.user(user_id),
            timeout=300
        )
        await instruction_text.delete()
        await source_input_msg.delete()

        if source_input_msg.text and source_input_msg.text.startswith('/cancel'):
            cancel_msg = await message.reply(Translation.CANCEL)
            await asyncio.sleep(3)
            await cancel_msg.delete()
            return

        if source_input_msg.forward_from_chat:
            fwd_chat = source_input_msg.forward_from_chat
            chat_id = fwd_chat.id
            source_chat_title = fwd_chat.title or "Private Chat"
            start_msg_id = source_input_msg.forward_from_message_id

            if start_msg_id is None:
                await message.reply_text(
                    "This looks like a forwarded message where the original message ID is hidden. "
                    "Please try sending a direct link to the message instead (e.g., `https://t.me/channel_name/message_id`)."
                )
                await asyncio.sleep(7)
                return

            is_forwarded_msg = True
        elif source_input_msg.text:
            input_text = source_input_msg.text.strip()

            # Regex to correctly parse channel links with numeric ID or username AND message ID
            regex_link = re.compile(r"(https?://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?([a-zA-Z0-9_]+)/(\d+)$")
            match_link = regex_link.match(input_text)

            if match_link:
                chat_identifier = match_link.group(4)
                if match_link.group(3) == 'c/':
                    chat_id = int("-100" + chat_identifier)
                else:
                    chat_id = chat_identifier

                start_msg_id = int(match_link.group(5))
            else:
                invalid_input_msg = await message.reply_text("Invalid input. Please provide a valid message link or forward a message.")
                await asyncio.sleep(5)
                await invalid_input_msg.delete()
                return
        else:
            invalid_input_msg = await message.reply_text("Invalid input. Please provide a valid message link or forward a message.")
            await asyncio.sleep(5)
            await invalid_input_msg.delete()
            return

    except asyncio.exceptions.TimeoutError:
        await instruction_text.delete()
        timeout_msg = await message.reply_text('Operation timed out. Please try again.')
        await asyncio.sleep(3)
        await timeout_msg.delete()
        return
    except Exception as e:
        await instruction_text.delete()
        error_msg = await message.reply_text(f'An unexpected error occurred during source input: {e}')
        await asyncio.sleep(3)
        await error_msg.delete()
        return


    # --- Step 3: Get Number of Messages to Forward ---
    ask_end_msg = await message.reply_text("📨 Now send the last msg link or forward a last message")
    
    try:
        end_input = await bot.listen(
            message.chat.id,
            filters.user(user_id),
            timeout=300
        )
        await ask_end_msg.delete()
        await end_input.delete()

        if end_input.text and end_input.text.startswith('/cancel'):
            cancel_msg = await message.reply(Translation.CANCEL)
            await asyncio.sleep(3)
            await cancel_msg.delete()
            return

        if end_input.forward_from_chat:
            fwd_chat = end_input.forward_from_chat
            #chat_id = fwd_chat.id
            #source_chat_title = fwd_chat.title or "Private Chat"
            last_msg_id = end_input.forward_from_message_id

            if last_msg_id is None:
                await message.reply_text(
                    "This looks like a forwarded message where the original message ID is hidden. "
                    "Please try sending a direct link to the message instead (e.g., `https://t.me/channel_name/message_id`)."
                )
                await asyncio.sleep(7)
                return

        elif end_input.text:
            input_text = end_input.text.strip()

            # Regex to correctly parse channel links with numeric ID or username AND message ID
            regex_link = re.compile(r"(https?://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?([a-zA-Z0-9_]+)/(\d+)$")
            match_link = regex_link.match(input_text)

            if match_link:
                chat_identifier = match_link.group(4)
                if match_link.group(3) == 'c/':
                    chat_id = int("-100" + chat_identifier)
                else:
                    chat_id = chat_identifier

                last_msg_id = int(match_link.group(5))
            else:
                invalid_input_msg = await message.reply_text("Invalid input. Please provide a valid message link or forward a message.")
                await asyncio.sleep(5)
                await invalid_input_msg.delete()
                return
        else:
            invalid_input_msg = await message.reply_text("Invalid input. Please provide a valid message link or forward a message.")
            await asyncio.sleep(5)
            await invalid_input_msg.delete()
            return

    except asyncio.exceptions.TimeoutError:
        await ask_end_msg.delete()
        timeout_msg = await message.reply_text('Operation timed out. Please try again.')
        await asyncio.sleep(3)
        await timeout_msg.delete()
        return
    except Exception as e:
        await ask_end_msg.delete()
        error_msg = await message.reply_text(f'An unexpected error occurred during source input: {e}')
        await asyncio.sleep(3)
        await error_msg.delete()
        return

    # Validate range
    if last_msg_id < start_msg_id:
        err = await message.reply_text("⚠️ Ending message ID cannot be less than starting message ID.")
        await asyncio.sleep(3)
        await err.delete()
        return

    num_messages_value = end_msg_id - start_msg_id + 1


    # --- Step 4: Confirmation ---
    forward_id = f"{user_id}-{message.id}-{int(time.time())}"
    
    confirmation_msg = await message.reply_text(
        text=f"**<u>Forwarding Details Summary</u>**\n\n"
             f"**Bot Name:** {_bot['name']} (@{_bot['username']})\n"
             f"**Source Chat:** `{source_chat_title}` (ID: `{chat_id}`)\n"
             f"**Destination Chat:** `{to_title}` (ID: `{toid}`)\n"
             f"**Starting from Message ID:** `{last_msg_id}`\n"
             f"**Messages to forward:** `{'All' if num_messages_value == 0 else num_messages_value}`\n\n"
             f"**Do you want to proceed? Reply (Y/N)**",
        disable_web_page_preview=True
    )

    try:
        proceed_response = await bot.listen(
            message.chat.id,
            filters.text & filters.user(user_id),
            timeout=60
        )
        await confirmation_msg.delete()
        await proceed_response.delete()

        if proceed_response.text.lower() == 'y':
            
            asyncio.create_task(start_forwarding(user_id, chat_id, toid, start_msg_id, num_messages_value, is_forwarded_msg, message))

        else:
            cancel_msg = await message.reply_text("Forwarding cancelled by user.")
            await asyncio.sleep(3)
            await cancel_msg.delete()
            return

    except asyncio.exceptions.TimeoutError:
        await confirmation_msg.delete()
        timeout_msg = await message.reply_text('Confirmation timed out. Process cancelled.')
        await asyncio.sleep(3)
        await timeout_msg.delete()
        return
    except Exception as e:
        await confirmation_msg.delete()
        error_msg = await message.reply_text(f'An error occurred during confirmation: {e}')
        await asyncio.sleep(3)
        await error_msg.delete()
        return
