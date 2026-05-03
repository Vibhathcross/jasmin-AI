import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- API CONFIGURATION ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your_gemini_api_key_here")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your_telegram_bot_token_here")
AUTHORIZED_CHAT_ID = os.getenv("AUTHORIZED_CHAT_ID", "")

# --- ASSISTANT SETTINGS ---
WAKE_WORD = "hey assistant"
NAME = "Vibhath"  # Your name or assistant's user name

# --- PATHS ---
# Adjust these to your common folders
DESKTOP_PATH = os.path.join(os.environ['USERPROFILE'], 'Desktop')
DOCUMENTS_PATH = os.path.join(os.environ['USERPROFILE'], 'Documents')
DOWNLOADS_PATH = os.path.join(os.environ['USERPROFILE'], 'Downloads')
