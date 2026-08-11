import os
import asyncio
import logging

from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

from config import API_ID, API_HASH


logger = logging.getLogger(__name__)


class TelegramPlayer:

    def __init__(self):
        self.client = None
        self.calls = None
        self.started = False

    async def start(self):

        if self.started:
            return

        if not API_ID:
            raise RuntimeError("API_ID belum diatur.")

        if not API_HASH:
            raise RuntimeError("API_HASH belum diatur.")

        self.client = Client(
            "kairo_music",
            api_id=int(API_ID),
            api_hash=API_HASH,
        )

        await self.client.start()

        self.calls = PyTgCalls(
            self.client
        )

        await self.calls.start()

        self.started = True

        logger.info(
            "Telegram voice/video engine started."
        )

    async def stop(self):

        if not self.started:
            return

        try:
            await self.calls.stop()
        except Exception:
            pass

        try:
            await self.client.stop()
        except Exception:
            pass

        self.started = False

    async def play(
        self,
        chat_id: int,
        source: str,
    ):

        if not self.started:
            await self.start()

        await self.calls.play(
            chat_id,
            MediaStream(
                source
            ),
        )

    async def pause(
        self,
        chat_id: int,
    ):

        if not self.started:
            return

        await self.calls.pause(
            chat_id
        )

    async def resume(
        self,
        chat_id: int,
    ):

        if not self.started:
            return

        await self.calls.resume(
            chat_id
        )

    async def stop_chat(
        self,
        chat_id: int,
    ):

        if not self.started:
            return

        await self.calls.leave_call(
            chat_id
        )


telegram_player = TelegramPlayer()
