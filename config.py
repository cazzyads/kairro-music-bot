import os

# ==============================
# BOT CONFIGURATION
# ==============================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Nama bot
BOT_NAME = "KAIRO MUSIC"

# Database
DATABASE_FILE = "musicbot.db"

# Folder temporary untuk file audio/video
DOWNLOAD_DIR = "downloads"

# Maximum queue per group
MAX_QUEUE_SIZE = 50

# Default volume
DEFAULT_VOLUME = 100

# ==============================
# VALIDATION
# ==============================

if not BOT_TOKEN:
    print("WARNING: BOT_TOKEN belum diatur.")
