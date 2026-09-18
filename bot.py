import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InputMediaVideo, Message

import config
import database as db
import keyboards as kb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

router = Router()


class AddVideoStates(StatesGroup):
    waiting_for_video = State()
    waiting_for_title = State()
    waiting_for_description = State()


def is_admin(telegram_id: int) -> bool:
    return telegram_id == config.ADMIN_ID


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


def build_caption(video: dict, index: Optional[int] = None, total: Optional[int] = None) -> str:
    header = f"🎬 {video['title']}"
    if index is not None and total is not None:
        header += f" ({index + 1}/{total})"
    description = video.get("description") or ""
    return f"{header}\n\n{description}".strip()


async def send_video_page(message: Message, videos: list[dict], index: int) -> None:
    video = videos[index]
    await message.answer_video(
        video=video["file_id"],
        caption=build_caption(video, index, len(videos)),
        reply_markup=kb.video_page_keyboard(video, index, len(videos)),
    )


# ==================== START VA A'ZOLIK ====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    if not await check_subscription(message.bot, message.from_user.id):
        await message.answer(
            "🔔 Botdan foydalanish uchun avval kanalimizga a'zo bo'ling.",
            reply_markup=kb.subscribe_keyboard(),
        )
        return

    await db.add_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}! 👋\n\n"
        "Video Voting botga xush kelibsiz! Quyidagi menyudan foydalaning.",
        reply_markup=kb.main_menu_keyboard(is_admin(message.from_user.id)),
    )


@router.callback_query(F.data == "check_membership")
async def cb_check_membership(callback: CallbackQuery):
    if not await check_subscription(callback.bot, callback.from_user.id):
        await callback.answer("❌ Siz hali kanalga a'zo bo'lmagansiz.", show_alert=True)
        return

    await db.add_user(
        callback.from_user.id, callback.from_user.username, callback.from_user.first_name
    )
    await callback.message.delete()
    await callback.message.answer(
        "✅ A'zolik tasdiqlandi!",
        reply_markup=kb.main_menu_keyboard(is_admin(callback.from_user.id)),
    )
    await callback.answer()


# ==================== VIDEOLAR VA OVOZ BERISH ====================

@router.message(F.text == "🎬 Videolar")
async def show_videos(message: Message):
    if not await check_subscription(message.bot, message.from_user.id):
        await message.answer(
            "🔔 Botdan foydalanish uchun avval kanalimizga a'zo bo'ling.",
            reply_markup=kb.subscribe_keyboard(),
        )
        return

    videos = await db.get_active_videos()
    if not videos:
        await message.answer("😔 Hozircha videolar mavjud emas.")
        return

    await send_video_page(message, videos, 0)


@router.callback_query(F.data.startswith("navpage:"))
async def cb_navpage(callback: CallbackQuery):
    if not await check_subscription(callback.bot, callback.from_user.id):
        await callback.answer("❌ Avval kanalga a'zo bo'ling.", show_alert=True)
        return

    index = int(callback.data.split(":")[1])
    videos = await db.get_active_videos()

    if not videos or index < 0 or index >= len(videos):
        await callback.answer()
        return

    video = videos[index]
    try:
        await callback.message.edit_media(
            media=InputMediaVideo(
                media=video["file_id"],
                caption=build_caption(video, index, len(videos)),
            ),
            reply_markup=kb.video_page_keyboard(video, index, len(videos)),
        )
    except Exception as e:
        logger.warning(f"Videoni almashtirishda xato: {e}")
    await callback.answer()


@router.callback_query(F.data.startswith("vote:"))
async def cb_vote(callback: CallbackQuery):
    _, video_id_raw, index_raw = callback.data.split(":")
    video_id = int(video_id_raw)
    index = int(index_raw)

    if not await check_subscription(callback.bot, callback.from_user.id):
        await callback.answer("❌ Avval kanalga a'zo bo'ling.", show_alert=True)
        return

    video = await db.get_video(video_id)
    if not video or not video["is_active"]:
        await callback.answer("⚠️ Bu video endi mavjud emas.", show_alert=True)
        return

    user_db_id = await db.get_user_db_id(callback.from_user.id)
    if user_db_id is None:
        user_db_id = await db.add_user(
            callback.from_user.id, callback.from_user.username, callback.from_user.first_name
        )

    success, new_count = await db.cast_vote(user_db_id, video_id)

    if not success:
        await callback.answer("⚠️ Siz bu videoga allaqachon ovoz bergansiz.", show_alert=True)
        return

    videos = await db.get_active_videos()
    total = len(videos) if videos else index + 1
    video["votes_count"] = new_count

    try:
        await callback.message.edit_reply_markup(
            reply_markup=kb.video_page_keyboard(video, index, total)
        )
    except Exception as e:
        logger.warning(f"Tugmani yangilashda xato: {e}")

    await callback.answer("✅ Ovoz qabul qilindi!")


@router.message(F.text == "🏆 Natijalar")
async def show_results(message: Message):
    videos = await db.get_results()
    if not videos:
        await message.answer("😔 Hozircha ovozlar mavjud emas.")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 OVOZ BERISH NATIJALARI\n"]
    for i, video in enumerate(videos):
        prefix = medals[i] if i < 3 else f"{i + 1}️⃣"
        lines.append(f"{prefix} {video['title']} — {video['votes_count']} ta ovoz")

    await message.answer("\n".join(lines))


@router.message(F.text == "ℹ️ Bot haqida")
async def about_bot(message: Message):
    await message.answer(
        "ℹ️ Bu bot orqali siz videolarga ovoz berishingiz mumkin.\n"
        "Har bir foydalanuvchi har bir videoga faqat bir marta ovoz bera oladi."
    )


# ==================== ADMIN PANEL ====================

@router.message(F.text == "🔐 ADMIN PANEL")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🔐 Admin panelga xush kelibsiz.", reply_markup=kb.admin_menu_keyboard())


@router.message(F.text == "⬅️ Asosiy menyu")
async def back_to_main_menu(message: Message):
    await message.answer(
        "Asosiy menyu.", reply_markup=kb.main_menu_keyboard(is_admin(message.from_user.id))
    )


@router.message(F.text == "➕ Video qo'shish")
async def add_video_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddVideoStates.waiting_for_video)
    await message.answer("🎬 Videoni yuboring.")


@router.message(AddVideoStates.waiting_for_video, F.video)
async def add_video_receive_video(message: Message, state: FSMContext):
    await state.update_data(file_id=message.video.file_id)
    await state.set_state(AddVideoStates.waiting_for_title)
    await message.answer("📝 Video nomini yuboring.")


@router.message(AddVideoStates.waiting_for_video)
async def add_video_wrong_type(message: Message):
    await message.answer("⚠️ Iltimos, video fayl yuboring.")


@router.message(AddVideoStates.waiting_for_title, F.text)
async def add_video_receive_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddVideoStates.waiting_for_description)
    await message.answer(kb.SKIP_DESCRIPTION_HINT)


@router.message(AddVideoStates.waiting_for_description, Command("skip"))
async def add_video_skip_description(message: Message, state: FSMContext):
    await finish_add_video(message, state, description=None)


@router.message(AddVideoStates.waiting_for_description, F.text)
async def add_video_receive_description(message: Message, state: FSMContext):
    await finish_add_video(message, state, description=message.text)


async def finish_add_video(message: Message, state: FSMContext, description: Optional[str]):
    data = await state.get_data()
    await db.add_video(data["file_id"], data["title"], description)
    await state.clear()
    await message.answer(
        "✅ Video muvaffaqiyatli qo'shildi.", reply_markup=kb.admin_menu_keyboard()
    )


@router.message(F.text == "📋 Videolar")
async def admin_list_videos(message: Message):
    if not is_admin(message.from_user.id):
        return
    videos = await db.get_all_videos()
    if not videos:
        await message.answer("😔 Hozircha videolar mavjud emas.")
        return
    for video in videos:
        status = "✅ Faol" if video["is_active"] else "🚫 Faol emas"
        caption = (
            f"🎬 {video['title']}\n{video['description'] or ''}\n\n"
            f"🗳 {video['votes_count']} ta ovoz | {status}"
        ).strip()
        await message.answer_video(video=video["file_id"], caption=caption)


@router.message(F.text == "📊 Statistika")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    stats = await db.get_stats()
    await message.answer(
        "📊 Statistika\n\n"
        f"👥 Jami foydalanuvchilar: {stats['users']}\n"
        f"🎬 Jami videolar: {stats['videos']}\n"
        f"🗳 Jami ovozlar: {stats['votes']}"
    )


@router.message(F.text == "🗑 Video o'chirish")
async def admin_delete_video_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    videos = await db.get_active_videos()
    if not videos:
        await message.answer("😔 O'chirish uchun video mavjud emas.")
        return
    await message.answer(
        "O'chirmoqchi bo'lgan videongizni tanlang:",
        reply_markup=kb.delete_video_list_keyboard(videos),
    )


@router.callback_query(F.data.startswith("delete_ask:"))
async def cb_delete_ask(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    video_id = int(callback.data.split(":")[1])
    video = await db.get_video(video_id)
    if not video:
        await callback.answer("⚠️ Video topilmadi.", show_alert=True)
        return
    await callback.message.answer(
        f"⚠️ Rostdan ham \"{video['title']}\" videoni o'chirmoqchimisiz?",
        reply_markup=kb.confirm_delete_keyboard(video_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_confirm:"))
async def cb_delete_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    video_id = int(callback.data.split(":")[1])
    await db.delete_video(video_id)
    await callback.message.edit_text("🗑 Video o'chirildi.")
    await callback.answer()


@router.callback_query(F.data == "delete_cancel")
async def cb_delete_cancel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()


@router.message(F.text == "🔄 Ovozlarni ko'rish")
async def admin_view_votes(message: Message):
    if not is_admin(message.from_user.id):
        return
    videos = await db.get_results()
    if not videos:
        await message.answer("😔 Hozircha ovozlar mavjud emas.")
        return
    lines = ["🔄 Ovozlar ro'yxati\n"]
    for video in videos:
        lines.append(f"🎬 {video['title']} — {video['votes_count']} ta ovoz")
    await message.answer("\n".join(lines))


async def main():
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await db.init_db()

    logger.info("Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")