import os
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
    MessageHandler,
    filters,
)

from config import BOT_TOKEN
from database import (
    init_database,
    add_user,
    add_group,
    add_history,
    get_user_count,
    get_group_count,
    get_settings,
    set_volume,
    set_loop,
)
from player import (
    MediaItem,
    player_manager,
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
# STARTUP
# ============================================================

init_database()


# ============================================================
# HELPER
# ============================================================

def is_group(update: Update) -> bool:
    chat = update.effective_chat

    if not chat:
        return False

    return chat.type in (
        "group",
        "supergroup",
    )


def get_requester(update: Update):
    user = update.effective_user

    if not user:
        return 0, "Unknown"

    name = user.first_name or user.username or "Unknown"

    return user.id, name


def main_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "🎵 MUSIC",
                callback_data="music_menu",
            ),
            InlineKeyboardButton(
                "🎬 WATCH",
                callback_data="watch_menu",
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

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# /START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    chat = update.effective_chat

    if user:
        add_user(user)

    if chat and chat.type in ("group", "supergroup"):
        add_group(chat)

    text = (
        "🎵 <b>KAIRO MUSIC + WATCH</b>\n\n"
        "Selamat datang!\n\n"
        "Bot ini dirancang untuk musik dan video "
        "di group voice/video chat.\n\n"
        "🎵 <b>Music</b>\n"
        "<code>/play judul lagu</code>\n\n"
        "🎬 <b>Watch</b>\n"
        "<code>/vplay judul video</code>\n\n"
        "Gunakan tombol di bawah untuk kontrol player."
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# ============================================================
# /HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = (
        "📖 <b>KAIRO MUSIC + WATCH</b>\n\n"

        "🎵 <b>MUSIC</b>\n"
        "/play &lt;judul&gt;\n"
        "/pause\n"
        "/resume\n"
        "/skip\n"
        "/stop\n"
        "/queue\n"
        "/now\n"
        "/shuffle\n"
        "/loop\n"
        "/volume &lt;1-100&gt;\n\n"

        "🎬 <b>WATCH</b>\n"
        "/vplay &lt;judul&gt;\n\n"

        "🎧 <b>VOICE CHAT</b>\n"
        "/join\n"
        "/leave\n\n"

        "📊 <b>INFO</b>\n"
        "/stats\n"
        "/help"
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
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
            "🎵 <b>Cara penggunaan:</b>\n\n"
            "<code>/play judul lagu</code>",
            parse_mode=ParseMode.HTML,
        )

        return

    query = " ".join(context.args)

    user_id, user_name = get_requester(update)

    chat_id = update.effective_chat.id

    item = MediaItem(
        title=query,
        url=query,
        media_type="audio",
        requested_by=user_id,
        requested_name=user_name,
    )

    await player_manager.add(
        chat_id,
        item,
    )

    add_history(
        user_id=user_id,
        chat_id=chat_id,
        title=query,
        url=query,
        media_type="audio",
    )

    await update.message.reply_text(
        "🎵 <b>Ditambahkan ke queue</b>\n\n"
        f"🎧 {escape(query)}\n"
        f"👤 {escape(user_name)}",
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
            "🎬 <b>Cara penggunaan:</b>\n\n"
            "<code>/vplay judul video</code>",
            parse_mode=ParseMode.HTML,
        )

        return

    query = " ".join(context.args)

    user_id, user_name = get_requester(update)

    chat_id = update.effective_chat.id

    item = MediaItem(
        title=query,
        url=query,
        media_type="video",
        requested_by=user_id,
        requested_name=user_name,
    )

    await player_manager.add(
        chat_id,
        item,
    )

    add_history(
        user_id=user_id,
        chat_id=chat_id,
        title=query,
        url=query,
        media_type="video",
    )

    await update.message.reply_text(
        "🎬 <b>Video ditambahkan ke queue</b>\n\n"
        f"🎞️ {escape(query)}\n"
        f"👤 {escape(user_name)}",
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

    success = player_manager.pause(chat_id)

    if not success:

        await update.message.reply_text(
            "❌ Tidak ada lagu/video yang sedang diputar."
        )

        return

    await update.message.reply_text(
        "⏸ <b>Player dijeda.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# ============================================================
# /RESUME
# ============================================================

async def resume_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    success = player_manager.resume(chat_id)

    if not success:

        await update.message.reply_text(
            "❌ Player tidak sedang dijeda."
        )

        return

    await update.message.reply_text(
        "▶️ <b>Player dilanjutkan.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# ============================================================
# /SKIP
# ============================================================

async def skip_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    item = await player_manager.skip(chat_id)

    if item is None:

        await update.message.reply_text(
            "⏭️ Queue sudah kosong."
        )

        return

    await update.message.reply_text(
        "⏭️ <b>Skip.</b>\n\n"
        f"▶️ {escape(item.title)}",
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

    player_manager.stop(chat_id)

    await update.message.reply_text(
        "⏹️ <b>Player dihentikan.</b>\n\n"
        "Queue telah dikosongkan.",
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

    queue = player_manager.get_queue(chat_id)

    current = player_manager.current(chat_id)

    if not current and not queue:

        await update.message.reply_text(
            "📋 Queue kosong."
        )

        return

    text = "📋 <b>QUEUE</b>\n\n"

    if current:

        text += (
            "🎧 <b>NOW PLAYING</b>\n"
            f"▶️ {escape(current.title)}\n"
            f"👤 {escape(current.requested_name)}\n\n"
        )

    if queue:

        text += "<b>Berikutnya:</b>\n"

        for index, item in enumerate(
            queue[:20],
            start=1,
        ):

            icon = (
                "🎬"
                if item.media_type == "video"
                else "🎵"
            )

            text += (
                f"{index}. {icon} "
                f"{escape(item.title)}\n"
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

    current = player_manager.current(chat_id)

    if not current:

        await update.message.reply_text(
            "🎧 Tidak ada media yang sedang diputar."
        )

        return

    icon = (
        "🎬"
        if current.media_type == "video"
        else "🎵"
    )

    text = (
        f"{icon} <b>NOW PLAYING</b>\n\n"
        f"▶️ {escape(current.title)}\n"
        f"👤 Request: {escape(current.requested_name)}\n"
        f"🔊 Volume: "
        f"{player_manager.get_player(chat_id).volume}%"
    )

    await update.message.reply_text(
        text,
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

    chat_id = update.effective_chat.id

    success = player_manager.shuffle(chat_id)

    if not success:

        await update.message.reply_text(
            "🔀 Minimal ada 2 lagu/video dalam queue."
        )

        return

    await update.message.reply_text(
        "🔀 <b>Queue berhasil diacak.</b>",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# /LOOP
# ============================================================

async def loop_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    player = player_manager.get_player(chat_id)

    new_value = not player.loop

    player_manager.set_loop(
        chat_id,
        new_value,
    )

    set_loop(
        chat_id,
        new_value,
    )

    status = "AKTIF" if new_value else "NONAKTIF"

    await update.message.reply_text(
        f"🔁 Loop sekarang <b>{status}</b>.",
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

        player = player_manager.get_player(chat_id)

        await update.message.reply_text(
            f"🔊 Volume sekarang: "
            f"<b>{player.volume}%</b>\n\n"
            "Gunakan:\n"
            "<code>/volume 50</code>",
            parse_mode=ParseMode.HTML,
        )

        return

    try:

        volume = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ Volume harus berupa angka 1-100."
        )

        return

    if volume < 1 or volume > 100:

        await update.message.reply_text(
            "❌ Volume harus antara 1-100."
        )

        return

    player_manager.set_volume(
        chat_id,
        volume,
    )

    set_volume(
        chat_id,
        volume,
    )

    await update.message.reply_text(
        f"🔊 Volume diatur ke <b>{volume}%</b>.",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# /JOIN
# ============================================================

async def join_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_group(update):

        await update.message.reply_text(
            "❌ Gunakan /join di grup."
        )

        return

    chat_id = update.effective_chat.id

    player_manager.set_joined(
        chat_id,
        True,
    )

    await update.message.reply_text(
        "🎧 <b>Join request diterima.</b>\n\n"
        "Engine Voice Chat akan menangani koneksi "
        "ke group call setelah player engine aktif.",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# /LEAVE
# ============================================================

async def leave_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    player_manager.stop(chat_id)

    player_manager.set_joined(
        chat_id,
        False,
    )

    await update.message.reply_text(
        "🚪 <b>Player dihentikan dan koneksi ditutup.</b>",
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
        "📊 <b>KAIRO MUSIC STATISTICS</b>\n\n"
        f"👤 Users: <b>{users}</b>\n"
        f"👥 Groups: <b>{groups}</b>",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# CALLBACK BUTTONS
# ============================================================

async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    chat_id = query.message.chat_id

    action = query.data

    if action == "pause":

        if player_manager.pause(chat_id):

            await query.edit_message_text(
                "⏸ Player dijeda.",
                reply_markup=main_menu(),
            )

        else:

            await query.answer(
                "Tidak ada player aktif.",
                show_alert=True,
            )

    elif action == "resume":

        if player_manager.resume(chat_id):

            await query.edit_message_text(
                "▶️ Player dilanjutkan.",
                reply_markup=main_menu(),
            )

        else:

            await query.answer(
                "Player tidak sedang pause.",
                show_alert=True,
            )

    elif action == "skip":

        item = await player_manager.skip(chat_id)

        if item:

            await query.edit_message_text(
                f"⏭️ Berikutnya:\n\n"
                f"▶️ {escape(item.title)}",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu(),
            )

        else:

            await query.edit_message_text(
                "⏭️ Queue kosong.",
                reply_markup=main_menu(),
            )

    elif action == "stop":

        player_manager.stop(chat_id)

        await query.edit_message_text(
            "⏹️ Player dihentikan.",
            reply_markup=main_menu(),
        )

    elif action == "shuffle":

        if player_manager.shuffle(chat_id):

            await query.edit_message_text(
                "🔀 Queue diacak.",
                reply_markup=main_menu(),
            )

        else:

            await query.answer(
                "Minimal 2 item diperlukan.",
                show_alert=True,
            )

    elif action == "loop":

        player = player_manager.get_player(chat_id)

        value = not player.loop

        player_manager.set_loop(
            chat_id,
            value,
        )

        set_loop(
            chat_id,
            value,
        )

        status = "AKTIF" if value else "NONAKTIF"

        await query.edit_message_text(
            f"🔁 Loop: <b>{status}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )

    elif action == "queue":

        queue = player_manager.get_queue(chat_id)

        current = player_manager.current(chat_id)

        text = "📋 <b>QUEUE</b>\n\n"

        if current:

            text += (
                "🎧 "
                f"{escape(current.title)}\n\n"
            )

        if queue:

            for index, item in enumerate(
                queue[:20],
                start=1,
            ):

                icon = (
                    "🎬"
                    if item.media_type == "video"
                    else "🎵"
                )

                text += (
                    f"{index}. {icon} "
                    f"{escape(item.title)}\n"
                )

        else:

            text += "Queue kosong."

        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )

    elif action == "now":

        current = player_manager.current(chat_id)

        if not current:

            await query.answer(
                "Tidak ada media yang sedang diputar.",
                show_alert=True,
            )

            return

        icon = (
            "🎬"
            if current.media_type == "video"
            else "🎵"
        )

        await query.edit_message_text(
            f"{icon} <b>NOW PLAYING</b>\n\n"
            f"{escape(current.title)}\n"
            f"👤 {escape(current.requested_name)}",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )

    elif action == "music_menu":

        await query.edit_message_text(
            "🎵 <b>MUSIC</b>\n\n"
            "<code>/play judul lagu</code>\n"
            "<code>/pause</code>\n"
            "<code>/resume</code>\n"
            "<code>/skip</code>\n"
            "<code>/stop</code>\n"
            "<code>/queue</code>\n"
            "<code>/volume 50</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )

    elif action == "watch_menu":

        await query.edit_message_text(
            "🎬 <b>WATCH</b>\n\n"
            "<code>/vplay judul video</code>\n\n"
            "Video akan menggunakan group "
            "video chat setelah engine video "
            "diaktifkan.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )

    elif action == "help":

        await query.edit_message_text(
            "📖 <b>HELP</b>\n\n"
            "/play - Music\n"
            "/vplay - Video\n"
            "/pause - Pause\n"
            "/resume - Resume\n"
            "/skip - Skip\n"
            "/stop - Stop\n"
            "/queue - Queue\n"
            "/shuffle - Shuffle\n"
            "/loop - Loop\n"
            "/volume - Volume\n"
            "/join - Join VC\n"
            "/leave - Leave VC",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.error(
        "Exception while handling update:",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN belum ditemukan. "
            "Tambahkan BOT_TOKEN di Railway Variables."
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
            "join",
            join_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "leave",
            leave_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            stats_command,
        )
    )

    # Buttons
    application.add_handler(
        CallbackQueryHandler(
            button_callback
        )
    )

    # Error
    application.add_error_handler(
        error_handler
    )

    logger.info(
        "KAIRO MUSIC + WATCH BOT STARTING..."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
