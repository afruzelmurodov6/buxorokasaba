import json
import logging
import os
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
                position INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
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
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vote_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                admin_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_cancelled INTEGER NOT NULL DEFAULT 0,
                cancelled_at TEXT,
                cancelled_by INTEGER,
                FOREIGN KEY (video_id) REFERENCES videos (id)
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS final_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                confirmed_by INTEGER NOT NULL,
                results_snapshot TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await conn.commit()

        # Migratsiya: eski bazalarda ba'zi ustunlar yo'q bo'lishi mumkin.
        cursor = await conn.execute("PRAGMA table_info(users)")
        existing_columns = {row[1] for row in await cursor.fetchall()}
        if "last_name" not in existing_columns:
            await conn.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
            await conn.commit()
            logger.info("Migratsiya: users jadvaliga last_name ustuni qo'shildi.")

        cursor = await conn.execute("PRAGMA table_info(videos)")
        existing_columns = {row[1] for row in await cursor.fetchall()}
        if "position" not in existing_columns:
            await conn.execute("ALTER TABLE videos ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
            await conn.commit()
            logger.info("Migratsiya: videos jadvaliga position ustuni qo'shildi.")
        if "is_active" not in existing_columns:
            await conn.execute("ALTER TABLE videos ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
            await conn.commit()
            logger.info("Migratsiya: videos jadvaliga is_active ustuni qo'shildi.")

    logger.info("Ma'lumotlar bazasi jadvallari tayyor.")

    await merge_legacy_backup()


async def merge_legacy_backup(backup_path: str = "backup_data.json") -> None:
    """
    Agar loyiha ildizida backup_data.json fayli bo'lsa (avvalgi xato kod
    tomonidan bazani tozalashdan oldin saqlangan zaxira), undagi
    foydalanuvchi va ovozlarni JORIY bazaga xavfsiz qo'shib qo'yadi.

    - Hozirgi bazada allaqachon mavjud bo'lgan foydalanuvchilar (telegram_id
      orqali) qayta qo'shilmaydi va ustiga yozilmaydi.
    - Bu funksiya faqat BIR MARTA ishlaydi (settings jadvalidagi belgi orqali).
    """
    if not os.path.exists(backup_path):
        return

    already_merged = await get_setting("legacy_backup_merged")
    if already_merged == "1":
        return

    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"backup_data.json o'qishda xato: {e}")
        return

    videos = await get_all_videos()
    title_to_id = {v["title"]: v["id"] for v in videos}

    added_users = 0
    added_votes = 0

    async with aiosqlite.connect(DB_PATH) as conn:
        for user in data.get("users", []):
            telegram_id = user.get("telegram_id")
            if telegram_id is None:
                continue

            cursor = await conn.execute(
                "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
            if row:
                continue  # Bu foydalanuvchi jonli bazada allaqachon bor — teginmaymiz

            cursor = await conn.execute(
                "INSERT INTO users (telegram_id, username, first_name, last_name, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    telegram_id,
                    user.get("username"),
                    user.get("first_name"),
                    user.get("last_name"),
                    user.get("created_at") or datetime.now().isoformat(),
                ),
            )
            user_db_id = cursor.lastrowid
            added_users += 1

            voted_title = user.get("voted_title")
            if voted_title and voted_title in title_to_id:
                video_id = title_to_id[voted_title]
                try:
                    await conn.execute(
                        "INSERT INTO votes (user_id, video_id, created_at) VALUES (?, ?, ?)",
                        (user_db_id, video_id, datetime.now().isoformat()),
                    )
                    await conn.execute(
                        "UPDATE videos SET votes_count = votes_count + 1 WHERE id = ?",
                        (video_id,),
                    )
                    added_votes += 1
                except aiosqlite.IntegrityError:
                    pass

        await conn.commit()

    await set_setting("legacy_backup_merged", "1")
    logger.info(
        f"Eski zaxira (backup_data.json) qo'shildi: {added_users} ta yangi foydalanuvchi, "
        f"{added_votes} ta ovoz tiklandi."
    )


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
            "SELECT telegram_id FROM users WHERE id NOT IN (SELECT user_id FROM votes)"
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


VIDEO_SELECT_WITH_ADJUSTMENTS = """
    SELECT
        v.id, v.file_id, v.title, v.description, v.position, v.is_active, v.created_at,
        v.votes_count AS organic_votes_count,
        v.votes_count + COALESCE(adj.total, 0) AS votes_count
    FROM videos v
    LEFT JOIN (
        SELECT video_id, SUM(amount) AS total
        FROM vote_adjustments
        WHERE is_cancelled = 0
        GROUP BY video_id
    ) adj ON adj.video_id = v.id
"""


async def get_all_videos() -> list[dict]:
    """Faqat FAOL (o'chirilmagan) videolarni qaytaradi — foydalanuvchilar shularni ko'radi.
    votes_count — organik (haqiqiy) ovozlar + tasdiqlangan tuzatish ovozlari yig'indisi.
    organic_votes_count — faqat haqiqiy foydalanuvchi ovozlari (tuzatishlarsiz)."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            VIDEO_SELECT_WITH_ADJUSTMENTS + " WHERE v.is_active = 1 ORDER BY v.position ASC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_videos_including_inactive() -> list[dict]:
    """Admin uchun: o'chirilgan (yashirin) videolarni ham qo'shib qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(VIDEO_SELECT_WITH_ADJUSTMENTS + " ORDER BY v.position ASC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_video(video_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            VIDEO_SELECT_WITH_ADJUSTMENTS + " WHERE v.id = ?", (video_id,)
        )
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
    """
    XAVFSIZ o'chirish: videoni haqiqatda o'chirmaydi, faqat yashiradi
    (is_active = 0). Ovozlar butunlay saqlanib qoladi. Kerak bo'lsa
    restore_video() orqali qaytarish mumkin.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("UPDATE videos SET is_active = 0 WHERE id = ?", (video_id,))
        await conn.commit()


async def restore_video(video_id: int) -> None:
    """Yashiringan (xato o'chirilgan) videoni, ovozlari bilan birga qayta faollashtiradi."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("UPDATE videos SET is_active = 1 WHERE id = ?", (video_id,))
        await conn.commit()


# ==================== VOTES ====================

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
            VIDEO_SELECT_WITH_ADJUSTMENTS
            + " WHERE v.is_active = 1 ORDER BY votes_count DESC, v.position ASC"
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


# ==================== ADMINLAR ====================

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


# ==================== SOZLAMALAR ====================

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


async def end_voting_now() -> None:
    """Admin uchun tezkor tugma: ovoz berishni AYNAN HOZIR yakunlaydi
    (sana kiritish shart emas). Agar boshlanish sanasi hali belgilanmagan
    bo'lsa, uni ham kechagi sana bilan avtomatik to'ldiradi."""
    from datetime import timedelta

    now = datetime.now()
    start_iso, _ = await get_voting_period()
    if not start_iso:
        start_iso = (now - timedelta(days=1)).isoformat()
    end_iso = (now - timedelta(seconds=1)).isoformat()
    await set_voting_period(start_iso, end_iso)


# ==================== OVOZ TUZATISHLARI (adolat uchun, to'liq shaffof) ====================
# Texnik nosozlik sabab yo'qolgan ovozlarni qayta hisobga olish uchun.
# Har bir tuzatish: kim, qachon, qancha, nima sababdan qo'shgani bilan saqlanadi.
# Bu ovozlar videos.votes_count ustuniga TEGMAYDI — alohida jadvalda saqlanadi
# va faqat KO'RSATISHDA (get_all_videos/get_video/get_results orqali) asl
# ovozlarga qo'shib chiqariladi, shunda har doim manba (organik/tuzatish)
# ajratib olinishi mumkin.

async def add_vote_adjustment(video_id: int, amount: int, admin_id: int, reason: str) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "INSERT INTO vote_adjustments (video_id, amount, admin_id, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (video_id, amount, admin_id, reason, datetime.now().isoformat()),
        )
        await conn.commit()
        return cursor.lastrowid


async def get_all_adjustments() -> list[dict]:
    """Barcha tuzatishlar tarixi (bekor qilinganlari ham), video nomi bilan birga."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT va.*, v.title AS video_title
            FROM vote_adjustments va
            JOIN videos v ON v.id = va.video_id
            ORDER BY va.created_at DESC
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_adjustment(adjustment_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT va.*, v.title AS video_title
            FROM vote_adjustments va
            JOIN videos v ON v.id = va.video_id
            WHERE va.id = ?
            """,
            (adjustment_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def cancel_adjustment(adjustment_id: int, cancelled_by: int) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE vote_adjustments SET is_cancelled = 1, cancelled_at = ?, cancelled_by = ? "
            "WHERE id = ?",
            (datetime.now().isoformat(), cancelled_by, adjustment_id),
        )
        await conn.commit()


# ==================== AUDIT LOG (barcha muhim admin harakatlari) ====================

async def log_audit(admin_id: int, action: str, details: str = "") -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO audit_log (admin_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (admin_id, action, details, datetime.now().isoformat()),
        )
        await conn.commit()


async def get_audit_log(limit: int = 30) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ==================== ANTI-FRAUD: FAQAT ANIQLASH, HECH NARSA AVTOMATIK O'ZGARMAYDI ====================
# MUHIM: bu funksiyalar faqat ADMIN uchun TEKSHIRUV SIGNALI beradi.
# IP, telefon yoki boshqa mavjud bo'lmagan ma'lumot ishlatilmaydi — faqat
# users/votes jadvalidagi haqiqiy vaqt belgilari va nomlar solishtiriladi.
# Hech qanday ovoz yoki foydalanuvchi bu yerda avtomatik o'chirilmaydi yoki
# "firibgar" deb belgilanmaydi — faqat ro'yxat ko'rsatiladi, qaror admin uchun.

FAST_VOTE_THRESHOLD_SECONDS = 10  # ro'yxatdan o'tish -> ovoz berish orasi shundan tez bo'lsa, shubhali
BURST_WINDOW_SECONDS = 30  # shu oyna ichida qancha akkaunt yaratilgani tekshiriladi
BURST_MIN_ACCOUNTS = 5  # shu oyna ichida kamida shuncha akkaunt bo'lsa, "burst" deb belgilanadi


async def get_fast_signup_to_vote() -> list[dict]:
    """
    Foydalanuvchi ro'yxatdan o'tishi bilan ovoz berishi orasida juda kam vaqt
    o'tgan holatlar (masalan, 10 soniyadan kam) — bu odatiy foydalanuvchi
    xatti-harakatiga o'xshamaydi (odam avval botni ko'rib chiqadi, keyin
    ovoz beradi), ko'proq avtomatlashtirilgan/skript orqali qilingan
    harakatlarga xos.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT u.telegram_id, u.username, u.first_name, u.last_name,
                   u.created_at AS user_created_at, vo.created_at AS vote_created_at,
                   v.title AS voted_title
            FROM users u
            JOIN votes vo ON vo.user_id = u.id
            JOIN videos v ON v.id = vo.video_id
            """
        )
        rows = await cursor.fetchall()

    flagged = []
    for row in rows:
        d = dict(row)
        try:
            user_created = datetime.fromisoformat(d["user_created_at"])
            voted_at = datetime.fromisoformat(d["vote_created_at"])
            delta = (voted_at - user_created).total_seconds()
        except (ValueError, TypeError):
            continue
        if 0 <= delta < FAST_VOTE_THRESHOLD_SECONDS:
            d["seconds_to_vote"] = round(delta, 1)
            flagged.append(d)

    flagged.sort(key=lambda x: x["seconds_to_vote"])
    return flagged


async def get_duplicate_name_clusters() -> list[dict]:
    """
    Bir xil (ism, familiya) juftligiga ega, lekin turli Telegram ID'lariga
    ega bo'lgan foydalanuvchilar guruhlari — soxta/nusxa akkauntlar
    yaratishning keng tarqalgan belgisi.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT
                COALESCE(first_name, '') AS first_name,
                COALESCE(last_name, '') AS last_name,
                COUNT(*) AS cnt
            FROM users
            WHERE first_name IS NOT NULL AND first_name != ''
            GROUP BY COALESCE(first_name, ''), COALESCE(last_name, '')
            HAVING COUNT(*) >= 2
            ORDER BY cnt DESC
            """
        )
        clusters = [dict(row) for row in await cursor.fetchall()]

        result = []
        for cluster in clusters:
            cursor = await conn.execute(
                """
                SELECT u.telegram_id, u.username, u.created_at, v.title AS voted_title
                FROM users u
                LEFT JOIN votes vo ON vo.user_id = u.id
                LEFT JOIN videos v ON v.id = vo.video_id
                WHERE COALESCE(u.first_name, '') = ? AND COALESCE(u.last_name, '') = ?
                ORDER BY u.created_at ASC
                """,
                (cluster["first_name"], cluster["last_name"]),
            )
            members = [dict(row) for row in await cursor.fetchall()]
            result.append({
                "first_name": cluster["first_name"],
                "last_name": cluster["last_name"],
                "count": cluster["cnt"],
                "members": members,
            })

    return result


async def get_signup_burst_clusters() -> list[dict]:
    """
    Qisqa vaqt oynasi ichida (masalan 30 soniyada) ro'yxatdan o'tgan va
    HAMMASI bitta ishtirokchiga ovoz bergan akkauntlar guruhini topadi —
    bu ommaviy/skript orqali yaratilgan akkauntlarga xos naqsh.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT u.telegram_id, u.username, u.first_name, u.last_name,
                   u.created_at, v.title AS voted_title
            FROM users u
            JOIN votes vo ON vo.user_id = u.id
            JOIN videos v ON v.id = vo.video_id
            ORDER BY u.created_at ASC
            """
        )
        rows = [dict(row) for row in await cursor.fetchall()]

    clusters = []
    i = 0
    n = len(rows)
    while i < n:
        window_start = datetime.fromisoformat(rows[i]["created_at"])
        j = i
        window = []
        while j < n:
            t = datetime.fromisoformat(rows[j]["created_at"])
            if (t - window_start).total_seconds() <= BURST_WINDOW_SECONDS:
                window.append(rows[j])
                j += 1
            else:
                break

        if len(window) >= BURST_MIN_ACCOUNTS:
            titles_in_window = {r["voted_title"] for r in window}
            if len(titles_in_window) == 1:
                clusters.append({
                    "video_title": window[0]["voted_title"],
                    "count": len(window),
                    "window_start": window[0]["created_at"],
                    "window_end": window[-1]["created_at"],
                    "members": window,
                })
                i = j
            else:
                # Aralash unvonli katta oyna — haqiqiy klaster shu oynaning
                # ichida kichikroq joyda bo'lishi mumkin, shuning uchun faqat
                # 1 qadam siljib, qaytadan tekshiramiz (j ga sakramaymiz).
                i += 1
        else:
            i += 1

    return clusters


async def get_fraud_stats() -> dict:
    fast_votes = await get_fast_signup_to_vote()
    duplicate_clusters = await get_duplicate_name_clusters()
    burst_clusters = await get_signup_burst_clusters()

    duplicate_user_count = sum(c["count"] for c in duplicate_clusters)
    burst_user_count = sum(c["count"] for c in burst_clusters)

    total_votes = await db_total_votes()

    return {
        "total_votes": total_votes,
        "fast_signup_votes": len(fast_votes),
        "duplicate_name_clusters": len(duplicate_clusters),
        "duplicate_name_users": duplicate_user_count,
        "burst_clusters": len(burst_clusters),
        "burst_users": burst_user_count,
    }


async def db_total_votes() -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM votes")
        return (await cursor.fetchone())[0]


# ==================== YAKUNIY NATIJANI TASDIQLASH ====================

async def confirm_final_results(admin_id: int) -> dict:
    """Joriy natijalarning o'zgarmas 'suratini' (snapshot) saqlaydi va
    tasdiqlangan sana/admin bilan birga yozib qo'yadi. Bu — rasmiy yakuniy
    natija sifatida keyinchalik ko'rsatiladi."""
    results = await get_results()
    snapshot = [
        {"title": v["title"], "votes_count": v["votes_count"], "position": v["position"]}
        for v in results
    ]
    snapshot_json = json.dumps(snapshot, ensure_ascii=False)

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO final_results (confirmed_by, results_snapshot, created_at) "
            "VALUES (?, ?, ?)",
            (admin_id, snapshot_json, datetime.now().isoformat()),
        )
        await conn.commit()

    return {"confirmed_by": admin_id, "results": snapshot}


async def get_final_results_confirmation() -> Optional[dict]:
    """Eng oxirgi tasdiqlangan yakuniy natijani qaytaradi (agar mavjud bo'lsa)."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM final_results ORDER BY created_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["results"] = json.loads(d["results_snapshot"])
        return d


# ==================== BOTNI OMMAVIY TO'XTATISH (faqat admin uchun ochiq qoladi) ====================

DEFAULT_LOCK_MESSAGE = "🔒 Ovoz berish yakunlandi. Ishtirok etganingiz uchun rahmat!"


async def is_bot_locked() -> bool:
    return (await get_setting("bot_locked")) == "1"


async def get_lock_message() -> str:
    return await get_setting("bot_locked_message") or DEFAULT_LOCK_MESSAGE


async def lock_bot(message: str) -> None:
    await set_setting("bot_locked", "1")
    await set_setting("bot_locked_message", message)


async def unlock_bot() -> None:
    await set_setting("bot_locked", "0")
