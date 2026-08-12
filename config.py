import os


# =========================
# TELEGRAM BOT
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()


# =========================
# TELEGRAM USER ACCOUNT
# =========================

TG_API_ID_RAW = os.getenv("TG_API_ID", "").strip()
TG_API_HASH = os.getenv("TG_API_HASH", "").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()


# =========================
# VALIDASI API ID
# =========================

try:
    TG_API_ID = int(TG_API_ID_RAW)
except (ValueError, TypeError):
    TG_API_ID = 0


# =========================
# VALIDASI CONFIG
# =========================

def validate_config():
    missing = []

    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")

    if not TG_API_ID:
        missing.append("TG_API_ID")

    if not TG_API_HASH:
        missing.append("TG_API_HASH")

    if not SESSION_STRING:
        missing.append("SESSION_STRING")

    if missing:
        raise RuntimeError(
            "Environment variable belum lengkap: "
            + ", ".join(missing)
        )
