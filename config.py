# created by vijay kumar
# Note if you are trying to deploy on vps then directly fill values in ("")

from os import getenv

API_ID = int(getenv("API_ID", ""))
API_HASH = getenv("API_HASH", "")
BOT_TOKEN = getenv("BOT_TOKEN", "")
OWNER_ID = list(map(int, getenv("OWNER_ID", "5914434064").split()))
MONGO_DB = getenv("MONGO_DB", "")
DB_NAME = getenv("DB_NAME", "vkkautoforwardbot")
LOG_GROUP = int(getenv("LOG_GROUP", ""))
CHANNEL_ID = getenv("CHANNEL_ID", "")
CHANNEL_LINK = getenv("CHANNEL_LINK", "")
CONTACT = getenv("CONTACT", "")
FREEMIUM_LIMIT = int(getenv("FREEMIUM_LIMIT", "0"))
PREMIUM_LIMIT = int(getenv("PREMIUM_LIMIT", "2000"))
WEBSITE_URL = getenv("WEBSITE_URL", "upshrink.com")
AD_API = getenv("AD_API", "52b4a2cf4687d81e7d3f8f2b7bc2943f618e78cb")
STRING = getenv("STRING", None)
YT_COOKIES = getenv("YT_COOKIES", None)
INSTA_COOKIES = getenv("INSTA_COOKIES", None)




CAPTION = (
    "🤖 <b>Auto Forward Bot – The Ultimate Message Forwarder!</b>\n\n"
    "✨ Automatically forward messages from:\n"
    "🔹 Public & Private Channels\n"
    "🔹 Groups and Users\n\n"
    "⚙️ <b>Powerful Features:</b>\n"
    "✅ Filter by text, media, or keywords\n"
    "✅ Forward photos, videos, documents, and more\n"
    "✅ Custom filtering support (attach your own filter file)\n"
    "✅ Supports multiple sources and destinations\n\n"
    "🚀 Set it up once and let the bot handle the rest!\n"
    "📎 Use /help to learn how to configure filters and start forwarding today."
)
