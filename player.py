```python
import asyncio
import logging
import random
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
# YOUTUBE / SOUNDCLOUD EXTRACTOR
# ============================================================

class MediaExtractor:

    # --------------------------------------------------------
    # AUDIO OPTIONS
    # --------------------------------------------------------

    AUDIO_OPTIONS = {
        "quiet": True,
        "no_warnings": True,

        "format": "bestaudio/best",

        "noplaylist": True,

        "skip_download": True,

        "source_address": "0.0.0.0",
    }

    # --------------------------------------------------------
    # VIDEO OPTIONS
    # --------------------------------------------------------

    VIDEO_OPTIONS = {
        "quiet": True,
        "no_warnings": True,

        "format": "bestvideo+bestaudio/best",

        "noplaylist": True,

        "skip_download": True,

        "source_address": "0.0.0.0",
    }

    # ========================================================
    # SEARCH AUDIO
    # ========================================================

    @staticmethod
    def search_audio(query: str):

        if not query:
            return None

        query = query.strip()

        options = dict(
            MediaExtractor.AUDIO_OPTIONS
        )

        # Search YouTube jika bukan URL
        if not query.startswith("http://") and not query.startswith("https://"):
            query = f"ytsearch1:{query}"

        try:

            with yt_dlp.YoutubeDL(options) as ydl:

                info = ydl.extract_info(
                    query,
                    download=False
                )

                if not info:
                    return None

                # Jika hasil pencarian
                if "entries" in info:

                    entries = info.get(
                        "entries"
                    ) or []

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

    # ========================================================
    # SEARCH VIDEO
    # ========================================================

    @staticmethod
    def search_video(query: str):

        if not query:
            return None

        query = query.strip()

        options = dict(
            MediaExtractor.VIDEO_OPTIONS
        )

        # Search YouTube jika bukan URL
        if not query.startswith("http://") and not query.startswith("https://"):
            query = f"ytsearch1:{query}"

        try:

            with yt_dlp.YoutubeDL(options) as ydl:

                info = ydl.extract_info(
                    query,
                    download=False
                )

                if not info:
                    return None

                # Jika hasil pencarian
                if "entries" in info:

                    entries = info.get(
                        "entries"
                    ) or []

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

    # ========================================================
    # SEARCH
    # ========================================================

    @staticmethod
    def search(
        query: str,
        media_type: str = "audio"
    ):

        if media_type == "video":

            return MediaExtractor.search_video(
                query
            )

        return MediaExtractor.search_audio(
            query
        )

    # ========================================================
    # MAKE MEDIA
    # ========================================================

    @staticmethod
    def make_media(
        info,
        media_type: str,
        user_id: int,
        user_name: str,
    ):

        if not info:
            return None

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        title = info.get(
            "title"
        ) or "Unknown"

        # ----------------------------------------------------
        # WEBPAGE URL
        # ----------------------------------------------------

        webpage_url = (
            info.get("webpage_url")
            or info.get("original_url")
        )

        # ----------------------------------------------------
        # STREAM URL
        # ----------------------------------------------------

        stream_url = info.get(
            "url"
        )

        # ----------------------------------------------------
        # DURATION
        # ----------------------------------------------------

        duration = info.get(
            "duration"
        ) or 0

        try:
            duration = int(duration)

        except (
            TypeError,
            ValueError
        ):

            duration = 0

        # ----------------------------------------------------
        # THUMBNAIL
        # ----------------------------------------------------

        thumbnail = info.get(
            "thumbnail"
        )

        # ----------------------------------------------------
        # CHECK STREAM
        # ----------------------------------------------------

        if not stream_url:

            logger.warning(
                "No stream URL for: %s",
                title
            )

            return None

        # ----------------------------------------------------
        # CREATE MEDIA
        # ----------------------------------------------------

        return Media(

            title=title,

            url=(
                webpage_url
                or stream_url
            ),

            stream_url=stream_url,

            media_type=media_type,

            duration=duration,

            thumbnail=thumbnail,

            webpage_url=webpage_url,

            requested_by=user_id,

            requested_name=(
                user_name
                or "Unknown"
            ),
        )

    # ========================================================
    # SEARCH AND CREATE MEDIA
    # ========================================================

    @staticmethod
    def get_media(
        query: str,
        media_type: str,
        user_id: int,
        user_name: str,
    ):

        info = MediaExtractor.search(
            query,
            media_type
        )

        if not info:
            return None

        return MediaExtractor.make_media(
            info=info,
            media_type=media_type,
            user_id=user_id,
            user_name=user_name,
        )


# ============================================================
# QUEUE PLAYER
# ============================================================

class QueuePlayer:

    def __init__(self):

        # ----------------------------------------------------
        # Queue per chat
        # ----------------------------------------------------

        self.queues = {}

        # ----------------------------------------------------
        # Current media per chat
        # ----------------------------------------------------

        self.current = {}

        # ----------------------------------------------------
        # Pause status
        # ----------------------------------------------------

        self.paused = {}

        # ----------------------------------------------------
        # Loop status
        # ----------------------------------------------------

        self.loop = {}

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        self.volume = {}

        # ----------------------------------------------------
        # Async locks
        # ----------------------------------------------------

        self.locks = {}

    # ========================================================
    # INTERNAL LOCK
    # ========================================================

    def _lock(
        self,
        chat_id: int
    ):

        if chat_id not in self.locks:

            self.locks[chat_id] = asyncio.Lock()

        return self.locks[chat_id]

    # ========================================================
    # INTERNAL QUEUE
    # ========================================================

    def _queue(
        self,
        chat_id: int
    ):

        if chat_id not in self.queues:

            self.queues[chat_id] = []

        return self.queues[chat_id]

    # ========================================================
    # ADD
    # ========================================================

    async def add(
        self,
        chat_id: int,
        media: Media
    ):

        async with self._lock(chat_id):

            queue = self._queue(
                chat_id
            )

            queue.append(
                media
            )

            return len(queue)

    # ========================================================
    # ADD MULTIPLE
    # ========================================================

    async def add_many(
        self,
        chat_id: int,
        medias: list
    ):

        async with self._lock(chat_id):

            queue = self._queue(
                chat_id
            )

            queue.extend(
                medias
            )

            return len(queue)

    # ========================================================
    # NEXT
    # ========================================================

    async def next(
        self,
        chat_id: int
    ):

        async with self._lock(chat_id):

            queue = self._queue(
                chat_id
            )

            # Tidak ada lagu
            if not queue:

                self.current[
                    chat_id
                ] = None

                self.paused[
                    chat_id
                ] = False

                return None

            # Ambil lagu pertama
            media = queue.pop(0)

            self.current[
                chat_id
            ] = media

            self.paused[
                chat_id
            ] = False

            return media

    # ========================================================
    # CURRENT
    # ========================================================

    def get_current(
        self,
        chat_id: int
    ):

        return self.current.get(
            chat_id
        )

    # ========================================================
    # QUEUE
    # ========================================================

    def get_queue(
        self,
        chat_id: int
    ):

        return list(
            self._queue(chat_id)
        )

    # ========================================================
    # QUEUE LENGTH
    # ========================================================

    def queue_length(
        self,
        chat_id: int
    ):

        return len(
            self._queue(chat_id)
        )

    # ========================================================
    # PAUSE
    # ========================================================

    def pause(
        self,
        chat_id: int
    ):

        if not self.current.get(
            chat_id
        ):

            return False

        if self.paused.get(
            chat_id,
            False
        ):

            return False

        self.paused[
            chat_id
        ] = True

        return True

    # ========================================================
    # RESUME
    # ========================================================

    def resume(
        self,
        chat_id: int
    ):

        if not self.current.get(
            chat_id
        ):

            return False

        if not self.paused.get(
            chat_id,
            False
        ):

            return False

        self.paused[
            chat_id
        ] = False

        return True

    # ========================================================
    # IS PAUSED
    # ========================================================

    def is_paused(
        self,
        chat_id: int
    ):

        return self.paused.get(
            chat_id,
            False
        )

    # ========================================================
    # SKIP
    # ========================================================

    async def skip(
        self,
        chat_id: int
    ):

        return await self.next(
            chat_id
        )

    # ========================================================
    # STOP
    # ========================================================

    def stop(
        self,
        chat_id: int
    ):

        self.queues[
            chat_id
        ] = []

        self.current[
            chat_id
        ] = None

        self.paused[
            chat_id
        ] = False

        return True

    # ========================================================
    # CLEAR QUEUE
    # ========================================================

    def clear_queue(
        self,
        chat_id: int
    ):

        queue = self._queue(
            chat_id
        )

        count = len(queue)

        queue.clear()

        return count

    # ========================================================
    # SHUFFLE
    # ========================================================

    def shuffle(
        self,
        chat_id: int
    ):

        queue = self._queue(
            chat_id
        )

        if len(queue) < 2:

            return False

        random.shuffle(
            queue
        )

        return True

    # ========================================================
    # REMOVE FROM QUEUE
    # ========================================================

    def remove(
        self,
        chat_id: int,
        index: int
    ):

        queue = self._queue(
            chat_id
        )

        if index < 0:
            return None

        if index >= len(queue):
            return None

        return queue.pop(
            index
        )

    # ========================================================
    # LOOP
    # ========================================================

    def set_loop(
        self,
        chat_id: int,
        enabled: bool
    ):

        self.loop[
            chat_id
        ] = bool(enabled)

        return self.loop[
            chat_id
        ]

    # ========================================================
    # TOGGLE LOOP
    # ========================================================

    def toggle_loop(
        self,
        chat_id: int
    ):

        current = self.loop.get(
            chat_id,
            False
        )

        self.loop[
            chat_id
        ] = not current

        return self.loop[
            chat_id
        ]

    # ========================================================
    # GET LOOP
    # ========================================================

    def get_loop(
        self,
        chat_id: int
    ):

        return self.loop.get(
            chat_id,
            False
        )

    # ========================================================
    # VOLUME
    # ========================================================

    def set_volume(
        self,
        chat_id: int,
        volume: int
    ):

        try:

            volume = int(
                volume
            )

        except (
            TypeError,
            ValueError
        ):

            volume = 100

        volume = max(
            1,
            min(
                100,
                volume
            )
        )

        self.volume[
            chat_id
        ] = volume

        return volume

    # ========================================================
    # GET VOLUME
    # ========================================================

    def get_volume(
        self,
        chat_id: int
    ):

        return self.volume.get(
            chat_id,
            100
        )

    # ========================================================
    # INCREASE VOLUME
    # ========================================================

    def volume_up(
        self,
        chat_id: int,
        amount: int = 10
    ):

        current = self.get_volume(
            chat_id
        )

        return self.set_volume(
            chat_id,
            current + amount
        )

    # ========================================================
    # DECREASE VOLUME
    # ========================================================

    def volume_down(
        self,
        chat_id: int,
        amount: int = 10
    ):

        current = self.get_volume(
            chat_id
        )

        return self.set_volume(
            chat_id,
            current - amount
        )

    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
        chat_id: int
    ):

        self.queues[
            chat_id
        ] = []

        self.current[
            chat_id
        ] = None

        self.paused[
            chat_id
        ] = False

        self.loop[
            chat_id
        ] = False

        self.volume[
            chat_id
        ] = 100

    # ========================================================
    # STATUS
    # ========================================================

    def status(
        self,
        chat_id: int
    ):

        return {

            "current":
                self.current.get(
                    chat_id
                ),

            "queue":
                self.get_queue(
                    chat_id
                ),

            "queue_length":
                self.queue_length(
                    chat_id
                ),

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
```
