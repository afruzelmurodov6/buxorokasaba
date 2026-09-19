import logging
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import database as db
import keyboards as kb
from utils import check_subscription, get_all_admin_ids, get_voting_status

logger = logging.getLogger(__name__)
router = Router()

ALREADY_VOTED_TEXT = (
    "⚠️ Siz allaqachon ovoz bergansiz.\n\n"
    "Siz ushbu tanlovda faqat bitta ishtirokchiga ovoz berishingiz mumkin."
)

NOT_STARTED_TEXT = "⏳ Ovoz berish hali boshlanmagan."
ENDED_TEXT = "🔒 Ovoz berish muddati yakunlangan."


async def notify_admins_new_vote(bot, voter, video: dict) -> None:
    full_name = voter.first_name or ""
    if voter.last_name:
        full_name = f"{full_name} {voter.last_name}".strip()
    handle = f"@{voter.username}" if voter.username else "username yo'q"

    text = (
        "🔔 <b>Yangi ovoz!</b>\n\n"
        f"👤 {escape(full_name) or 'Noma\'lum'}\n"
        f"🔗 {escape(handle)}\n"
        f"🎬 {escape(video['title'])}"
    )

    for admin_id in await get_all_admin_ids():
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.warning(f"Adminga bildirishnoma yuborishda xato ({admin_id}): {e}")


async def check_vote_eligibility(callback: CallbackQuery, video_id: int):
    """Qaytaradi: (video_dict, None) muvaffaqiyatli bo'lsa, yoki (None, xato_matni)"""
    if not await check_subscription(callback.bot, callback.from_user.id):
        return None, "❌ Avval kanalga a'zo bo'ling."

    voting_status = await get_voting_status()
    if voting_status == "not_started":
        return None, NOT_STARTED_TEXT
    if voting_status == "ended":
        return None, ENDED_TEXT

    video = await db.get_video(video_id)
    if not video:
        return None, "⚠️ Bu video endi mavjud emas."

    user_db_id = await db.get_user_db_id(callback.from_user.id)
    if user_db_id is not None and await db.has_voted(user_db_id):
        return None, ALREADY_VOTED_TEXT

    return video, None


@router.callback_query(F.data.startswith("vote:"))
async def cb_vote(callback: CallbackQuery, state: FSMContext):
    video_id = int(callback.data.split(":")[1])

    video, error = await check_vote_eligibility(callback, video_id)
    if error:
        await callback.answer(error, show_alert=True)
        return

    await state.update_data(
        pending_vote_video_id=video_id,
        pending_vote_chat_id=callback.message.chat.id,
        pending_vote_message_id=callback.message.message_id,
    )

    await callback.message.answer(
        f"❓ Rostdan ham <b>{escape(video['title'])}</b> ga ovoz berasizmi?\n\n"
        "Buni keyin bekor qila olmaysiz.",
        reply_markup=kb.vote_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "vote_confirm")
async def cb_vote_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    video_id = data.get("pending_vote_video_id")
    origin_chat_id = data.get("pending_vote_chat_id")
    origin_message_id = data.get("pending_vote_message_id")

    if video_id is None:
        await callback.answer()
        return

    video, error = await check_vote_eligibility(callback, video_id)
    if error:
        await callback.message.edit_text(error)
        await callback.answer()
        return

    user_db_id = await db.get_user_db_id(callback.from_user.id)
    if user_db_id is None:
        user_db_id = await db.add_user(
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name,
        )

    success, new_count = await db.cast_vote(user_db_id, video_id)
    await state.update_data(
        pending_vote_video_id=None, pending_vote_chat_id=None, pending_vote_message_id=None
    )

    if not success:
        await callback.message.edit_text(ALREADY_VOTED_TEXT)
        await callback.answer()
        return

    video["votes_count"] = new_count

    if origin_chat_id and origin_message_id:
        try:
            await callback.bot.edit_message_reply_markup(
                chat_id=origin_chat_id,
                message_id=origin_message_id,
                reply_markup=kb.video_page_keyboard(video, video_id),
            )
        except Exception as e:
            logger.warning(f"Asosiy videoni yangilashda xato: {e}")

    await callback.message.edit_text(
        "✅ Ovozingiz qabul qilindi!\n\nSiz ushbu tanlovda o'z ovozingizni berdingiz."
    )
    await callback.answer()

    await notify_admins_new_vote(callback.bot, callback.from_user, video)


@router.callback_query(F.data == "vote_cancel")
async def cb_vote_cancel(callback: CallbackQuery, state: FSMContext):
    await state.update_data(
        pending_vote_video_id=None, pending_vote_chat_id=None, pending_vote_message_id=None
    )
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()
