import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import yt_dlp

logger = logging.getLogger(__name__)


# ============================================================
# MEDIA
# ============================================================

@dataclass
class Media:
    title: str
    url: str
    stream_url: str
    media_type: str
    duration: int = 0
    thumbnail: Optional[str] = None
    webpage_url: Optional[str] = None
    requested_by: int = 0
    requested_name: str = "Unknown"


# ============================================================
# YOUTUBE / SOUNDCLOUD SEARCH
# ============================================================

class MediaExtractor:

    AUDIO_OPTIONS = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "noplaylist": True,
        "skip_download": True,
    }

    VIDEO_OPTIONS = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestvideo+bestaudio/best",
        "noplaylist": True,
        "skip_download": True,
    }

    @staticmethod
    def search_audio(query: str):

        options = dict(
            MediaExtractor.AUDIO_OPTIONS
        )

        if not query.startswith("http"):
            query = f"ytsearch1:{query}"

        try:
            with yt_dlp.YoutubeDL(options) as ydl:

                info = ydl.extract_info(
                    query,
                    download=False
                )

                if "entries" in info:

                    entries = info.get("entries") or []

                    if not entries:
                        return None

                    info = entries[0]

                return info

        except Exception as error:

            logger.exception(
                "Audio extraction failed: %s",
                error
            )

            return None

    @staticmethod
    def search_video(query: str):

        options = dict(
            MediaExtractor.VIDEO_OPTIONS
        )

        if not query.startswith("http"):
            query = f"ytsearch1:{query}"

        try:
            with yt_dlp.YoutubeDL(options) as ydl:

                info = ydl.extract_info(
                    query,
                    download=False
                )

                if "entries" in info:

                    entries = info.get("entries") or []

                    if not entries:
                        return None

                    info = entries[0]

                return info

        except Exception as error:

            logger.exception(
                "Video extraction failed: %s",
                error
            )

            return None

    @staticmethod
    def make_media(
        info,
        media_type: str,
        user_id: int,
        user_name: str,
    ):

        if not info:
            return None

        title = info.get(
            "title",
            "Unknown"
        )

        webpage_url = info.get(
            "webpage_url"
        ) or info.get(
            "original_url"
        )

        stream_url = info.get(
            "url"
        )

        duration = info.get(
            "duration"
        ) or 0

        thumbnail = info.get(
            "thumbnail"
        )

        if not stream_url:
            return None

        return Media(
            title=title,
            url=webpage_url or stream_url,
            stream_url=stream_url,
            media_type=media_type,
            duration=duration,
            thumbnail=thumbnail,
            webpage_url=webpage_url,
            requested_by=user_id,
            requested_name=user_name,
        )


# ============================================================
# QUEUE PLAYER
# ============================================================

class QueuePlayer:

    def __init__(self):

        self.queues = {}

        self.current = {}

        self.paused = {}

        self.loop = {}

        self.volume = {}

        self.locks = {}

    # --------------------------------------------------------
    # INTERNAL
    # --------------------------------------------------------

    def _lock(self, chat_id):

        if chat_id not in self.locks:

            self.locks[chat_id] = (
                asyncio.Lock()
            )

        return self.locks[chat_id]

    def _queue(self, chat_id):

        if chat_id not in self.queues:

            self.queues[chat_id] = []

        return self.queues[chat_id]

    # --------------------------------------------------------
    # ADD
    # --------------------------------------------------------

    async def add(
        self,
        chat_id: int,
        media: Media
    ):

        async with self._lock(chat_id):

            self._queue(chat_id).append(
                media
            )

            return len(
                self._queue(chat_id)
            )

    # --------------------------------------------------------
    # NEXT
    # --------------------------------------------------------

    async def next(
        self,
        chat_id: int
    ):

        async with self._lock(chat_id):

            queue = self._queue(chat_id)

            if not queue:

                self.current[chat_id] = None

                return None

            media = queue.pop(0)

            self.current[chat_id] = media

            self.paused[chat_id] = False

            return media

    # --------------------------------------------------------
    # CURRENT
    # --------------------------------------------------------

    def get_current(
        self,
        chat_id: int
    ):

        return self.current.get(
            chat_id
        )

    # --------------------------------------------------------
    # QUEUE
    # --------------------------------------------------------

    def get_queue(
        self,
        chat_id: int
    ):

        return list(
            self._queue(chat_id)
        )

    # --------------------------------------------------------
    # PAUSE
    # --------------------------------------------------------

    def pause(
        self,
        chat_id: int
    ):

        if not self.current.get(chat_id):
            return False

        if self.paused.get(chat_id):
            return False

        self.paused[chat_id] = True

        return True

    # --------------------------------------------------------
    # RESUME
    # --------------------------------------------------------

    def resume(
        self,
        chat_id: int
    ):

        if not self.current.get(chat_id):
            return False

        if not self.paused.get(chat_id):
            return False

        self.paused[chat_id] = False

        return True

    # --------------------------------------------------------
    # SKIP
    # --------------------------------------------------------

    async def skip(
        self,
        chat_id: int
    ):

        return await self.next(
            chat_id
        )

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    def stop(
        self,
        chat_id: int
    ):

        self.queues[chat_id] = []

        self.current[chat_id] = None

        self.paused[chat_id] = False

    # --------------------------------------------------------
    # SHUFFLE
    # --------------------------------------------------------

    def shuffle(
        self,
        chat_id: int
    ):

        import random

        queue = self._queue(chat_id)

        if len(queue) < 2:
            return False

        random.shuffle(queue)

        return True

    # --------------------------------------------------------
    # LOOP
    # --------------------------------------------------------

    def set_loop(
        self,
        chat_id: int,
        enabled: bool
    ):

        self.loop[chat_id] = enabled

        return enabled

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    def set_volume(
        self,
        chat_id: int,
        volume: int
    ):

        volume = max(
            1,
            min(100, volume)
        )

        self.volume[chat_id] = volume

        return volume

    def get_volume(
        self,
        chat_id: int
    ):

        return self.volume.get(
            chat_id,
            100
        )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    def status(
        self,
        chat_id: int
    ):

        return {
            "current":
                self.current.get(chat_id),

            "queue":
                self._queue(chat_id),

            "paused":
                self.paused.get(
                    chat_id,
                    False
                ),

            "loop":
                self.loop.get(
                    chat_id,
                    False
                ),

            "volume":
                self.get_volume(
                    chat_id
                ),
        }


# ============================================================
# GLOBAL PLAYER
# ============================================================

player = QueuePlayer()
