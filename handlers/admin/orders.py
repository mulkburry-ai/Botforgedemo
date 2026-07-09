# ============================================================
# BOTFORGE — handlers/admin/orders.py
# Buyurtmalar boshqaruvi
# ============================================================

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_ID
from db import (
    get_orders_by_status, count_orders_by_status,
    get_order, get_order_items, update_order_status,
    update_order_delivery,
)
from keyboards import (
    OrderAdminCB,
    admin_orders_list_kb, admin_order_detail_kb,
    orders_menu_kb,
)
from utils import fmt_order_card, fmt_status, fmt_order_progress, fmt_price

logger = logging.getLogger(__name__)
router = Router()

ORDERS_PER_PAGE = 10


# ============================================================
# FSM — Yetkazib berish narxi va vaqti
# ============================================================

class ShipOrderState(StatesGroup):
    delivery_price = State()
    delivery_time  = State()


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================

async def _get_status_counts() -> dict:
    statuses = ["pending", "confirmed", "shipping", "delivered", "cancelled", "problem"]
    return {s: await count_orders_by_status(s) for s in statuses}


def _ship_cancel_kb(order_id: int, page: int) -> InlineKeyboardMarkup:
    """Yetkazish jarayonida bekor qilish tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data=OrderAdminCB(
            action="detail", order_id=order_id, page=page
        ).pack()
    ))
    return builder.as_markup()


def _skip_free_kb(order_id: int, page: int) -> InlineKeyboardMarkup:
    """Narx bosqichi: Bepul yetkazish + Bekor."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⏭ Bepul yetkazish",
            callback_data=f"ship_free:{order_id}:{page}"
        ),
        InlineKeyboardButton(
            text="❌ Bekor",
            callback_data=OrderAdminCB(
                action="detail", order_id=order_id, page=page
            ).pack()
        )
    )
    return builder.as_markup()


def _skip_time_kb(order_id: int, page: int) -> InlineKeyboardMarkup:
    """Vaqt bosqichi: Vaqtsiz yuborish + Bekor."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⏭ Vaqtsiz yuborish",
            callback_data=f"ship_notime:{order_id}:{page}"
        ),
        InlineKeyboardButton(
            text="❌ Bekor",
            callback_data=OrderAdminCB(
                action="detail", order_id=order_id, page=page
            ).pack()
        )
    )
    return builder.as_markup()


def _delivery_confirm_kb(order_id: int) -> InlineKeyboardMarkup:
    """Mijozga — 'yetib bordimi?' tugmalari."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Ha, oldim!",
            callback_data=f"delivery_got:{order_id}"
        ),
        InlineKeyboardButton(
            text="❌ Hali olmadim",
            callback_data=f"delivery_notgot:{order_id}"
        )
    )
    return builder.as_markup()


def _admin_ship_kb(order_id: int) -> InlineKeyboardMarkup:
    """Adminga — yo'lga chiqqandan keyin 'Yetkazildi/Muammo' tugmalari."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📦 Yetkazildi",
            callback_data=OrderAdminCB(
                action="status", order_id=order_id, status="delivered"
            ).pack()
        ),
        InlineKeyboardButton(
            text="⚠️ Muammo bor",
            callback_data=OrderAdminCB(
                action="status", order_id=order_id, status="problem"
            ).pack()
        )
    )
    return builder.as_markup()


# ============================================================
# BUYURTMALAR RO'YXATI — Holat bo'yicha
# ============================================================

@router.callback_query(OrderAdminCB.filter(F.action == "list"))
async def cb_orders_list(
    callback: CallbackQuery,
    callback_data: OrderAdminCB,
    state: FSMContext
) -> None:
    await state.clear()
    status = callback_data.status
    page   = callback_data.page
    total  = await count_orders_by_status(status)

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
    page   = max(1, min(page, total_pages))
    offset = (page - 1) * ORDERS_PER_PAGE
    orders = await get_orders_by_status(status, offset=offset, limit=ORDERS_PER_PAGE)

    await callback.message.edit_text(
        text=f"📋 *{fmt_status(status)}* ({total} ta)",
        reply_markup=admin_orders_list_kb(
            orders=orders, status=status,
            page=page, total_pages=total_pages
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
    callback_data: OrderAdminCB,
    state: FSMContext
) -> None:
    await state.clear()
    order = await get_order(callback_data.order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return

    items = await get_order_items(callback_data.order_id)
    text  = fmt_order_card(order, items)

    # Yetkazib berish ma'lumotlari (agar kiritilgan bo'lsa)
    d_price = float(order.get("delivery_price") or 0)
    d_time  = order.get("delivery_time") or ""
    if d_price or d_time:
        total = float(order.get("total_price") or 0)
        grand = total + d_price
        text += "\n\n*Yetkazib berish:*"
        if d_price:
            text += (
                f"\n💰 Mahsulotlar: {fmt_price(total)}"
                f"\n🚚 Yetkazish: {fmt_price(d_price)}"
                f"\n💳 Jami: *{fmt_price(grand)}*"
            )
        else:
            text += f"\n🚚 Bepul yetkazish\n💳 Jami: *{fmt_price(float(order.get('total_price') or 0))}*"
        if d_time:
            text += f"\n🕐 Vaqt: {d_time}"

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
# ODDIY HOLAT O'ZGARTIRISH (ship bundan tashqari)
# ============================================================

@router.callback_query(OrderAdminCB.filter(F.action == "status"))
async def cb_order_status(
    callback: CallbackQuery,
    callback_data: OrderAdminCB
) -> None:
    order = await get_order(callback_data.order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return

    new_status = callback_data.status
    await update_order_status(callback_data.order_id, new_status)
    await _notify_user(
        bot=callback.bot,
        user_id=order["user_id"],
        order_code=order["order_code"],
        new_status=new_status
    )
    await callback.answer(f"✅ {fmt_status(new_status)}")

    updated = await get_order(callback_data.order_id)
    items   = await get_order_items(callback_data.order_id)
    await callback.message.edit_text(
        text=fmt_order_card(updated, items),
        reply_markup=admin_order_detail_kb(
            order_id=callback_data.order_id,
            current_status=new_status,
            page=callback_data.page
        ),
        parse_mode="Markdown"
    )


# ============================================================
# YO'LGA CHIQARISH FSM
# confirmed → ship → (narx) → (vaqt) → shipping
# ============================================================

@router.callback_query(OrderAdminCB.filter(F.action == "ship"))
async def cb_ship_start(
    callback: CallbackQuery,
    callback_data: OrderAdminCB,
    state: FSMContext
) -> None:
    order = await get_order(callback_data.order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    if order["status"] != "confirmed":
        await callback.answer(
            f"Holat: {fmt_status(order['status'])} — yo'lga chiqarish mumkin emas.",
            show_alert=True
        )
        return

    await state.update_data(
        ship_order_id=callback_data.order_id,
        ship_page=callback_data.page,
        ship_order=dict(order)
    )
    await state.set_state(ShipOrderState.delivery_price)
    await callback.message.edit_text(
        text=(
            f"🚚 *Buyurtma #{order['order_code']}*\n\n"
            f"💰 Yetkazib berish narxini kiriting (so'mda):\n"
            f"_(0 kiriting = bepul)_"
        ),
        reply_markup=_skip_free_kb(callback_data.order_id, callback_data.page),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ship_free:"))
async def cb_ship_free(callback: CallbackQuery, state: FSMContext) -> None:
    """'Bepul yetkazish' — narx 0, vaqt bosqichiga o'tadi."""
    data = await state.get_data()
    if "ship_order_id" not in data:
        await callback.answer(
            "⏱ Jarayon eskirgan. Buyurtmani qayta oching.",
            show_alert=True
        )
        return

    _, order_id, page = callback.data.split(":")
    await state.update_data(ship_delivery_price=0)
    await state.set_state(ShipOrderState.delivery_time)
    await callback.message.edit_text(
        text=(
            "🕐 Taxminiy yetkazish vaqtini yozing:\n"
            "_(Masalan: Bugun soat 18:00 yoki Ertaga)_"
        ),
        reply_markup=_skip_time_kb(int(order_id), int(page)),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(ShipOrderState.delivery_price, F.text)
async def process_delivery_price(message: Message, state: FSMContext) -> None:
    data     = await state.get_data()
    order_id = data["ship_order_id"]
    page     = data["ship_page"]

    txt = message.text.strip().replace(" ", "").replace(",", "")
    if not txt.isdigit():
        await message.answer(
            "❌ Faqat raqam kiriting. Masalan: 15000",
            reply_markup=_skip_free_kb(order_id, page)
        )
        return
    price = int(txt)
    if price > 10_000_000:
        await message.answer(
            "❌ Narx juda katta. Qaytadan kiriting.",
            reply_markup=_skip_free_kb(order_id, page)
        )
        return

    await state.update_data(ship_delivery_price=price)
    await state.set_state(ShipOrderState.delivery_time)
    await message.answer(
        "🕐 Taxminiy yetkazish vaqtini yozing:\n"
        "_(Masalan: Bugun soat 18:00 yoki Ertaga)_",
        reply_markup=_skip_time_kb(order_id, page),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("ship_notime:"))
async def cb_ship_notime(callback: CallbackQuery, state: FSMContext) -> None:
    """'Vaqtsiz yuborish' — vaqt bo'sh, yakunlaydi."""
    data = await state.get_data()
    if "ship_order_id" not in data:
        await callback.answer(
            "⏱ Jarayon eskirgan. Buyurtmani qayta oching.",
            show_alert=True
        )
        return

    await _finish_ship(state=state, delivery_time="", bot=callback.bot)
    await callback.answer("🚚 Yo'lga chiqdi!")
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.message(ShipOrderState.delivery_time, F.text)
async def process_delivery_time(message: Message, state: FSMContext) -> None:
    await _finish_ship(
        state=state,
        delivery_time=message.text.strip(),
        bot=message.bot
    )
    await message.answer("🚚 Yo'lga chiqdi!")


async def _finish_ship(state: FSMContext, delivery_time: str, bot) -> None:
    """
    DB ga yozadi, holatni 'shipping' ga o'zgartiradi.
    Mijozga: yo'lda + narx + vaqt xabari.
    Adminga: yo'lga chiqdi + [Yetkazildi | Muammo] tugmalari.
    """
    data           = await state.get_data()
    order_id       = data["ship_order_id"]
    order          = data["ship_order"]
    delivery_price = data.get("ship_delivery_price", 0)
    await state.clear()

    # DB ga yozish
    await update_order_status(order_id, "shipping")
    await update_order_delivery(order_id, delivery_price, delivery_time)

    # Narx hisoblash
    total = float(order.get("total_price") or 0)
    grand = total + delivery_price

    # Mijozga: "Buyurtmangiz yo'lda" xabari
    lines = [f"🚚 *Buyurtma #{order['order_code']} yo'lda!*"]
    if delivery_price:
        lines += [
            f"💰 Mahsulotlar: {fmt_price(total)}",
            f"🚚 Yetkazish: {fmt_price(delivery_price)}",
            f"💳 Jami to'lov: *{fmt_price(grand)}*",
        ]
    else:
        lines += [
            "🚚 Yetkazish: *Bepul*",
            f"💳 Jami: *{fmt_price(total)}*",
        ]
    if delivery_time:
        lines.append(f"🕐 Taxminiy vaqt: *{delivery_time}*")

    try:
        await bot.send_message(
            chat_id=order["user_id"],
            text="\n".join(lines),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Mijozga xabar yuborib bo'lmadi: {e}")

    # Mijozga: "Yetib bordimi?" tugmalari
    try:
        await bot.send_message(
            chat_id=order["user_id"],
            text=f"📦 *Buyurtma yetib bordimi?*\n#{order['order_code']}",
            reply_markup=_delivery_confirm_kb(order_id),
            parse_mode="Markdown"
        )
    except Exception:
        pass

    # Adminga: "Yo'lga chiqdi" xabari + Yetkazildi/Muammo tugmalari
    time_text = f"\n🕐 {delivery_time}" if delivery_time else ""
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🚚 Buyurtma *#{order['order_code']}* yo'lga chiqdi.\n"
                f"👤 {order.get('full_name', '—')} | 📱 {order.get('phone', '—')}\n"
                f"💳 {fmt_price(grand)}{time_text}"
            ),
            reply_markup=_admin_ship_kb(order_id),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Adminga xabar yuborib bo'lmadi: {e}")


# ============================================================
# MIJOZ TASDIQLASHI — "Yetib bordimi?"
# ============================================================

@router.callback_query(F.data.startswith("delivery_got:"))
async def cb_delivery_got(callback: CallbackQuery) -> None:
    """Mijoz: 'Ha, oldim!' — yetkazildi deb belgilanadi."""
    order_id = int(callback.data.split(":")[1])
    order    = await get_order(order_id)
    if not order:
        await callback.answer()
        return
    if order["user_id"] != callback.from_user.id:
        await callback.answer("Bu sizning buyurtmangiz emas.", show_alert=True)
        return

    await update_order_status(order_id, "delivered")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer(
        "📦 Rahmat! Xaridingiz uchun minnatdormiz! ✨",
        show_alert=True
    )
    try:
        await callback.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📦 Buyurtma *#{order['order_code']}* yetkazildi! Mijoz tasdiqladi.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Adminga xabar yuborib bo'lmadi: {e}")


@router.callback_query(F.data.startswith("delivery_notgot:"))
async def cb_delivery_notgot(callback: CallbackQuery) -> None:
    """Mijoz: 'Hali olmadim' — adminga xabar yuboriladi."""
    order_id = int(callback.data.split(":")[1])
    order    = await get_order(order_id)
    if not order:
        await callback.answer()
        return
    if order["user_id"] != callback.from_user.id:
        await callback.answer("Bu sizning buyurtmangiz emas.", show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("⚠️ Sotuvchiga xabar berildi.", show_alert=True)
    try:
        await callback.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"⚠️ Buyurtma *#{order['order_code']}* — mijoz hali olmagan!\n"
                f"📱 {order.get('phone', '—')}"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Adminga xabar yuborib bo'lmadi: {e}")


# ============================================================
# FOYDALANUVCHIGA HOLAT XABARI
# ============================================================

async def _notify_user(
    bot,
    user_id: int,
    order_code: str,
    new_status: str
) -> None:
    status_messages = {
        "confirmed": "✅ Buyurtmangiz tasdiqlandi va tayyorlanmoqda!",
        "delivered": "📦 Buyurtmangiz yetkazildi!\n\nRahmat! 🙏",
        "cancelled": "❌ Buyurtmangiz bekor qilindi.\nSavollar uchun admin bilan bog'laning.",
        "problem":   "⚠️ Buyurtmangizda muammo bor.\nAdmin tez orada siz bilan bog'lanadi.",
    }
    message_text = status_messages.get(new_status)
    if not message_text:
        return
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"🔔 *#{order_code} buyurtma holati o'zgardi*\n\n"
                f"{message_text}\n\n"
                f"{fmt_order_progress(new_status)}"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Foydalanuvchi {user_id} ga xabar yuborib bo'lmadi: {e}")
