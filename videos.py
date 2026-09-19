import logging
from html import escape

from aiogram import F, Router
from aiogram.types import Message

import database as db
import keyboards as kb
from utils import check_subscription, format_time_left, get_voting_status

logger = logging.getLogger(__name__)
router = Router()


def build_caption(video: dict, index: int, total: int) -> str:
    title = escape(video["title"])
    description = escape(video.get("description") or "")
    header = f"🎬 <b>{title}</b>\n\n({index + 1}/{total})"
    return f"{header}\n\n{description}".strip()


async def build_intro_text(total: int) -> str:
    lines = [f"🎬 <b>ISHTIROKCHILAR</b>\n\n{total} ta video. Har birini ko'rib, bittasiga ovoz bering:"]

    status = await get_voting_status()
    if status == "not_started":
        lines.append("\n⏳ Ovoz berish hali boshlanmagan.")
    elif status == "active":
        _, end_iso = await db.get_voting_period()
        lines.append(f"\n⏰ Ovoz berish tugashiga: <b>{format_time_left(end_iso)}</b> qoldi")
    elif status == "ended":
        lines.append("\n🔒 Ovoz berish muddati yakunlangan.")

    return "\n".join(lines)


@router.message(F.text == "🎬 Videolar")
async def show_videos(message: Message):
    if not await check_subscription(message.bot, message.from_user.id):
        await message.answer(
            "🔔 Botdan foydalanish uchun avval kanalimizga a'zo bo'ling.",
            reply_markup=kb.subscribe_keyboard(),
        )
        return

    videos = await db.get_all_videos()
    if not videos:
        await message.answer("😔 Hozircha videolar mavjud emas.")
        return

    user_db_id = await db.get_user_db_id(message.from_user.id)
    if user_db_id is None:
        user_db_id = await db.add_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
    voted_video_id = await db.get_user_voted_video_id(user_db_id)

    await message.answer(await build_intro_text(len(videos)))

    for index, video in enumerate(videos):
        await message.answer_video(
            video=video["file_id"],
            caption=build_caption(video, index, len(videos)),
            reply_markup=kb.video_page_keyboard(video, voted_video_id),
        )


@router.message(F.text == "🏆 Natijalar")
async def show_results(message: Message):
    videos = await db.get_results()
    if not videos:
        await message.answer("😔 Hozircha ovozlar mavjud emas.")
        return

    total_votes = sum(v["votes_count"] for v in videos)

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>OVOZ BERISH NATIJALARI</b>\n"]
    for i, video in enumerate(videos):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        title = escape(video["title"])
        percent = (video["votes_count"] / total_votes * 100) if total_votes > 0 else 0
        lines.append(
            f"{prefix} {title} — <b>{video['votes_count']}</b> ta ovoz ({percent:.1f}%)"
        )

    await message.answer("\n".join(lines))
