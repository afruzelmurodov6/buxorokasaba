import logging
from datetime import datetime
from typing import Optional

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                votes_count INTEGER NOT NULL DEFAULT 0,
                position INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                video_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (video_id) REFERENCES videos (id)
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                added_by INTEGER,
                created_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        await conn.commit()
    logger.info("Ma'lumotlar bazasi jadvallari tayyor.")


# ==================== USERS ====================

async def add_user(
    telegram_id: int,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        if row:
            await conn.execute(
                "UPDATE users SET username = ?, first_name = ?, last_name = ? "
                "WHERE telegram_id = ?",
                (username, first_name, last_name, telegram_id),
            )
            await conn.commit()
            return row[0]

        cursor = await conn.execute(
            "INSERT INTO users (telegram_id, username, first_name, last_name, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (telegram_id, username, first_name, last_name, datetime.now().isoformat()),
        )
        await conn.commit()
        return cursor.lastrowid


async def get_user_db_id(telegram_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def search_user_by_username(username: str) -> Optional[dict]:
    clean = username.lstrip("@")
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (clean,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def search_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    return await get_user_by_telegram_id(telegram_id)


async def get_users_count() -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        return (await cursor.fetchone())[0]


async def get_all_user_telegram_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT telegram_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_non_voted_telegram_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            """
            SELECT telegram_id FROM users
            WHERE id NOT IN (SELECT user_id FROM votes)
            """
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_all_users_full() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT u.*, v.title AS voted_title
            FROM users u
            LEFT JOIN votes vo ON vo.user_id = u.id
            LEFT JOIN videos v ON v.id = vo.video_id
            ORDER BY u.created_at ASC
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_users_page(offset: int, limit: int) -> list[dict]:
    """Foydalanuvchilar ro'yxati, har biri uchun ovoz bergan videosi (agar bo'lsa) bilan."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT u.*, v.title AS voted_title
            FROM users u
            LEFT JOIN votes vo ON vo.user_id = u.id
            LEFT JOIN videos v ON v.id = vo.video_id
            ORDER BY u.created_at ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_user_vote_title(user_db_id: int) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            """
            SELECT v.title FROM votes vo
            JOIN videos v ON v.id = vo.video_id
            WHERE vo.user_id = ?
            """,
            (user_db_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


# ==================== VIDEOS ====================

async def add_video(file_id: str, title: str, description: Optional[str], position: int) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "INSERT INTO videos (file_id, title, description, votes_count, position, created_at) "
            "VALUES (?, ?, ?, 0, ?, ?)",
            (file_id, title, description, position, datetime.now().isoformat()),
        )
        await conn.commit()
        return cursor.lastrowid


async def get_all_videos() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM videos ORDER BY position ASC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_video(video_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_video(
    video_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    position: Optional[int] = None,
) -> None:
    fields = []
    values = []
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if position is not None:
        fields.append("position = ?")
        values.append(position)
    if not fields:
        return
    values.append(video_id)
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(f"UPDATE videos SET {', '.join(fields)} WHERE id = ?", values)
        await conn.commit()


async def get_video_count() -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM videos")
        return (await cursor.fetchone())[0]


async def delete_video(video_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM votes WHERE video_id = ?", (video_id,))
        await conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        await conn.commit()


# ==================== VOTES (1 foydalanuvchi = 1 ovoz, butun tanlov bo'yicha) ====================

async def has_voted(user_db_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT 1 FROM votes WHERE user_id = ?", (user_db_id,)
        )
        row = await cursor.fetchone()
        return row is not None


async def get_user_voted_video_id(user_db_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT video_id FROM votes WHERE user_id = ?", (user_db_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def cast_vote(user_db_id: int, video_id: int) -> tuple[bool, int]:
    """
    Foydalanuvchi butun tanlov davomida faqat BITTA ovozga ega bo'lishi uchun,
    votes.user_id ustunida UNIQUE cheklovi ishlatiladi. Shu tufayli parallel
    so'rovlar kelsa ham (race condition), ikkinchi marta ovoz yozilmaydi.

    Qaytaradi: (muvaffaqiyatli_bo'ldimi, video_ning_joriy_ovozlar_soni)
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        try:
            await conn.execute("BEGIN IMMEDIATE")
            await conn.execute(
                "INSERT INTO votes (user_id, video_id, created_at) VALUES (?, ?, ?)",
                (user_db_id, video_id, datetime.now().isoformat()),
            )
            await conn.execute(
                "UPDATE videos SET votes_count = votes_count + 1 WHERE id = ?",
                (video_id,),
            )
            await conn.commit()
            success = True
        except aiosqlite.IntegrityError:
            await conn.rollback()
            success = False

        cursor = await conn.execute(
            "SELECT votes_count FROM videos WHERE id = ?", (video_id,)
        )
        row = await cursor.fetchone()
        current_count = row[0] if row else 0

    return success, current_count


async def get_results() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM videos ORDER BY votes_count DESC, position ASC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ==================== STATISTIKA ====================

async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        users_count = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM videos")
        videos_count = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM votes")
        votes_count = (await cursor.fetchone())[0]

    voted_users = votes_count
    not_voted_users = max(users_count - voted_users, 0)

    return {
        "users": users_count,
        "videos": videos_count,
        "votes": votes_count,
        "voted_users": voted_users,
        "not_voted_users": not_voted_users,
    }


# ==================== ADMINLAR (qo'shimcha, .env dagi ADMIN_ID dan tashqari) ====================

async def add_admin(telegram_id: int, added_by: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as conn:
        try:
            await conn.execute(
                "INSERT INTO admins (telegram_id, added_by, created_at) VALUES (?, ?, ?)",
                (telegram_id, added_by, datetime.now().isoformat()),
            )
            await conn.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_admin(telegram_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))
        await conn.commit()


async def get_admin_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT telegram_id FROM admins ORDER BY created_at ASC")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def is_table_admin(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT 1 FROM admins WHERE telegram_id = ?", (telegram_id,)
        )
        return await cursor.fetchone() is not None


# ==================== SOZLAMALAR (ovoz berish muddati) ====================

async def get_setting(key: str) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await conn.commit()


async def get_voting_period() -> tuple[Optional[str], Optional[str]]:
    start_at = await get_setting("voting_start_at")
    end_at = await get_setting("voting_end_at")
    return start_at, end_at


async def set_voting_period(start_iso: str, end_iso: str) -> None:
    await set_setting("voting_start_at", start_iso)
    await set_setting("voting_end_at", end_iso)
