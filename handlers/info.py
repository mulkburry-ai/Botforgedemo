# ============================================================
# BOTFORGE — handlers/info.py
# Ma'lumot bo'limi — do'kon haqida, yetkazib berish,
# to'lov, aloqa, mahsulot so'rovi, sevimlilar, oxirgi ko'rilgan
# ============================================================

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import get_setting, get_favorites, get_last_seen
from keyboards import InfoCB, info_kb, info_back_kb

logger = logging.getLogger(__name__)
router = Router()


# ============================================================
# FSM — Mahsulot so'rovi
# ============================================================

class InfoState(StatesGroup):
    waiting_request = State()   # Foydalanuvchi so'rovini yozadi


# ============================================================
# ASOSIY MENYU — "ℹ️ Ma'lumot" tugmasi
# ============================================================

@router.message(F.text == "ℹ️ Ma'lumot")
async def show_info(message: Message, state: FSMContext) -> None:
    """Ma'lumot bo'limi asosiy menyusi."""
    await state.clear()
    await message.answer(
        text="ℹ️ *Ma'lumot*\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=info_kb(),
        parse_mode="Markdown"
    )


# ============================================================
# DO'KON HAQIDA
# ============================================================

@router.callback_query(InfoCB.filter(F.section == "about"))
async def cb_about(callback: CallbackQuery) -> None:
    shop_name    = await get_setting("shop_name")
    shop_phone   = await get_setting("shop_phone")
    shop_address = await get_setting("shop_address")

    text = (
        f"🏪 *{shop_name}*\n\n"
        f"📞 Telefon: {shop_phone}\n"
        f"📍 Manzil: {shop_address}"
    )
    await callback.message.edit_text(
        text=text,
        reply_markup=info_back_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# YETKAZIB BERISH
# ============================================================

@router.callback_query(InfoCB.filter(F.section == "delivery"))
async def cb_delivery(callback: CallbackQuery) -> None:
    delivery_info = await get_setting("delivery_info")

    await callback.message.edit_text(
        text=f"🚚 *Yetkazib berish*\n\n{delivery_info}",
        reply_markup=info_back_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# TO'LOV
# ============================================================

@router.callback_query(InfoCB.filter(F.section == "payment"))
async def cb_payment(callback: CallbackQuery) -> None:
    payment_info = await get_setting("payment_info")
    payment_card = await get_setting("payment_card")

    text = f"💳 *To'lov*\n\n{payment_info}"
    if payment_card:
        text += f"\n\n💳 Karta: `{payment_card}`"

    await callback.message.edit_text(
        text=text,
        reply_markup=info_back_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# ALOQA
# ============================================================

@router.callback_query(InfoCB.filter(F.section == "contact"))
async def cb_contact(callback: CallbackQuery) -> None:
    shop_phone    = await get_setting("shop_phone")
    admin_username = await get_setting("admin_username", "")

    text = f"📞 *Aloqa*\n\nTelefon: {shop_phone}"
    if admin_username:
        text += f"\nTelegram: {admin_username}"

    await callback.message.edit_text(
        text=text,
        reply_markup=info_back_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# MAHSULOT SO'ROVI
# ============================================================

@router.callback_query(InfoCB.filter(F.section == "request"))
async def cb_request_start(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Mahsulot so'rovini boshlash."""
    await state.set_state(InfoState.waiting_request)
    await callback.message.edit_text(
        text=(
            "💡 *Mahsulot so'rovi*\n\n"
            "Qaysi mahsulotni xohlayotganingizni yozing.\n"
            "Admin ko'rib chiqadi va siz bilan bog'lanadi."
        ),
        reply_markup=info_back_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(InfoState.waiting_request, F.text)
async def process_request(message: Message, state: FSMContext) -> None:
    """Mahsulot so'rovini qabul qilish va adminga yuborish."""
    from config import ADMIN_ID

    request_text = message.text.strip()
    if len(request_text) < 3:
        await message.answer("❌ So'rov juda qisqa. Aniqroq yozing.")
        return

    await state.clear()

    # Foydalanuvchiga javob
    await message.answer(
        "✅ So'rovingiz qabul qilindi!\n"
        "Admin tez orada siz bilan bog'lanadi."
    )

    # Adminga xabar
    user = message.from_user
    username = f"@{user.username}" if user.username else "username yo'q"
    admin_text = (
        f"💡 *Yangi mahsulot so'rovi*\n\n"
        f"👤 {user.full_name} ({username})\n"
        f"🆔 `{user.id}`\n\n"
        f"📝 So'rov:\n{request_text}"
    )

    try:
        await message.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Adminga so'rov yuborishda xato: {e}")


# ============================================================
# SEVIMLILAR
# ============================================================

@router.callback_query(InfoCB.filter(F.section == "favorites"))
async def cb_favorites(callback: CallbackQuery) -> None:
    """Foydalanuvchining sevimli mahsulotlari."""
    user_id = callback.from_user.id
    products = await get_favorites(user_id)

    if not products:
        await callback.message.edit_text(
            text="🤍 Sevimlilar bo'sh.\n\nMahsulot kartasida ❤️ tugmasini bosing.",
            reply_markup=info_back_kb(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    lines = ["❤️ *Sevimlilar:*\n"]
    for p in products:
        lines.append(f"• #{p['id']} {p['name']} — {int(p['price']):,} so'm")

    await callback.message.edit_text(
        text="\n".join(lines),
        reply_markup=info_back_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# OXIRGI KO'RILGANLAR
# ============================================================

@router.callback_query(InfoCB.filter(F.section == "last_seen"))
async def cb_last_seen(callback: CallbackQuery) -> None:
    """Foydalanuvchi oxirgi ko'rgan mahsulotlari (max 10)."""
    user_id = callback.from_user.id
    products = await get_last_seen(user_id)

    if not products:
        await callback.message.edit_text(
            text="🕐 Hali hech qanday mahsulot ko'rilmagan.",
            reply_markup=info_back_kb(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    lines = ["🕐 *Oxirgi ko'rilganlar:*\n"]
    for p in products:
        lines.append(f"• #{p['id']} {p['name']} — {int(p['price']):,} so'm")

    await callback.message.edit_text(
        text="\n".join(lines),
        reply_markup=info_back_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# ASOSIY MA'LUMOT MENYUSIGA QAYTISH
# ============================================================

@router.callback_query(InfoCB.filter(F.section == "main"))
async def cb_info_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Ma'lumot bo'limi asosiy menyusiga qaytish."""
    await state.clear()
    await callback.message.edit_text(
        text="ℹ️ *Ma'lumot*\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=info_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()
