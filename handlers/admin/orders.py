# ============================================================
# BOTFORGE — handlers/admin/orders.py
# Buyurtmalar boshqaruvi
# ============================================================

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from db import (
    get_orders_by_status, count_orders_by_status,
    get_order, get_order_items, update_order_status,
)
from keyboards import (
    AdminCB, OrderAdminCB,
    admin_orders_list_kb, admin_order_detail_kb,
    orders_menu_kb,
)
from utils import fmt_order_card, fmt_status, fmt_order_progress

logger = logging.getLogger(__name__)
router = Router()

ORDERS_PER_PAGE = 10


# ============================================================
# YORDAMCHI — Holat sanoqlari
# ============================================================

async def _get_status_counts() -> dict:
    statuses = ["pending", "confirmed", "shipping", "delivered", "cancelled", "problem"]
    counts = {}
    for status in statuses:
        counts[status] = await count_orders_by_status(status)
    return counts


# ============================================================
# BUYURTMALAR RO'YXATI — Holat bo'yicha
# ============================================================

@router.callback_query(OrderAdminCB.filter(F.action == "list"))
async def cb_orders_list(
    callback: CallbackQuery,
    callback_data: OrderAdminCB,
    state: FSMContext
) -> None:
    """Holat bo'yicha buyurtmalar ro'yxati — pagination bilan."""
    await state.clear()
    status = callback_data.status
    page   = callback_data.page

    total = await count_orders_by_status(status)

    if total == 0:
        counts = await _get_status_counts()
        await callback.message.edit_text(
            text=f"📋 *{fmt_status(status)}* — buyurtmalar yo'q.",
            reply_markup=orders_menu_kb(counts),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    total_pages = max(1, (total + ORDERS_PER_PAGE - 1) // ORDERS_PER_PAGE)
    page  = max(1, min(page, total_pages))
    offset = (page - 1) * ORDERS_PER_PAGE

    orders = await get_orders_by_status(status, offset=offset, limit=ORDERS_PER_PAGE)

    await callback.message.edit_text(
        text=f"📋 *{fmt_status(status)}* ({total} ta)",
        reply_markup=admin_orders_list_kb(
            orders=orders,
            status=status,
            page=page,
            total_pages=total_pages
        ),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# BUYURTMA DETAIL
# ============================================================

@router.callback_query(OrderAdminCB.filter(F.action == "detail"))
async def cb_order_detail(
    callback: CallbackQuery,
    callback_data: OrderAdminCB
) -> None:
    """Buyurtma to'liq ma'lumoti va holat o'zgartirish tugmalari."""
    order = await get_order(callback_data.order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return

    items = await get_order_items(callback_data.order_id)
    text  = fmt_order_card(order, items)

    # To'lov screenshoti borligini ko'rsatish
    if order.get("payment_photo"):
        text += "\n\n💳 *To'lov screenshoti yuborilgan* ✅"

    await callback.message.edit_text(
        text=text,
        reply_markup=admin_order_detail_kb(
            order_id=callback_data.order_id,
            current_status=order["status"],
            page=callback_data.page
        ),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# BUYURTMA HOLATI O'ZGARTIRISH
# ============================================================

@router.callback_query(OrderAdminCB.filter(F.action == "status"))
async def cb_order_status(
    callback: CallbackQuery,
    callback_data: OrderAdminCB
) -> None:
    """
    Buyurtma holatini o'zgartirish.
    pending → confirmed da stok avtomatik kamayadi (db/orders.py da).
    """
    order = await get_order(callback_data.order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return

    new_status = callback_data.status
    await update_order_status(callback_data.order_id, new_status)

    # Foydalanuvchiga holat o'zgargani haqida xabar
    await _notify_user(
        bot=callback.bot,
        user_id=order["user_id"],
        order_code=order["order_code"],
        new_status=new_status
    )

    await callback.answer(f"✅ Holat: {fmt_status(new_status)}")

    # Kartani yangi holat bilan yangilash
    updated_order = await get_order(callback_data.order_id)
    items = await get_order_items(callback_data.order_id)
    text  = fmt_order_card(updated_order, items)

    if updated_order.get("payment_photo"):
        text += "\n\n💳 *To'lov screenshoti yuborilgan* ✅"

    await callback.message.edit_text(
        text=text,
        reply_markup=admin_order_detail_kb(
            order_id=callback_data.order_id,
            current_status=new_status,
            page=callback_data.page
        ),
        parse_mode="Markdown"
    )


# ============================================================
# YORDAMCHI — Foydalanuvchiga holat xabari
# ============================================================

async def _notify_user(
    bot,
    user_id: int,
    order_code: str,
    new_status: str
) -> None:
    """
    Buyurtma holati o'zgarganda foydalanuvchiga
    avtomatik xabar yuboriladi.
    """
    status_messages = {
        "confirmed": "✅ Buyurtmangiz tasdiqlandi va tayyorlanmoqda!",
        "shipping":  "🚚 Buyurtmangiz yo'lga chiqdi!",
        "delivered": "📦 Buyurtmangiz yetkazildi!\n\nRahmat! 🙏",
        "cancelled": "❌ Buyurtmangiz bekor qilindi.\nSavollar uchun admin bilan bog'laning.",
        "problem":   "⚠️ Buyurtmangizda muammo bor.\nAdmin tez orada siz bilan bog'lanadi.",
    }

    message_text = status_messages.get(new_status)
    if not message_text:
        return

    progress = fmt_order_progress(new_status)

    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"🔔 *#{order_code} buyurtma holati o'zgardi*\n\n"
                f"{message_text}\n\n"
                f"{progress}"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Foydalanuvchi {user_id} ga xabar yuborib bo'lmadi: {e}")
