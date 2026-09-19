import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot
from aiogram.enums import ChatMemberStatus

import config
import database as db

logger = logging.getLogger(__name__)

DATE_FORMAT = "%d.%m.%Y %H:%M"


def is_super_admin(telegram_id: int) -> bool:
    """Faqat .env dagi ADMIN_ID — boshqa adminlarni qo'sha/o'chira oladi."""
    return telegram_id == config.ADMIN_ID


async def is_admin(telegram_id: int) -> bool:
    """.env dagi asosiy admin YOKI bazada qo'shilgan qo'shimcha adminlardan biri."""
    if is_super_admin(telegram_id):
        return True
    return await db.is_table_admin(telegram_id)


async def get_all_admin_ids() -> list[int]:
    table_admins = await db.get_admin_ids()
    return list({config.ADMIN_ID, *table_admins})


async def check_subscription(bot: Bot, telegram_id: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=config.REQUIRED_CHANNEL, user_id=telegram_id
        )
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        )
    except Exception as e:
        logger.warning(f"A'zolikni tekshirishda xato: {e}")
        return False


def format_user_line(user: dict) -> str:
    full_name = user.get("first_name") or ""
    if user.get("last_name"):
        full_name = f"{full_name} {user['last_name']}".strip()
    if not full_name:
        full_name = "Noma'lum"

    username = user.get("username")
    handle = f"@{username}" if username else "username yo'q"

    voted_title = user.get("voted_title")
    vote_line = f"🗳 Ovoz bergan: {voted_title}" if voted_title else "🗳 Hali ovoz bermagan"

    return f"👤 {full_name}\n🔗 {handle}\n{vote_line}"


def parse_datetime(text: str) -> Optional[datetime]:
    try:
        return datetime.strptime(text.strip(), DATE_FORMAT)
    except ValueError:
        return None


async def get_voting_status() -> str:
    """
    Qaytaradi: 'unset' (muddat belgilanmagan), 'not_started', 'active', 'ended'
    """
    start_iso, end_iso = await db.get_voting_period()
    if not start_iso or not end_iso:
        return "unset"

    now = datetime.now()
    start_dt = datetime.fromisoformat(start_iso)
    end_dt = datetime.fromisoformat(end_iso)

    if now < start_dt:
        return "not_started"
    if now > end_dt:
        return "ended"
    return "active"


def format_time_left(end_iso: str) -> str:
    end_dt = datetime.fromisoformat(end_iso)
    delta = end_dt - datetime.now()
    if delta.total_seconds() <= 0:
        return "tugagan"

    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60

    if days > 0:
        return f"{days} kun {hours} soat"
    if hours > 0:
        return f"{hours} soat {minutes} daqiqa"
    return f"{minutes} daqiqa"
