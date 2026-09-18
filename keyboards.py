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
        [KeyboardButton(text="ℹ️ Bot haqida")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="🔐 ADMIN PANEL")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Video qo'shish"), KeyboardButton(text="📋 Videolar")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🗑 Video o'chirish")],
            [KeyboardButton(text="🔄 Ovozlarni ko'rish")],
            [KeyboardButton(text="⬅️ Asosiy menyu")],
        ],
        resize_keyboard=True,
    )


def video_page_keyboard(video: dict, index: int, total: int) -> InlineKeyboardMarkup:
    """Bitta video ostidagi ovoz berish tugmasi + oldingi/keyingi navigatsiya."""
    vote_row = [
        InlineKeyboardButton(
            text=f"🗳 Ovoz berish | {video['votes_count']} ta ovoz",
            callback_data=f"vote:{video['id']}:{index}",
        )
    ]

    nav_row = []
    if index > 0:
        nav_row.append(
            InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"navpage:{index - 1}")
        )
    if index < total - 1:
        nav_row.append(
            InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"navpage:{index + 1}")
        )

    rows = [vote_row]
    if nav_row:
        rows.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def confirm_delete_keyboard(video_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data=f"delete_confirm:{video_id}"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="delete_cancel"),
            ]
        ]
    )


SKIP_DESCRIPTION_HINT = "📄 Video tavsifini yuboring yoki /skip yozing."