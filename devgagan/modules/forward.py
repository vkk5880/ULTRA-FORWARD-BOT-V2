import re
import asyncio
from database import db
from config import temp
from translation import Translation
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate as PrivateChat
from pyrogram.errors.exceptions.bad_request_400 import (
    ChannelInvalid,
    ChatAdminRequired,
    UsernameInvalid,
    UsernameNotModified,
    ChannelPrivate,
    PeerIdInvalid
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


from .utils import STS, get_readable_time

# ===================Run Function===================#

@Client.on_message(filters.private & filters.command(["fwd", "forward"]))
async def run(bot, message):
    user_id = message.from_user.id
    _bot = await db.get_bot(user_id) #_bot, caption, forward_tag, data, protect, button = await sts.get_data(user)

    if not _bot:
        initial_msg = await message.reply("You haven't added any bots yet. Please add a bot using /settings before trying to forward messages.")
        await asyncio.sleep(5) # Give user time to read
        await initial_msg.delete()
        return

    channels = await db.get_user_channels(user_id)
    if not channels:
        initial_msg = await message.reply_text("Please set a **target channel** in /settings before you can start forwarding messages.")
        await asyncio.sleep(5) # Give user time to read
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
            _toid_response = await bot.listen(message.chat.id, filters.text, timeout=120)
            await choose_target_msg.delete() # Delete bot's message
            await _toid_response.delete() # Delete user's message

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
    last_msg_id = None
    source_chat_title = "Unknown Chat"

    # Ask for source message/link
    instruction_text = await message.reply_text(
        "**To start, Please send the start link.\n\n> Maximum tries 3**\n\n"
        "You can either:\n"
        "**Forward a message from the source chat** (from a bot or user).\n"
        "**Important for Private Chats:**\n"
        "- If it's a **private chat**, the bot you added in /settings **must be an admin** in that chat.\n"
        "- If you're forwarding from a **user or bot**, you must have **login**  using /login or go to /settings to add user bot\n\n"
        "Type `/cancel` to stop this process.",
        reply_markup=ReplyKeyboardRemove() # Ensure keyboard is removed
    )

    try:
        source_input_msg = await bot.listen(message.chat.id, timeout=300)
        await instruction_text.delete() # Delete bot's instruction message
        await source_input_msg.delete() # Delete user's input message

        if source_input_msg.text and source_input_msg.text.startswith('/cancel'):
            cancel_msg = await message.reply(Translation.CANCEL)
            await asyncio.sleep(3)
            await cancel_msg.delete()
            return

        # Case 1: Message was forwarded
        if source_input_msg.forward_from_chat:
            fwd_chat = source_input_msg.forward_from_chat
            chat_id = fwd_chat.id
            source_chat_title = fwd_chat.title or "Private Chat"
            last_msg_id = source_input_msg.forward_from_message_id

            if last_msg_id is None:
                # This can happen if forwarded from an anonymous admin in a group
                await message.reply_text(
                    "This looks like a forwarded message from an anonymous admin where the original message ID is hidden. "
                )
                await asyncio.sleep(5)
                return await message.delete() # Clean up
            # Verify _bot has Access or user bot  ---

        # Case 2: Text input (link, username, or ID)
        elif source_input_msg.text:
            input_text = source_input_msg.text.strip()

            # Regex for links
            regex_link = re.compile(r"(https?://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/?(\d+)?$")
            match_link = regex_link.match(input_text)

            if match_link:
                # Extract message ID if present in link, otherwise invalid 
                if match_link.group(5):
                    last_msg_id = int(match_link.group(5))
                else:
                    invalid_input_msg = await message.reply_text("Invalid input. Please provide a valid link or forward a message.")
                    await asyncio.sleep(5)
                    await invalid_input_msg.delete()
                    return
                chat_identifier = match_link.group(4)
                if chat_identifier.isnumeric():
                    chat_id = int("-100" + chat_identifier) # For channel IDs (c/XXXX format)
                else:
                    chat_id = chat_identifier # for public channels 

            else:
                invalid_input_msg = await message.reply_text("Invalid input. Please provide a valid link or forward a message.")
                await asyncio.sleep(5)
                await invalid_input_msg.delete()
                return
        else:
            invalid_input_msg = await message.reply_text("Invalid input. Please provide a valid link, username, ID, or forward a message.")
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

    
    # --- Step 4: Get Skip Number ---
    num_messages_prompt = await message.reply_text(
        "Please enter the **number of messages to forward ** from the starting message ID. "
        "Enter `0` if you want to forward all from the provided message ID."
    )
    try:
        num_messages = await bot.listen(message.chat.id, filters.text, timeout=60)
        await num_messages_prompt.delete() # Delete bot's message
        await num_messages.delete() # Delete user's message

        if num_messages.text.startswith('/cancel'):
            cancel_msg = await message.reply(Translation.CANCEL)
            await asyncio.sleep(3)
            await cancel_msg.delete()
            return
        try:
            num_messages_value = int(num_messages.text)
            if num_messages_value < 0:
                raise ValueError("Skip number cannot be negative.")
        except ValueError:
            invalid_skip_msg = await message.reply("Invalid skip number. Please enter a non-negative integer.")
            await asyncio.sleep(3)
            await invalid_skip_msg.delete()
            return
    except asyncio.exceptions.TimeoutError:
        await num_messages_prompt.delete()
        timeout_msg = await message.reply_text('Operation timed out. Please try again.')
        await asyncio.sleep(3)
        await timeout_msg.delete()
        return
    except Exception as e:
        await num_messages_prompt.delete()
        error_msg = await message.reply_text(f'An unexpected error occurred during skip input: {e}')
        await asyncio.sleep(3)
        await error_msg.delete()
        return


    # --- Step 5: Confirmation ---
    forward_id = f"{user_id}-{message.id}-{int(time.time())}" # More unique ID for STS
    
    confirmation_msg = await message.reply_text(
        text=f"**<u>Forwarding Details Summary</u>**\n\n"
             f"**Bot Name:** {_bot['name']} (@{_bot['username']})\n"
             f"**Source Chat:** `{source_chat_title}` (ID: `{chat_id}`)\n"
             f"**Destination Chat:** `{to_title}` (ID: `{toid}`)\n"
             f"**Starting from Message ID:** `{last_msg_id}`\n"
             f"**Messages to forward:** `{num_messages_value}`\n\n"
             f"**Do you want to proceed? reply(Y/N)**",
        disable_web_page_preview=True
    )

    try:
        proceed_response = await bot.listen(message.chat.id, filters.text, timeout=60)
        await confirmation_msg.delete() # Delete bot's confirmation message
        await proceed_response.delete() # Delete user's reply

        if proceed_response.text.lower() == 'y':
            
            await message.reply_text("👍 Starting the forwarding process... You'll receive updates.")
            # i call here to forward functions
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
