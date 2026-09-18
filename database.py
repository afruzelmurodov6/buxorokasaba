import logging
from datetime import datetime
from typing import Optional

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Kerakli jadvallarni (agar mavjud bo'lmasa) yaratadi."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
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
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                video_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, video_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (video_id) REFERENCES videos (id)
            )
            """
        )
        await conn.commit()
    logger.info("Ma'lumotlar bazasi jadvallari tayyor.")


async def add_user(telegram_id: int, username: Optional[str], first_name: Optional[str]) -> int:
    """Foydalanuvchini qo'shadi (yoki mavjud bo'lsa yangilaydi). Bazadagi ichki id qaytadi."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        if row:
            await conn.execute(
                "UPDATE users SET username = ?, first_name = ? WHERE telegram_id = ?",
                (username, first_name, telegram_id),
            )
            await conn.commit()
            return row[0]

        cursor = await conn.execute(
            "INSERT INTO users (telegram_id, username, first_name, created_at) VALUES (?, ?, ?, ?)",
            (telegram_id, username, first_name, datetime.now().isoformat()),
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


async def add_video(file_id: str, title: str, description: Optional[str]) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "INSERT INTO videos (file_id, title, description, votes_count, is_active, created_at) "
            "VALUES (?, ?, ?, 0, 1, ?)",
            (file_id, title, description, datetime.now().isoformat()),
        )
        await conn.commit()
        return cursor.lastrowid


async def get_active_videos() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM videos WHERE is_active = 1 ORDER BY created_at ASC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_videos() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM videos ORDER BY created_at ASC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_video(video_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_video(video_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM votes WHERE video_id = ?", (video_id,))
        await conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        await conn.commit()


async def has_voted(user_db_id: int, video_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT 1 FROM votes WHERE user_id = ? AND video_id = ?",
            (user_db_id, video_id),
        )
        row = await cursor.fetchone()
        return row is not None


async def cast_vote(user_db_id: int, video_id: int) -> tuple[bool, int]:
    """
    Ovoz berishga urinadi.

    votes jadvalidagi UNIQUE(user_id, video_id) cheklovi tufayli, bir vaqtda
    bir nechta so'rov kelsa ham (race condition), foydalanuvchi bir videoga
    faqat bir marta ovoz bera oladi — buni SQLite darajasida ta'minlaymiz,
    shunchaki "avval tekshirib keyin yozish" mantig'iga tayanmaymiz.

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
            "SELECT * FROM videos WHERE is_active = 1 ORDER BY votes_count DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        users_count = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM videos WHERE is_active = 1")
        videos_count = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM votes")
        votes_count = (await cursor.fetchone())[0]

    return {"users": users_count, "videos": videos_count, "votes": votes_count}