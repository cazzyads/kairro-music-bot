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
# CONFIG
# =========================================================

COOKIES_FILE = os.getenv(
    "YOUTUBE_COOKIES_FILE",
    "cookies.txt",
)


# =========================================================
# TRACK
# =========================================================

@dataclass
class Track:
    title: str
    webpage_url: str
    stream_url: str
    duration: int
    requested_by: str
    source: str


# =========================================================
# MUSIC PLAYER
# =========================================================

class MusicPlayer:

    def __init__(self):
        self.client: Optional[Client] = None
        self.calls: Optional[PyTgCalls] = None

        # Queue per chat
        self.queues = defaultdict(deque)

        # Currently playing per chat
        self.current = {}

        # Lock per chat
        self.locks = defaultdict(asyncio.Lock)

        self.started = False

    # =====================================================
    # YOUTUBE OPTIONS
    # =====================================================

    @staticmethod
    def _youtube_options():

        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extract_flat": False,
            "geo_bypass": True,
            "nocheckcertificate": True,
        }

        if os.path.exists(COOKIES_FILE):

            options["cookiefile"] = COOKIES_FILE

            logger.info(
                "YouTube cookies ditemukan: %s",
                COOKIES_FILE,
            )

        return options

    # =====================================================
    # START
    # =====================================================

    async def start(self):

        if self.started:
            return

        logger.info("Starting Pyrogram...")

        if not TG_API_ID:
            raise RuntimeError(
                "TG_API_ID belum diatur."
            )

        if not TG_API_HASH:
            raise RuntimeError(
                "TG_API_HASH belum diatur."
            )

        if not SESSION_STRING:
            raise RuntimeError(
                "SESSION_STRING belum diatur."
            )

        logger.info("TG_API_ID ditemukan.")
        logger.info("TG_API_HASH ditemukan.")
        logger.info("SESSION_STRING ditemukan.")

        # =================================================
        # PYROGRAM USER CLIENT
        # =================================================

        self.client = Client(
            "music_user",
            api_id=TG_API_ID,
            api_hash=TG_API_HASH,
            session_string=SESSION_STRING,
            in_memory=True,
        )

        try:

            await self.client.start()

        except Exception as exc:

            logger.exception(
                "PYROGRAM START ERROR: %s",
                exc,
            )

            self.client = None

            raise

        logger.info(
            "Pyrogram connected."
        )

        # =================================================
        # ACCOUNT INFO
        # =================================================

        try:

            me = await self.client.get_me()

            username = (
                f"@{me.username}"
                if me.username
                else "@none"
            )

            logger.info(
                "Telegram account: %s | ID: %s | username: %s",
                me.first_name or "Unknown",
                me.id,
                username,
            )

        except Exception:

            logger.exception(
                "Failed getting Telegram account."
            )

        # =================================================
        # PYTGCALLS
        # =================================================

        try:

            self.calls = PyTgCalls(
                self.client
            )

            await self.calls.start()

        except Exception as exc:

            logger.exception(
                "PYTGCALLS START ERROR: %s",
                exc,
            )

            try:

                await self.client.stop()

            except Exception:

                pass

            self.calls = None
            self.client = None

            raise

        logger.info(
            "PyTgCalls started."
        )

        # =================================================
        # STREAM END HANDLER
        # =================================================

        @self.calls.on_update(
            tg_filters.stream_end()
        )
        async def stream_end_handler(
            _,
            update: StreamEnded,
        ):

            chat_id = update.chat_id

            logger.info(
                "Stream ended in chat %s",
                chat_id,
            )

            try:

                await self._play_next(
                    chat_id
                )

            except Exception:

                logger.exception(
                    "Failed playing next track in chat %s",
                    chat_id,
                )

        self.started = True

        logger.info(
            "Music engine ready."
        )

    # =====================================================
    # SHUTDOWN
    # =====================================================

    async def shutdown(self):

        logger.info(
            "Stopping music engine..."
        )

        # Leave active calls
        if self.calls:

            for chat_id in list(
                self.current.keys()
            ):

                try:

                    await self.calls.leave_call(
                        chat_id
                    )

                except Exception:

                    logger.debug(
                        "Failed leaving call %s",
                        chat_id,
                        exc_info=True,
                    )

        # Stop Pyrogram
        if self.client:

            try:

                await self.client.stop()

            except Exception:

                logger.exception(
                    "Failed stopping Pyrogram."
                )

        self.calls = None
        self.client = None

        self.started = False

        logger.info(
            "Music engine stopped."
        )

    # =====================================================
    # RESOLVE TRACK
    # =====================================================

    async def _resolve(
        self,
        query: str,
        source: str,
    ) -> Track:

        def work():

            query_clean = query.strip()

            if not query_clean:
                raise RuntimeError(
                    "Judul lagu tidak boleh kosong."
                )

            # =================================================
            # TARGET
            # =================================================

            if query_clean.startswith(
                (
                    "http://",
                    "https://",
                )
            ):

                target = query_clean

            elif source.lower() == "soundcloud":

                target = (
                    f"scsearch5:{query_clean}"
                )

            else:

                target = (
                    f"ytsearch5:{query_clean}"
                )

            # =================================================
            # SEARCH OPTIONS
            # =================================================

            if source.lower() == "youtube":

                search_options = (
                    self._youtube_options()
                )

            else:

                search_options = {
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                    "extract_flat": False,
                }

            logger.info(
                "Resolving %s: %s",
                source,
                target,
            )

            # =================================================
            # SEARCH
            # =================================================

            with yt_dlp.YoutubeDL(
                search_options
            ) as ydl:

                info = ydl.extract_info(
                    target,
                    download=False,
                )

            if not info:

                raise RuntimeError(
                    "Lagu tidak ditemukan."
                )

            # =================================================
            # SEARCH RESULT
            # =================================================

            if info.get("entries"):

                entries = [
                    entry
                    for entry in info["entries"]
                    if entry
                ]

                if not entries:

                    raise RuntimeError(
                        "Tidak ada hasil lagu."
                    )

                info = entries[0]

            # =================================================
            # WEBPAGE URL
            # =================================================

            webpage_url = (
                info.get("webpage_url")
                or info.get("original_url")
                or info.get("url")
            )

            if not webpage_url:

                raise RuntimeError(
                    "URL lagu tidak ditemukan."
                )

            logger.info(
                "Extracting audio: %s",
                webpage_url,
            )

            # =================================================
            # STREAM OPTIONS
            # =================================================

            if source.lower() == "youtube":

                stream_options = (
                    self._youtube_options()
                )

            else:

                stream_options = {
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                    "extract_flat": False,
                }

            stream_options[
                "format"
            ] = "bestaudio/best"

            # =================================================
            # EXTRACT MEDIA
            # =================================================

            with yt_dlp.YoutubeDL(
                stream_options
            ) as ydl:

                media = ydl.extract_info(
                    webpage_url,
                    download=False,
                )

            if not media:

                raise RuntimeError(
                    "Gagal mengambil media."
                )

            # =================================================
            # STREAM URL
            # =================================================

            stream_url = media.get(
                "url"
            )

            # =================================================
            # FALLBACK FORMAT
            # =================================================

            if not stream_url:

                formats = (
                    media.get("formats")
                    or []
                )

                audio_formats = [
                    fmt
                    for fmt in formats
                    if fmt.get("url")
                    and fmt.get("acodec")
                    and fmt.get("acodec") != "none"
                ]

                if not audio_formats:

                    raise RuntimeError(
                        "Audio stream tidak tersedia."
                    )

                # Pilih format audio dengan bitrate
                # terbaik yang tersedia.
                audio_formats.sort(
                    key=lambda fmt: (
                        fmt.get("abr")
                        or 0
                    )
                )

                stream_url = (
                    audio_formats[-1]["url"]
                )

            # =================================================
            # INFO
            # =================================================

            title = (
                media.get("title")
                or info.get("title")
                or "Unknown"
            )

            duration = int(
                media.get("duration")
                or info.get("duration")
                or 0
            )

            return Track(
                title=title,
                webpage_url=webpage_url,
                stream_url=stream_url,
                duration=duration,
                requested_by="Unknown",
                source=source,
            )

        return await asyncio.to_thread(
            work
        )

    # =====================================================
    # ENQUEUE
    # =====================================================

    async def enqueue(
        self,
        chat_id: int,
        query: str,
        requested_by: str,
        source: str,
    ):

        if not self.started:

            raise RuntimeError(
                "Music engine belum siap."
            )

        track = await self._resolve(
            query,
            source,
        )

        track.requested_by = requested_by

        async with self.locks[chat_id]:

            # Tidak ada lagu aktif
            was_empty = (
                self.current.get(chat_id)
                is None
                and not self.queues[chat_id]
            )

            # Masukkan queue
            self.queues[chat_id].append(
                track
            )

            # Jika kosong, langsung mainkan
            if was_empty:

                await self._start_track_locked(
                    chat_id
                )

                position = 0

            else:

                position = len(
                    self.queues[chat_id]
                )

        return {
            "title": track.title,
            "requested_by": requested_by,
            "position": position,
        }

    # =====================================================
    # START TRACK
    # =====================================================

    async def _start_track_locked(
        self,
        chat_id: int,
    ):

        if not self.queues[chat_id]:

            self.current.pop(
                chat_id,
                None,
            )

            return

        track = self.queues[
            chat_id
        ].popleft()

        self.current[
            chat_id
        ] = track

        logger.info(
            "Playing '%s' in chat %s",
            track.title,
            chat_id,
        )

        if not self.calls:

            self.current.pop(
                chat_id,
                None,
            )

            raise RuntimeError(
                "PyTgCalls belum aktif."
            )

        # =================================================
        # MEDIA STREAM
        # =================================================

        try:

            stream = MediaStream(
                track.stream_url,
                AudioQuality.HIGH,
            )

        except Exception as exc:

            self.current.pop(
                chat_id,
                None,
            )

            logger.exception(
                "Failed creating MediaStream: %s",
                exc,
            )

            raise RuntimeError(
                f"Gagal membuat audio stream: {exc}"
            ) from exc

        # =================================================
        # PLAY
        # =================================================

        try:

            await self.calls.play(
                chat_id,
                stream,
            )

            logger.info(
                "Playback started: %s",
                track.title,
            )

        except Exception as exc:

            self.current.pop(
                chat_id,
                None,
            )

            logger.exception(
                "Failed to play '%s': %s",
                track.title,
                exc,
            )

            raise

    # =====================================================
    # PLAY NEXT
    # =====================================================

    async def _play_next(
        self,
        chat_id: int,
    ):

        async with self.locks[chat_id]:

            self.current.pop(
                chat_id,
                None,
            )

            # Tidak ada lagu berikutnya
            if not self.queues[chat_id]:

                logger.info(
                    "Queue empty in chat %s",
                    chat_id,
                )

                if self.calls:

                    try:

                        await self.calls.leave_call(
                            chat_id
                        )

                    except Exception:

                        pass

                return

            await self._start_track_locked(
                chat_id
            )

    # =====================================================
    # SKIP
    # =====================================================

    async def skip(
        self,
        chat_id: int,
    ):

        async with self.locks[chat_id]:

            if (
                not self.current.get(chat_id)
                and not self.queues[chat_id]
            ):

                return None

            # Ambil lagu berikutnya
            if not self.queues[chat_id]:

                self.current.pop(
                    chat_id,
                    None,
                )

                if self.calls:

                    try:

                        await self.calls.leave_call(
                            chat_id
                        )

                    except Exception:

                        pass

                return None

            next_track = self.queues[
                chat_id
            ].popleft()

            self.current[
                chat_id
            ] = next_track

            logger.info(
                "Skipping to '%s' in chat %s",
                next_track.title,
                chat_id,
            )

            if not self.calls:

                self.current.pop(
                    chat_id,
                    None,
                )

                raise RuntimeError(
                    "PyTgCalls belum aktif."
                )

            try:

                stream = MediaStream(
                    next_track.stream_url,
                    AudioQuality.HIGH,
                )

                await self.calls.play(
                    chat_id,
                    stream,
                )

                logger.info(
                    "Playback started after skip: %s",
                    next_track.title,
                )

                return next_track.title

            except Exception:

                self.current.pop(
                    chat_id,
                    None,
                )

                logger.exception(
                    "Failed playing next track after skip."
                )

                raise

    # =====================================================
    # STOP
    # =====================================================

    async def stop(
        self,
        chat_id: int,
    ):

        async with self.locks[chat_id]:

            self.queues[
                chat_id
            ].clear()

            self.current.pop(
                chat_id,
                None,
            )

            if self.calls:

                try:

                    await self.calls.leave_call(
                        chat_id
                    )

                except Exception:

                    pass

    # =====================================================
    # PAUSE
    # =====================================================

    async def pause(
        self,
        chat_id: int,
    ):

        if not self.current.get(chat_id):

            raise RuntimeError(
                "Tidak ada lagu yang sedang diputar."
            )

        if not self.calls:

            raise RuntimeError(
                "PyTgCalls belum aktif."
            )

        await self.calls.pause(
            chat_id
        )

    # =====================================================
    # RESUME
    # =====================================================

    async def resume(
        self,
        chat_id: int,
    ):

        if not self.current.get(chat_id):

            raise RuntimeError(
                "Tidak ada lagu yang sedang diputar."
            )

        if not self.calls:

            raise RuntimeError(
                "PyTgCalls belum aktif."
            )

        await self.calls.resume(
            chat_id
        )

    # =====================================================
    # QUEUE TEXT
    # =====================================================

    def queue_text(
        self,
        chat_id: int,
    ):

        current = self.current.get(
            chat_id
        )

        items = list(
            self.queues[chat_id]
        )

        if not current and not items:

            return (
                "📭 *Queue kosong.*"
            )

        lines = [
            "🎵 *Music Queue*"
        ]

        # =================================================
        # CURRENT
        # =================================================

        if current:

            lines.append(
                "\n▶️ *Sedang diputar:*"
            )

            lines.append(
                f"🎵 {current.title}"
            )

            if current.requested_by:

                lines.append(
                    f"👤 {current.requested_by}"
                )

        # =================================================
        # NEXT
        # =================================================

        if items:

            lines.append(
                "\n📜 *Berikutnya:*"
            )

            for index, track in enumerate(
                items[:10],
                1,
            ):

                lines.append(
                    f"{index}. {track.title}"
                )

        if len(items) > 10:

            lines.append(
                f"\n… dan "
                f"{len(items) - 10} "
                f"lagu lainnya."
            )

        return "\n".join(
            lines
        )
