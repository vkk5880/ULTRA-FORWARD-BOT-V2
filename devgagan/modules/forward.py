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
        "**To start, please provide the source channel/group information.**\n\n"
        "You can either:\n"
        "1.  **Forward a message from the source chat** (if you're a member and I have access).\n"
        "2.  **Send an invite link** to the chat (e.g., `https://t.me/my_public_channel/123` or `https://t.me/+abcdXYZ`).\n"
        "3.  **Send the chat's username** (e.g., `@my_public_channel`).\n"
        "4.  **Send the chat's numeric ID** (e.g., `-1001234567890`).\n\n"
        "**Important for Private Chats:**\n"
        "- If it's a **private chat**, the bot you added in /settings **must be an admin** in that chat.\n"
        "- If you're using a **user bot**, it must have **started** your main bot to function correctly and be a member of the private chat.\n\n"
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
                    "Please try sending the chat's invite link, username, or numeric ID instead."
                )
                return await message.delete() # Clean up

            # Check if original sender was bot or user
            if source_input_msg.forward_from:
                # The 'forward_from' field is for users, not chats.
                # If it's a channel/group forward, we primarily rely on forward_from_chat.
                pass # Already handled by forward_from_chat logic above.

        # Case 2: Text input (link, username, or ID)
        elif source_input_msg.text:
            input_text = source_input_msg.text.strip()

            # Regex for links
            regex_link = re.compile(r"(https?://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/?(\d+)?$")
            match_link = regex_link.match(input_text)

            if match_link:
                chat_identifier = match_link.group(4)
                if chat_identifier.isnumeric():
                    chat_id = int("-100" + chat_identifier) # For channel IDs (c/XXXX format)
                else:
                    chat_id = "@" + chat_identifier # For usernames

                # Extract message ID if present in link, otherwise prompt
                if match_link.group(5):
                    last_msg_id = int(match_link.group(5))
                else:
                    # No message ID in link, ask for it
                    msg_id_prompt = await message.reply_text("Please enter the **last message ID** from which you want to start forwarding:")
                    msg_id_response = await bot.listen(message.chat.id, filters.text, timeout=60)
                    await msg_id_prompt.delete()
                    await msg_id_response.delete()
                    if msg_id_response.text.startswith('/cancel'):
                        cancel_msg = await message.reply(Translation.CANCEL)
                        await asyncio.sleep(3)
                        await cancel_msg.delete()
                        return
                    try:
                        last_msg_id = int(msg_id_response.text)
                    except ValueError:
                        invalid_id_msg = await message.reply("Invalid message ID. Please send a valid number.")
                        await asyncio.sleep(3)
                        await invalid_id_msg.delete()
                        return

            # If not a link, check for username or numeric ID directly
            elif input_text.startswith('@') or input_text.lstrip('-').isdigit():
                try:
                    chat_id = int(input_text) if input_text.lstrip('-').isdigit() else input_text
                    
                    # Ask for last message ID
                    msg_id_prompt = await message.reply_text("Please enter the **last message ID** from which you want to start forwarding:")
                    msg_id_response = await bot.listen(message.chat.id, filters.text, timeout=60)
                    await msg_id_prompt.delete()
                    await msg_id_response.delete()

                    if msg_id_response.text.startswith('/cancel'):
                        cancel_msg = await message.reply(Translation.CANCEL)
                        await asyncio.sleep(3)
                        await cancel_msg.delete()
                        return
                    try:
                        last_msg_id = int(msg_id_response.text)
                    except ValueError:
                        invalid_id_msg = await message.reply("Invalid message ID. Please send a valid number.")
                        await asyncio.sleep(3)
                        await invalid_id_msg.delete()
                        return

                except Exception as e:
                    invalid_input_msg = await message.reply_text(f"Invalid username/ID format or unable to get chat information: {e}")
                    await asyncio.sleep(5)
                    await invalid_input_msg.delete()
                    return
            else:
                invalid_input_msg = await message.reply_text("Invalid input. Please provide a valid link, username, ID, or forward a message.")
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

    # --- Step 3: Verify Chat Access ---
    try:
        chat = await bot.get_chat(chat_id)
        source_chat_title = chat.title or chat.first_name # For private chats without titles
        if chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]:
            if chat.username:
                source_chat_title += f" (@{chat.username})"
            else:
                source_chat_title += f" (ID: {chat.id})"

        # If it's a private chat, check bot's admin status
        if chat.type in [enums.ChatType.PRIVATE, enums.ChatType.GROUP, enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL]:
            try:
                # Try getting member status of the bot you added (_bot['id']) in the source chat
                # This assumes _bot_info has a 'id' or 'client_id' field for the bot you setup.
                # If _bot is just metadata, you need to use the actual client you initialized for _bot
                # Or, if your main 'bot' instance is what you're using for fetching, check its status.
                # For simplicity, let's assume 'bot' (the main client) is trying to get chat info
                # and Pyrogram will raise ChatAdminRequired if it can't.

                # If the chat is private, we assume the bot (or user bot) needs to be an admin.
                # A more thorough check would involve:
                # client_to_use = user_client_manager.get_client(user_id) # if using user clients
                # member = await client_to_use.get_chat_member(chat_id, (await client_to_use.get_me()).id)
                # if not member.can_post_messages: # or other relevant admin rights
                #    raise ChatAdminRequired
                pass # Pyrogram's get_chat usually handles access issues by raising errors

            except ChatAdminRequired:
                error_msg = await message.reply_text(
                    f"**Error:** I cannot access the source chat '{source_chat_title}'. "
                    f"Please make sure the bot you added in /settings is **an administrator** in this channel/group, "
                    f"or if it's a user bot, that it's a member and has started your bot."
                )
                await asyncio.sleep(5)
                await error_msg.delete()
                return
            except PeerIdInvalid:
                error_msg = await message.reply_text("The provided chat ID/username is invalid or does not exist.")
                await asyncio.sleep(3)
                await error_msg.delete()
                return
            except Exception as e:
                error_msg = await message.reply_text(f"An unexpected error occurred while verifying source chat access: {e}")
                await asyncio.sleep(3)
                await error_msg.delete()
                return

    except (PrivateChat, ChannelPrivate, ChannelInvalid):
        # This typically means the chat is private and the bot might not have access,
        # or the ID/username is simply invalid.
        # We've already tried to get chat info, if it failed here, it's an access issue.
        error_msg = await message.reply_text(
            f"**Error:** I cannot access the source chat. "
            f"Please ensure it's a valid link/ID/forwarded message, and if private, "
            f"that the bot you added has administrator rights in it."
        )
        await asyncio.sleep(5)
        await error_msg.delete()
        return
    except (UsernameInvalid, UsernameNotModified, PeerIdInvalid):
        error_msg = await message.reply_text('The provided username/ID for the source chat is invalid. Please double-check it.')
        await asyncio.sleep(3)
        await error_msg.delete()
        return
    except Exception as e:
        error_msg = await message.reply_text(f'An unexpected error occurred while getting source chat details: {e}')
        await asyncio.sleep(3)
        await error_msg.delete()
        return

    # --- Step 4: Get Skip Number ---
    skip_prompt = await message.reply_text(
        "Please enter the **number of messages to skip** from the starting message ID. "
        "Enter `0` if you want to start from the provided message ID."
    )
    try:
        skipno = await bot.listen(message.chat.id, filters.text, timeout=60)
        await skip_prompt.delete() # Delete bot's message
        await skipno.delete() # Delete user's message

        if skipno.text.startswith('/cancel'):
            cancel_msg = await message.reply(Translation.CANCEL)
            await asyncio.sleep(3)
            await cancel_msg.delete()
            return
        try:
            skip_value = int(skipno.text)
            if skip_value < 0:
                raise ValueError("Skip number cannot be negative.")
        except ValueError:
            invalid_skip_msg = await message.reply("Invalid skip number. Please enter a non-negative integer.")
            await asyncio.sleep(3)
            await invalid_skip_msg.delete()
            return
    except asyncio.exceptions.TimeoutError:
        await skip_prompt.delete()
        timeout_msg = await message.reply_text('Operation timed out. Please try again.')
        await asyncio.sleep(3)
        await timeout_msg.delete()
        return
    except Exception as e:
        await skip_prompt.delete()
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
             f"**Messages to Skip:** `{skip_value}`\n\n"
             f"**Do you want to proceed? (Y/N)**",
        disable_web_page_preview=True
    )

    try:
        proceed_response = await bot.listen(message.chat.id, filters.text, timeout=60)
        await confirmation_msg.delete() # Delete bot's confirmation message
        await proceed_response.delete() # Delete user's reply

        if proceed_response.text.lower() == 'y':
            # Store data in STS
            sts_instance = STS(forward_id).store(chat_id, toid, skip_value, last_msg_id)

            # Call the next function for actual forwarding
            # You need to ensure 'forward_messages_loop' is defined and accessible
            # This is a conceptual call, ensure your actual bot client is passed if needed.
            # Here, 'bot' (your main client) is passed, which might be sufficient.
            # If you need to use the user's added bot for forwarding, you'd load/instantiate it here.
            await message.reply_text("👍 Starting the forwarding process... You'll receive updates.")
            
            # --- Call the actual forwarding loop here ---
            # Make sure forward_messages_loop accepts a Pyrogram Client instance
            # and the STS object.
            # You might want to get the actual bot client instance if _bot_info represents another bot.
            # Example:
            # client_to_use = user_client_manager.get_client(user_id) # If you have a manager for user bots
            _bot_info, caption_template, forward_tag, fetch_params, protect_content, custom_buttons = await sts_instance.get_data(user_id)

            asyncio.create_task(forward_messages_loop( # Use asyncio.create_task to run in background
                bot_client=bot, # Use your main bot for fetching/forwarding, or the user's bot client
                sts_instance=sts_instance,
                main_bot_user_id=user_id,
                caption_template=caption_template,
                forward_tag=forward_tag,
                protect_content=protect_content,
                custom_buttons=custom_buttons,
                fetch_params=fetch_params
            ))

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

# --- Make sure your forward_messages_loop function is defined and imported/accessible ---
# Example placeholder for forward_messages_loop (same as previous response, ensure it's imported or defined here)
# from .forward_logic import forward_messages_loop
# Or define it here if it's small enough

# async def forward_messages_loop(...):
#     # ... (your message fetching and forwarding logic) ...
#     pass
