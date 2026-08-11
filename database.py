import sqlite3
from config import DATABASE_FILE


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_connection():
    conn = sqlite3.connect(
        DATABASE_FILE,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


# ==========================================
# INITIALIZE DATABASE
# ==========================================

def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    # ------------------------------
    # USERS
    # ------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------
    # GROUPS
    # ------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------
    # PLAY HISTORY
    # ------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS play_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            title TEXT,
            url TEXT,
            media_type TEXT,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------
    # GROUP SETTINGS
    # ------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            chat_id INTEGER PRIMARY KEY,
            volume INTEGER DEFAULT 100,
            loop INTEGER DEFAULT 0,
            announce INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()


# ==========================================
# USER FUNCTIONS
# ==========================================

def add_user(user):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (
            user_id,
            username,
            first_name
        )
        VALUES (?, ?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_active = CURRENT_TIMESTAMP
    """, (
        user.id,
        user.username,
        user.first_name
    ))

    conn.commit()
    conn.close()


def get_user_count():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM users
    """)

    result = cursor.fetchone()
    conn.close()

    return result["total"]


# ==========================================
# GROUP FUNCTIONS
# ==========================================

def add_group(chat):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO groups (
            chat_id,
            title
        )
        VALUES (?, ?)

        ON CONFLICT(chat_id)
        DO UPDATE SET
            title = excluded.title,
            last_active = CURRENT_TIMESTAMP
    """, (
        chat.id,
        chat.title
    ))

    conn.commit()
    conn.close()


def get_group_count():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM groups
    """)

    result = cursor.fetchone()
    conn.close()

    return result["total"]


# ==========================================
# PLAY HISTORY
# ==========================================

def add_history(
    user_id,
    chat_id,
    title,
    url,
    media_type
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO play_history (
            user_id,
            chat_id,
            title,
            url,
            media_type
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        chat_id,
        title,
        url,
        media_type
    ))

    conn.commit()
    conn.close()


# ==========================================
# GROUP SETTINGS
# ==========================================

def get_settings(chat_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM settings
        WHERE chat_id = ?
    """, (chat_id,))

    result = cursor.fetchone()

    if result is None:
        cursor.execute("""
            INSERT INTO settings (
                chat_id,
                volume,
                loop,
                announce
            )
            VALUES (?, 100, 0, 1)
        """)

        conn.commit()

        cursor.execute("""
            SELECT *
            FROM settings
            WHERE chat_id = ?
        """, (chat_id,))

        result = cursor.fetchone()

    conn.close()

    return dict(result)


def set_volume(chat_id, volume):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO settings (
            chat_id,
            volume
        )
        VALUES (?, ?)

        ON CONFLICT(chat_id)
        DO UPDATE SET
            volume = excluded.volume
    """, (
        chat_id,
        volume
    ))

    conn.commit()
    conn.close()


def set_loop(chat_id, enabled):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO settings (
            chat_id,
            loop
        )
        VALUES (?, ?)

        ON CONFLICT(chat_id)
        DO UPDATE SET
            loop = excluded.loop
    """, (
        chat_id,
        1 if enabled else 0
    ))

    conn.commit()
    conn.close()


def set_announce(chat_id, enabled):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO settings (
            chat_id,
            announce
        )
        VALUES (?, ?)

        ON CONFLICT(chat_id)
        DO UPDATE SET
            announce = excluded.announce
    """, (
        chat_id,
        1 if enabled else 0
    ))

    conn.commit()
    conn.close()
