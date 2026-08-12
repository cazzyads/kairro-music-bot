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
# YOUTUBE COOKIES
# =========================================================

COOKIES_FILE = os.getenv("YOUTUBE_COOKIES_FILE", "cookies.txt")
YOUTUBE_COOKIES = os.getenv("YOUTUBE_COOKIES", "").strip()


def prepare_cookies():
    """
    Membuat cookies.txt dari Railway Variable YOUTUBE_COOKIES.
    """

    if not YOUTUBE_COOKIES:
        logger.warning(
            "YOUTUBE_COOKIES tidak ditemukan. "
            "YouTube mungkin menolak request."
        )
        return

    try:
        with open(COOKIES_FILE, "w", encoding="utf-8") as file:
            file.write(YOUTUBE_COOKIES)

        logger.info("YouTube cookies berhasil disiapkan.")

    except Exception as exc:
        logger.exception(
            "Gagal membuat file YouTube cookies: %s",
            exc,
        )


prepare_cookies()


# =========================================================
# YT-DLP OPTIONS
# =========================================================

def ytdlp_options():
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": False,
        "geo_bypass": True,
        "nocheckcertificate": True,

        # Audio
        "format": "bestaudio/best",

        # Jangan download file.
        "skip_download": True,

        # User-Agent browser biasa.
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        },
    }

    if os.path.exists(COOKIES_FILE):
        options["cookiefile"] = COOKIES_FILE

    return options


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

        self.queues = defaultdict(deque)
        self.current = {}

        self.locks = defaultdict(asyncio.Lock)

        self.started = False

    # =====================================================
    # START
    # =====================================================

    async def start(self):

        if self.started:
            logger.info("Music player sudah berjalan.")
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

        if os.path.exists(COOKIES_FILE):
            logger.info(
                "YouTube cookies file ditemukan: %s",
                COOKIES_FILE,
            )
        else:
            logger.warning(
                "cookies.txt tidak ditemukan."
            )

        # -------------------------------------------------
        # PYROGRAM
        # -------------------------------------------------

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

            raise

        logger.info("Pyrogram connected.")

        # -------------------------------------------------
        # ACCOUNT INFO
        # -------------------------------------------------

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

        except Exception as exc:
            logger.warning(
                "Gagal mendapatkan info akun: %s",
                exc,
            )

        # -------------------------------------------------
        # PYTGCALLS
        # -------------------------------------------------

        try:
            self.calls = PyTgCalls(self.client)

            await self.calls.start()

            logger.info(
                "PyTgCalls started."
            )

        except Exception as exc:
            logger.exception(
                "PYTGCALLS START ERROR: %s",
                exc,
            )

            try:
                await self.client.stop()
            except Exception:
                pass

            self.client = None

            raise

        # -------------------------------------------------
        # STREAM END EVENT
        # -------------------------------------------------

        @self.calls.on_update(
            tg_filters.stream_end()
        )
        async def stream_end_handler(
            _,
            update: StreamEnded,
        ):
            try:
                await self._play_next(
                    update.chat_id
                )

            except Exception:
                logger.exception(
                    "Error saat memainkan lagu berikutnya."
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
            "Shutting down music player..."
        )

        if self.calls:

            for chat_id in list(
                self.current.keys()
            ):
                try:
                    await self.calls.leave_call(
                        chat_id
                    )

                except Exception:
                    pass

        self.current.clear()

        for queue in self.queues.values():
            queue.clear()

        if self.client:

            try:
                await self.client.stop()

            except Exception:
                pass

        self.client = None
        self.calls = None
        self.started = False

        logger.info(
            "Music player stopped."
        )

    # =====================================================
    # RESOLVE SONG
    # =====================================================

    async def _resolve(
        self,
        query: str,
        source: str,
    ):

        # Simpan query lokal supaya tidak pernah
        # terkena UnboundLocalError.
        search_query = str(
            query or ""
        ).strip()

        if not search_query:
            raise ValueError(
                "Judul lagu atau URL kosong."
            )

        source = (
            source or "youtube"
        ).lower().strip()

        def work():

            # ---------------------------------------------
            # TARGET
            # ---------------------------------------------

            if search_query.startswith(
                ("http://", "https://")
            ):
                target = search_query

            elif source == "soundcloud":

                target = (
                    "scsearch5:"
                    + search_query
                )

            else:

                target = (
                    "ytsearch5:"
                    + search_query
                )

            logger.info(
                "Resolving %s: %s",
                source,
                target,
            )

            # ---------------------------------------------
            # SEARCH
            # ---------------------------------------------

            options = ytdlp_options()

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                info = ydl.extract_info(
                    target,
                    download=False,
                )

            if not info:
                raise RuntimeError(
                    "Lagu tidak ditemukan."
                )

            # ---------------------------------------------
            # SEARCH RESULT
            # ---------------------------------------------

            if "entries" in info:

                entries = [
                    entry
                    for entry in info.get(
                        "entries",
                        []
                    )
                    if entry
                ]

                if not entries:
                    raise RuntimeError(
                        "Tidak ada hasil lagu."
                    )

                info = entries[0]

            # ---------------------------------------------
            # WEBPAGE URL
            # ---------------------------------------------

            webpage_url = (
                info.get("webpage_url")
                or info.get("original_url")
                or info.get("url")
            )

            if not webpage_url:
                raise RuntimeError(
                    "URL lagu tidak ditemukan."
                )

            # ---------------------------------------------
            # EXTRACT AUDIO
            # ---------------------------------------------

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                media = ydl.extract_info(
                    webpage_url,
                    download=False,
                )

            if not media:
                raise RuntimeError(
                    "Gagal mendapatkan informasi audio."
                )

            # ---------------------------------------------
            # STREAM URL
            # ---------------------------------------------

            stream_url = media.get(
                "url"
            )

            # Kalau URL utama tidak tersedia,
            # cari format audio.
            if not stream_url:

                formats = media.get(
                    "formats",
                    []
                )

                audio_formats = [
                    fmt
                    for fmt in formats
                    if fmt.get("url")
                    and fmt.get("acodec")
                    and fmt.get("acodec") != "none"
                ]

                if audio_formats:

                    audio_formats.sort(
                        key=lambda fmt: (
                            fmt.get(
                                "abr"
                            )
                            or 0
                        ),
                        reverse=True,
                    )

                    stream_url = (
                        audio_formats[0]
                        .get("url")
                    )

            if not stream_url:
                raise RuntimeError(
                    "Audio stream tidak tersedia."
                )

            # ---------------------------------------------
            # TRACK
            # ---------------------------------------------

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
        chat_id,
        query,
        requested_by,
        source="youtube",
    ):

        if not self.started:
            raise RuntimeError(
                "Music engine belum berjalan."
            )

        if not self.calls:
            raise RuntimeError(
                "PyTgCalls belum tersedia."
            )

        track = await self._resolve(
            query=query,
            source=source,
        )

        track.requested_by = (
            requested_by
            or "Unknown"
        )

        async with self.locks[
            chat_id
        ]:

            is_empty = (
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

            if is_empty:

                await self._start_track_locked(
                    chat_id
                )

                position = 0

            else:

                position = len(
                    self.queues[
                        chat_id
                    ]
                )

        return {
            "title": track.title,
            "position": position,
            "requested_by": track.requested_by,
            "duration": track.duration,
            "source": track.source,
        }

    # =====================================================
    # START TRACK
    # =====================================================

    async def _start_track_locked(
        self,
        chat_id,
    ):

        if not self.queues[
            chat_id
        ]:

            self.current.pop(
                chat_id,
                None,
            )

            return

        if not self.calls:
            raise RuntimeError(
                "PyTgCalls belum berjalan."
            )

        track = self.queues[
            chat_id
        ].popleft()

        self.current[
            chat_id
        ] = track

        logger.info(
            "Playing: %s | chat_id=%s",
            track.title,
            chat_id,
        )

        try:

            stream = MediaStream(
                track.stream_url,
                AudioQuality.HIGH,
            )

            await self.calls.play(
                chat_id,
                stream,
            )

        except Exception:

            self.current.pop(
                chat_id,
                None,
            )

            logger.exception(
                "Gagal memainkan track: %s",
                track.title,
            )

            raise

    # =====================================================
    # PLAY NEXT
    # =====================================================

    async def _play_next(
        self,
        chat_id,
    ):

        async with self.locks[
            chat_id
        ]:

            self.current.pop(
                chat_id,
                None,
            )

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
    # SKIP
    # =====================================================

    async def skip(
        self,
        chat_id,
    ):

        async with self.locks[
            chat_id
        ]:

            if not self.current.get(
                chat_id
            ):

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

                return (
                    current.title
                    if current
                    else None
                )

            self.current.pop(
                chat_id,
                None,
            )

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

                return None

            await self._start_track_locked(
                chat_id
            )

            current = self.current.get(
                chat_id
            )

            return (
                current.title
                if current
                else None
            )

    # =====================================================
    # STOP
    # =====================================================

    async def stop(
        self,
        chat_id,
    ):

        async with self.locks[
            chat_id
        ]:

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
        chat_id,
    ):

        if not self.calls:
            raise RuntimeError(
                "PyTgCalls belum berjalan."
            )

        await self.calls.pause(
            chat_id
        )

    # =====================================================
    # RESUME
    # =====================================================

    async def resume(
        self,
        chat_id,
    ):

        if not self.calls:
            raise RuntimeError(
                "PyTgCalls belum berjalan."
            )

        await self.calls.resume(
            chat_id
        )

    # =====================================================
    # QUEUE TEXT
    # =====================================================

    def queue_text(
        self,
        chat_id,
    ):

        current = self.current.get(
            chat_id
        )

        items = list(
            self.queues[
                chat_id
            ]
        )

        if not current and not items:
            return "📭 Queue kosong."

        text = [
            "🎵 *Music Queue*"
        ]

        if current:

            text.append(
                "\n▶️ *Sedang diputar:*"
            )

            text.append(
                f"🎵 {current.title}"
            )

            if current.requested_by:
                text.append(
                    f"👤 Request: {current.requested_by}"
                )

        if items:

            text.append(
                "\n📜 *Berikutnya:*"
            )

            for index, track in enumerate(
                items,
                1,
            ):

                text.append(
                    f"{index}. {track.title}"
                )

        return "\n".join(
            text
        )
