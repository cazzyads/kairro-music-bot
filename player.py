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
    "/tmp/youtube_cookies.txt",
)

YOUTUBE_COOKIES = os.getenv("YOUTUBE_COOKIES")


# =========================================================
# PREPARE YOUTUBE COOKIES
# =========================================================

def prepare_youtube_cookies():
    """
    Membuat file cookies dari Railway Variable:
    YOUTUBE_COOKIES

    Cookies tidak perlu disimpan di GitHub.
    """

    if not YOUTUBE_COOKIES:
        logger.warning(
            "YOUTUBE_COOKIES tidak ditemukan di environment."
        )
        return False

    try:
        cookies = YOUTUBE_COOKIES.strip()

        if not cookies:
            logger.warning(
                "YOUTUBE_COOKIES kosong."
            )
            return False

        with open(
            COOKIES_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(cookies)

        # Pastikan file benar-benar ada
        if not os.path.exists(COOKIES_FILE):
            logger.error(
                "File cookies gagal dibuat."
            )
            return False

        size = os.path.getsize(COOKIES_FILE)

        if size < 100:
            logger.warning(
                "File cookies terlalu kecil: %s bytes",
                size
            )
            return False

        logger.info(
            "YouTube cookies berhasil disiapkan."
        )

        return True

    except Exception:
        logger.exception(
            "Gagal menyiapkan YouTube cookies."
        )

        return False


# Jalankan sekali ketika module dimuat
YOUTUBE_COOKIES_READY = prepare_youtube_cookies()


# =========================================================
# YT-DLP OPTIONS
# =========================================================

def youtube_options():
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": False,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "format": "bestaudio/best",

        # Hindari beberapa masalah YouTube
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
    }

    if (
        YOUTUBE_COOKIES_READY
        and os.path.exists(COOKIES_FILE)
    ):
        options["cookiefile"] = COOKIES_FILE

        logger.info(
            "yt-dlp menggunakan YouTube cookies."
        )

    else:
        logger.warning(
            "yt-dlp berjalan TANPA YouTube cookies."
        )

    return options


# =========================================================
# GENERIC OPTIONS
# =========================================================

def soundcloud_options():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": False,
        "format": "bestaudio/best",
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
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

        self.queues = defaultdict(deque)

        self.current = {}

        self.locks = defaultdict(
            asyncio.Lock
        )

        self.started = False


    # =====================================================
    # START
    # =====================================================

    async def start(self):

        if self.started:
            return

        logger.info(
            "Starting Pyrogram..."
        )

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
                exc
            )

            raise


        logger.info(
            "Pyrogram connected."
        )


        # =================================================
        # ACCOUNT INFO
        # =================================================

        try:

            me = await self.client.get_me()

            logger.info(
                "Telegram account: %s | ID: %s | username: @%s",
                me.first_name,
                me.id,
                me.username or "none",
            )

        except Exception:

            logger.exception(
                "Gagal mengambil informasi akun Telegram."
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
                exc
            )

            try:
                await self.client.stop()
            except Exception:
                pass

            self.client = None

            raise


        logger.info(
            "PyTgCalls started."
        )


        # =================================================
        # STREAM END
        # =================================================

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
                    "Gagal memainkan lagu berikutnya di %s",
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
            "Stopping music engine..."
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
    # RESOLVE
    # =====================================================

    async def _resolve(
        self,
        query: str,
        source: str
    ) -> Track:

        def work():

            query = query.strip()

            # =============================================
            # TARGET
            # =============================================

            if query.startswith(
                (
                    "http://",
                    "https://"
                )
            ):

                target = query

            elif source == "soundcloud":

                target = (
                    f"scsearch5:{query}"
                )

            else:

                target = (
                    f"ytsearch5:{query}"
                )


            # =============================================
            # SEARCH OPTIONS
            # =============================================

            if source == "youtube":

                options = youtube_options()

            else:

                options = soundcloud_options()


            logger.info(
                "Resolving %s: %s",
                source,
                target
            )


            # =============================================
            # SEARCH
            # =============================================

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                info = ydl.extract_info(
                    target,
                    download=False
                )


            if not info:

                raise RuntimeError(
                    "Lagu tidak ditemukan."
                )


            # =============================================
            # SEARCH RESULT
            # =============================================

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


            # =============================================
            # WEBPAGE URL
            # =============================================

            webpage_url = (
                info.get("webpage_url")
                or info.get("original_url")
                or info.get("url")
            )


            if not webpage_url:

                raise RuntimeError(
                    "URL lagu tidak ditemukan."
                )


            # =============================================
            # EXTRACT MEDIA
            # =============================================

            logger.info(
                "Extracting media: %s",
                webpage_url
            )


            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                media = ydl.extract_info(
                    webpage_url,
                    download=False
                )


            if not media:

                raise RuntimeError(
                    "Gagal mengambil informasi media."
                )


            # =============================================
            # STREAM URL
            # =============================================

            stream_url = media.get(
                "url"
            )


            # =============================================
            # FORMAT FALLBACK
            # =============================================

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
                    != "none"

                ]


                if audio_formats:

                    # Pilih audio yang memiliki bitrate
                    # paling tinggi

                    audio_formats.sort(
                        key=lambda x: (
                            x.get("abr")
                            or 0
                        )
                    )

                    stream_url = (
                        audio_formats[-1]
                        .get("url")
                    )


            if not stream_url:

                raise RuntimeError(
                    "Audio stream tidak tersedia."
                )


            # =============================================
            # TRACK INFO
            # =============================================

            title = (
                media.get("title")
                or "Unknown"
            )


            duration = int(
                media.get("duration")
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


        track.requested_by = (
            requested_by
        )


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

            "requested_by": requested_by,

            "position": position,
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


        if not self.calls:

            raise RuntimeError(
                "PyTgCalls belum aktif."
            )


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


        try:

            stream = MediaStream(
                track.stream_url,
                AudioQuality.HIGH,
            )


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
                "Failed playing '%s'",
                track.title
            )


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


            if not self.queues[
                chat_id
            ]:

                try:

                    if self.calls:

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

                return self.current[
                    chat_id
                ].title


            # Simpan queue
            next_track = None

            if self.queues[
                chat_id
            ]:

                next_track = (
                    self.queues[
                        chat_id
                    ].popleft()
                )


            # Hentikan voice chat
            try:

                if self.calls:

                    await self.calls.leave_call(
                        chat_id
                    )

            except Exception:

                pass


            self.current.pop(
                chat_id,
                None
            )


            # Tidak ada lagu berikutnya
            if not next_track:

                return None


            # Masukkan sementara sebagai current
            self.current[
                chat_id
            ] = next_track


            try:

                stream = MediaStream(
                    next_track.stream_url,
                    AudioQuality.HIGH,
                )


                await self.calls.play(
                    chat_id,
                    stream
                )


                return next_track.title


            except Exception:

                self.current.pop(
                    chat_id,
                    None
                )

                raise


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
                "PyTgCalls belum aktif."
            )


        await self.calls.resume(
            chat_id
        )


    # =====================================================
    # QUEUE
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


        if not current and not items:

            return (
                "📭 Queue kosong."
            )


        lines = [
            "🎵 *Music Queue*"
        ]


        if current:

            lines.append(
                "\n▶️ *Sedang diputar:*\n"
                f"{current.title}"
            )


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


        if len(items) > 10:

            lines.append(
                f"\n… dan "
                f"{len(items) - 10} "
                f"lagu lainnya."
            )


        return "\n".join(
            lines
        )
