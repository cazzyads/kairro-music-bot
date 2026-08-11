import asyncio
import random
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# MEDIA ITEM
# ============================================================

@dataclass
class MediaItem:
    title: str
    url: str
    media_type: str = "audio"
    requested_by: int = 0
    requested_name: str = "Unknown"
    duration: int = 0
    thumbnail: Optional[str] = None


# ============================================================
# PLAYER STATE
# ============================================================

@dataclass
class PlayerState:
    chat_id: int

    queue: list = field(default_factory=list)

    current: Optional[MediaItem] = None

    paused: bool = False

    volume: int = 100

    loop: bool = False

    playing: bool = False

    joined: bool = False

    mode: str = "audio"

    lock: asyncio.Lock = field(
        default_factory=asyncio.Lock
    )


# ============================================================
# PLAYER MANAGER
# ============================================================

class PlayerManager:

    def __init__(self):
        self.players = {}

    # --------------------------------------------------------
    # GET PLAYER
    # --------------------------------------------------------

    def get_player(self, chat_id: int) -> PlayerState:

        if chat_id not in self.players:

            self.players[chat_id] = PlayerState(
                chat_id=chat_id
            )

        return self.players[chat_id]

    # --------------------------------------------------------
    # REMOVE PLAYER
    # --------------------------------------------------------

    def remove_player(self, chat_id: int):

        if chat_id in self.players:

            del self.players[chat_id]

    # --------------------------------------------------------
    # ADD QUEUE
    # --------------------------------------------------------

    async def add(
        self,
        chat_id: int,
        item: MediaItem
    ):

        player = self.get_player(chat_id)

        async with player.lock:

            player.queue.append(item)

            if len(player.queue) == 1 and not player.playing:

                await self.play_next(chat_id)

    # --------------------------------------------------------
    # GET CURRENT
    # --------------------------------------------------------

    def current(
        self,
        chat_id: int
    ):

        player = self.get_player(chat_id)

        return player.current

    # --------------------------------------------------------
    # GET QUEUE
    # --------------------------------------------------------

    def get_queue(
        self,
        chat_id: int
    ):

        player = self.get_player(chat_id)

        return list(player.queue)

    # --------------------------------------------------------
    # PLAY NEXT
    # --------------------------------------------------------

    async def play_next(
        self,
        chat_id: int
    ):

        player = self.get_player(chat_id)

        # LOOP CURRENT SONG
        if player.loop and player.current:

            player.playing = True
            player.paused = False

            return player.current

        # NO QUEUE
        if not player.queue:

            player.current = None
            player.playing = False
            player.paused = False

            return None

        # GET NEXT
        item = player.queue.pop(0)

        player.current = item

        player.mode = item.media_type

        player.playing = True

        player.paused = False

        return item

    # --------------------------------------------------------
    # PAUSE
    # --------------------------------------------------------

    def pause(
        self,
        chat_id: int
    ):

        player = self.get_player(chat_id)

        if not player.playing:
            return False

        if player.paused:
            return False

        player.paused = True

        return True

    # --------------------------------------------------------
    # RESUME
    # --------------------------------------------------------

    def resume(
        self,
        chat_id: int
    ):

        player = self.get_player(chat_id)

        if not player.playing:
            return False

        if not player.paused:
            return False

        player.paused = False

        return True

    # --------------------------------------------------------
    # SKIP
    # --------------------------------------------------------

    async def skip(
        self,
        chat_id: int
    ):

        player = self.get_player(chat_id)

        player.current = None

        player.playing = False

        player.paused = False

        return await self.play_next(chat_id)

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    def stop(
        self,
        chat_id: int
    ):

        player = self.get_player(chat_id)

        player.queue.clear()

        player.current = None

        player.playing = False

        player.paused = False

        return True

    # --------------------------------------------------------
    # SHUFFLE
    # --------------------------------------------------------

    def shuffle(
        self,
        chat_id: int
    ):

        player = self.get_player(chat_id)

        if len(player.queue) < 2:

            return False

        random.shuffle(player.queue)

        return True

    # --------------------------------------------------------
    # SET LOOP
    # --------------------------------------------------------

    def set_loop(
        self,
        chat_id: int,
        enabled: bool
    ):

        player = self.get_player(chat_id)

        player.loop = enabled

        return player.loop

    # --------------------------------------------------------
    # SET VOLUME
    # --------------------------------------------------------

    def set_volume(
        self,
        chat_id: int,
        volume: int
    ):

        player = self.get_player(chat_id)

        volume = max(
            1,
            min(100, int(volume))
        )

        player.volume = volume

        return volume

    # --------------------------------------------------------
    # CLEAR QUEUE
    # --------------------------------------------------------

    def clear_queue(
        self,
        chat_id: int
    ):

        player = self.get_player(chat_id)

        player.queue.clear()

        return True

    # --------------------------------------------------------
    # REMOVE QUEUE ITEM
    # --------------------------------------------------------

    def remove_queue_item(
        self,
        chat_id: int,
        index: int
    ):

        player = self.get_player(chat_id)

        if index < 0:
            return False

        if index >= len(player.queue):
            return False

        player.queue.pop(index)

        return True

    # --------------------------------------------------------
    # JOIN STATE
    # --------------------------------------------------------

    def set_joined(
        self,
        chat_id: int,
        joined: bool
    ):

        player = self.get_player(chat_id)

        player.joined = joined

        return joined

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    def status(
        self,
        chat_id: int
    ):

        player = self.get_player(chat_id)

        return {
            "chat_id": player.chat_id,
            "current": player.current,
            "queue": player.queue,
            "paused": player.paused,
            "playing": player.playing,
            "volume": player.volume,
            "loop": player.loop,
            "joined": player.joined,
            "mode": player.mode,
        }


# ============================================================
# GLOBAL PLAYER MANAGER
# ============================================================

player_manager = PlayerManager()
