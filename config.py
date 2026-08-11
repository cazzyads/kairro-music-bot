import os

# ==============================
# TELEGRAM BOT
# ==============================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ==============================
# TELEGRAM API
# ==============================

API_ID = os.getenv("API_ID", "")
API_HASH = os.getenv("API_HASH", "")

# ==============================
# BOT
# ==============================

BOT_NAME = "KAIRO MUSIC"

# ==============================
# DATABASE
# ==============================

DATABASE_FILE = "musicbot.db"

# ==============================
# MEDIA
# ==============================

DOWNLOAD_DIR = "downloads"

MAX_QUEUE_SIZE = 50

DEFAULT_VOLUME = 100


# ==============================
# VALIDATION
# ==============================

if not BOT_TOKEN:
    print("WARNING: BOT_TOKEN belum diatur.")

if not API_ID:
    print("WARNING: API_ID belum diatur.")

if not API_HASH:
    print("WARNING: API_HASH belum diatur.")
