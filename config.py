import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- API CONFIGURATION ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
AUTHORIZED_CHAT_ID = os.getenv("AUTHORIZED_CHAT_ID", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLAMALAB_SECRET = os.getenv("LLAMALAB_SECRET", "")
LLAMALAB_EMAIL = os.getenv("LLAMALAB_EMAIL", "")

# --- ASSISTANT SETTINGS ---
WAKE_WORD = "hey assistant"
NAME = "Vibhath"  # Your name or assistant's user name

# --- PATHS ---
# Adjust these to your common folders
DESKTOP_PATH = os.path.join(os.environ['USERPROFILE'], 'Desktop')
DOCUMENTS_PATH = os.path.join(os.environ['USERPROFILE'], 'Documents')
DOWNLOADS_PATH = os.path.join(os.environ['USERPROFILE'], 'Downloads')
