DEFAULT_CONFIGS = {
    'caption': None,
    'duplicate': True,
    'forward_tag': False,
    'file_size': 0,
    'size_limit': None,
    'extension': None,
    'keywords': None,
    'protect': None,
    'button': None,
    'db_uri': None,
    'filters': {
        'poll': True, 'text': True, 'audio': True, 'voice': True,
        'video': True, 'photo': True, 'document': True,
        'animation': True, 'sticker': True
    }
}





from config import MONGO_DB, DB_NAME
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import json
import gc
import os


class Database:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name].db
        self.token = self._client[database_name].token
        self.bots = self._client[database_name].bots
        self.user_bots = self._client[database_name].user_bots
        self.notify = self._client[database_name].notify
        self.channels = self._client[database_name].channels

    async def mongodb_version(self):
        return (await self._client.server_info())['version']

    async def create_ttl_index(self):
        """Ensure the TTL index exists for the `tokens` collection."""
        await self.token.create_index("expires_at", expireAfterSeconds=0)

    async def is_user_verified(self, user_id):
        """Checks if a user exists in the 'db' collection."""
        user = await self.token.find_one({'user_id': int(user_id)})
        return bool(user)

    
    # --- Functions for 'db' collection (consolidated user data) ---

    async def get_data(self, user_id):
        """
        Fetches all data for a given user from the 'db' collection.
        This serves as the primary way to retrieve a user's document.
        """
        return await self.db.find_one({"user_id": user_id})

    def new_user_document(self, user_id, name):
        """
        Creates a new user document structure with default values.
        This will be stored in the 'db' collection.
        """
        return {
            "user_id": user_id,
            "name": name,
            "ban_status": {
                "is_banned": False,
                "ban_reason": "",
            },
            # Initialize other fields that might be added later, to ensure consistency
            "thumb": None,
            "caption": None,
            "replace_txt": None,
            "to_replace": None,
            "session": None, # For Pyrogram session
            "userbot_token": None, # For userbot token
            "user_session_string": None, # For the "real" user session (if different from 'session')
            "clean_words": [],
            "configs": DEFAULT_CONFIGS
        }

    async def add_user(self, user_id, name):
        """Adds a new user document to 'db' if they don't already exist."""
        if not await self.is_user_exist(user_id):
            user_doc = self.new_user_document(user_id, name)
            await self.db.insert_one(user_doc)



    async def update_user(self, user_id, data):
        """update user document to 'db' """
        await self.add_user(user_id, data["name"])
        await self.db.update_one(
            {"user_id": user_id},
            {"$set": user_doc}
        )
       
    


    
    async def is_user_exist(self, user_id):
        """Checks if a user exists in the 'db' collection."""
        user = await self.db.find_one({'user_id': int(user_id)})
        return bool(user)

    async def delete_user(self, user_id):
        """Deletes a user's entire document from 'db'."""
        await self.db.delete_many({'user_id': int(user_id)})

    async def total_users_count(self):
        """Returns the total number of users in 'db'."""
        return await self.db.count_documents({})

    # --- User-specific data setters/getters (all targeting 'db') ---

    async def set_thumbnail(self, user_id, thumb):
        await self.db.update_one(
            {"user_id": user_id},
            {"$set": {"thumb": thumb}},
            upsert=True
        )

    async def remove_thumbnail(self, user_id):
        await self.db.update_one({"user_id": user_id}, {"$unset": {"thumb": ""}})

    async def set_caption(self, user_id, caption):
        await self.db.update_one(
            {"user_id": user_id},
            {"$set": {"caption": caption}},
            upsert=True
        )

    async def remove_caption(self, user_id):
        await self.db.update_one({"user_id": user_id}, {"$unset": {"caption": ""}})

    async def replace_caption(self, user_id, replace_txt, to_replace):
        await self.db.update_one(
            {"user_id": user_id},
            {"$set": {"replace_txt": replace_txt, "to_replace": to_replace}},
            upsert=True
        )

    async def remove_replace(self, user_id):
        await self.db.update_one({"user_id": user_id}, {"$unset": {"replace_txt": "", "to_replace": ""}})

    async def set_session(self, user_id, session):
        """Set Pyrogram session string in the user's document."""
        await self.db.update_one(
            {"user_id": user_id},
            {"$set": {"session": session}},
            upsert=True
        )

    async def save_userbot_token(self, user_id, token_string):
        """Set userbot_token string in the user's document."""
        await self.db.update_one(
            {"user_id": user_id},
            {"$set": {"userbot_token": token_string}},
            upsert=True
        )

    async def get_sessions(self, user_id):
        """
        Retrieves Pyrogram and userbot sessions from the user's document.
        Returns a dict with session info or None if not found.
        """
        try:
            print(f"🔍 Fetching sessions for user {user_id}...")
            data = await self.db.find_one({"user_id": user_id})

            if not data:
                print("❌ No session data found for this user in database.")
                return None

            sessions = {
                "userbot_token": data.get("userbot_token"),
                "pyro_session": data.get("session"),
                "has_pyro": bool(data.get("session"))
            }
            print(f"Pyrogram: {'✅' if sessions['has_pyro'] else '❌'}")
            return sessions

        except Exception as e:
            print(f"⚠️ Error fetching sessions for user {user_id}: {e}")
            return None

    async def remove_pyro_session(self, user_id):
        """Removes the Pyrogram session from the user's document."""
        await self.db.update_one(
            {"user_id": user_id},
            {"$unset": {"session": ""}}
        )

    async def remove_session(self, user_id):
        """Alias for remove_pyro_session, removes the 'session' field."""
        await self.remove_pyro_session(user_id)

    async def clean_words(self, user_id, new_clean_words):
        """Adds new clean words to the user's document."""
        data = await self.get_data(user_id)
        existing_words = data.get("clean_words", []) if data else []
        updated_words = list(set(existing_words + new_clean_words))
        await self.db.update_one({"user_id": user_id}, {"$set": {"clean_words": updated_words}}, upsert=True)

    async def remove_clean_words(self, user_id, words_to_remove):
        """Removes specific clean words from the user's document."""
        data = await self.get_data(user_id)
        existing_words = data.get("clean_words", []) if data else []
        updated_words = [word for word in existing_words if word not in words_to_remove]
        await self.db.update_one({"user_id": user_id}, {"$set": {"clean_words": updated_words}}, upsert=True)

    async def all_words_remove(self, user_id):
        """Removes all clean words from the user's document."""
        await self.db.update_one({"user_id": user_id}, {"$unset": {"clean_words": ""}})

    # --- Ban Status Functions (all targeting 'db') ---

    async def remove_ban(self, user_id):
        """Removes ban status for a user."""
        ban_status = {
            "is_banned": False,
            "ban_reason": ''
        }
        await self.db.update_one({'user_id': user_id}, {'$set': {'ban_status': ban_status}})

    async def ban_user(self, user_id, ban_reason="No Reason"):
        """Bans a user with a given reason."""
        ban_status = {
            "is_banned": True,
            "ban_reason": ban_reason
        }
        await self.db.update_one({'user_id': user_id}, {'$set': {'ban_status': ban_status}})

    async def get_ban_status(self, user_id):
        """Retrieves the ban status for a user."""
        default = {
            "is_banned": False,
            "ban_reason": ''
        }
        user = await self.db.find_one({'user_id': int(user_id)})
        return user.get('ban_status', default) if user else default

    async def get_all_users(self):
        """Returns a cursor for all user documents in 'db'."""
        return self.db.find({})

    async def get_banned(self):
        """Returns a list of IDs for all banned users."""
        users = self.db.find({'ban_status.is_banned': True})
        b_users = [user['user_id'] async for user in users]
        return b_users

    # --- Configuration Functions (all targeting 'db') ---

    async def update_configs(self, user_id, configs):
        """Updates the configuration settings for a user."""
        await self.db.update_one({'user_id': int(user_id)}, {'$set': {'configs': configs}})

    async def update_configs_for_all(self, configs: dict):
    """Updates the 'configs' field for all users in the database."""
    await self.db.update_many(
        {},  # empty filter matches all documents
        {'$set': {'configs': configs}}
    )

    async def get_configs(self, user_id):
        """Retrieves the configuration settings for a user, or defaults if not set."""
        user = await self.db.find_one({'user_id': int(user_id)})
        return user.get('configs', DEFAULT_CONFIGS) if user else DEFAULT_CONFIGS

    async def get_filters(self, user_id):
        """Returns a list of filters that are currently disabled for a user."""
        filters_list = []
        filter_configs = (await self.get_configs(user_id))['filters']
        for k, v in filter_configs.items():
            if not v: # If filter is False (i.e., disabled)
                filters_list.append(str(k))
        return filters_list

    # --- Bot-related Functions (still in 'bots' collection) ---

    async def total_users_bots_count(self):
        """Returns counts of total users and bots."""
        bcount = await self.bots.count_documents({})
        # Count users from the main 'db' collection
        ucount = await self.db.count_documents({})
        return ucount, bcount

    async def add_bot(self, datas):
        """Adds a new bot to the 'bots' collection if it doesn't already exist."""
        if not await self.is_bot_exist(datas['user_id']):
            await self.bots.insert_one(datas)

    async def remove_bot(self, user_id):
        """Removes a bot from the 'bots' collection."""
        await self.bots.delete_many({'user_id': int(user_id)})

    async def get_bot(self, user_id: int):
        """Retrieves bot data from the 'bots' collection."""
        return await self.bots.find_one({'user_id': user_id})

    async def is_bot_exist(self, user_id):
        """Checks if a bot exists in the 'bots' collection."""
        return bool(await self.bots.find_one({'user_id': user_id}))





    # --- User Bot-related Functions ---

    async def total_users_userbots_count(self):
        """Returns counts of total users and bots."""
        bcount = await self.bots.count_documents({})
        ubcount = await self.user_bots.count_documents({})
        # Count users from the main 'db' collection
        ucount = await self.db.count_documents({})
        return ucount, bcount, ubcount

    async def add_userbot(self, datas):
        """Adds a new bot to the 'bots' collection if it doesn't already exist."""
        if not await self.is_userbot_exist(datas['user_id']):
            await self.user_bots.insert_one(datas)

    async def remove_userbot(self, user_id):
        """Removes a bot from the 'bots' collection."""
        await self.user_bots.delete_many({'user_id': int(user_id)})

    async def get_userbot(self, user_id: int):
        """Retrieves bot data from the 'bots' collection."""
        return await self.user_bots.find_one({'user_id': user_id})

    async def is_userbot_exist(self, user_id):
        """Checks if a bot exists in the 'bots' collection."""
        return bool(await self.user_bots.find_one({'user_id': user_id}))


    
    # --- Channel-related Functions (still in 'channels' collection) ---

    async def total_channels(self):
        """Returns the total number of channels."""
        return await self.channels.count_documents({})

    async def in_channel(self, user_id: int, chat_id: int) -> bool:
        """Checks if a channel is associated with a user."""
        return bool(await self.channels.find_one({"user_id": int(user_id), "chat_id": int(chat_id)}))

    async def add_channel(self, user_id: int, chat_id: int, title, username):
        """Adds a channel for a user if it doesn't already exist."""
        if await self.in_channel(user_id, chat_id):
            return False
        return await self.channels.insert_one({"user_id": user_id, "chat_id": chat_id, "title": title, "username": username})

    async def remove_channel(self, user_id: int, chat_id: int):
        """Removes a channel associated with a user."""
        if not await self.in_channel(user_id, chat_id):
            return False
        return await self.channels.delete_many({"user_id": int(user_id), "chat_id": int(chat_id)})

    async def get_channel_details(self, user_id: int, chat_id: int):
        """Retrieves details of a specific channel for a user."""
        return await self.channels.find_one({"user_id": int(user_id), "chat_id": int(chat_id)})

    async def get_user_channels(self, user_id: int):
        """Returns a list of channels associated with a user."""
        channels_cursor = self.channels.find({"user_id": int(user_id)})
        return [channel async for channel in channels_cursor]

    # --- Notification-related Functions (still in 'notify' collection) ---

    async def add_frwd(self, user_id):
        """Adds a user to the forward notification list."""
        return await self.notify.insert_one({'user_id': int(user_id)})

    async def rmve_frwd(self, user_id=0, all=False):
        """Removes a user from the forward notification list, or all users."""
        data = {} if all else {'user_id': int(user_id)}
        return await self.notify.delete_many(data)

    async def get_all_frwd(self):
        """Returns a cursor for all users in the forward notification list."""
        return self.notify.find({})


# Initialize the Database instance for use throughout your application
db = Database(MONGO_DB, DB_NAME)
