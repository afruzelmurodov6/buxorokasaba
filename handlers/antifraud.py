from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from utils import is_admin, is_super_admin

router = Router()


def format_dt(iso_str: str) -> str:
    try:
        date_part, time_part = iso_str.split("T")
        return f"{date_part} {time_part.split('.')[0]}"
    except Exception:
        return iso_str


@router.message(F.text == "🛡 Anti-Fraud / Audit")
async def antifraud_menu(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer(
        "🛡 <b>ANTI-FRAUD / AUDIT</b>\n\n"
        "Bu bo'lim faqat TEKSHIRUV signallarini ko'rsatadi. Hech qanday "
        "ovoz yoki foydalanuvchi bu yerda avtomatik o'chirilmaydi yoki "
        "\"firibgar\" deb belgilanmaydi — yakuniy qaror sizga bog'liq.",
        reply_markup=kb.antifraud_menu_keyboard(),
    )


@router.message(F.text == "⬅️ Admin panelga qaytish")
async def back_to_admin_menu(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer(
        "🔐 Admin panel.", reply_markup=kb.admin_menu_keyboard(is_super_admin(message.from_user.id))
    )


# ==================== FAOLLIK AUDITI (strukturaviy naqshlar) ====================

@router.message(F.text == "🔎 Faollik auditi")
async def activity_audit(message: Message):
    if not await is_admin(message.from_user.id):
        return

    burst_clusters = await db.get_signup_burst_clusters()
    duplicate_clusters = await db.get_duplicate_name_clusters()

    lines = ["🔎 <b>FAOLLIK AUDITI</b>\n"]

    if burst_clusters:
        lines.append("⏱ <b>Qisqa vaqtda ommaviy ro'yxatdan o'tish (bitta ishtirokchiga):</b>")
        for c in burst_clusters[:10]:
            lines.append(
                f"— {escape(c['video_title'])}: {c['count']} ta akkaunt "
                f"({format_dt(c['window_start'])} — {format_dt(c['window_end'])})"
            )
        lines.append("")
    else:
        lines.append("⏱ Qisqa vaqtli ommaviy ro'yxatdan o'tish naqshlari topilmadi.\n")

    if duplicate_clusters:
        lines.append("👥 <b>Bir xil ism-familiyali akkauntlar:</b>")
        for c in duplicate_clusters[:10]:
            full_name = f"{c['first_name']} {c['last_name']}".strip() or "(ism yo'q)"
            lines.append(f"— {escape(full_name)}: {c['count']} ta akkaunt")
    else:
        lines.append("👥 Bir xil ism-familiyali akkauntlar guruhlari topilmadi.")

    await message.answer("\n".join(lines))


# ==================== SHUBHALI OVOZLAR (tez ovoz berganlar) ====================

@router.message(F.text == "🚨 Shubhali ovozlar")
async def suspicious_votes(message: Message):
    if not await is_admin(message.from_user.id):
        return

    fast_votes = await db.get_fast_signup_to_vote()

    if not fast_votes:
        await message.answer(
            "🚨 Hozircha shubhali (juda tez ovoz bergan) holatlar topilmadi."
        )
        return

    lines = [
        f"🚨 <b>SHUBHALI OVOZLAR</b>\n\n"
        f"Ro'yxatdan o'tib, {db.FAST_VOTE_THRESHOLD_SECONDS} soniyadan kamroq vaqtda "
        f"ovoz bergan foydalanuvchilar ({len(fast_votes)} ta):\n"
    ]
    for v in fast_votes[:30]:
        handle = f"@{v['username']}" if v.get("username") else "username yo'q"
        name = escape(v.get("first_name") or "Noma'lum")
        lines.append(
            f"— {name} ({handle}) → {escape(v['voted_title'])}, "
            f"{v['seconds_to_vote']}s ichida"
        )
    if len(fast_votes) > 30:
        lines.append(f"\n... yana {len(fast_votes) - 30} ta.")

    await message.answer("\n".join(lines))


# ==================== FRAUD STATISTIKASI ====================

@router.message(F.text == "📊 Fraud statistikasi")
async def fraud_stats(message: Message):
    if not await is_admin(message.from_user.id):
        return
    stats = await db.get_fraud_stats()
    await message.answer(
        "📊 <b>Fraud statistikasi</b>\n\n"
        f"🗳 Jami ovozlar: <b>{stats['total_votes']}</b>\n\n"
        f"⚡ Tez ovoz berganlar: <b>{stats['fast_signup_votes']}</b>\n"
        f"👥 Bir xil ismli akkaunt guruhlari: <b>{stats['duplicate_name_clusters']}</b> "
        f"({stats['duplicate_name_users']} ta akkaunt)\n"
        f"⏱ Ommaviy ro'yxatdan o'tish guruhlari: <b>{stats['burst_clusters']}</b> "
        f"({stats['burst_users']} ta akkaunt)\n\n"
        "ℹ️ Bu raqamlar faqat tekshiruv uchun signal — avtomatik xulosa emas."
    )


# ==================== AUDIT LOG ====================

@router.message(F.text == "📜 Audit log")
async def audit_log_view(message: Message):
    if not await is_admin(message.from_user.id):
        return
    entries = await db.get_audit_log(30)
    if not entries:
        await message.answer("📜 Hozircha audit log bo'sh.")
        return

    lines = ["📜 <b>AUDIT LOG</b> (oxirgi 30 ta)\n"]
    for e in entries:
        date = format_dt(e["created_at"])
        details = f" — {escape(e['details'])}" if e.get("details") else ""
        lines.append(f"• {date} | admin <code>{e['admin_id']}</code> | {escape(e['action'])}{details}")

    await message.answer("\n".join(lines))


# ==================== YAKUNIY NATIJANI TASDIQLASH ====================

@router.message(F.text == "🏆 Yakuniy natijani tasdiqlash")
async def confirm_final_start(message: Message):
    if not await is_admin(message.from_user.id):
        return

    existing = await db.get_final_results_confirmation()
    if existing:
        date = format_dt(existing["created_at"])
        await message.answer(
            f"ℹ️ Natijalar allaqachon {date} sanada admin <code>{existing['confirmed_by']}</code> "
            "tomonidan tasdiqlangan. Qayta tasdiqlashingiz mumkin (yangi surat saqlanadi)."
        )

    results = await db.get_results()
    if not results:
        await message.answer("😔 Hozircha natijalar mavjud emas.")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Tasdiqlanadigan yakuniy natija:</b>\n"]
    for i, v in enumerate(results):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{prefix} {escape(v['title'])} — {v['votes_count']} ta ovoz")
    lines.append("\n⚠️ Tasdiqlagach, bu natija rasmiy yakuniy natija sifatida qayd etiladi.")

    await message.answer("\n".join(lines), reply_markup=kb.confirm_final_results_keyboard())


@router.callback_query(F.data == "confirm_final_yes")
async def cb_confirm_final_yes(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer()
        return
    await db.confirm_final_results(callback.from_user.id)
    await db.log_audit(callback.from_user.id, "Yakuniy natija tasdiqlandi", "")
    await callback.message.edit_text("✅ Yakuniy natija rasmiy ravishda tasdiqlandi va saqlandi.")
    await callback.answer()


@router.callback_query(F.data == "confirm_final_no")
async def cb_confirm_final_no(callback: CallbackQuery):
    await callback.message.edit_text("❌ Bekor qilindi, hech narsa tasdiqlanmadi.")
    await callback.answer()


# ==================== YAKUNIY HISOBOT ====================

@router.message(F.text == "📄 Yakuniy hisobot")
async def final_report(message: Message):
    if not await is_admin(message.from_user.id):
        return

    results = await db.get_results()
    stats = await db.get_stats()
    fraud = await db.get_fraud_stats()
    confirmation = await db.get_final_results_confirmation()

    lines = ["📄 <b>YAKUNIY HISOBOT</b>\n"]

    if confirmation:
        lines.append(
            f"✅ Rasmiy tasdiqlangan: {format_dt(confirmation['created_at'])} "
            f"(admin <code>{confirmation['confirmed_by']}</code>)\n"
        )
    else:
        lines.append("⚠️ Natijalar hali rasmiy tasdiqlanmagan.\n")

    medals = ["🥇", "🥈", "🥉"]
    lines.append("🏆 <b>Natijalar:</b>")
    for i, v in enumerate(results):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{prefix} {escape(v['title'])} — {v['votes_count']} ta ovoz")

    lines.append(
        f"\n📊 <b>Umumiy statistika:</b>\n"
        f"👥 Jami foydalanuvchilar: {stats['users']}\n"
        f"🗳 Jami ovozlar: {stats['votes']}\n"
        f"✅ Ovoz bergan: {stats['voted_users']} | ⏳ Bermagan: {stats['not_voted_users']}"
    )

    lines.append(
        f"\n🛡 <b>Anti-fraud xulosasi:</b>\n"
        f"⚡ Tez ovoz berganlar: {fraud['fast_signup_votes']}\n"
        f"👥 Bir xil ismli guruhlar: {fraud['duplicate_name_clusters']} "
        f"({fraud['duplicate_name_users']} akkaunt)\n"
        f"⏱ Ommaviy ro'yxatdan o'tish guruhlari: {fraud['burst_clusters']} "
        f"({fraud['burst_users']} akkaunt)\n"
        f"\nℹ️ Bu ko'rsatkichlar faqat tekshiruv signali, avtomatik xulosa emas — "
        f"batafsil ma'lumot uchun \"📤 Excel eksport\"dan foydalaning."
    )

    await message.answer("\n".join(lines))
