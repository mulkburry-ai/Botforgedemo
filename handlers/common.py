# ============================================================
# BOTFORGE — handlers/common.py
# /start, /admin, xatolik tutish
# aiogram 3.x Router
# ============================================================

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ErrorEvent
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID
from db import get_or_create_user, get_dashboard, get_setting
from keyboards import main_menu_kb, admin_panel_kb
from utils import fmt_dashboard

logger = logging.getLogger(__name__)
router = Router()


# ============================================================
# /start
# ============================================================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    Foydalanuvchi botga birinchi marta kirganida yoki
    /start yuborganida chaqiriladi.
    1. Foydalanuvchini bazaga qo'shadi / yangilaydi
    2. Asosiy menyuni ko'rsatadi
    """
    # FSM holatini tozalash — oldingi jarayon o'chadi
    await state.clear()

    # Foydalanuvchini bazaga qo'shish yoki yangilash
    await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )

    # Do'kon nomi va tavsifini sozlamalardan olish
    shop_name = await get_setting("shop_name")
    shop_phone = await get_setting("shop_phone")

    welcome_text = (
        f"👋 *{shop_name}* ga xush kelibsiz!\n\n"
        f"📞 Aloqa: {shop_phone}\n\n"
        f"Quyidagi bo'limlardan birini tanlang:"
    )

    await message.answer(
        text=welcome_text,
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )


# ============================================================
# /admin
# ============================================================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    """
    Admin panelini ochish.
    Faqat ADMIN_ID ga ruxsat beriladi.
    """
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Ruxsat yo'q.")
        return

    # FSM tozalash
    await state.clear()

    # Dashboard ma'lumotlari
    data = await get_dashboard()
    dashboard_text = fmt_dashboard(data)

    await message.answer(
        text=f"👨‍💼 *Admin panel*\n\n{dashboard_text}",
        reply_markup=admin_panel_kb(),
        parse_mode="Markdown"
    )


# ============================================================
# NOOP CALLBACK — Hech narsa qilmaydigan tugmalar
# ============================================================

@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery) -> None:
    """
    Sahifa raqami kabi faqat ko'rinish uchun tugmalar.
    Bosilganda faqat alert o'chiriladi.
    """
    await callback.answer()


# ============================================================
# XATOLIK TUTISH
# ============================================================

async def error_handler(event: ErrorEvent) -> None:
    """
    Kutilmagan xatolarni tutib log qiladi.
    Foydalanuvchiga umumiy xato xabari yuboriladi.
    Bot to'xtamaydi.
    """
    logger.error(
        f"Kutilmagan xato: {event.exception}",
        exc_info=event.exception
    )

    # Xato qaysi update dan kelganini aniqlaymiz
    update = event.update
    if update.message:
        await update.message.answer(
            "⚠️ Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring."
        )
    elif update.callback_query:
        await update.callback_query.answer(
            "⚠️ Xatolik yuz berdi.",
            show_alert=True
        )
