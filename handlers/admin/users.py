# ============================================================
# BOTFORGE — handlers/admin/users.py
# Foydalanuvchilar boshqaruvi — ro'yxat, qidirish,
# bloklash, xabar yuborish, ommaviy xabar
# ============================================================

import logging
from aiogram import Router, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import (
    get_all_users, count_users, search_user,
    get_user, ban_user, unban_user, get_all_user_ids,
)
from keyboards import (
    AdminCB, UserAdminCB,
    users_menu_kb, user_detail_kb, confirm_ban_kb,
    back_to_main_kb,
)
from utils import fmt_date, broadcast, send_to_user, validate_user_id

logger = logging.getLogger(__name__)
router = Router()

USERS_PER_PAGE = 10


# ============================================================
# FSM HOLATLARI
# ============================================================

class SearchUserState(StatesGroup):
    query = State()


class BanUserState(StatesGroup):
    user_id = State()


class UnbanUserState(StatesGroup):
    user_id = State()


class MessageUserState(StatesGroup):
    user_id = State()
    text    = State()


class BroadcastState(StatesGroup):
    text    = State()
    confirm = State()


# ============================================================
# FOYDALANUVCHILAR RO'YXATI
# ============================================================

@router.callback_query(UserAdminCB.filter(F.action == "list"))
async def cb_users_list(
    callback: CallbackQuery,
    callback_data: UserAdminCB,
    state: FSMContext
) -> None:
    """Barcha foydalanuvchilar — pagination bilan."""
    await state.clear()
    page  = callback_data.page
    total = await count_users()

    total_pages = max(1, (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    page   = max(1, min(page, total_pages))
    offset = (page - 1) * USERS_PER_PAGE

    users = await get_all_users(offset=offset, limit=USERS_PER_PAGE)

    lines = [f"👥 *Foydalanuvchilar* ({total} ta)\n"]
    for u in users:
        ban_icon = "🚫" if u["is_banned"] else "👤"
        username = f"@{u['username']}" if u["username"] else "—"
        lines.append(f"{ban_icon} `{u['id']}` — {u['full_name']} ({username})")

    # Pagination tugmalari
    builder = InlineKeyboardBuilder()

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(
            text="◀️",
            callback_data=UserAdminCB(action="list", page=page - 1).pack()
        ))
    nav.append(InlineKeyboardButton(
        text=f"{page}/{total_pages}", callback_data="noop"
    ))
    if page < total_pages:
        nav.append(InlineKeyboardButton(
            text="▶️",
            callback_data=UserAdminCB(action="list", page=page + 1).pack()
        ))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data=AdminCB(section="users").pack()
    ))

    await callback.message.edit_text(
        text="\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# FOYDALANUVCHI QIDIRISH
# ============================================================

@router.callback_query(UserAdminCB.filter(F.action == "search"))
async def cb_search_start(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    await state.set_state(SearchUserState.query)
    await callback.message.edit_text(
        text=(
            "🔍 *Foydalanuvchi qidirish*\n\n"
            "ID, username yoki ism yozing:"
        ),
        reply_markup=None,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(SearchUserState.query, F.text)
async def process_search(message: Message, state: FSMContext) -> None:
    await state.clear()
    users = await search_user(message.text.strip())

    if not users:
        await message.answer("🔍 Hech kim topilmadi.")
        return

    lines = ["🔍 *Natijalar:*\n"]
    for u in users:
        ban_icon = "🚫" if u["is_banned"] else "👤"
        username = f"@{u['username']}" if u["username"] else "—"
        phone    = u["phone"] or "—"
        lines.append(
            f"{ban_icon} `{u['id']}` — {u['full_name']}\n"
            f"   {username} | 📱 {phone}"
        )

    builder = InlineKeyboardBuilder()

    # Bitta foydalanuvchi topilsa — detail ko'rsatish tugmasi
    if len(users) == 1:
        u = users[0]
        builder.row(InlineKeyboardButton(
            text="👤 Batafsil",
            callback_data=UserAdminCB(
                action="detail", user_id=u["id"]
            ).pack()
        ))
    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data=AdminCB(section="users").pack()
    ))

    await message.answer(
        text="\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


# ============================================================
# FOYDALANUVCHI DETAIL
# ============================================================

@router.callback_query(UserAdminCB.filter(F.action == "detail"))
async def cb_user_detail(
    callback: CallbackQuery,
    callback_data: UserAdminCB,
    state: FSMContext
) -> None:
    """Foydalanuvchi to'liq ma'lumoti."""
    await state.clear()
    user = await get_user(callback_data.user_id)
    if not user:
        await callback.answer("Foydalanuvchi topilmadi", show_alert=True)
        return

    ban_icon = "🚫 Bloklangan" if user["is_banned"] else "✅ Faol"
    username = f"@{user['username']}" if user["username"] else "—"
    phone    = user["phone"] or "—"

    text = (
        f"👤 *{user['full_name']}*\n\n"
        f"🆔 `{user['id']}`\n"
        f"📱 {username}\n"
        f"☎️ {phone}\n"
        f"📅 Ro'yxat: {fmt_date(user['created_at'])}\n"
        f"🕐 Oxirgi: {fmt_date(user['last_seen'])}\n"
        f"📊 Holat: {ban_icon}"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=user_detail_kb(
            user_id=callback_data.user_id,
            is_banned=user["is_banned"]
        ),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# BLOKLASH
# ============================================================

@router.callback_query(UserAdminCB.filter(F.action == "ban"))
async def cb_ban_start(
    callback: CallbackQuery,
    callback_data: UserAdminCB,
    state: FSMContext
) -> None:
    """Bloklash — user_id detail dan kelgan bo'lsa confirm, yo'q bo'lsa ID so'rash."""
    if callback_data.user_id:
        user = await get_user(callback_data.user_id)
        if not user:
            await callback.answer("Topilmadi", show_alert=True)
            return
        await callback.message.edit_text(
            text=(
                f"⚠️ *Rostdan ham bloklaysizmi?*\n\n"
                f"👤 {user['full_name']}\n"
                f"🆔 `{user['id']}`"
            ),
            reply_markup=confirm_ban_kb(callback_data.user_id),
            parse_mode="Markdown"
        )
    else:
        await state.set_state(BanUserState.user_id)
        await callback.message.edit_text(
            text="🚫 *Bloklash*\n\nFoydalanuvchi ID sini yozing:",
            reply_markup=None,
            parse_mode="Markdown"
        )
    await callback.answer()


@router.message(BanUserState.user_id, F.text)
async def process_ban_id(message: Message, state: FSMContext) -> None:
    user_id, error = validate_user_id(message.text)
    if error:
        await message.answer(error)
        return

    await state.clear()
    user = await get_user(user_id)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return

    await message.answer(
        text=(
            f"⚠️ *Rostdan ham bloklaysizmi?*\n\n"
            f"👤 {user['full_name']}\n"
            f"🆔 `{user['id']}`"
        ),
        reply_markup=confirm_ban_kb(user_id),
        parse_mode="Markdown"
    )


@router.callback_query(UserAdminCB.filter(F.action == "ban_confirm"))
async def cb_ban_confirm(
    callback: CallbackQuery,
    callback_data: UserAdminCB
) -> None:
    success = await ban_user(callback_data.user_id)
    if success:
        await callback.message.edit_text(
            text=f"✅ Foydalanuvchi `{callback_data.user_id}` bloklandi.",
            reply_markup=back_to_main_kb(),
            parse_mode="Markdown"
        )
    else:
        await callback.answer("Allaqachon bloklangan yoki topilmadi", show_alert=True)


# ============================================================
# BLOKDAN CHIQARISH
# ============================================================

@router.callback_query(UserAdminCB.filter(F.action == "unban"))
async def cb_unban_start(
    callback: CallbackQuery,
    callback_data: UserAdminCB,
    state: FSMContext
) -> None:
    if callback_data.user_id:
        success = await unban_user(callback_data.user_id)
        if success:
            await callback.answer("✅ Blokdan chiqarildi")
            user = await get_user(callback_data.user_id)
            await callback.message.edit_text(
                text=f"✅ `{callback_data.user_id}` blokdan chiqarildi.",
                reply_markup=user_detail_kb(
                    user_id=callback_data.user_id,
                    is_banned=False
                ),
                parse_mode="Markdown"
            )
        else:
            await callback.answer("Bloklangan emas yoki topilmadi", show_alert=True)
    else:
        await state.set_state(UnbanUserState.user_id)
        await callback.message.edit_text(
            text="✅ *Blokdan chiqarish*\n\nFoydalanuvchi ID sini yozing:",
            reply_markup=None,
            parse_mode="Markdown"
        )
    await callback.answer()


@router.message(UnbanUserState.user_id, F.text)
async def process_unban_id(message: Message, state: FSMContext) -> None:
    user_id, error = validate_user_id(message.text)
    if error:
        await message.answer(error)
        return

    await state.clear()
    success = await unban_user(user_id)
    if success:
        await message.answer(f"✅ `{user_id}` blokdan chiqarildi.", parse_mode="Markdown")
    else:
        await message.answer("❌ Foydalanuvchi bloklangan emas yoki topilmadi.")


# ============================================================
# BITTA FOYDALANUVCHIGA XABAR
# ============================================================

@router.callback_query(UserAdminCB.filter(F.action == "msg"))
async def cb_msg_start(
    callback: CallbackQuery,
    callback_data: UserAdminCB,
    state: FSMContext
) -> None:
    if callback_data.user_id:
        await state.update_data(target_user_id=callback_data.user_id)
        await state.set_state(MessageUserState.text)
        await callback.message.edit_text(
            text=f"✉️ *Xabar yuborish*\n\n`{callback_data.user_id}` ga xabar yozing:",
            reply_markup=None,
            parse_mode="Markdown"
        )
    else:
        await state.set_state(MessageUserState.user_id)
        await callback.message.edit_text(
            text="✉️ *Xabar yuborish*\n\nFoydalanuvchi ID sini yozing:",
            reply_markup=None,
            parse_mode="Markdown"
        )
    await callback.answer()


@router.message(MessageUserState.user_id, F.text)
async def process_msg_user_id(message: Message, state: FSMContext) -> None:
    user_id, error = validate_user_id(message.text)
    if error:
        await message.answer(error)
        return

    await state.update_data(target_user_id=user_id)
    await state.set_state(MessageUserState.text)
    await message.answer(
        f"✉️ `{user_id}` ga yuboriladigan xabarni yozing:",
        parse_mode="Markdown"
    )


@router.message(MessageUserState.text, F.text)
async def process_msg_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    success = await send_to_user(
        bot=message.bot,
        user_id=data["target_user_id"],
        text=message.text
    )

    if success:
        await message.answer(f"✅ Xabar `{data['target_user_id']}` ga yuborildi.", parse_mode="Markdown")
    else:
        await message.answer(f"❌ Xabar yuborib bo'lmadi. Foydalanuvchi botni bloklagan bo'lishi mumkin.")


# ============================================================
# OMMAVIY XABAR (BROADCAST)
# ============================================================

@router.callback_query(UserAdminCB.filter(F.action == "broadcast"))
async def cb_broadcast_start(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    await state.set_state(BroadcastState.text)
    await callback.message.edit_text(
        text=(
            "📢 *Ommaviy xabar*\n\n"
            "Barcha foydalanuvchilarga yuboriladigan xabarni yozing:\n\n"
            "_Markdown formatlash ishlaydi: *qalin*, _kursiv_"
        ),
        reply_markup=None,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(BroadcastState.text, F.text)
async def process_broadcast_text(message: Message, state: FSMContext) -> None:
    """Xabarni ko'rsatib tasdiqlash so'rash."""
    await state.update_data(broadcast_text=message.text)
    await state.set_state(BroadcastState.confirm)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Yuborish", callback_data="broadcast_confirm"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="broadcast_cancel")
    )

    total = await count_users()
    await message.answer(
        text=(
            f"📢 *Xabar ko'rinishi:*\n\n"
            f"{message.text}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👥 Jami {total} ta foydalanuvchiga yuboriladi."
        ),
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "broadcast_confirm")
async def cb_broadcast_confirm(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Broadcast yuborish."""
    data = await state.get_data()
    await state.clear()

    user_ids = await get_all_user_ids()
    await callback.message.edit_text(
        text=f"📤 Yuborilmoqda... ({len(user_ids)} ta foydalanuvchi)",
        reply_markup=None
    )

    result = await broadcast(
        bot=callback.bot,
        user_ids=user_ids,
        text=data["broadcast_text"]
    )

    await callback.message.edit_text(
        text=(
            f"✅ *Broadcast tugadi!*\n\n"
            f"✅ Yuborildi: {result['sent']}\n"
            f"❌ Xato: {result['failed']}\n"
            f"👥 Jami: {result['total']}"
        ),
        reply_markup=back_to_main_kb(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "broadcast_cancel")
async def cb_broadcast_cancel(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    await state.clear()
    await callback.message.edit_text(
        text="❌ Ommaviy xabar bekor qilindi.",
        reply_markup=back_to_main_kb()
    )
    await callback.answer()
