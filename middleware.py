from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

import database as db
from utils import is_admin


class BotLockMiddleware(BaseMiddleware):
    """
    Bot 'to'xtatilgan' holatda bo'lsa, ADMIN bo'lmagan har qanday
    foydalanuvchining xabari yoki tugma bosishi haqiqiy handlerga
    yetib bormasdan ushlab qolinadi va unga faqat belgilangan xabar
    ko'rsatiladi. Admin uchun bot har doim to'liq ishlaydi.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")

        if user is not None and not await is_admin(user.id):
            if await db.is_bot_locked():
                lock_message = await db.get_lock_message()
                if isinstance(event, Message):
                    await event.answer(lock_message)
                elif isinstance(event, CallbackQuery):
                    await event.answer(lock_message, show_alert=True)
                return None

        return await handler(event, data)
