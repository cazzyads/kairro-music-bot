import logging
from html import escape

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import BOT_TOKEN
from database import (
    init_database,
    add_user,
    add_group,
    add_history,
    get_user_count,
    get_group_count,
    set_volume,
    set_loop,
)
from player import (
    MediaExtractor,
    Media,
    player,
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

init_database()


# ============================================================
# MENU
# ============================================================

def main_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "🎵 MUSIC",
                callback_data="music",
            ),
            InlineKeyboardButton(
                "🎬 WATCH",
                callback_data="watch",
            ),
        ],
        [
            InlineKeyboardButton(
                "📋 QUEUE",
                callback_data="queue",
            ),
            InlineKeyboardButton(
                "🎧 NOW PLAYING",
                callback_data="now",
            ),
        ],
        [
            InlineKeyboardButton(
                "⏸ PAUSE",
                callback_data="pause",
            ),
            InlineKeyboardButton(
                "▶️ RESUME",
                callback_data="resume",
            ),
        ],
        [
            InlineKeyboardButton(
                "⏭ SKIP",
                callback_data="skip",
            ),
            InlineKeyboardButton(
                "⏹ STOP",
                callback_data="stop",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔀 SHUFFLE",
                callback_data="shuffle",
            ),
            InlineKeyboardButton(
                "🔁 LOOP",
                callback_data="loop",
            ),
        ],
        [
            InlineKeyboardButton(
                "📖 HELP",
                callback_data="help",
            ),
        ],
    ]

    return InlineKeyboardMarkup(
        keyboard
    )


# ============================================================
# HELPERS
# ============================================================

def get_user_info(update: Update):

    user = update.effective_user

    if not user:
        return 0, "Unknown"

    name = (
        user.first_name
        or user.username
        or "Unknown"
    )

    return user.id, name


def is_group(update: Update):

    chat = update.effective_chat

    if not chat:
        return False

    return chat.type in (
        "group",
        "supergroup",
    )


def format_duration(seconds):

    if not seconds:
        return "Unknown"

    seconds = int(seconds)

    minutes = seconds // 60

    seconds = seconds % 60

    hours = minutes // 60

    minutes = minutes % 60

    if hours:

        return (
            f"{hours}:{minutes:02d}:{seconds:02d}"
        )

    return (
        f"{minutes}:{seconds:02d}"
    )


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user
    chat = update.effective_chat

    if user:

        add_user(user)

    if chat and chat.type in (
        "group",
        "supergroup",
    ):

        add_group(chat)

    text = (
        "🎵 <b>KAIRO MUSIC + WATCH</b>\n\n"
        "Music & Video Bot untuk Telegram.\n\n"

        "🎵 <b>Music</b>\n"
        "<code>/play judul lagu</code>\n\n"

        "🎬 <b>Watch</b>\n"
        "<code>/vplay judul video</code>\n\n"

        "🌐 Mendukung pencarian YouTube "
        "dan SoundCloud.\n\n"

        "Gunakan tombol di bawah."
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# ============================================================
# /PLAY
# ============================================================

async def play_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_group(update):

        await update.message.reply_text(
            "❌ Gunakan /play di dalam grup."
        )

        return

    if not context.args:

        await update.message.reply_text(
            "🎵 Contoh:\n\n"
            "<code>/play Bruno Mars Just The Way You Are</code>",
            parse_mode=ParseMode.HTML,
        )

        return

    query = " ".join(
        context.args
    )

    user_id, user_name = (
        get_user_info(update)
    )

    status = await update.message.reply_text(
        "🔎 <b>Mencari lagu...</b>\n\n"
        f"🎵 {escape(query)}",
        parse_mode=ParseMode.HTML,
    )

    info = await __import__(
        "asyncio"
    ).to_thread(
        MediaExtractor.search_audio,
        query,
    )

    if not info:

        await status.edit_text(
            "❌ Lagu tidak ditemukan."
        )

        return

    media = MediaExtractor.make_media(
        info,
        "audio",
        user_id,
        user_name,
    )

    if not media:

        await status.edit_text(
            "❌ Stream lagu tidak tersedia."
        )

        return

    position = await player.add(
        update.effective_chat.id,
        media,
    )

    add_history(
        user_id=user_id,
        chat_id=update.effective_chat.id,
        title=media.title,
        url=media.url,
        media_type="audio",
    )

    text = (
        "🎵 <b>DITAMBAHKAN KE QUEUE</b>\n\n"
        f"🎧 <b>{escape(media.title)}</b>\n"
        f"⏱ {format_duration(media.duration)}\n"
        f"👤 {escape(user_name)}\n\n"
        f"📋 Posisi queue: <b>{position}</b>"
    )

    await status.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# ============================================================
# /VPLAY
# ============================================================

async def vplay_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_group(update):

        await update.message.reply_text(
            "❌ Gunakan /vplay di dalam grup."
        )

        return

    if not context.args:

        await update.message.reply_text(
            "🎬 Contoh:\n\n"
            "<code>/vplay Naruto opening 1</code>",
            parse_mode=ParseMode.HTML,
        )

        return

    query = " ".join(
        context.args
    )

    user_id, user_name = (
        get_user_info(update)
    )

    status = await update.message.reply_text(
        "🔎 <b>Mencari video...</b>\n\n"
        f"🎬 {escape(query)}",
        parse_mode=ParseMode.HTML,
    )

    info = await __import__(
        "asyncio"
    ).to_thread(
        MediaExtractor.search_video,
        query,
    )

    if not info:

        await status.edit_text(
            "❌ Video tidak ditemukan."
        )

        return

    media = MediaExtractor.make_media(
        info,
        "video",
        user_id,
        user_name,
    )

    if not media:

        await status.edit_text(
            "❌ Stream video tidak tersedia."
        )

        return

    position = await player.add(
        update.effective_chat.id,
        media,
    )

    add_history(
        user_id=user_id,
        chat_id=update.effective_chat.id,
        title=media.title,
        url=media.url,
        media_type="video",
    )

    text = (
        "🎬 <b>VIDEO DITAMBAHKAN</b>\n\n"
        f"🎞 <b>{escape(media.title)}</b>\n"
        f"⏱ {format_duration(media.duration)}\n"
        f"👤 {escape(user_name)}\n\n"
        f"📋 Posisi queue: <b>{position}</b>"
    )

    await status.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# ============================================================
# /PAUSE
# ============================================================

async def pause_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    if player.pause(chat_id):

        await update.message.reply_text(
            "⏸️ <b>Player dijeda.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )

    else:

        await update.message.reply_text(
            "❌ Tidak ada media yang sedang diputar."
        )


# ============================================================
# /RESUME
# ============================================================

async def resume_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    if player.resume(chat_id):

        await update.message.reply_text(
            "▶️ <b>Player dilanjutkan.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )

    else:

        await update.message.reply_text(
            "❌ Player tidak sedang pause."
        )


# ============================================================
# /SKIP
# ============================================================

async def skip_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    media = await player.skip(
        chat_id
    )

    if not media:

        await update.message.reply_text(
            "⏭️ Queue kosong."
        )

        return

    await update.message.reply_text(
        "⏭️ <b>Berikutnya:</b>\n\n"
        f"🎧 {escape(media.title)}",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# ============================================================
# /STOP
# ============================================================

async def stop_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    player.stop(chat_id)

    await update.message.reply_text(
        "⏹️ <b>Player dihentikan.</b>\n\n"
        "Queue dikosongkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# ============================================================
# /QUEUE
# ============================================================

async def queue_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    current = player.get_current(
        chat_id
    )

    queue = player.get_queue(
        chat_id
    )

    if not current and not queue:

        await update.message.reply_text(
            "📋 Queue kosong."
        )

        return

    text = "📋 <b>QUEUE</b>\n\n"

    if current:

        icon = (
            "🎬"
            if current.media_type == "video"
            else "🎵"
        )

        text += (
            f"{icon} <b>NOW PLAYING</b>\n"
            f"{escape(current.title)}\n"
            f"👤 {escape(current.requested_name)}\n\n"
        )

    if queue:

        text += "<b>UP NEXT</b>\n"

        for index, media in enumerate(
            queue[:20],
            start=1,
        ):

            icon = (
                "🎬"
                if media.media_type == "video"
                else "🎵"
            )

            text += (
                f"{index}. {icon} "
                f"{escape(media.title)}\n"
            )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# /NOW
# ============================================================

async def now_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    media = player.get_current(
        chat_id
    )

    if not media:

        await update.message.reply_text(
            "🎧 Tidak ada media yang sedang diputar."
        )

        return

    icon = (
        "🎬"
        if media.media_type == "video"
        else "🎵"
    )

    await update.message.reply_text(
        f"{icon} <b>NOW PLAYING</b>\n\n"
        f"🎧 {escape(media.title)}\n"
        f"⏱ {format_duration(media.duration)}\n"
        f"👤 {escape(media.requested_name)}",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# ============================================================
# /SHUFFLE
# ============================================================

async def shuffle_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if player.shuffle(
        update.effective_chat.id
    ):

        await update.message.reply_text(
            "🔀 Queue berhasil diacak."
        )

    else:

        await update.message.reply_text(
            "❌ Minimal 2 media diperlukan."
        )


# ============================================================
# /LOOP
# ============================================================

async def loop_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    current = player.loop.get(
        chat_id,
        False,
    )

    new_value = not current

    player.set_loop(
        chat_id,
        new_value,
    )

    set_loop(
        chat_id,
        new_value,
    )

    status = (
        "AKTIF"
        if new_value
        else "NONAKTIF"
    )

    await update.message.reply_text(
        f"🔁 Loop: <b>{status}</b>",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# /VOLUME
# ============================================================

async def volume_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    if not context.args:

        await update.message.reply_text(
            f"🔊 Volume: "
            f"<b>{player.get_volume(chat_id)}%</b>\n\n"
            "Contoh:\n"
            "<code>/volume 50</code>",
            parse_mode=ParseMode.HTML,
        )

        return

    try:

        volume = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "❌ Masukkan angka 1-100."
        )

        return

    if volume < 1 or volume > 100:

        await update.message.reply_text(
            "❌ Volume harus 1-100."
        )

        return

    player.set_volume(
        chat_id,
        volume,
    )

    set_volume(
        chat_id,
        volume,
    )

    await update.message.reply_text(
        f"🔊 Volume: <b>{volume}%</b>",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# /STATS
# ============================================================

async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    users = get_user_count()

    groups = get_group_count()

    await update.message.reply_text(
        "📊 <b>KAIRO STATISTICS</b>\n\n"
        f"👤 Users: <b>{users}</b>\n"
        f"👥 Groups: <b>{groups}</b>",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# /HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "📖 <b>KAIRO MUSIC + WATCH</b>\n\n"

        "🎵 <b>MUSIC</b>\n"
        "<code>/play judul lagu</code>\n"
        "<code>/pause</code>\n"
        "<code>/resume</code>\n"
        "<code>/skip</code>\n"
        "<code>/stop</code>\n"
        "<code>/queue</code>\n"
        "<code>/now</code>\n"
        "<code>/shuffle</code>\n"
        "<code>/loop</code>\n"
        "<code>/volume 50</code>\n\n"

        "🎬 <b>WATCH</b>\n"
        "<code>/vplay judul video</code>\n\n"

        "📊 <b>INFO</b>\n"
        "<code>/stats</code>",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# BUTTON HANDLER
# ============================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    chat_id = query.message.chat_id

    action = query.data

    if action == "pause":

        player.pause(chat_id)

        await query.answer(
            "⏸ Pause"
        )

    elif action == "resume":

        player.resume(chat_id)

        await query.answer(
            "▶️ Resume"
        )

    elif action == "skip":

        await player.skip(
            chat_id
        )

        await query.answer(
            "⏭ Skip"
        )

    elif action == "stop":

        player.stop(chat_id)

        await query.answer(
            "⏹ Stop"
        )

    elif action == "shuffle":

        player.shuffle(chat_id)

        await query.answer(
            "🔀 Shuffle"
        )

    elif action == "loop":

        current = player.loop.get(
            chat_id,
            False,
        )

        player.set_loop(
            chat_id,
            not current,
        )

        await query.answer(
            "🔁 Loop"
        )

    elif action == "queue":

        queue = player.get_queue(
            chat_id
        )

        if not queue:

            await query.answer(
                "📋 Queue kosong.",
                show_alert=True,
            )

            return

        text = "📋 QUEUE\n\n"

        for index, media in enumerate(
            queue[:10],
            start=1,
        ):

            text += (
                f"{index}. "
                f"{media.title}\n"
            )

        await query.message.reply_text(
            text
        )

    elif action == "now":

        media = player.get_current(
            chat_id
        )

        if not media:

            await query.answer(
                "Tidak ada media.",
                show_alert=True,
            )

            return

        await query.message.reply_text(
            f"🎧 {media.title}"
        )

    elif action == "music":

        await query.message.reply_text(
            "🎵 Music:\n\n"
            "<code>/play judul lagu</code>",
            parse_mode=ParseMode.HTML,
        )

    elif action == "watch":

        await query.message.reply_text(
            "🎬 Watch:\n\n"
            "<code>/vplay judul video</code>",
            parse_mode=ParseMode.HTML,
        )

    elif action == "help":

        await query.message.reply_text(
            "📖 Gunakan /help untuk melihat semua command."
        )


# ============================================================
# ERROR
# ============================================================

async def error_handler(
    update,
    context,
):

    logger.error(
        "BOT ERROR",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN belum diatur."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
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
            "play",
            play_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "vplay",
            vplay_command,
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
            "queue",
            queue_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "now",
            now_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "shuffle",
            shuffle_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "loop",
            loop_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "volume",
            volume_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            stats_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    # Buttons

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # Error

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "KAIRO MUSIC + WATCH STARTING..."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
