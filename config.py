import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot & API Configuration
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Admin IDs (as a list of integers)
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
try:
    ADMIN_IDS = list(map(int, ADMIN_IDS_RAW.split(",")))
except ValueError:
    raise ValueError("Invalid ADMIN_IDS. Must be comma-separated integers.")

# Spotify API
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# MongoDB
MONGO_URL = os.getenv("MONGO_URL")

# Command Prefix Support
COMMAND_PREFIX_RAW = os.getenv("COMMAND_PREFIX", "!|.|#|,|/")
COMMAND_PREFIX = [prefix.strip() for prefix in COMMAND_PREFIX_RAW.split("|") if prefix.strip()]

print("Loaded COMMAND_PREFIX:", COMMAND_PREFIX)

if not COMMAND_PREFIX:
    raise ValueError("Sorry Bro No Command Prefix Found. First Fix It!")

# YouTube cookies file path (if required for yt-dlp or similar)
YT_COOKIES_PATH = "./cookies/ItsSmartToolBot.txt"
