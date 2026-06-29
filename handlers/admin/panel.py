# ============================================================
# BOTFORGE — handlers/admin/panel.py
# Admin paneli — dashboard va bo'limlarga yo'naltirish
# ============================================================

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from db import get_dashboard, count_orders_by_status
from keyboards import (
    AdminCB,
    admin_panel_kb,
    products_menu_kb,
    orders_menu_kb,
    users_menu_kb,
    stats_menu_kb,
)
from utils import fmt_dashboard

logger = logging.getLogger(__name__)
router = Router()


# ============================================================
# YORDAMCHI — Dashboard matni
# ============================================================

async def _build_dashboard_text() -> str:
    data = await get_dashboard()
    return f"👨‍💼 *Admin panel*\n\n{fmt_dashboard(data)}"


# ============================================================
# ASOSIY PANEL — Qaytish
# ============================================================

@router.callback_query(AdminCB.filter(F.section == "main"))
async def cb_admin_main(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """
    Istalgan bo'limdan asosiy admin panelga qaytish.
    FSM tozalanadi — yarim qolgan jarayon o'chadi.
    """
    await state.clear()
    text = await _build_dashboard_text()

    await callback.message.edit_text(
        text=text,
        reply_markup=admin_panel_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# BO'LIMLARGA YO'NALTIRISH
# ============================================================

@router.callback_query(AdminCB.filter(F.section == "products"))
async def cb_section_products(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Mahsulotlar bo'limiga o'tish."""
    await state.clear()
    await callback.message.edit_text(
        text="📦 *Mahsulotlar boshqaruvi*\nNimani qilmoqchisiz?",
        reply_markup=products_menu_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(AdminCB.filter(F.section == "orders"))
async def cb_section_orders(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Buyurtmalar bo'limiga o'tish — holat sanoqlari bilan."""
    await state.clear()

    # Har bir holat uchun sanoq olish
    statuses = ["pending", "confirmed", "shipping", "delivered", "cancelled", "problem"]
    counts = {}
    for status in statuses:
        counts[status] = await count_orders_by_status(status)

    await callback.message.edit_text(
        text="📋 *Buyurtmalar boshqaruvi*\nHolatni tanlang:",
        reply_markup=orders_menu_kb(counts),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(AdminCB.filter(F.section == "users"))
async def cb_section_users(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Boshqaruv bo'limiga o'tish."""
    await state.clear()
    await callback.message.edit_text(
        text="👥 *Foydalanuvchilar boshqaruvi*\nNimani qilmoqchisiz?",
        reply_markup=users_menu_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(AdminCB.filter(F.section == "stats"))
async def cb_section_stats(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Ma'lumotlar bo'limiga o'tish."""
    await state.clear()
    await callback.message.edit_text(
        text="📊 *Ma'lumotlar*\nQaysi bo'limni ko'rmoqchisiz?",
        reply_markup=stats_menu_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()
