import asyncio
import logging

import database as db
from utils import get_voting_status

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30 * 60  # har 30 daqiqada tekshiradi
REMINDER_WINDOW_HOURS = 24  # tugashiga 24 soat qolganda eslatma yuboradi

REMINDER_TEXT = (
    "⏰ <b>Eslatma!</b>\n\n"
    "Ovoz berish tez orada yakunlanadi, lekin siz hali ovoz bermadingiz.\n\n"
    "🎬 \"Videolar\" bo'limiga o'ting va o'zingiz munosib deb bilgan "
    "ishtirokchiga ovoz bering!"
)


async def reminder_loop(bot) -> None:
    while True:
        try:
            await check_and_send_reminder(bot)
        except Exception as e:
            logger.warning(f"Eslatma yuborishda xato: {e}")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def check_and_send_reminder(bot) -> None:
    from datetime import datetime

    status = await get_voting_status()
    if status != "active":
        return

    _, end_iso = await db.get_voting_period()
    hours_left = (datetime.fromisoformat(end_iso) - datetime.now()).total_seconds() / 3600
    if hours_left > REMINDER_WINDOW_HOURS or hours_left <= 0:
        return

    already_sent_for = await db.get_setting("reminder_sent_for")
    if already_sent_for == end_iso:
        return

    non_voted = await db.get_non_voted_telegram_ids()
    sent = 0
    for telegram_id in non_voted:
        try:
            await bot.send_message(telegram_id, REMINDER_TEXT)
            sent += 1
        except Exception:
            pass

    await db.set_setting("reminder_sent_for", end_iso)
    logger.info(f"Eslatma yuborildi: {sent} ta foydalanuvchiga.")
