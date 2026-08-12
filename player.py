import asyncio
import logging
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
# DATA LAGU
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

        self.queues = defaultdict(deque)
        self.current = {}

        self.locks = defaultdict(asyncio.Lock)

        self.started = False

    # =====================================================
    # START
    # =====================================================

    async def start(self):

        if self.started:
            return

        logger.info("Starting Pyrogram...")

        # -------------------------------------------------
        # CEK CONFIG
        # -------------------------------------------------

        if not TG_API_ID:
            raise RuntimeError("TG_API_ID belum diisi.")

        if not TG_API_HASH:
            raise RuntimeError("TG_API_HASH belum diisi.")

        if not SESSION_STRING:
            raise RuntimeError("SESSION_STRING belum diisi.")

        logger.info("TG_API_ID ditemukan.")
        logger.info("TG_API_HASH ditemukan.")
        logger.info("SESSION_STRING ditemukan.")

        # -------------------------------------------------
        # PYROGRAM CLIENT
        # -------------------------------------------------

        self.client = Client(
            "music_user",
            api_id=int(TG_API_ID),
            api_hash=TG_API_HASH,
            session_string=SESSION_STRING,
            in_memory=True,
        )

        # -------------------------------------------------
        # START PYROGRAM
        # -------------------------------------------------

        try:

            await self.client.start()

            logger.info(
                "Pyrogram connected."
            )

        except Exception as exc:

            logger.exception(
                "PYROGRAM START ERROR: %s",
                exc
            )

            raise

        # -------------------------------------------------
        # CEK AKUN TELEGRAM
        # -------------------------------------------------

        try:

            me = await self.client.get_me()

            logger.info(
                "Telegram account: %s | ID: %s | username: @%s",
                me.first_name or "Unknown",
                me.id,
                me.username or "none",
            )

        except Exception as exc:

            logger.exception(
                "Failed getting Telegram account information: %s",
                exc
            )

            try:
                await self.client.stop()
            except Exception:
                pass

            raise

        # -------------------------------------------------
        # PYTGCALLS
        # -------------------------------------------------

        logger.info(
            "Starting PyTgCalls..."
        )

        try:

            self.calls = PyTgCalls(
                self.client
            )

            await self.calls.start()

            logger.info(
                "PyTgCalls started."
            )

        except Exception as exc:

            logger.exception(
                "PYTGCALLS START ERROR: %s",
                exc
            )

            try:
                await self.client.stop()
            except Exception:
                pass

            raise

        # -------------------------------------------------
        # EVENT STREAM END
        # -------------------------------------------------

        @self.calls.on_update(
            tg_filters.stream_end()
        )
        async def stream_end_handler(
            _,
            update: StreamEnded
        ):

            chat_id = update.chat_id

            logger.info(
                "Stream ended in chat %s",
                chat_id
            )

            try:

                await self._play_next(
                    chat_id
                )

            except Exception:

                logger.exception(
                    "Failed playing next track in %s",
                    chat_id
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
            "Shutting down music engine..."
        )

        # -------------------------------------------------
        # LEAVE VOICE CHATS
        # -------------------------------------------------

        if self.calls:

            for chat_id in list(
                self.current.keys()
            ):

                try:

                    await self.calls.leave_call(
                        chat_id
                    )

                except Exception:

                    logger.exception(
                        "Failed leaving voice chat %s",
                        chat_id
                    )

        # -------------------------------------------------
        # STOP PYROGRAM
        # -------------------------------------------------

        if self.client:

            try:

                await self.client.stop()

            except Exception:

                logger.exception(
                    "Failed stopping Pyrogram"
                )

        self.client = None
        self.calls = None

        self.started = False

        logger.info(
            "Music engine stopped."
        )

    # =====================================================
    # YT-DLP OPTIONS
    # =====================================================

    @staticmethod
    def _search_options():

        return {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "extract_flat": False,
        }

    # =====================================================
    # RESOLVE LAGU
    # =====================================================

    async def _resolve(
        self,
        query: str,
        source: str
    ) -> Track:

        def work():

            search_options = (
                self._search_options()
            )

            # -------------------------------------------------
            # URL LANGSUNG
            # -------------------------------------------------

            if query.startswith(
                (
                    "http://",
                    "https://"
                )
            ):

                target = query

            # -------------------------------------------------
            # SOUNDCLOUD
            # -------------------------------------------------

            elif source == "soundcloud":

                target = (
                    f"scsearch5:{query}"
                )

            # -------------------------------------------------
            # YOUTUBE
            # -------------------------------------------------

            else:

                target = (
                    f"ytsearch5:{query}"
                )

            # -------------------------------------------------
            # SEARCH
            # -------------------------------------------------

            logger.info(
                "Searching %s: %s",
                source,
                query
            )

            with yt_dlp.YoutubeDL(
                search_options
            ) as ydl:

                info = ydl.extract_info(
                    target,
                    download=False
                )

            if not info:

                raise RuntimeError(
                    "Lagu tidak ditemukan."
                )

            # -------------------------------------------------
            # SEARCH RESULT
            # -------------------------------------------------

            if "entries" in info:

                entries = [
                    item
                    for item in info["entries"]
                    if item
                ]

                if not entries:

                    raise RuntimeError(
                        "Tidak ada hasil lagu."
                    )

                info = entries[0]

            # -------------------------------------------------
            # WEBPAGE URL
            # -------------------------------------------------

            webpage_url = (
                info.get("webpage_url")
                or info.get("original_url")
                or info.get("url")
            )

            if not webpage_url:

                raise RuntimeError(
                    "URL lagu tidak ditemukan."
                )

            # -------------------------------------------------
            # AMBIL AUDIO
            # -------------------------------------------------

            stream_options = {

                "quiet": True,

                "no_warnings": True,

                "noplaylist": True,

                "format": "bestaudio/best",
            }

            with yt_dlp.YoutubeDL(
                stream_options
            ) as ydl:

                media = ydl.extract_info(
                    webpage_url,
                    download=False
                )

            if not media:

                raise RuntimeError(
                    "Gagal mengambil media."
                )

            # -------------------------------------------------
            # STREAM URL
            # -------------------------------------------------

            stream_url = media.get(
                "url"
            )

            # -------------------------------------------------
            # FALLBACK FORMAT
            # -------------------------------------------------

            if not stream_url:

                formats = (
                    media.get("formats")
                    or []
                )

                audio_formats = [

                    fmt

                    for fmt in formats

                    if fmt.get("url")

                    and fmt.get(
                        "acodec"
                    ) != "none"
                ]

                if not audio_formats:

                    raise RuntimeError(
                        "Audio stream tidak tersedia."
                    )

                stream_url = (
                    audio_formats[-1]["url"]
                )

            # -------------------------------------------------
            # INFO LAGU
            # -------------------------------------------------

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

            logger.info(
                "Resolved track: %s",
                title
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
        source: str
    ):

        if not self.started:

            raise RuntimeError(
                "Music engine belum siap."
            )

        track = await self._resolve(
            query,
            source
        )

        track.requested_by = requested_by

        async with self.locks[chat_id]:

            was_empty = (

                not self.current.get(
                    chat_id
                )

                and not self.queues[
                    chat_id
                ]
            )

            self.queues[
                chat_id
            ].append(track)

            # -------------------------------------------------
            # LANGSUNG PLAY JIKA BELUM ADA
            # -------------------------------------------------

            if was_empty:

                await self._start_track_locked(
                    chat_id
                )

            # -------------------------------------------------
            # POSISI QUEUE
            # -------------------------------------------------

            if self.current.get(
                chat_id
            ):

                position = (
                    len(
                        self.queues[
                            chat_id
                        ]
                    ) + 1
                )

            else:

                position = len(
                    self.queues[
                        chat_id
                    ]
                )

        return {

            "title": track.title,

            "requested_by":
                requested_by,

            "position":
                position,
        }

    # =====================================================
    # START TRACK
    # =====================================================

    async def _start_track_locked(
        self,
        chat_id: int
    ):

        if not self.queues[
            chat_id
        ]:

            self.current.pop(
                chat_id,
                None
            )

            return

        track = (
            self.queues[
                chat_id
            ].popleft()
        )

        self.current[
            chat_id
        ] = track

        logger.info(
            "Playing '%s' in chat %s",
            track.title,
            chat_id
        )

        if not self.calls:

            raise RuntimeError(
                "PyTgCalls belum siap."
            )

        stream = MediaStream(

            track.stream_url,

            AudioQuality.HIGH,
        )

        try:

            await self.calls.play(
                chat_id,
                stream
            )

            logger.info(
                "Playback started: %s",
                track.title
            )

        except Exception:

            self.current.pop(
                chat_id,
                None
            )

            logger.exception(
                "Failed to play '%s'",
                track.title
            )

            # -------------------------------------------------
            # COBA LAGU BERIKUTNYA
            # -------------------------------------------------

            if self.queues[
                chat_id
            ]:

                await self._play_next(
                    chat_id
                )

            raise

    # =====================================================
    # PLAY NEXT
    # =====================================================

    async def _play_next(
        self,
        chat_id: int
    ):

        async with self.locks[
            chat_id
        ]:

            self.current.pop(
                chat_id,
                None
            )

            # -------------------------------------------------
            # QUEUE KOSONG
            # -------------------------------------------------

            if not self.queues[
                chat_id
            ]:

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
        chat_id: int
    ):

        async with self.locks[
            chat_id
        ]:

            if (

                not self.current.get(
                    chat_id
                )

                and not self.queues[
                    chat_id
                ]
            ):

                return None

            # -------------------------------------------------
            # LEAVE CALL
            # -------------------------------------------------

            if self.calls:

                try:

                    await self.calls.leave_call(
                        chat_id
                    )

                except Exception:

                    pass

            self.current.pop(
                chat_id,
                None
            )

            # -------------------------------------------------
            # QUEUE KOSONG
            # -------------------------------------------------

            if not self.queues[
                chat_id
            ]:

                return None

            await self._start_track_locked(
                chat_id
            )

            current = self.current.get(
                chat_id
            )

            if current:

                return current.title

            return None

    # =====================================================
    # STOP
    # =====================================================

    async def stop(
        self,
        chat_id: int
    ):

        async with self.locks[
            chat_id
        ]:

            self.queues[
                chat_id
            ].clear()

            self.current.pop(
                chat_id,
                None
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
        chat_id: int
    ):

        if not self.current.get(
            chat_id
        ):

            raise RuntimeError(
                "Tidak ada lagu yang sedang diputar."
            )

        if not self.calls:

            raise RuntimeError(
                "Music engine belum siap."
            )

        await self.calls.pause(
            chat_id
        )

    # =====================================================
    # RESUME
    # =====================================================

    async def resume(
        self,
        chat_id: int
    ):

        if not self.current.get(
            chat_id
        ):

            raise RuntimeError(
                "Tidak ada lagu yang sedang diputar."
            )

        if not self.calls:

            raise RuntimeError(
                "Music engine belum siap."
            )

        await self.calls.resume(
            chat_id
        )

    # =====================================================
    # QUEUE TEXT
    # =====================================================

    def queue_text(
        self,
        chat_id: int
    ):

        current = self.current.get(
            chat_id
        )

        items = list(
            self.queues[
                chat_id
            ]
        )

        # -------------------------------------------------
        # KOSONG
        # -------------------------------------------------

        if not current and not items:

            return (
                "📭 *Queue kosong.*"
            )

        lines = [
            "🎵 *Music Queue*"
        ]

        # -------------------------------------------------
        # CURRENT
        # -------------------------------------------------

        if current:

            lines.append(

                "\n▶️ *Sedang diputar:*\n"
                f"{current.title}"

            )

        # -------------------------------------------------
        # QUEUE
        # -------------------------------------------------

        if items:

            lines.append(
                "\n📜 *Berikutnya:*"
            )

            for index, track in enumerate(
                items[:10],
                1
            ):

                lines.append(
                    f"{index}. {track.title}"
                )

        # -------------------------------------------------
        # LEBIH DARI 10
        # -------------------------------------------------

        if len(items) > 10:

            lines.append(

                f"\n… dan "
                f"{len(items) - 10} "
                f"lagu lainnya."

            )

        return "\n".join(
            lines
        )
