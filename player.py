```python
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


# =========================================================
# LOGGING
# =========================================================

logger = logging.getLogger("musicbot.player")


# =========================================================
# YOUTUBE COOKIES
# =========================================================

COOKIES_FILE = os.getenv(
    "YOUTUBE_COOKIES_FILE",
    "cookies.txt",
)

YOUTUBE_COOKIES = os.getenv(
    "YOUTUBE_COOKIES",
)


def prepare_youtube_cookies():
    """
    Membuat cookies.txt dari Railway Variable
    YOUTUBE_COOKIES jika variable tersebut tersedia.
    """

    if not YOUTUBE_COOKIES:
        logger.warning(
            "YOUTUBE_COOKIES tidak ditemukan."
        )
        return

    try:
        with open(
            COOKIES_FILE,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(YOUTUBE_COOKIES)

        logger.info(
            "YouTube cookies berhasil disiapkan: %s",
            COOKIES_FILE,
        )

    except Exception:
        logger.exception(
            "Gagal membuat cookies.txt."
        )


prepare_youtube_cookies()


# =========================================================
# YT-DLP OPTIONS
# =========================================================

def youtube_options():
    """
    Opsi yt-dlp untuk YouTube.
    """

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": False,
        "geo_bypass": True,
        "nocheckcertificate": True,

        # Audio terbaik yang tersedia
        "format": "bestaudio/best",

        # Hindari cache yang kadang menyebabkan
        # masalah extractor.
        "cachedir": False,
    }

    if os.path.exists(COOKIES_FILE):
        options["cookiefile"] = COOKIES_FILE

        logger.info(
            "yt-dlp menggunakan cookies: %s",
            COOKIES_FILE,
        )

    else:
        logger.warning(
            "cookies.txt tidak ditemukan."
        )

    return options


# =========================================================
# SOUNDCLOUD OPTIONS
# =========================================================

def soundcloud_options():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": False,
        "nocheckcertificate": True,
        "format": "bestaudio/best",
        "cachedir": False,
    }


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

        # chat_id -> queue
        self.queues = defaultdict(deque)

        # chat_id -> current Track
        self.current = {}

        # chat_id -> asyncio.Lock
        self.locks = defaultdict(
            asyncio.Lock
        )

        self.started = False


    # =====================================================
    # START
    # =====================================================

    async def start(self):

        if self.started:
            logger.info(
                "Music engine already started."
            )
            return

        logger.info(
            "Starting Pyrogram..."
        )

        # -------------------------------------------------
        # CONFIG CHECK
        # -------------------------------------------------

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

        logger.info(
            "TG_API_ID ditemukan."
        )

        logger.info(
            "TG_API_HASH ditemukan."
        )

        logger.info(
            "SESSION_STRING ditemukan."
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

        except Exception:

            logger.exception(
                "PYROGRAM START ERROR."
            )

            self.client = None

            raise

        logger.info(
            "Pyrogram connected."
        )

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
                me.first_name,
                me.id,
                username,
            )

        except Exception:

            logger.exception(
                "Gagal mengambil informasi akun Telegram."
            )

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

        except Exception:

            logger.exception(
                "PYTGCALLS START ERROR."
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

        # -------------------------------------------------
        # STREAM END HANDLER
        # -------------------------------------------------

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

                    pass

        # -------------------------------------------------
        # STOP PYROGRAM
        # -------------------------------------------------

        if self.client:

            try:

                await self.client.stop()

            except Exception:

                logger.exception(
                    "Failed stopping Pyrogram."
                )

        self.calls = None
        self.client = None

        self.current.clear()

        for queue in self.queues.values():
            queue.clear()

        self.queues.clear()

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

        # -------------------------------------------------
        # SIMPAN NILAI KE VARIABLE BARU
        #
        # Ini penting untuk menghindari:
        # UnboundLocalError: query
        # -------------------------------------------------

        search_query = (
            str(query or "")
            .strip()
        )

        selected_source = (
            str(source or "youtube")
            .lower()
            .strip()
        )

        if not search_query:

            raise RuntimeError(
                "Judul atau URL lagu kosong."
            )

        if selected_source not in (
            "youtube",
            "soundcloud",
        ):

            raise RuntimeError(
                "Source lagu tidak dikenal."
            )


        # -------------------------------------------------
        # WORKER
        # -------------------------------------------------

        def work():

            # -------------------------------------------------
            # TARGET
            # -------------------------------------------------

            if search_query.startswith(
                (
                    "http://",
                    "https://",
                )
            ):

                target = search_query

            elif selected_source == "soundcloud":

                target = (
                    f"scsearch5:{search_query}"
                )

            else:

                target = (
                    f"ytsearch5:{search_query}"
                )


            logger.info(
                "Resolving %s: %s",
                selected_source,
                target,
            )


            # -------------------------------------------------
            # SEARCH OPTIONS
            # -------------------------------------------------

            if selected_source == "youtube":

                search_options = (
                    youtube_options()
                )

            else:

                search_options = (
                    soundcloud_options()
                )


            # -------------------------------------------------
            # SEARCH
            # -------------------------------------------------

            try:

                with yt_dlp.YoutubeDL(
                    search_options
                ) as ydl:

                    info = ydl.extract_info(
                        target,
                        download=False,
                    )

            except Exception as exc:

                logger.exception(
                    "yt-dlp search error."
                )

                raise RuntimeError(
                    f"Gagal mencari lagu: {exc}"
                ) from exc


            if not info:

                raise RuntimeError(
                    "Lagu tidak ditemukan."
                )


            # -------------------------------------------------
            # SEARCH RESULT
            # -------------------------------------------------

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
            # EXTRACT MEDIA
            # -------------------------------------------------

            logger.info(
                "Extracting media: %s",
                webpage_url,
            )

            if selected_source == "youtube":

                media_options = (
                    youtube_options()
                )

            else:

                media_options = (
                    soundcloud_options()
                )


            try:

                with yt_dlp.YoutubeDL(
                    media_options
                ) as ydl:

                    media = ydl.extract_info(
                        webpage_url,
                        download=False,
                    )

            except Exception as exc:

                logger.exception(
                    "yt-dlp media extraction error."
                )

                error_text = str(exc)

                if (
                    "Sign in to confirm" in error_text
                    or "not a bot" in error_text
                ):

                    raise RuntimeError(
                        "YouTube meminta verifikasi bot. "
                        "Cookies YouTube di Railway kemungkinan "
                        "sudah expired atau tidak valid."
                    ) from exc

                raise RuntimeError(
                    f"Gagal mengambil audio: {exc}"
                ) from exc


            if not media:

                raise RuntimeError(
                    "Media tidak ditemukan."
                )


            # -------------------------------------------------
            # STREAM URL
            # -------------------------------------------------

            stream_url = media.get(
                "url"
            )


            # -------------------------------------------------
            # FORMAT FALLBACK
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

                    and fmt.get("acodec")
                    and fmt.get("acodec") != "none"

                ]

                if audio_formats:

                    # Pilih format audio terakhir
                    # yang tersedia.

                    stream_url = (
                        audio_formats[-1]["url"]
                    )


            if not stream_url:

                raise RuntimeError(
                    "Audio stream tidak tersedia."
                )


            # -------------------------------------------------
            # INFO
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


            # -------------------------------------------------
            # RETURN TRACK
            # -------------------------------------------------

            return Track(

                title=title,

                webpage_url=webpage_url,

                stream_url=stream_url,

                duration=duration,

                requested_by="Unknown",

                source=selected_source,
            )


        # -------------------------------------------------
        # RUN YT-DLP DI THREAD
        # -------------------------------------------------

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
        source: str = "youtube",
    ):

        if not self.started:

            raise RuntimeError(
                "Music engine belum siap."
            )

        if not query:

            raise RuntimeError(
                "Judul lagu atau URL kosong."
            )


        # -------------------------------------------------
        # RESOLVE
        # -------------------------------------------------

        track = await self._resolve(
            query=query,
            source=source,
        )

        track.requested_by = (
            requested_by
            or "Unknown"
        )


        # -------------------------------------------------
        # QUEUE
        # -------------------------------------------------

        async with self.locks[
            chat_id
        ]:

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
            # LANGSUNG PLAY
            # -------------------------------------------------

            if was_empty:

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

            "requested_by":
                track.requested_by,

            "position":
                position,

            "source":
                track.source,
        }


    # =====================================================
    # START TRACK
    # =====================================================

    async def _start_track_locked(
        self,
        chat_id: int,
    ):

        if not self.calls:

            raise RuntimeError(
                "PyTgCalls belum aktif."
            )


        if not self.queues[
            chat_id
        ]:

            self.current.pop(
                chat_id,
                None,
            )

            return


        # -------------------------------------------------
        # AMBIL LAGU PERTAMA
        # -------------------------------------------------

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
            chat_id,
        )


        # -------------------------------------------------
        # MEDIA STREAM
        # -------------------------------------------------

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
                "Failed creating MediaStream."
            )

            raise RuntimeError(
                f"Gagal membuat audio stream: {exc}"
            ) from exc


        # -------------------------------------------------
        # PLAY
        # -------------------------------------------------

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
                "Failed playing '%s'",
                track.title,
            )

            raise RuntimeError(
                f"Gagal memutar audio: {exc}"
            ) from exc


    # =====================================================
    # PLAY NEXT
    # =====================================================

    async def _play_next(
        self,
        chat_id: int,
    ):

        async with self.locks[
            chat_id
        ]:

            self.current.pop(
                chat_id,
                None,
            )


            # -------------------------------------------------
            # QUEUE HABIS
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


            # -------------------------------------------------
            # NEXT TRACK
            # -------------------------------------------------

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

        async with self.locks[
            chat_id
        ]:

            has_current = bool(
                self.current.get(
                    chat_id
                )
            )

            has_queue = bool(
                self.queues[
                    chat_id
                ]
            )

            if not has_current and not has_queue:

                return None


            # -------------------------------------------------
            # REMOVE CURRENT
            # -------------------------------------------------

            self.current.pop(
                chat_id,
                None,
            )


            # -------------------------------------------------
            # LEAVE CURRENT CALL
            # -------------------------------------------------

            if self.calls:

                try:

                    await self.calls.leave_call(
                        chat_id
                    )

                except Exception:

                    pass


            # -------------------------------------------------
            # QUEUE HABIS
            # -------------------------------------------------

            if not self.queues[
                chat_id
            ]:

                return None


            # -------------------------------------------------
            # PLAY NEXT
            # -------------------------------------------------

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
        chat_id: int,
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
        chat_id: int,
    ):

        if not self.calls:

            raise RuntimeError(
                "PyTgCalls belum aktif."
            )


        if not self.current.get(
            chat_id
        ):

            raise RuntimeError(
                "Tidak ada lagu yang sedang diputar."
            )


        try:

            await self.calls.pause(
                chat_id
            )

        except Exception as exc:

            raise RuntimeError(
                f"Gagal pause: {exc}"
            ) from exc


    # =====================================================
    # RESUME
    # =====================================================

    async def resume(
        self,
        chat_id: int,
    ):

        if not self.calls:

            raise RuntimeError(
                "PyTgCalls belum aktif."
            )


        if not self.current.get(
            chat_id
        ):

            raise RuntimeError(
                "Tidak ada lagu yang sedang diputar."
            )


        try:

            await self.calls.resume(
                chat_id
            )

        except Exception as exc:

            raise RuntimeError(
                f"Gagal resume: {exc}"
            ) from exc


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
            self.queues[
                chat_id
            ]
        )


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
                "\n▶️ *Sedang diputar:*"
            )

            lines.append(
                current.title
            )

            if current.requested_by:

                lines.append(
                    f"👤 Request: "
                    f"{current.requested_by}"
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
                1,
            ):

                lines.append(
                    f"{index}. "
                    f"{track.title}"
                )


        # -------------------------------------------------
        # MORE
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
```
