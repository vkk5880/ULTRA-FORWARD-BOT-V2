import asyncio
from database import db
from translation import Translation
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from devgagan.core.get_func import update_user_configs, parse_buttons, set_bot, set_userbot
from devgagan import app

# --- Message Handlers ---

@app.on_message(filters.private & filters.command(['settings']))
async def show_main_settings(client, message):
    """
    Handles the /settings command to display the main settings menu.
    """
    await message.reply_text(
        text="<b>Change Your Settings As Your Wish</b>",
        reply_markup=generate_main_settings_buttons(),
        quote=True
    )

# --- Callback Query Handlers ---

@app.on_callback_query(filters.regex(r'^settings#main'))
async def handle_main_settings_query(bot, query):
    """Handles callback for the main settings menu."""
    await query.message.edit_text(
        "<b>Change Your Settings As Your Wish</b>",
        reply_markup=generate_main_settings_buttons()
    )

@app.on_callback_query(filters.regex(r'^settings#bots'))
async def display_bot_settings(bot, query):
    """Displays options to manage bots (add/edit)."""
    user_id = query.from_user.id
    buttons = []
    bot_data = await db.get_bot(user_id)
    userbot_data = await db.get_userbot(user_id)
    if bot_data and bot_data.get('bot_token'):
        buttons.append([InlineKeyboardButton(bot_data['name'],
                                             callback_data=f"settings#editbot")])

    else:
        buttons.append([InlineKeyboardButton('✚ Add Bot ✚',
                                             callback_data="settings#addbot")])

    if bot_data and userbot_data.get('userbot_session'):
        buttons.append([InlineKeyboardButton(bot_data['name'],
                                             callback_data=f"settings#edituserbot")])
    else:
        buttons.append([InlineKeyboardButton('✚ Add User Bot ✚',
                                             callback_data="settings#adduserbot")])
    buttons.append([InlineKeyboardButton('🔙 Back',
                                         callback_data="settings#main")])
    await query.message.edit_text(
        "<b><u>My Bots</u></b>\n\nYou Can Manage Your Bots In Here",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#addbot'))
async def add_new_bot_token(bot, query):
    """Initiates the process to add a new bot token."""
    user_id = query.from_user.id
    await query.message.delete()
    success = await set_bot(bot, query)
    if success:
        await query.message.reply_text(
            "<b>Bot Token Successfully Added To Database</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#bots")]])
        )

@app.on_callback_query(filters.regex(r'^settings#adduserbot'))
async def add_new_user_session(bot, query):
    """Initiates the process to add a new user session."""
    user_id = query.from_user.id
    await query.message.delete()
    success = await set_userbot(bot, query)
    if success:
        await query.message.reply_text(
            "<b>Session Successfully Added To Database</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#bots")]])
        )

@app.on_callback_query(filters.regex(r'^settings#channels'))
async def display_channel_settings(bot, query):
    """Displays options to manage channels (add/edit/remove)."""
    user_id = query.from_user.id
    buttons = []
    channels = await db.get_user_channels(user_id)
    for channel in channels:
        buttons.append([InlineKeyboardButton(f"{channel['title']}",
                                             callback_data=f"settings#editchannels_{channel['chat_id']}")])
    buttons.append([InlineKeyboardButton('✚ Add Channel ✚',
                                         callback_data="settings#addchannel")])
    buttons.append([InlineKeyboardButton('🔙 Back',
                                         callback_data="settings#main")])
    await query.message.edit_text(
        "<b><u>My Channels</u></b>\n\nYou Can Manage Your Target Chats In Here",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#addchannel'))
async def process_add_chat(bot, query):
    """Processes the addition of a new channel or group."""
    user_id = query.from_user.id
    await query.message.delete()
    try:
        instruction_text = await bot.send_message(
            user_id,
            "<b><u>Add Channel or Group or User</u></b>\n\n"
            "If it's a **public chat**, please send its **invite link**.\n"
            "If it's a **private chat**, please send its **username** (e.g., `@user`) or **post link** or **numeric ID**.\n\n"
            "**Important:**\n"
            "- For **private chats**, make your bot **admin** in the chat.\n"
            "- If you're adding a **user**, user must have **started** your bot to function correctly.\n\n"
            "/cancel - To Cancel This Process"
        )

        chat_input_msg = await bot.listen(chat_id=user_id, timeout=300)

        if chat_input_msg.text == "/cancel":
            await chat_input_msg.delete()
            return await instruction_text.edit_text(
                "Process Canceled",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#channels")]])
            )

        chat_id = None
        title = None
        username = "private"
        chat_type_str = ""

        if chat_input_msg.text:
            input_text = chat_input_msg.text.strip()
            try:
                if input_text.startswith(('http://t.me/', 'https://t.me/', '@')) or input_text.lstrip('-').isdigit():
                    chat = await bot.get_chat(input_text)

                    chat_id = chat.id
                    title = chat.title
                    username = "@" + chat.username if chat.username else \
                               "private_group" if chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP] else "private_channel"
                    chat_type_str = "channel" if chat.type == enums.ChatType.CHANNEL else "group"
                else:
                    await chat_input_msg.delete()
                    return await instruction_text.edit_text(
                        "Invalid input. Please send an invite link (for public chats) or a username/numeric ID (for private chats).",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#channels")]])
                    )

            except Exception:
                await chat_input_msg.delete()
                return await instruction_text.edit_text(
                    "Invalid input, invite link, username/ID, or bot doesn't have access. "
                    "Remember, for private chats, the bot needs to be an admin.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#channels")]])
                )
        else:
            await chat_input_msg.delete()
            return await instruction_text.edit_text(
                "Invalid input. Please send an invite link, username, or ID.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#channels")]])
            )

        added_chat = await db.add_channel(
            user_id=user_id,
            chat_id=chat_id,
            title=title,
            username=username,
        )

        await chat_input_msg.delete()
        await instruction_text.edit_text(
            f"Successfully added {chat_type_str}!" if added_chat else "This chat already exists in your list.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#channels")]])
        )

    except asyncio.exceptions.TimeoutError:
        await instruction_text.edit_text(
            'Process timed out.',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#channels")]])
        )
    except Exception as e:
        await instruction_text.edit_text(
            f'Error: {str(e)}',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#channels")]])
        )



@app.on_callback_query(filters.regex(r'^settings#edituserbot'))
async def display_bot_details(bot, query):
    """Displays details of the added bot/userbot."""
    user_id = query.from_user.id
    bot_data = await db.get_userbot(user_id)
    text_template = Translation.USER_DETAILS
    buttons = [[InlineKeyboardButton('❌ Remove ❌', callback_data=f"settings#removeuserbot")],
               [InlineKeyboardButton('🔙 Back', callback_data="settings#bots")]]
    await query.message.edit_text(
        text_template.format(bot_data['name'], bot_data['id'], bot_data['username']),
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#editbot'))
async def display_bot_details(bot, query):
    """Displays details of the added bot/userbot."""
    user_id = query.from_user.id
    bot_data = await db.get_bot(user_id)
    text_template = Translation.BOT_DETAILS
    buttons = [[InlineKeyboardButton('❌ Remove ❌', callback_data=f"settings#removebot")],
               [InlineKeyboardButton('🔙 Back', callback_data="settings#bots")]]
    await query.message.edit_text(
        text_template.format(bot_data['name'], bot_data['id'], bot_data['username']),
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#removeuserbot'))
async def remove_bot_entry(bot, query):
    """Removes the stored bot/userbot entry."""
    user_id = query.from_user.id
    await db.remove_userbot(user_id)
    await query.message.edit_text(
        "Successfully Updated",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#bots")]])
    )


@app.on_callback_query(filters.regex(r'^settings#removebot'))
async def remove_bot_entry(bot, query):
    """Removes the stored bot/userbot entry."""
    user_id = query.from_user.id
    await db.remove_bot(user_id)
    await query.message.edit_text(
        "Successfully Updated",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#bots")]])
    )

@app.on_callback_query(filters.regex(r'^settings#editchannels_'))
async def display_channel_details(bot, query):
    """Displays details of a specific channel."""
    user_id = query.from_user.id
    chat_id = query.data.split('_')[1]
    chat_info = await db.get_channel_details(user_id, chat_id)
    buttons = [[InlineKeyboardButton('❌ Remove ❌', callback_data=f"settings#removechannel_{chat_id}")],
               [InlineKeyboardButton('🔙 Back', callback_data="settings#channels")]]
    await query.message.edit_text(
        f"<b><u>📄 Channel Details</b></u>\n\n<b>Title :</b> <code>{chat_info['title']}</code>\n<b>Channel ID :</b> <code>{chat_info['chat_id']}</code>\n<b>Username :</b> {chat_info['username']}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#removechannel_'))
async def remove_channel_entry(bot, query):
    """Removes a channel entry from the database."""
    user_id = query.from_user.id
    chat_id = query.data.split('_')[1]
    await db.remove_channel(user_id, chat_id)
    await query.message.edit_text(
        "Successfully Updated",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#channels")]])
    )

@app.on_callback_query(filters.regex(r'^settings#caption'))
async def display_caption_settings(bot, query):
    """Displays options for managing custom captions."""
    user_id = query.from_user.id
    buttons = []
    user_configs = await  db.get_configs(user_id)
    caption_text = user_configs.get('caption')
    if caption_text:
        buttons.append([InlineKeyboardButton('👀 See Caption', callback_data="settings#seecaption")])
        buttons[-1].append(InlineKeyboardButton('🗑️ Delete Caption', callback_data="settings#deletecaption"))
    else:
        buttons.append([InlineKeyboardButton('✚ Add Caption ✚', callback_data="settings#addcaption")])
    buttons.append([InlineKeyboardButton('🔙 Back', callback_data="settings#main")])
    await query.message.edit_text(
        "<b><u>Custom Caption</b></u>\n\nYou Can Set A Custom Caption To Videos And Documents. Normally Use Its Default Caption\n\n<b><u>Available Fillings :</b></u>\n\n<code>{filename}</code> : Filename\n<code>{size}</code> : File Size\n<code>{caption}</code> : Default Caption",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#seecaption'))
async def display_current_caption(bot, query):
    """Displays the currently set custom caption."""
    user_id = query.from_user.id
    user_configs = await  db.get_configs(user_id)
    caption_text = user_configs.get('caption')
    buttons = [[InlineKeyboardButton('✏️ Edit Caption', callback_data="settings#addcaption")],
               [InlineKeyboardButton('🔙 Back', callback_data="settings#caption")]]
    await query.message.edit_text(
        f"<b><u>Your Custom Caption</b></u>\n\n<code>{caption_text}</code>",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#deletecaption'))
async def delete_custom_caption(bot, query):
    """Deletes the custom caption."""
    user_id = query.from_user.id
    await update_user_configs(user_id, 'caption', None)
    await query.message.edit_text(
        "Successfully Updated",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#caption")]])
    )

@app.on_callback_query(filters.regex(r'^settings#addcaption'))
async def prompt_add_or_edit_caption(bot, query):
    """Prompts the user to send a new custom caption."""
    user_id = query.from_user.id
    await query.message.delete()
    try:
        instruction_msg = await bot.send_message(query.message.chat.id, "Send your custom caption\n/cancel - <code>cancel this process</code>")
        caption_input = await bot.listen(chat_id=user_id, timeout=300)
        if caption_input.text == "/cancel":
            await caption_input.delete()
            return await instruction_msg.edit_text(
                "Process Canceled !",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#caption")]])
            )
        try:
            caption_input.text.format(filename='', size='', caption='')
        except KeyError as e:
            await caption_input.delete()
            return await instruction_msg.edit_text(
                f"Wrong Filling {e} Used In Your Caption. Change It",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#caption")]])
            )
        await update_user_configs(user_id, 'caption', caption_input.text)
        await caption_input.delete()
        await instruction_msg.edit_text(
            "Successfully Updated",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#caption")]])
        )
    except asyncio.exceptions.TimeoutError:
        await instruction_msg.edit_text('Process Has Been Automatically Cancelled',
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#caption")]])
        )

@app.on_callback_query(filters.regex(r'^settings#button'))
async def display_button_settings(bot, query):
    """Displays options for managing custom buttons."""
    user_id = query.from_user.id
    buttons = []
    user_configs = await  db.get_configs(user_id)
    custom_button = user_configs.get('button')
    if custom_button:
        buttons.append([InlineKeyboardButton('👀 See Button', callback_data="settings#seebutton")])
        buttons[-1].append(InlineKeyboardButton('🗑️ Remove Button ', callback_data="settings#deletebutton"))
    else:
        buttons.append([InlineKeyboardButton('✚ Add Button ✚', callback_data="settings#addbutton")])
    buttons.append([InlineKeyboardButton('🔙 Back', callback_data="settings#main")])
    await query.message.edit_text(
        "<b><u>Custom Button</b></u>\n\nYou Can Set A Inline Button To Messages.\n\n<b><u>Format :</b></u>\n`[Madflix Botz][buttonurl:https://t.me/Madflix_Bots]`\n",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#addbutton'))
async def prompt_add_custom_button(bot, query):
    """Prompts the user to send a new custom button format."""
    user_id = query.from_user.id
    await query.message.delete()
    try:
        instruction_msg = await bot.send_message(
            user_id,
            text="**Send your custom button.**\n\n"
                 "**FORMAT:**\n"
                 "`[Forward Bot][buttonurl:https://t.me/KR_Forward_Bot]`"
        )

        button_input = await bot.listen(chat_id=user_id, timeout=300)
        parsed_button = parse_buttons(button_input.text)

        if not parsed_button:
            await button_input.delete()
            return await instruction_msg.edit_text(
                "❌ Invalid format.\n\nPlease use this format:\n"
                "`[Button Text][buttonurl:https://example.com]`",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton('🔙 Back', callback_data="settings#button")]]
                )
            )

        await update_user_configs(user_id, 'button', button_input.text)
        await button_input.delete()
        await instruction_msg.edit_text(
            "✅ Successfully Button Added",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton('🔙 Back', callback_data="settings#button")]]
            )
        )

    except asyncio.exceptions.TimeoutError:
        await instruction_msg.edit_text(
            '⏳ Process Has Been Automatically Cancelled',
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton('🔙 Back', callback_data="settings#button")]]
            )
        )


@app.on_callback_query(filters.regex(r'^settings#seebutton'))
async def display_current_button(bot, query):
    """Displays the currently set custom button."""
    user_id = query.from_user.id
    user_configs = await db.get_configs(user_id)
    button_html = user_configs.get('button') or ""

    parsed_buttons = parse_buttons(button_html, markup=False) or []
    parsed_buttons.append([InlineKeyboardButton("🔙 Back", "settings#button")])

    await query.message.edit_text(
        "**Your Custom Button:**",
        reply_markup=InlineKeyboardMarkup(parsed_buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#deletebutton'))
async def delete_custom_button(bot, query):
    """Deletes the custom button."""
    user_id = query.from_user.id
    await update_user_configs(user_id, 'button', None)
    await query.message.edit_text(
        "Successfully Button Deleted",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#button")]])
    )

@app.on_callback_query(filters.regex(r'^settings#database'))
async def display_database_settings(bot, query):
    """Displays options for managing the MongoDB database URL."""
    user_id = query.from_user.id
    buttons = []
    user_configs = await  db.get_configs(user_id)
    db_uri = user_configs.get('db_uri')
    if db_uri:
        buttons.append([InlineKeyboardButton('👀 See URL', callback_data="settings#seeurl")])
        buttons[-1].append(InlineKeyboardButton('🗑️ Remove URL', callback_data="settings#deleteurl"))
    else:
        buttons.append([InlineKeyboardButton('✚ Add URL ✚', callback_data="settings#addurl")])
    buttons.append([InlineKeyboardButton('🔙 Back', callback_data="settings#main")])
    await query.message.edit_text(
        "<b><u>Database</u></b>\n\nDatabase Is Required For Store Your Duplicate Messages Permanently. Otherwise Stored Duplicate Media May Be Disappeared When After Bot Restart.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#addurl'))
async def prompt_add_mongodb_url(bot, query):
    """Prompts the user to send their MongoDB URL."""
    user_id = query.from_user.id
    await query.message.delete()
    uri_input = await bot.ask(user_id, "<b>Please send your MongoDB URL.</b>\n\n<i>Get your Mongodb URL from [here](https://mongodb.com)</i>", disable_web_page_preview=True)
    if uri_input.text == "/cancel":
        return await uri_input.reply_text(
            "Process Cancelled !",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#database")]])
        )
    if not uri_input.text.startswith("mongodb+srv://") and not uri_input.text.endswith("majority"):
        return await uri_input.reply("Invalid Mongodb URL",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#database")]])
        )
    await update_user_configs(user_id, 'db_uri', uri_input.text)
    await uri_input.reply("Successfully Database URL Added ✅",
                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#database")]])
    )

@app.on_callback_query(filters.regex(r'^settings#seeurl'))
async def display_mongodb_url(bot, query):
    """Displays the currently set MongoDB URL."""
    user_id = query.from_user.id
    user_configs = await  db.get_configs(user_id)
    db_uri = user_configs.get('db_uri')
    await query.answer(f"Database URL : {db_uri}", show_alert=True)

@app.on_callback_query(filters.regex(r'^settings#deleteurl'))
async def delete_mongodb_url(bot, query):
    """Deletes the MongoDB URL."""
    user_id = query.from_user.id
    await update_user_configs(user_id, 'db_uri', None)
    await query.message.edit_text(
        "Successfully Your Database URL Deleted",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#database")]])
    )

@app.on_callback_query(filters.regex(r'^settings#filters'))
async def display_filter_settings(bot, query):
    """Displays the main filter settings."""
    user_id = query.from_user.id
    await query.message.edit_text(
        "<b><u>Custom Filters</u></b>\n\nConfigure The Type Of Messages Which You Want Forward",
        reply_markup=await generate_filter_buttons(user_id)
    )

@app.on_callback_query(filters.regex(r'^settings#nextfilters'))
async def display_extra_filter_settings(bot, query):
    """Displays extra filter settings."""
    user_id = query.from_user.id
    await query.edit_message_reply_markup(
        reply_markup=await generate_extra_filter_buttons(user_id)
    )

@app.on_callback_query(filters.regex(r'^settings#updatefilter-'))
async def update_filter_setting(bot, query):
    """Updates a specific filter setting."""
    user_id = query.from_user.id
    _, key, current_value_str = query.data.split('-')
    new_value = not (current_value_str == "True")
    await update_user_configs(user_id, key, new_value)
    if key in ['poll', 'protect']:
        return await query.edit_message_reply_markup(
            reply_markup=await generate_extra_filter_buttons(user_id)
        )
    await query.edit_message_reply_markup(
        reply_markup=await generate_filter_buttons(user_id)
    )

@app.on_callback_query(filters.regex(r'^settings#file_size'))
async def display_file_size_settings(bot, query):
    """Displays settings related to file size limits."""
    user_id = query.from_user.id
    user_configs = await  db.get_configs(user_id)
    size_limit_mb = user_configs.get('file_size', 0)
    limit_text, comparison_word = get_size_limit_display(user_configs.get('size_limit'))
    await query.message.edit_text(
        f'<b><u>Size Limit</u></b>\n\nYou Can Set File Size Limit To Forward\n\nStatus : Files With {comparison_word} `{size_limit_mb} MB` Will Forward',
        reply_markup=generate_size_adjustment_buttons(size_limit_mb)
    )

@app.on_callback_query(filters.regex(r'^settings#update_size-'))
async def update_file_size_limit(bot, query):
    """Updates the file size limit."""
    user_id = query.from_user.id
    new_size = int(query.data.split('-')[1])
    if not (0 <= new_size <= 2000):
        return await query.answer("Size Limit Exceeded (0-2000 MB)", show_alert=True)
    await update_user_configs(user_id, 'file_size', new_size)
    user_configs = await  db.get_configs(user_id)
    limit_text, comparison_word = get_size_limit_display(user_configs.get('size_limit'))
    await query.message.edit_text(
        f'<b><u>Size Limit</u></b>\n\nYou Can Set File Size Limit To Forward\n\nStatus : Files With {comparison_word} `{new_size} MB` Will Forward',
        reply_markup=generate_size_adjustment_buttons(new_size)
    )

@app.on_callback_query(filters.regex(r'^settings#update_limit-'))
async def update_size_limit_type(bot, query):
    """Updates whether files greater than, less than, or exactly a size are forwarded."""
    user_id = query.from_user.id
    _, limit_type, size_str = query.data.split('-')
    current_size = int(size_str)
    mapped_limit_type, display_word = get_size_limit_display(limit_type)
    await update_user_configs(user_id, 'size_limit', mapped_limit_type)
    await query.message.edit_text(
        f'<b><u>Size Limit</u></b>\n\nYou Can Set File Size Limit To Forward\n\nStatus : Files With {display_word} `{current_size} MB` Will Forward',
        reply_markup=generate_size_adjustment_buttons(current_size)
    )

@app.on_callback_query(filters.regex(r'^settings#add_extension'))
async def prompt_add_extensions(bot, query):
    """Prompts the user to send file extensions to filter."""
    user_id = query.from_user.id
    await query.message.delete()
    ext_input = await bot.ask(user_id, text="Please Send Your Extensions (Seperated By Space)")
    if ext_input.text == '/cancel':
        return await ext_input.reply_text(
            "Process Cancelled",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#get_extension")]])
        )
    new_extensions = ext_input.text.split(" ")
    user_configs = await  db.get_configs(user_id)
    current_extensions = user_configs.get('extension') or []
    current_extensions.extend(new_extensions)
    await update_user_configs(user_id, 'extension', current_extensions)
    await ext_input.reply_text(
        "Successfully Updated",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#get_extension")]])
    )

@app.on_callback_query(filters.regex(r'^settings#get_extension'))
async def display_extensions_settings(bot, query):
    """Displays the list of currently filtered extensions."""
    user_id = query.from_user.id
    user_configs = await  db.get_configs(user_id)
    extensions = user_configs.get('extension')
    buttons = create_dynamic_buttons_for_list(extensions)
    buttons.append([InlineKeyboardButton('✚ Add ✚', 'settings#add_extension')])
    buttons.append([InlineKeyboardButton('Remove All', 'settings#rmve_all_extension')])
    buttons.append([InlineKeyboardButton('🔙 Back', 'settings#main')])
    await query.message.edit_text(
        text='<b><u>Extensions</u></b>\n\nFiles With These Extensions Will Not Forward',
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#rmve_all_extension'))
async def remove_all_extensions(bot, query):
    """Removes all stored file extensions."""
    user_id = query.from_user.id
    await update_user_configs(user_id, 'extension', None)
    await query.message.edit_text(
        text="Successfully Deleted",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#get_extension")]])
    )

@app.on_callback_query(filters.regex(r'^settings#add_keyword'))
async def prompt_add_keywords(bot, query):
    """Prompts the user to send keywords to filter."""
    user_id = query.from_user.id
    await query.message.delete()
    keyword_input = await bot.ask(user_id, text="Please Send The Keywords (Seperated By Space)")
    if keyword_input.text == '/cancel':
        return await keyword_input.reply_text(
            "Process Canceled",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#get_keyword")]])
        )
    new_keywords = keyword_input.text.split(" ")
    user_configs = await  db.get_configs(user_id)
    current_keywords = user_configs.get('keywords') or []
    current_keywords.extend(new_keywords)
    await update_user_configs(user_id, 'keywords', current_keywords)
    await keyword_input.reply_text(
        "Successfully Updated",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#get_keyword")]])
    )

@app.on_callback_query(filters.regex(r'^settings#get_keyword'))
async def display_keywords_settings(bot, query):
    """Displays the list of currently filtered keywords."""
    user_id = query.from_user.id
    user_configs = await  db.get_configs(user_id)
    keywords = user_configs.get('keywords')
    buttons = create_dynamic_buttons_for_list(keywords)
    buttons.append([InlineKeyboardButton('✚ Add ✚', 'settings#add_keyword')])
    buttons.append([InlineKeyboardButton('Remove All', 'settings#rmve_all_keyword')])
    buttons.append([InlineKeyboardButton('🔙 Back', 'settings#main')])
    await query.message.edit_text(
        text='<b><u>Keywords</u></b>\n\nFile With These Keywords In File Name Will Forward',
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r'^settings#rmve_all_keyword'))
async def remove_all_keywords(bot, query):
    """Removes all stored keywords."""
    user_id = query.from_user.id
    await update_user_configs(user_id, 'keywords', None)
    await query.message.edit_text(
        text="Successfully Deleted",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data="settings#get_keyword")]])
    )

@app.on_callback_query(filters.regex(r'^settings#alert_'))
async def handle_alert_query(bot, query):
    """Handles alert callbacks to show simple pop-ups."""
    alert_text = query.data.split('_')[1]
    await query.answer(alert_text, show_alert=True)

# --- Button Generators ---

def generate_main_settings_buttons():
    """Generates the main settings menu inline keyboard."""
    buttons = [
        [
            InlineKeyboardButton('🤖 Bots', callback_data=f'settings#bots'),
            InlineKeyboardButton('🔥 Channels', callback_data=f'settings#channels')
        ],
        [
            InlineKeyboardButton('✏️ Caption', callback_data=f'settings#caption'),
            InlineKeyboardButton('🗃 MongoDB', callback_data=f'settings#database')
        ],
        [
            InlineKeyboardButton('🕵‍♀ Filters', callback_data=f'settings#filters'),
            InlineKeyboardButton('🏓 Button', callback_data=f'settings#button')
        ],
        [
            InlineKeyboardButton('⚙️ Extra Settings', callback_data='settings#nextfilters')
        ],
        [
            InlineKeyboardButton('🔙 Back', callback_data='back')
        ]
    ]
    return InlineKeyboardMarkup(buttons)

def get_size_limit_display(limit_value):
    """Helper to get display text for size limit."""
    if str(limit_value) == "None":
        return None, ""
    elif str(limit_value) == "True":
        return True, "more than"
    else:
        return False, "less than"

def create_dynamic_buttons_for_list(data_list):
    """Creates inline buttons for a list of items, splitting into rows."""
    row_size = 5
    buttons = []
    if data_list:
        for i, item in enumerate(data_list):
            if i % row_size == 0:
                buttons.append([])
            buttons[-1].append(InlineKeyboardButton(item, f'settings#alert_{item}'))
    return buttons

def generate_size_adjustment_buttons(current_size):
    """Generates inline buttons for adjusting file size limit."""
    buttons = [
        [
            InlineKeyboardButton('+', callback_data=f'settings#update_limit-True-{current_size}'),
            InlineKeyboardButton('=', callback_data=f'settings#update_limit-None-{current_size}'),
            InlineKeyboardButton('-', callback_data=f'settings#update_limit-False-{current_size}')
        ],
        [
            InlineKeyboardButton('+1', callback_data=f'settings#update_size-{current_size + 1}'),
            InlineKeyboardButton('-1', callback_data=f'settings#update_size-{current_size - 1}')
        ],
        [
            InlineKeyboardButton('+5', callback_data=f'settings#update_size-{current_size + 5}'),
            InlineKeyboardButton('-5', callback_data=f'settings#update_size-{current_size - 5}')
        ],
        [
            InlineKeyboardButton('+10', callback_data=f'settings#update_size-{current_size + 10}'),
            InlineKeyboardButton('-10', callback_data=f'settings#update_size-{current_size - 10}')
        ],
        [
            InlineKeyboardButton('+50', callback_data=f'settings#update_size-{current_size + 50}'),
            InlineKeyboardButton('-50', callback_data=f'settings#update_size-{current_size - 50}')
        ],
        [
            InlineKeyboardButton('+100', callback_data=f'settings#update_size-{current_size + 100}'),
            InlineKeyboardButton('-100', callback_data=f'settings#update_size-{current_size - 100}')
        ],
        [
            InlineKeyboardButton('↩ Back', callback_data="settings#filters")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

async def generate_filter_buttons(user_id):
    """Generates inline keyboard for main filter settings."""
    user_configs = await  db.get_configs(user_id)
    filters = user_configs.get('filters', {})
    buttons = [
        [
            InlineKeyboardButton('🏷️ Forward Tag', callback_data=f'settings_#updatefilter-forward_tag-{user_configs.get("forward_tag")}'),
            InlineKeyboardButton('✅' if user_configs.get('forward_tag') else '❌', callback_data=f'settings#updatefilter-forward_tag-{user_configs.get("forward_tag")}')
        ],
        [
            InlineKeyboardButton('🖍️ Texts', callback_data=f'settings_#updatefilter-text-{filters.get("text")}'),
            InlineKeyboardButton('✅' if filters.get('text') else '❌', callback_data=f'settings#updatefilter-text-{filters.get("text")}')
        ],
        [
            InlineKeyboardButton('📁 Documents', callback_data=f'settings_#updatefilter-document-{filters.get("document")}'),
            InlineKeyboardButton('✅' if filters.get('document') else '❌', callback_data=f'settings#updatefilter-document-{filters.get("document")}')
        ],
        [
            InlineKeyboardButton('🎞️ Videos', callback_data=f'settings_#updatefilter-video-{filters.get("video")}'),
            InlineKeyboardButton('✅' if filters.get('video') else '❌', callback_data=f'settings#updatefilter-video-{filters.get("video")}')
        ],
        [
            InlineKeyboardButton('📷 Photos', callback_data=f'settings_#updatefilter-photo-{filters.get("photo")}'),
            InlineKeyboardButton('✅' if filters.get('photo') else '❌', callback_data=f'settings#updatefilter-photo-{filters.get("photo")}')
        ],
        [
            InlineKeyboardButton('🎧 Audios', callback_data=f'settings_#updatefilter-audio-{filters.get("audio")}'),
            InlineKeyboardButton('✅' if filters.get('audio') else '❌', callback_data=f'settings#updatefilter-audio-{filters.get("audio")}')
        ],
        [
            InlineKeyboardButton('🎤 Voices', callback_data=f'settings_#updatefilter-voice-{filters.get("voice")}'),
            InlineKeyboardButton('✅' if filters.get('voice') else '❌', callback_data=f'settings#updatefilter-voice-{filters.get("voice")}')
        ],
        [
            InlineKeyboardButton('🎭 Animations', callback_data=f'settings_#updatefilter-animation-{filters.get("animation")}'),
            InlineKeyboardButton('✅' if filters.get('animation') else '❌', callback_data=f'settings#updatefilter-animation-{filters.get("animation")}')
        ],
        [
            InlineKeyboardButton('🃏 Stickers', callback_data=f'settings_#updatefilter-sticker-{filters.get("sticker")}'),
            InlineKeyboardButton('✅' if filters.get('sticker') else '❌', callback_data=f'settings#updatefilter-sticker-{filters.get("sticker")}')
        ],
        [
            InlineKeyboardButton('▶️ Skip Duplicate', callback_data=f'settings_#updatefilter-duplicate-{user_configs.get("duplicate")}'),
            InlineKeyboardButton('✅' if user_configs.get('duplicate') else '❌', callback_data=f'settings#updatefilter-duplicate-{user_configs.get("duplicate")}')
        ],
        [
            InlineKeyboardButton('🔙 Back', callback_data="settings#main")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

async def generate_extra_filter_buttons(user_id):
    """Generates inline keyboard for extra filter settings."""
    user_configs = await  db.get_configs(user_id)
    filters = user_configs.get('filters', {})
    buttons = [
        [
            InlineKeyboardButton('📊 Poll', callback_data=f'settings_#updatefilter-poll-{filters.get("poll")}'),
            InlineKeyboardButton('✅' if filters.get('poll') else '❌', callback_data=f'settings#updatefilter-poll-{filters.get("poll")}')
        ],
        [
            InlineKeyboardButton('🔒 Secure Message', callback_data=f'settings_#updatefilter-protect-{user_configs.get("protect")}'),
            InlineKeyboardButton('✅' if user_configs.get('protect') else '❌', callback_data=f'settings#updatefilter-protect-{user_configs.get("protect")}')
        ],
        [
            InlineKeyboardButton('🛑 Size Limit', callback_data='settings#file_size')
        ],
        [
            InlineKeyboardButton('💾 Extension', callback_data='settings#get_extension')
        ],
        [
            InlineKeyboardButton('📌 Keywords', callback_data='settings#get_keyword')
        ],
        [
            InlineKeyboardButton('🔙 Back', callback_data="settings#main")
        ]
    ]
    return InlineKeyboardMarkup(buttons)
