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
    "cookies.txt"
)


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
        }

        # Pakai cookies jika file tersedia
        if os.path.exists(COOKIES_FILE):
            options["cookiefile"] = COOKIES_FILE

            logger.info(
                "YouTube cookies ditemukan: %s",
                COOKIES_FILE
            )

        else:
            logger.warning(
                "YouTube cookies tidak ditemukan: %s",
                COOKIES_FILE
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
        # PYTGCALLS
        # =================================================

        self.calls = PyTgCalls(
            self.client
        )

        await self.calls.start()

        logger.info(
            "PyTgCalls started."
        )


        # =================================================
        # STREAM END EVENT
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
                    "Failed playing next track in %s",
                    chat_id
                )


        # =================================================
        # ACCOUNT INFO
        # =================================================

        try:

            me = await self.client.get_me()

            logger.info(
                "Telegram account: %s (%s)",
                me.first_name,
                me.id
            )

        except Exception:

            logger.exception(
                "Failed getting Telegram account."
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
    # RESOLVE LAGU
    # =====================================================

    async def _resolve(
        self,
        query: str,
        source: str
    ) -> Track:

        def work():

            # =================================================
            # SEARCH TARGET
            # =================================================

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


            # =================================================
            # SEARCH
            # =================================================

            search_options = (
                self._youtube_options()
                if source == "youtube"
                else {
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                    "extract_flat": False,
                }
            )


            logger.info(
                "Resolving: %s",
                target
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


            # =================================================
            # SEARCH RESULTS
            # =================================================

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


            # =================================================
            # AUDIO STREAM
            # =================================================

            stream_options = (
                self._youtube_options()
                if source == "youtube"
                else {
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                    "format": "bestaudio/best",
                }
            )

            stream_options[
                "format"
            ] = "bestaudio/best"


            logger.info(
                "Extracting audio: %s",
                webpage_url
            )


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
                    != "none"
                ]

                if not audio_formats:

                    raise RuntimeError(
                        "Audio stream tidak tersedia."
                    )

                # Ambil audio terakhir
                stream_url = (
                    audio_formats[-1]["url"]
                )


            # =================================================
            # INFO
            # =================================================

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


            if was_empty:

                await self._start_track_locked(
                    chat_id
                )


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
                "PyTgCalls belum aktif."
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


        if not current and not items:

            return (
                "📭 *Queue kosong.*"
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
