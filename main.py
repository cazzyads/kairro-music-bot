import asyncio
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN, validate_config
from player import MusicPlayer


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)

logger = logging.getLogger(
    "musicbot"
)


# =========================================================
# MUSIC PLAYER
# =========================================================

player = MusicPlayer()


# =========================================================
# MENU
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
# WELCOME
# =========================================================

def welcome_text():

    return (
        "🎵 *Telegram Music Bot*\n\n"
        "Cari lagu dan putar langsung "
        "ke Voice Chat.\n\n"

        "🎧 *Cara menggunakan:*\n"
        "• `/play Mangu`\n"
        "• `/sc Mangu`\n"
        "• Bisa juga cukup ketik:\n"
        "  `Mangu`\n\n"

        "🎮 *Perintah:*\n"
        "• `/play judul` — cari lagu\n"
        "• `/sc judul` — cari SoundCloud\n"
        "• `/skip` — lagu berikutnya\n"
        "• `/queue` — lihat antrean\n"
        "• `/stop` — hentikan musik\n"
        "• `/pause` — jeda musik\n"
        "• `/resume` — lanjutkan musik\n\n"

        "⚠️ Akun musik harus berada di grup "
        "dan mempunyai akses ke Voice Chat."
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
# PLAY ENGINE
# =========================================================

async def process_song(
    update: Update,
    song_query: str,
):

    if not update.message:
        return

    query_text = (
        song_query or ""
    ).strip()

    if not query_text:
        return

    status = await update.message.reply_text(
        f"🔎 Mencari *{query_text}*...\n"
        "⏳ Tunggu sebentar.",
        parse_mode="Markdown",
    )

    try:

        user = update.effective_user

        requested_by = (
            user.full_name
            if user
            else "Unknown"
        )

        result = await player.enqueue(
            chat_id=update.effective_chat.id,
            query=query_text,
            requested_by=requested_by,
            source="soundcloud",
        )

        if result["position"] == 0:

            message = (
                "✅ *Lagu ditemukan!*\n\n"
                f"🎵 *{result['title']}*\n"
                f"👤 Request: {result['requested_by']}\n\n"
                "▶️ *Sedang diputar di Voice Chat.*"
            )

        else:

            message = (
                "✅ *Lagu masuk queue!*\n\n"
                f"🎵 *{result['title']}*\n"
                f"👤 Request: {result['requested_by']}\n"
                f"📍 Posisi: {result['position']}\n\n"
                "⏳ Akan diputar setelah lagu sebelumnya."
            )

        await status.edit_text(
            message,
            parse_mode="Markdown",
            reply_markup=MENU,
        )

    except Exception as exc:

        logger.exception(
            "Song processing failed"
        )

        error_text = str(
            exc
        )

        # Jangan tampilkan traceback panjang
        # ke user.
        if len(error_text) > 500:
            error_text = (
                error_text[:500]
                + "..."
            )

        await status.edit_text(
            "❌ *Gagal memutar lagu.*\n\n"
            f"`{type(exc).__name__}: "
            f"{error_text}`\n\n"
            "Pastikan Voice Chat aktif dan "
            "akun musik sudah berada di grup.",
            parse_mode="Markdown",
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
            "❌ Masukkan judul lagu.\n\n"
            "Contoh:\n"
            "`/play Mangu`\n"
            "`/play Hindia Secukupnya`",
            parse_mode="Markdown",
        )

        return

    await process_song(
        update,
        query,
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
            "❌ Masukkan judul lagu.\n\n"
            "Contoh:\n"
            "`/sc Mangu`\n"
            "`/sc The Weeknd`",
            parse_mode="Markdown",
        )

        return

    await process_song(
        update,
        query,
    )


# =========================================================
# PESAN BIASA = CARI LAGU
# =========================================================

async def text_song_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    text = (
        update.message.text or ""
    ).strip()

    if not text:
        return

    # Jangan proses pesan yang terlalu pendek.
    if len(text) < 2:
        return

    # Langsung dianggap sebagai pencarian lagu.
    await process_song(
        update,
        text,
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
                f"▶️ *{title}*",
                parse_mode="Markdown",
            )

        else:

            await update.message.reply_text(
                "⏭ Queue kosong."
            )

    except Exception as exc:

        logger.exception(
            "Skip failed"
        )

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
            "Queue sudah dikosongkan.",
            parse_mode="Markdown",
        )

    except Exception as exc:

        logger.exception(
            "Stop failed"
        )

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

    if not query.message:
        return

    chat_id = (
        query.message.chat.id
    )

    # -----------------------------------------------------
    # CARI LAGU
    # -----------------------------------------------------

    if query.data == "help_play":

        await query.message.reply_text(
            "🎵 *Cara mencari lagu:*\n\n"
            "Bisa pakai:\n"
            "`/play Mangu`\n\n"
            "atau cukup kirim:\n"
            "`Mangu`\n\n"
            "Bot akan mencari lagu di "
            "SoundCloud dan memutarnya "
            "ke Voice Chat.",
            parse_mode="Markdown",
        )

    # -----------------------------------------------------
    # QUEUE
    # -----------------------------------------------------

    elif query.data == "queue":

        await query.message.reply_text(
            player.queue_text(
                chat_id
            ),
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

            logger.exception(
                "Button skip failed"
            )

            await query.message.reply_text(
                f"❌ Gagal skip:\n`{exc}`",
                parse_mode="Markdown",
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
                f"❌ Gagal stop:\n`{exc}`"
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

    # -----------------------------------------------------
    # COMMANDS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # BUTTONS
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # -----------------------------------------------------
    # TEXT BIASA = CARI LAGU
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            text_song_handler,
        )
    )

    return application


# =========================================================
# MAIN
# =========================================================

async def run_bot():

    validate_config()

    application = build_application()

    logger.info(
        "Initializing Telegram bot..."
    )

    await application.initialize()

    await post_init(
        application
    )

    await application.start()

    await application.updater.start_polling(
        drop_pending_updates=True
    )

    logger.info(
        "BOT ONLINE."
    )

    try:

        await asyncio.Event().wait()

    finally:

        logger.info(
            "Stopping Telegram polling..."
        )

        try:
            await application.updater.stop()
        except Exception:
            pass

        try:
            await application.stop()
        except Exception:
            pass

        try:
            await application.shutdown()
        except Exception:
            pass


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
