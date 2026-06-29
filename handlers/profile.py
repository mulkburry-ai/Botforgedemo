# ============================================================
# BOTFORGE — handlers/profile.py
# Buyurtmalarim — foydalanuvchi buyurtmalari va holati
# ============================================================

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from db import get_user_orders, get_order, get_order_items
from keyboards import OrderCB, orders_list_kb, order_detail_kb
from utils import fmt_order_card, fmt_order_progress, fmt_status, fmt_date

logger = logging.getLogger(__name__)
router = Router()


# ============================================================
# YORDAMCHI — Takroriy kod bitta joyda
# ============================================================

async def _build_orders_view(user_id: int) -> tuple[str | None, object | None]:
    """
    Buyurtmalar ro'yxati matni va klaviaturasini qaytaradi.
    show_orders va cb_orders_list ikkisi ham ishlatadi.
    """
    orders = await get_user_orders(user_id, limit=5)
    if not orders:
        return None, None

    lines = ["📦 *Buyurtmalarim:*\n"]
    for order in orders:
        lines.append(
            f"#{order['order_code']} — "
            f"{fmt_status(order['status'])} — "
            f"{fmt_date(order['created_at'])}"
        )
    return "\n".join(lines), orders_list_kb(orders)


# ============================================================
# BUYURTMALARIM — Asosiy sahifa
# ============================================================

@router.message(F.text == "📦 Buyurtmalarim")
async def show_orders(message: Message, state: FSMContext) -> None:
    """Foydalanuvchining oxirgi 5 ta buyurtmasi."""
    await state.clear()

    text, kb = await _build_orders_view(message.from_user.id)
    if not text:
        await message.answer(
            "📦 Sizda hali buyurtmalar yo'q.\n\n"
            "Buyurtma berish uchun Katalogga o'ting."
        )
        return

    await message.answer(text=text, reply_markup=kb, parse_mode="Markdown")


# ============================================================
# BUYURTMA DETAIL — Batafsil va progress
# ============================================================

@router.callback_query(OrderCB.filter(F.action == "detail"))
async def cb_order_detail(
    callback: CallbackQuery,
    callback_data: OrderCB
) -> None:
    """Bitta buyurtmaning to'liq ma'lumoti va progress."""
    order = await get_order(callback_data.order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return

    items = await get_order_items(callback_data.order_id)
    card = fmt_order_card(order, items)
    progress = fmt_order_progress(order["status"])

    await callback.message.edit_text(
        text=f"{card}\n\n*Holat:*\n{progress}",
        reply_markup=order_detail_kb(callback_data.order_id),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# BUYURTMALAR RO'YXATIGA QAYTISH
# ============================================================

@router.callback_query(OrderCB.filter(F.action == "list"))
async def cb_orders_list(callback: CallbackQuery) -> None:
    """Buyurtmalar ro'yxatiga qaytish."""
    text, kb = await _build_orders_view(callback.from_user.id)

    if not text:
        await callback.message.edit_text(
            text="📦 Buyurtmalar yo'q.",
            reply_markup=None
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        text=text, reply_markup=kb, parse_mode="Markdown"
    )
    await callback.answer()
