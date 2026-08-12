import asyncio
import logging
import os
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional

import yt_dlp

from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls import filters as tg_filters
from pytgcalls.types import AudioQuality, MediaStream, StreamEnded

from config import TG_API_ID, TG_API_HASH, SESSION_STRING

logger = logging.getLogger("musicbot.player")

# =========================================================
# YOUTUBE COOKIES (Railway Variables)
# =========================================================

COOKIES_FILE = os.getenv(
    "YOUTUBE_COOKIES_FILE",
    "cookies.txt"
)

YOUTUBE_COOKIES = os.getenv("YOUTUBE_COOKIES")

# Buat cookies.txt otomatis dari Railway Variables
if YOUTUBE_COOKIES:
    try:
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            f.write(YOUTUBE_COOKIES)
        logger.info("YouTube cookies dibuat dari Railway Variables.")
    except Exception as e:
        logger.error(f"Gagal membuat cookies.txt: {e}")

# =========================================================
# YT-DLP OPTIONS
# =========================================================

def get_ytdlp_options():
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": False,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "format": "bestaudio/best",
    }

    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
        logger.info("Menggunakan cookies YouTube: %s", COOKIES_FILE)
    else:
        logger.warning("cookies.txt tidak ditemukan, menggunakan mode tanpa cookies.")

    return opts
