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

COOKIES_FILE = os.getenv("YOUTUBE_COOKIES_FILE", "cookies.txt")
YOUTUBE_COOKIES = os.getenv("YOUTUBE_COOKIES")

if YOUTUBE_COOKIES:
    try:
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            f.write(YOUTUBE_COOKIES)
        logger.info("YouTube cookies dibuat dari Railway Variables.")
    except Exception as e:
        logger.error(f"Gagal membuat cookies.txt: {e}")


def ytdlp_options():
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
    return opts


@dataclass
class Track:
    title: str
    webpage_url: str
    stream_url: str
    duration: int
    requested_by: str
    source: str


class MusicPlayer:
    def __init__(self):
        self.client: Optional[Client] = None
        self.calls: Optional[PyTgCalls] = None
        self.queues = defaultdict(deque)
        self.current = {}
        self.locks = defaultdict(asyncio.Lock)
        self.started = False

    async def start(self):
        if self.started:
            return

        self.client = Client(
            "music_user",
            api_id=TG_API_ID,
            api_hash=TG_API_HASH,
            session_string=SESSION_STRING,
            in_memory=True,
        )

        await self.client.start()
        logger.info("Pyrogram connected.")

        me = await self.client.get_me()
        logger.info(
            "Telegram account: %s | ID: %s | username: @%s",
            me.first_name,
            me.id,
            me.username,
        )

        self.calls = PyTgCalls(self.client)
        await self.calls.start()
        logger.info("PyTgCalls started.")

        @self.calls.on_update(tg_filters.stream_end())
        async def stream_end(_, update: StreamEnded):
            await self._play_next(update.chat_id)

        self.started = True
        logger.info("Music engine ready.")

    async def shutdown(self):
        if self.calls:
            try:
                for chat_id in list(self.current.keys()):
                    await self.calls.leave_call(chat_id)
            except Exception:
                pass

        if self.client:
            await self.client.stop()

        self.started = False

    async def _resolve(self, query: str, source: str):
        def work():
            target = (
                query
                if query.startswith(("http://", "https://"))
                else (f"scsearch5:{query}" if source == "soundcloud" else f"ytsearch5:{query}")
            )

            with yt_dlp.YoutubeDL(ytdlp_options()) as ydl:
                info = ydl.extract_info(target, download=False)

            if "entries" in info:
                info = next((e for e in info["entries"] if e), None)

            if not info:
                raise RuntimeError("Lagu tidak ditemukan.")

            webpage = info.get("webpage_url") or info.get("url")

            with yt_dlp.YoutubeDL(ytdlp_options()) as ydl:
                media = ydl.extract_info(webpage, download=False)

            stream = media.get("url")
            if not stream:
                for f in reversed(media.get("formats", [])):
                    if f.get("url") and f.get("acodec") != "none":
                        stream = f["url"]
                        break

            if not stream:
                raise RuntimeError("Audio stream tidak tersedia.")

            return Track(
                title=media.get("title", "Unknown"),
                webpage_url=webpage,
                stream_url=stream,
                duration=int(media.get("duration") or 0),
                requested_by="Unknown",
                source=source,
            )

        return await asyncio.to_thread(work)

    async def enqueue(self, chat_id, query, requested_by, source):
        track = await self._resolve(query, source)
        track.requested_by = requested_by

        async with self.locks[chat_id]:
            empty = not self.current.get(chat_id) and not self.queues[chat_id]
            self.queues[chat_id].append(track)

            if empty:
                await self._start_track_locked(chat_id)
                pos = 0
            else:
                pos = len(self.queues[chat_id])

        return {"title": track.title, "position": pos}

    async def _start_track_locked(self, chat_id):
        if not self.queues[chat_id]:
            self.current.pop(chat_id, None)
            return

        track = self.queues[chat_id].popleft()
        self.current[chat_id] = track

        stream = MediaStream(track.stream_url, AudioQuality.HIGH)
        await self.calls.play(chat_id, stream)

    async def _play_next(self, chat_id):
        async with self.locks[chat_id]:
            self.current.pop(chat_id, None)

            if not self.queues[chat_id]:
                try:
                    await self.calls.leave_call(chat_id)
                except Exception:
                    pass
                return

            await self._start_track_locked(chat_id)

    async def skip(self, chat_id):
        await self._play_next(chat_id)

    async def stop(self, chat_id):
        async with self.locks[chat_id]:
            self.queues[chat_id].clear()
            self.current.pop(chat_id, None)
            try:
                await self.calls.leave_call(chat_id)
            except Exception:
                pass

    async def pause(self, chat_id):
        await self.calls.pause(chat_id)

    async def resume(self, chat_id):
        await self.calls.resume(chat_id)

    def queue_text(self, chat_id):
        current = self.current.get(chat_id)
        items = list(self.queues[chat_id])

        if not current and not items:
            return "📭 Queue kosong."

        text = ["🎵 Music Queue"]

        if current:
            text.append(f"\\n▶️ Sedang diputar: {current.title}")

        if items:
            text.append("\\n📜 Berikutnya:")
            for i, t in enumerate(items, 1):
                text.append(f"{i}. {t.title}")

        return "\\n".join(text)
