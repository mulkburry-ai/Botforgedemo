# ============================================================
# BOTFORGE — handlers/cart.py
# Savat va buyurtma berish jarayoni (3 qadam)
# ============================================================

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_ID
from db import (
    get_cart, sync_cart_with_stock, add_to_cart, remove_from_cart,
    clear_cart, get_cart_total, create_order,
    get_user, get_product, get_available_stock, get_setting,
    save_phone, get_order, get_order_items,
)
from keyboards import (
    ProductCB, CartCB,
    cart_kb, checkout_confirm_kb,
    order_final_confirm_kb, phone_kb, main_menu_kb,
    admin_order_detail_kb,
)
from utils import fmt_cart, fmt_order_card, fmt_price

logger = logging.getLogger(__name__)
router = Router()


# ============================================================
# FSM HOLATLARI — Buyurtma berish 3 qadam
# ============================================================

class OrderState(StatesGroup):
    waiting_phone   = State()   # 1. Telefon raqami
    waiting_address = State()   # 2. Manzil
    waiting_confirm = State()   # 3. Tasdiqlash


# ============================================================
# SAVAT KO'RSATISH
# ============================================================

@router.message(F.text == "🧺 Savat")
async def show_cart(message: Message, state: FSMContext) -> None:
    """
    Foydalanuvchi savatini ko'rsatish.
    Ko'rsatishdan oldin stok bilan solishtiriladi — agar biror
    narsa tugagan yoki kamaygan bo'lsa, avtomatik to'g'irlanadi va
    mijozga ogohlantiriladi (Burry taklifi).
    """
    await state.clear()
    user_id = message.from_user.id

    changes = await sync_cart_with_stock(user_id)
    if changes:
        await message.answer(_fmt_stock_changes(changes), parse_mode="Markdown")

    items = await get_cart(user_id)

    if not items:
        await message.answer(
            "🧺 Savatingiz bo'sh.\n\nMahsulot qo'shish uchun Katalogga o'ting.",
            reply_markup=main_menu_kb()
        )
        return

    totals = await get_cart_total(user_id)
    text = fmt_cart(items, totals["total"])

    await message.answer(
        text=text,
        reply_markup=cart_kb(items),
        parse_mode="Markdown"
    )


def _fmt_stock_changes(changes: list) -> str:
    """Savatdagi avtomatik o'zgarishlar haqida ogohlantirish matni."""
    lines = ["⚠️ *Diqqat! Savatingizda o'zgarish bo'ldi:*\n"]
    for c in changes:
        if c["type"] == "removed":
            lines.append(f"❌ *{c['name']}* — tugab qolgani uchun savatdan olib tashlandi")
        else:
            lines.append(
                f"⚠️ *{c['name']}* — endi faqat {c['new_qty']} dona bor "
                f"(oldin {c['old_qty']} ta edi), savatingiz yangilandi"
            )
    return "\n".join(lines)


# ============================================================
# SAVATGA QO'SHISH
# ============================================================

@router.callback_query(ProductCB.filter(F.action == "cart"))
async def cb_add_to_cart(
    callback: CallbackQuery,
    callback_data: ProductCB
) -> None:
    """
    Miqdor tanlash ekranida "🛒 Savatga solish" bosilganda —
    yakuniy, real-vaqtdagi stok tekshiruvidan keyin savatga qo'shiladi.

    Diqqat: bu yerga kelguncha mijoz allaqachon tur (kerak bo'lsa) va
    miqdorni tanlagan (qty_start/variant_pick/qty orqali). Shu sababli
    bu funksiya faqat YAKUNIY xavfsizlik tekshiruvini bajaradi — chunki
    mijoz ekranda turgan payt boshqa birov sotib olgan bo'lishi mumkin.
    """
    user_id = callback.from_user.id
    product_id = callback_data.product_id
    variant_id = callback_data.variant_id or None
    qty = max(1, callback_data.qty)

    product = await get_product(product_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    # Yakuniy, real-vaqtdagi stok tekshiruvi
    available = await get_available_stock(product_id, variant_id)
    if available <= 0:
        await callback.answer("😔 Bu mahsulot/tur tugab qoldi.", show_alert=True)
        return

    final_qty = min(qty, available)

    await add_to_cart(user_id, product_id, variant_id, final_qty)

    if final_qty < qty:
        await callback.answer(
            f"⚠️ Faqat {final_qty} dona bor edi — shuncha qo'shildi.",
            show_alert=True
        )
    else:
        await callback.answer(f"✅ {final_qty} dona savatga qo'shildi!")


# ============================================================
# SAVATDAN O'CHIRISH
# ============================================================

@router.callback_query(CartCB.filter(F.action == "remove"))
async def cb_remove_from_cart(
    callback: CallbackQuery,
    callback_data: CartCB
) -> None:
    """Savatdan bitta mahsulotni o'chirish."""
    await remove_from_cart(callback_data.cart_id)

    user_id = callback.from_user.id
    items = await get_cart(user_id)

    if not items:
        await callback.message.edit_text(
            text="🧺 Savat bo'shadi.",
            reply_markup=None
        )
        await callback.answer()
        return

    totals = await get_cart_total(user_id)
    await callback.message.edit_text(
        text=fmt_cart(items, totals["total"]),
        reply_markup=cart_kb(items),
        parse_mode="Markdown"
    )
    await callback.answer("🗑 O'chirildi")


@router.callback_query(CartCB.filter(F.action == "clear"))
async def cb_clear_cart(
    callback: CallbackQuery,
    callback_data: CartCB
) -> None:
    """Savatni to'liq tozalash."""
    await clear_cart(callback.from_user.id)
    await callback.message.edit_text(
        text="🧺 Savat tozalandi.",
        reply_markup=None
    )
    await callback.answer()


# ============================================================
# BUYURTMA BERISH — 1-QADAM: TELEFON
# ============================================================

@router.callback_query(CartCB.filter(F.action == "checkout"))
async def cb_checkout(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """
    Buyurtma berish boshlanadi.
    Foydalanuvchining saqlangan telefon raqami bo'lsa
    tasdiqlanadi, yo'q bo'lsa kiritish so'raladi.
    """
    user_id = callback.from_user.id

    # Yakuniy tekshiruv — checkout boshlanishidan oldin savat qayta
    # sinxronlanadi (Burry talabi: har doim eng so'nggi stok bilan ishlash)
    changes = await sync_cart_with_stock(user_id)
    if changes:
        await callback.message.answer(
            _fmt_stock_changes(changes), parse_mode="Markdown"
        )

    items = await get_cart(user_id)

    if not items:
        await callback.answer(
            "Savat bo'sh qoldi — mahsulotlar tugab qolgan edi.",
            show_alert=True
        )
        return

    # Minimal buyurtma summasi tekshirish
    min_sum = int(await get_setting("min_order_sum", "0"))
    totals = await get_cart_total(user_id)
    if min_sum > 0 and totals["total"] < min_sum:
        await callback.answer(
            f"Minimal buyurtma summasi: {fmt_price(min_sum)}",
            show_alert=True
        )
        return

    # Saqlangan telefon borligini tekshirish
    user = await get_user(user_id)
    saved_phone = user.get("phone") if user else None

    if saved_phone:
        await state.set_state(OrderState.waiting_phone)
        await state.update_data(phone=saved_phone)
        await callback.message.edit_text(
            text=f"📱 Telefon raqam:\n*{saved_phone}*\n\nShu raqamdan buyurtma berasizmi?",
            reply_markup=checkout_confirm_kb(use_saved_phone=True),
            parse_mode="Markdown"
        )
    else:
        await state.set_state(OrderState.waiting_phone)
        await callback.message.edit_text(
            text="📱 Telefon raqamingizni yuboring:",
            reply_markup=checkout_confirm_kb(use_saved_phone=False),
        )
        # Telefon tugmasi ko'rsatiladi
        await callback.message.answer(
            text="👇",
            reply_markup=phone_kb()
        )

    await callback.answer()


@router.callback_query(CartCB.filter(F.action == "phone_confirm"))
async def cb_phone_confirm(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Saqlangan telefon raqamini tasdiqlash."""
    await state.set_state(OrderState.waiting_address)
    await callback.message.edit_text(
        text="📍 Yetkazib berish manzilini yozing:",
        reply_markup=None
    )
    await callback.answer()


@router.callback_query(CartCB.filter(F.action == "phone_change"))
async def cb_phone_change(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Boshqa telefon raqami kiritish."""
    await callback.message.edit_text(
        text="📱 Yangi telefon raqamingizni yuboring:",
        reply_markup=None
    )
    await callback.message.answer("👇", reply_markup=phone_kb())
    await callback.answer()


@router.message(OrderState.waiting_phone, F.contact)
async def process_phone_contact(
    message: Message,
    state: FSMContext
) -> None:
    """Kontakt orqali yuborilgan telefon raqamini qabul qilish."""
    from utils import validate_phone
    phone, error = validate_phone(message.contact.phone_number)
    if error:
        await message.answer(error)
        return

    await state.update_data(phone=phone)
    await state.set_state(OrderState.waiting_address)
    await message.answer(
        text=f"✅ Raqam qabul qilindi: *{phone}*\n\n📍 Yetkazib berish manzilini yozing:",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )


@router.message(OrderState.waiting_phone, F.text)
async def process_phone_text(
    message: Message,
    state: FSMContext
) -> None:
    """Matn orqali yozilgan telefon raqamini qabul qilish."""
    from utils import validate_phone
    phone, error = validate_phone(message.text)
    if error:
        await message.answer(error)
        return

    await state.update_data(phone=phone)
    await state.set_state(OrderState.waiting_address)
    await message.answer(
        text=f"✅ Raqam qabul qilindi: *{phone}*\n\n📍 Yetkazib berish manzilini yozing:",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )


# ============================================================
# 2-QADAM: MANZIL
# ============================================================

@router.message(OrderState.waiting_address, F.text)
async def process_address(
    message: Message,
    state: FSMContext
) -> None:
    """Manzilni qabul qilish va tasdiqlash sahifasini ko'rsatish."""
    address = message.text.strip()

    if len(address) < 5:
        await message.answer(
            "❌ Manzil juda qisqa. Aniqroq yozing.\n"
            "Misol: Toshkent, Chilonzor, 7-kvartal, 15-uy"
        )
        return

    await state.update_data(address=address)
    await state.set_state(OrderState.waiting_confirm)

    # Buyurtma ma'lumotlarini ko'rsatish
    user_id = message.from_user.id
    data = await state.get_data()
    items = await get_cart(user_id)
    totals = await get_cart_total(user_id)

    summary = fmt_cart(items, totals["total"])
    summary += f"\n\n📍 Manzil: *{address}*\n📱 Telefon: *{data['phone']}*"

    await message.answer(
        text=f"{summary}\n\n✅ Buyurtmani tasdiqlaysizmi?",
        reply_markup=order_final_confirm_kb(),
        parse_mode="Markdown"
    )


# ============================================================
# 3-QADAM: TASDIQLASH
# ============================================================

@router.callback_query(CartCB.filter(F.action == "confirm"))
async def cb_order_confirm(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """
    Buyurtmani yakunlash.
    1. Bazaga yoziladi
    2. Foydalanuvchiga tasdiqlash xabari
    3. Adminga yangi buyurtma xabari
    4. Telefon raqami saqlanadi
    """
    user_id = callback.from_user.id
    data = await state.get_data()
    await state.clear()

    totals = await get_cart_total(user_id)

    try:
        order = await create_order(
            user_id=user_id,
            total_price=totals["total"],
            address=data["address"],
            phone=data["phone"],
        )
    except ValueError:
        await callback.answer("Savat bo'sh", show_alert=True)
        return

    # Telefon raqamini saqlaymiz
    await save_phone(user_id, data["phone"])

    order_code = order["order_code"]

    # Foydalanuvchiga xabar
    await callback.message.edit_text(
        text=(
            f"✅ *Buyurtma qabul qilindi!*\n\n"
            f"🧾 Buyurtma raqami: *#{order_code}*\n"
            f"💳 Summa: *{fmt_price(totals['total'])}*\n\n"
            f"📦 Buyurtmangiz holati 'Buyurtmalarim' bo'limida ko'rinadi."
        ),
        reply_markup=None,
        parse_mode="Markdown"
    )

    # Adminga xabar
    full_order = await get_order(order["id"])
    items = await get_order_items(order["id"])

    admin_text = (
        f"🔔 *Yangi buyurtma!*\n\n"
        f"{fmt_order_card(full_order, items)}"
    )

    try:
        bot: Bot = callback.bot
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=admin_order_detail_kb(
                order_id=order["id"],
                current_status="pending"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Adminga xabar yuborishda xato: {e}")

    await callback.answer()


@router.callback_query(CartCB.filter(F.action == "back"))
async def cb_order_cancel(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Buyurtma jarayonini bekor qilish — savatga qaytish."""
    await state.clear()
    user_id = callback.from_user.id
    items = await get_cart(user_id)

    if not items:
        await callback.message.edit_text("🧺 Savat bo'sh.", reply_markup=None)
        await callback.answer()
        return

    totals = await get_cart_total(user_id)
    await callback.message.edit_text(
        text=fmt_cart(items, totals["total"]),
        reply_markup=cart_kb(items),
        parse_mode="Markdown"
    )
    await callback.answer()
