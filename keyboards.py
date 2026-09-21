from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import REQUIRED_CHANNEL


def subscribe_keyboard() -> InlineKeyboardMarkup:
    channel_username = REQUIRED_CHANNEL.lstrip("@")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Kanalga a'zo bo'lish",
                    url=f"https://t.me/{channel_username}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ A'zolikni tekshirish",
                    callback_data="check_membership",
                )
            ],
        ]
    )


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🎬 Videolar"), KeyboardButton(text="🏆 Natijalar")],
        [KeyboardButton(text="ℹ️ Biz haqimizda")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="🔐 Admin panel")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def admin_menu_keyboard(is_super_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="➕ Video qo'shish"), KeyboardButton(text="📋 Videolar")],
        [KeyboardButton(text="👥 Foydalanuvchilar"), KeyboardButton(text="🔎 Foydalanuvchini qidirish")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🏆 Natijalar")],
        [KeyboardButton(text="✏️ Video tahrirlash"), KeyboardButton(text="🗑 Video o'chirish")],
        [KeyboardButton(text="📅 Sana belgilash"), KeyboardButton(text="📢 Xabar yuborish")],
        [KeyboardButton(text="🔒 Ovoz berishni hoziroq yakunlash")],
        [KeyboardButton(text="🛑 Botni to'xtatish"), KeyboardButton(text="🟢 Botni qayta yoqish")],
        [KeyboardButton(text="📤 Excel eksport")],
        [KeyboardButton(text="⚖️ Ovoz tuzatish"), KeyboardButton(text="📜 Tuzatishlar tarixi")],
        [KeyboardButton(text="🛡 Anti-Fraud / Audit")],
    ]
    if is_super_admin:
        keyboard.append([KeyboardButton(text="👤 Adminlar"), KeyboardButton(text="➕ Admin qo'shish")])
    keyboard.append([KeyboardButton(text="⬅️ Asosiy menyu")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def admins_list_keyboard(admin_ids: list[int]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🗑 {admin_id}", callback_data=f"admin_remove:{admin_id}")]
        for admin_id in admin_ids
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, yuborish", callback_data="broadcast_send"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="broadcast_cancel"),
            ]
        ]
    )


def video_page_keyboard(video: dict, voted_video_id: int | None) -> InlineKeyboardMarkup:
    if voted_video_id == video["id"]:
        vote_text = f"✅ Ovoz berilgan | {video['votes_count']} ta ovoz"
    else:
        vote_text = f"🗳 Ovoz berish | {video['votes_count']} ta ovoz"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=vote_text, callback_data=f"vote:{video['id']}")]
        ]
    )


def delete_video_list_keyboard(videos: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"🗑 {video['title']}",
                callback_data=f"delete_ask:{video['id']}",
            )
        ]
        for video in videos
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def restore_video_keyboard(video_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="♻️ Tiklash", callback_data=f"restore_video:{video_id}")]
        ]
    )


def end_voting_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, yakunlash", callback_data="end_voting_confirm"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="end_voting_cancel"),
            ]
        ]
    )


def lock_bot_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, to'xtatish", callback_data="lock_bot_confirm"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="lock_bot_cancel"),
            ]
        ]
    )


def antifraud_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔎 Faollik auditi"), KeyboardButton(text="🚨 Shubhali ovozlar")],
            [KeyboardButton(text="📊 Fraud statistikasi"), KeyboardButton(text="📜 Audit log")],
            [KeyboardButton(text="🔒 Ovoz berishni hoziroq yakunlash")],
            [KeyboardButton(text="🏆 Yakuniy natijani tasdiqlash"), KeyboardButton(text="📄 Yakuniy hisobot")],
            [KeyboardButton(text="⬅️ Admin panelga qaytish")],
        ],
        resize_keyboard=True,
    )


def confirm_final_results_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, tasdiqlayman", callback_data="confirm_final_yes"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_final_no"),
            ]
        ]
    )


def adjust_video_pick_keyboard(videos: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{video['title']} — hozir {video['votes_count']} ta ovoz",
                callback_data=f"adjust_pick:{video['id']}",
            )
        ]
        for video in videos
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def adjust_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="adjust_confirm"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adjust_cancel"),
            ]
        ]
    )


def cancel_adjustment_keyboard(adjustment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Bu tuzatishni bekor qilish", callback_data=f"cancel_adj:{adjustment_id}")]
        ]
    )


def confirm_delete_keyboard(video_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data=f"delete_confirm:{video_id}"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="delete_cancel"),
            ]
        ]
    )


def edit_video_list_keyboard(videos: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"✏️ {video['title']}",
                callback_data=f"edit_pick:{video['id']}",
            )
        ]
        for video in videos
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_field_keyboard(video_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Nomi", callback_data=f"edit_field:{video_id}:title")],
            [InlineKeyboardButton(text="📄 Tavsifi", callback_data=f"edit_field:{video_id}:description")],
            [InlineKeyboardButton(text="🔢 Tartib raqami", callback_data=f"edit_field:{video_id}:position")],
            [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="edit_cancel")],
        ]
    )


def users_page_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"userspage:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"userspage:{page + 1}"))
    rows = [nav_row] if nav_row else []
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vote_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, ovoz beraman", callback_data="vote_confirm"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="vote_cancel"),
            ]
        ]
    )


def profile_link_keyboard(username: str | None, telegram_id: int) -> InlineKeyboardMarkup:
    if username:
        url = f"https://t.me/{username.lstrip('@')}"
    else:
        url = f"tg://user?id={telegram_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔗 Profilni ochish", url=url)]]
    )


def search_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆔 Telegram ID orqali", callback_data="search_by:id")],
            [InlineKeyboardButton(text="👤 Username orqali", callback_data="search_by:username")],
        ]
    )


SKIP_DESCRIPTION_HINT = "📄 Video tavsifini yuboring."
