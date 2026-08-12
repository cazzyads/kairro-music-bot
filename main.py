import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import BOT_TOKEN, validate_config
from player import MusicPlayer


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("musicbot")


# =========================================================
# MUSIC PLAYER
# =========================================================

player = MusicPlayer()


# =========================================================
# MENU UTAMA
# =========================================================

MENU = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "🔎 Cari Lagu",
                callback_data="help_play",
            ),
            InlineKeyboardButton(
                "📜 Queue",
                callback_data="queue",
            ),
        ],
        [
            InlineKeyboardButton(
                "⏭ Skip",
                callback_data="skip",
            ),
            InlineKeyboardButton(
                "⏹ Stop",
                callback_data="stop",
            ),
        ],
    ]
)


# =========================================================
# PESAN WELCOME
# =========================================================

def welcome_text():

    return (
        "🎵 *Telegram Music Bot*\n\n"
        "Bot musik untuk mencari dan memutar lagu "
        "ke Voice Chat.\n\n"

        "🎧 *Perintah:*\n"
        "• `/play judul lagu` — cari di YouTube\n"
        "• `/sc judul lagu` — cari di SoundCloud\n"
        "• `/play URL` — putar URL\n"
        "• `/skip` — lagu berikutnya\n"
        "• `/queue` — lihat antrean\n"
        "• `/stop` — hentikan musik\n"
        "• `/pause` — jeda musik\n"
        "• `/resume` — lanjutkan musik\n\n"

        "⚠️ Akun Telegram yang digunakan oleh "
        "Pyrogram harus sudah berada di grup "
        "dan memiliki akses untuk masuk Voice Chat."
    )


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await update.message.reply_text(
        welcome_text(),
        parse_mode="Markdown",
        reply_markup=MENU,
    )


# =========================================================
# /HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await update.message.reply_text(
        welcome_text(),
        parse_mode="Markdown",
        reply_markup=MENU,
    )


# =========================================================
# /PLAY
# =========================================================

async def play_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    query = " ".join(
        context.args
    ).strip()

    if not query:

        await update.message.reply_text(
            "❌ Kamu belum memasukkan judul lagu.\n\n"
            "Contoh:\n"
            "`/play Alan Walker Faded`\n"
            "`/play The Weeknd Blinding Lights`\n"
            "`/play https://youtube.com/...`",
            parse_mode="Markdown",
        )

        return

    status = await update.message.reply_text(
        "🔎 Mencari lagu...\n"
        "⏳ Tunggu sebentar."
    )

    try:

        result = await player.enqueue(
            chat_id=update.effective_chat.id,
            query=query,
            requested_by=update.effective_user.full_name,
            source="youtube",
        )

        await status.edit_text(
            "✅ *Lagu ditemukan!*\n\n"
            f"🎵 *{result['title']}*\n"
            f"👤 Request: {result['requested_by']}\n"
            f"📍 Posisi queue: {result['position']}\n\n"
            "▶️ Musik sedang diproses.",
            parse_mode="Markdown",
            reply_markup=MENU,
        )

    except Exception as exc:

        logger.exception(
            "Play command failed"
        )

        await status.edit_text(
            "❌ *Gagal memutar lagu.*\n\n"
            f"`{type(exc).__name__}: {exc}`\n\n"
            "Pastikan Voice Chat grup sudah aktif "
            "dan akun musik sudah berada di grup.",
            parse_mode="Markdown",
        )


# =========================================================
# /SC
# =========================================================

async def sc_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    query = " ".join(
        context.args
    ).strip()

    if not query:

        await update.message.reply_text(
            "❌ Masukkan judul lagu SoundCloud.\n\n"
            "Contoh:\n"
            "`/sc The Weeknd`\n"
            "`/sc Alan Walker`",
            parse_mode="Markdown",
        )

        return

    status = await update.message.reply_text(
        "🔎 Mencari di SoundCloud...\n"
        "⏳ Tunggu sebentar."
    )

    try:

        result = await player.enqueue(
            chat_id=update.effective_chat.id,
            query=query,
            requested_by=update.effective_user.full_name,
            source="soundcloud",
        )

        await status.edit_text(
            "✅ *SoundCloud ditemukan!*\n\n"
            f"🎵 *{result['title']}*\n"
            f"👤 Request: {result['requested_by']}\n"
            f"📍 Posisi queue: {result['position']}\n\n"
            "▶️ Musik sedang diproses.",
            parse_mode="Markdown",
            reply_markup=MENU,
        )

    except Exception as exc:

        logger.exception(
            "SoundCloud command failed"
        )

        await status.edit_text(
            "❌ *Gagal memutar SoundCloud.*\n\n"
            f"`{type(exc).__name__}: {exc}`",
            parse_mode="Markdown",
        )


# =========================================================
# /SKIP
# =========================================================

async def skip_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    try:

        title = await player.skip(
            update.effective_chat.id
        )

        if title:

            await update.message.reply_text(
                "⏭ *Skip berhasil!*\n\n"
                f"▶️ Sekarang memainkan:\n"
                f"*{title}*",
                parse_mode="Markdown",
            )

        else:

            await update.message.reply_text(
                "⏭ Queue kosong."
            )

    except Exception as exc:

        await update.message.reply_text(
            f"❌ Gagal skip:\n`{exc}`",
            parse_mode="Markdown",
        )


# =========================================================
# /STOP
# =========================================================

async def stop_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    try:

        await player.stop(
            update.effective_chat.id
        )

        await update.message.reply_text(
            "⏹ *Musik dihentikan.*\n\n"
            "Queue juga sudah dikosongkan.",
            parse_mode="Markdown",
        )

    except Exception as exc:

        await update.message.reply_text(
            f"❌ Gagal stop:\n`{exc}`",
            parse_mode="Markdown",
        )


# =========================================================
# /PAUSE
# =========================================================

async def pause_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    try:

        await player.pause(
            update.effective_chat.id
        )

        await update.message.reply_text(
            "⏸ Musik dijeda."
        )

    except Exception as exc:

        await update.message.reply_text(
            f"❌ Gagal pause:\n`{exc}`",
            parse_mode="Markdown",
        )


# =========================================================
# /RESUME
# =========================================================

async def resume_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    try:

        await player.resume(
            update.effective_chat.id
        )

        await update.message.reply_text(
            "▶️ Musik dilanjutkan."
        )

    except Exception as exc:

        await update.message.reply_text(
            f"❌ Gagal resume:\n`{exc}`",
            parse_mode="Markdown",
        )


# =========================================================
# /QUEUE
# =========================================================

async def queue_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    text = player.queue_text(
        update.effective_chat.id
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    chat_id = query.message.chat.id

    # -----------------------------------------------------
    # CARI LAGU
    # -----------------------------------------------------

    if query.data == "help_play":

        await query.message.reply_text(
            "🎵 *Cara mencari lagu:*\n\n"
            "`/play Faded`\n"
            "`/play The Weeknd`\n\n"
            "🎧 SoundCloud:\n"
            "`/sc The Weeknd`\n\n"
            "🔗 URL:\n"
            "`/play https://youtube.com/...`",
            parse_mode="Markdown",
        )

    # -----------------------------------------------------
    # QUEUE
    # -----------------------------------------------------

    elif query.data == "queue":

        await query.message.reply_text(
            player.queue_text(chat_id),
            parse_mode="Markdown",
        )

    # -----------------------------------------------------
    # SKIP
    # -----------------------------------------------------

    elif query.data == "skip":

        try:

            title = await player.skip(
                chat_id
            )

            if title:

                await query.message.reply_text(
                    "⏭ *Skip berhasil!*\n\n"
                    f"▶️ *{title}*",
                    parse_mode="Markdown",
                )

            else:

                await query.message.reply_text(
                    "⏭ Queue kosong."
                )

        except Exception as exc:

            await query.message.reply_text(
                f"❌ {exc}"
            )

    # -----------------------------------------------------
    # STOP
    # -----------------------------------------------------

    elif query.data == "stop":

        try:

            await player.stop(
                chat_id
            )

            await query.message.reply_text(
                "⏹ Musik dihentikan."
            )

        except Exception as exc:

            await query.message.reply_text(
                f"❌ {exc}"
            )


# =========================================================
# PLAYER START
# =========================================================

async def post_init(
    application: Application,
):

    logger.info(
        "Starting music engine..."
    )

    await player.start()

    logger.info(
        "Music engine started."
    )


# =========================================================
# PLAYER SHUTDOWN
# =========================================================

async def post_shutdown(
    application: Application,
):

    logger.info(
        "Stopping music engine..."
    )

    await player.shutdown()

    logger.info(
        "Music engine stopped."
    )


# =========================================================
# BUILD APPLICATION
# =========================================================

def build_application():

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "play",
            play_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "sc",
            sc_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "skip",
            skip_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "stop",
            stop_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "pause",
            pause_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "resume",
            resume_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "queue",
            queue_command,
        )
    )

    # Buttons
    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    return application


# =========================================================
# MAIN
# =========================================================

async def run_bot():

    # Pastikan variable Railway lengkap
    validate_config()

    application = build_application()

    logger.info(
        "Initializing Telegram bot..."
    )

    await application.initialize()

    await application.start()

    await application.updater.start_polling(
        drop_pending_updates=True
    )

    logger.info(
        "BOT ONLINE."
    )

    try:

        # Menjaga proses tetap hidup
        await asyncio.Event().wait()

    finally:

        logger.info(
            "Stopping Telegram polling..."
        )

        await application.updater.stop()

        await application.stop()

        await application.shutdown()


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            run_bot()
        )

    except KeyboardInterrupt:

        logger.info(
            "Bot stopped manually."
        )
