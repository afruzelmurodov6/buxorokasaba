import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database as db
from handlers import admin, start, users, videos, voting
from reminders import reminder_loop
from webserver import start_webserver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(videos.router)
    dp.include_router(voting.router)
    dp.include_router(admin.router)
    dp.include_router(users.router)

    # Jadvallarni yaratadi (mavjud bo'lsa tegmaydi)
    await db.init_db()

    # Baza chindan ham bo'sh bo'lsa (masalan yangi Volume birinchi marta
    # ulanganda) — backup_data.json'dan eski foydalanuvchi/ovozlarni
    # avtomatik tiklaydi. Bazada ma'lumot bo'lsa, hech narsa qilmaydi.
    await db.restore_from_backup_if_empty()

    await start_webserver(config.PORT)

    logger.info("Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)

    await asyncio.gather(
        dp.start_polling(bot),
        reminder_loop(bot),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")
