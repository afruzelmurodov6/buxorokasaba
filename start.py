from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from utils import check_subscription, is_admin

router = Router()

WELCOME_TEXT = (
    "👋 Assalomu alaykum!\n\n"
    "🏛 <b>Buxoro Kasaba Uyushmasi</b>ning\n"
    "rasmiy video ovoz berish botiga\n"
    "xush kelibsiz!\n\n"
    "🎬 Videolarni tomosha qiling va\n"
    "ishtirokchilardan o'zingiz munosib\n"
    "deb bilgan BITTASIGA ovoz bering.\n\n"
    "🤝 Sizning fikringiz va ovozingiz muhim!"
)

NOT_SUBSCRIBED_TEXT = (
    "🏛 <b>BUXORO KASABA UYUSHMASI</b>\n\n"
    "Botdan foydalanish uchun avval rasmiy kanalimizga a'zo bo'ling."
)


async def send_welcome(message_or_callback_message: Message, telegram_id: int) -> None:
    user_db_id = await db.get_user_db_id(telegram_id)
    voted = await db.has_voted(user_db_id) if user_db_id else False

    text = WELCOME_TEXT
    if voted:
        text = (
            "👋 Qaytganingizdan xursandmiz!\n\n"
            "Siz ushbu tanlovda allaqachon ovoz bergansiz.\n\n"
            "🏆 Natijalarni <b>Natijalar</b> bo'limidan kuzatib borishingiz mumkin."
        )
    else:
        text += "\n\n🎬 Videolarni ko'ring va bitta ishtirokchiga ovoz bering."

    await message_or_callback_message.answer(
        text, reply_markup=kb.main_menu_keyboard(await is_admin(telegram_id))
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not await check_subscription(message.bot, message.from_user.id):
        await message.answer(NOT_SUBSCRIBED_TEXT, reply_markup=kb.subscribe_keyboard())
        return

    await db.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
    )
    await send_welcome(message, message.from_user.id)


@router.callback_query(F.data == "check_membership")
async def cb_check_membership(callback: CallbackQuery):
    if not await check_subscription(callback.bot, callback.from_user.id):
        await callback.answer("❌ Siz hali kanalga a'zo bo'lmagansiz.", show_alert=True)
        return

    await db.add_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
        callback.from_user.last_name,
    )
    await callback.message.delete()
    await callback.message.answer("✅ A'zolik tasdiqlandi!")
    await send_welcome(callback.message, callback.from_user.id)
    await callback.answer()


@router.message(F.text == "ℹ️ Biz haqimizda")
async def about_bot(message: Message):
    await message.answer(
        "🏛 <b>BUXORO KASABA UYUSHMASI</b>\n\n"
        "Buxoro viloyatidagi kasaba uyushmalari faoliyati, xodimlarning mehnat "
        "va ijtimoiy manfaatlarini himoya qilish hamda jamoatchilik bilan "
        "samarali muloqotni rivojlantirishga xizmat qiladi.\n\n"
        "🎬 Ushbu bot orqali tanlov ishtirokchilarining videolarini ko'rish va "
        "ulardan BITTASIGA ovoz berish mumkin.\n\n"
        "🤝 Sizning fikringiz muhim!"
    )
