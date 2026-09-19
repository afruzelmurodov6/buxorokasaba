import math
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from config import USERS_PER_PAGE
from states import SearchUserStates
from utils import is_admin

router = Router()


def format_date(iso_str: str) -> str:
    try:
        date_part = iso_str.split("T")[0]
        year, month, day = date_part.split("-")
        return f"{day}.{month}.{year}"
    except Exception:
        return iso_str


async def build_users_page_text(page: int) -> tuple[str, int]:
    total = await db.get_users_count()
    total_pages = max(math.ceil(total / USERS_PER_PAGE), 1)
    offset = page * USERS_PER_PAGE
    users = await db.get_users_page(offset, USERS_PER_PAGE)

    start_num = offset + 1
    end_num = offset + len(users)

    lines = [f"👥 <b>FOYDALANUVCHILAR</b>\n\nJami: {total} ta\n\n{start_num}-{end_num} foydalanuvchi\n"]
    for user in users:
        handle = f"@{escape(user['username'])}" if user.get("username") else "username yo'q"
        voted_title = user.get("voted_title")
        vote_line = f"🗳 {escape(voted_title)}" if voted_title else "🗳 Hali ovoz bermagan"
        name = escape(user.get("first_name") or "Noma'lum")
        lines.append(f"👤 <b>{name}</b>\n🔗 {handle}\n{vote_line}\n")

    return "\n".join(lines), total_pages


@router.message(F.text == "👥 Foydalanuvchilar")
async def admin_users_list(message: Message):
    if not await is_admin(message.from_user.id):
        return
    text, total_pages = await build_users_page_text(0)
    await message.answer(text, reply_markup=kb.users_page_keyboard(0, total_pages))


@router.callback_query(F.data.startswith("userspage:"))
async def cb_users_page(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer()
        return
    page = int(callback.data.split(":")[1])
    text, total_pages = await build_users_page_text(page)
    try:
        await callback.message.edit_text(text, reply_markup=kb.users_page_keyboard(page, total_pages))
    except Exception:
        pass
    await callback.answer()


# ==================== FOYDALANUVCHI QIDIRISH ====================

@router.message(F.text == "🔎 Foydalanuvchini qidirish")
async def admin_search_start(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer(
        "Qanday qidirmoqchisiz?", reply_markup=kb.search_type_keyboard()
    )


@router.callback_query(F.data == "search_by:id")
async def cb_search_by_id(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(SearchUserStates.waiting_for_id)
    await callback.message.answer("🆔 Telegram ID raqamini yuboring.")
    await callback.answer()


@router.callback_query(F.data == "search_by:username")
async def cb_search_by_username(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(SearchUserStates.waiting_for_username)
    await callback.message.answer("👤 Username'ni yuboring (masalan: @azizbek yoki azizbek).")
    await callback.answer()


async def send_user_card(message: Message, user: dict) -> None:
    full_name = user.get("first_name") or ""
    if user.get("last_name"):
        full_name = f"{full_name} {user['last_name']}".strip()
    if not full_name:
        full_name = "Noma'lum"
    full_name = escape(full_name)

    username = user.get("username")
    handle = f"@{escape(username)}" if username else "username yo'q"

    voted_title = await db.get_user_vote_title(user["id"])
    vote_line = f"🎬 {escape(voted_title)}" if voted_title else "Hali ovoz bermagan"

    reg_date = format_date(user["created_at"])

    text = (
        "👤 <b>FOYDALANUVCHI</b>\n\n"
        f"Ism: <b>{full_name}</b>\n"
        f"Username: {handle}\n"
        f"Telegram ID: <code>{user['telegram_id']}</code>\n\n"
        f"🗳 Ovoz bergan:\n{vote_line}\n\n"
        f"📅 Ro'yxatdan o'tgan:\n{reg_date}"
    )
    await message.answer(text, reply_markup=kb.profile_link_keyboard(username, user["telegram_id"]))


@router.message(SearchUserStates.waiting_for_id, F.text)
async def search_by_id_receive(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.clear()
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Iltimos, to'g'ri Telegram ID (raqam) kiriting.")
        return

    user = await db.search_user_by_telegram_id(telegram_id)
    if not user:
        await message.answer("😔 Bunday ID bilan foydalanuvchi topilmadi.")
        return
    await send_user_card(message, user)


@router.message(SearchUserStates.waiting_for_username, F.text)
async def search_by_username_receive(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.clear()
    user = await db.search_user_by_username(message.text.strip())
    if not user:
        await message.answer("😔 Bunday username bilan foydalanuvchi topilmadi.")
        return
    await send_user_card(message, user)
