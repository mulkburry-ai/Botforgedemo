# ============================================================
# BOTFORGE — handlers/admin/products.py
# Mahsulot boshqaruvi — qo'shish, tahrirlash, o'chirish,
# chegirma, stok, kategoriyalar
# ============================================================

import logging
from aiogram import Router, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_ID
from db import (
    get_all_products_admin, count_products_admin,
    get_product, get_variants, add_product, update_product,
    soft_delete_product, add_variant, update_stock,
    get_all_categories, add_category, delete_category,
    deactivate_discount, get_setting, search_products,
)
from keyboards import (
    AdminCB, ProductAdminCB,
    products_menu_kb, products_list_kb as admin_products_list_kb,
    product_detail_kb, confirm_delete_kb,
    back_to_main_kb,
)
from utils import (
    fmt_product_admin,
    validate_name, validate_price, validate_stock,
    validate_discount, validate_discount_duration,
)

logger = logging.getLogger(__name__)
router = Router()

PRODUCTS_PER_PAGE = 10


# ============================================================
# FSM HOLATLARI
# ============================================================

class AddProductState(StatesGroup):
    category    = State()   # Kategoriya tanlash
    name        = State()   # Nom
    price       = State()   # Narx
    description = State()   # Tavsif (ixtiyoriy)
    photo       = State()   # Rasm (ixtiyoriy)
    stock       = State()   # Stok miqdori


class EditProductState(StatesGroup):
    choose_field = State()  # Qaysi maydonni o'zgartirish
    new_value    = State()  # Yangi qiymat


class DiscountState(StatesGroup):
    choose_product = State()  # Mahsulot ID
    value          = State()  # Chegirma qiymati
    duration       = State()  # Vaqt (soat)


class StockState(StatesGroup):
    choose_product = State()  # Mahsulot ID
    new_qty        = State()  # Yangi miqdor


class CategoryState(StatesGroup):
    name       = State()  # Kategoriya nomi
    parent     = State()  # Ota-kategoriya (ixtiyoriy)


class SearchState(StatesGroup):
    query = State()  # Qidiruv so'zi


# ============================================================
# MAHSULOTLAR BO'LIMI MENYUSI
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "menu"))
async def cb_products_menu(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    await state.clear()
    await callback.message.edit_text(
        text="📦 *Mahsulotlar boshqaruvi*\nNimani qilmoqchisiz?",
        reply_markup=products_menu_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# MAHSULOTLAR RO'YXATI
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "list"))
async def cb_products_list(
    callback: CallbackQuery,
    callback_data: ProductAdminCB,
    state: FSMContext
) -> None:
    """Mahsulotlar ro'yxati — pagination bilan."""
    await state.clear()
    page = callback_data.page
    total = await count_products_admin()

    if total == 0:
        await callback.message.edit_text(
            text="📭 Hozircha mahsulotlar yo'q.\n\n➕ Qo'shish tugmasini bosing.",
            reply_markup=products_menu_kb(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    total_pages = max(1, (total + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * PRODUCTS_PER_PAGE
    products = await get_all_products_admin(offset=offset, limit=PRODUCTS_PER_PAGE)

    await callback.message.edit_text(
        text=f"📦 *Mahsulotlar ro'yxati* ({total} ta)",
        reply_markup=admin_products_list_kb(
            products=products,
            page=page,
            total_pages=total_pages
        ),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# MAHSULOT DETAIL (ADMIN)
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "edit"))
async def cb_product_detail(
    callback: CallbackQuery,
    callback_data: ProductAdminCB,
    state: FSMContext
) -> None:
    """Mahsulot detail sahifasi — barcha amallar."""
    await state.clear()
    product = await get_product(callback_data.product_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    variants = await get_variants(callback_data.product_id)
    text = fmt_product_admin(product)

    if variants:
        text += "\n\n*Turlar:*"
        for v in variants:
            stock_icon = "🚫" if v["stock_qty"] == 0 else "✅"
            price = f"{int(v['price']):,} so'm" if v.get("price") else "asosiy narx"
            text += f"\n{stock_icon} {v['name']} — {price} — {v['stock_qty']} dona"

    await callback.message.edit_text(
        text=text,
        reply_markup=product_detail_kb(
            product_id=callback_data.product_id,
            is_active=product["is_active"],
            page=callback_data.page
        ),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# MAHSULOT QO'SHISH — FSM
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "add"))
async def cb_add_product_start(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Mahsulot qo'shish jarayonini boshlash."""
    categories = await get_all_categories()

    if not categories:
        await callback.answer(
            "Avval kategoriya qo'shing!",
            show_alert=True
        )
        return

    # Kategoriyalar ro'yxatini ko'rsatish
    lines = ["📂 *Kategoriyani tanlang:*\n"]
    for cat in categories:
        prefix = "  └ " if cat["parent_id"] else ""
        lines.append(f"`{cat['id']}` — {prefix}{cat['name']}")

    await state.set_state(AddProductState.category)
    await callback.message.edit_text(
        text="\n".join(lines) + "\n\nKategoriya ID sini yozing:",
        reply_markup=None,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(AddProductState.category, F.text)
async def add_product_category(message: Message, state: FSMContext) -> None:
    try:
        cat_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")
        return

    await state.update_data(category_id=cat_id)
    await state.set_state(AddProductState.name)
    await message.answer("📝 Mahsulot nomini yozing:")


@router.message(AddProductState.name, F.text)
async def add_product_name(message: Message, state: FSMContext) -> None:
    name, error = validate_name(message.text)
    if error:
        await message.answer(error)
        return

    await state.update_data(name=name)
    await state.set_state(AddProductState.price)
    await message.answer("💰 Narxini yozing (so'mda):\nMisol: 85000")


@router.message(AddProductState.price, F.text)
async def add_product_price(message: Message, state: FSMContext) -> None:
    price, error = validate_price(message.text)
    if error:
        await message.answer(error)
        return

    await state.update_data(price=price)
    await state.set_state(AddProductState.description)
    await message.answer(
        "📋 Tavsif yozing (ixtiyoriy):\n"
        "Yo'q bo'lsa — /skip yozing"
    )


@router.message(AddProductState.description, F.text)
async def add_product_description(message: Message, state: FSMContext) -> None:
    desc = "" if message.text.strip() == "/skip" else message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(AddProductState.photo)
    await message.answer(
        "🖼 Rasm yuboring (ixtiyoriy):\n"
        "Yo'q bo'lsa — /skip yozing"
    )


@router.message(AddProductState.photo, F.photo)
async def add_product_photo(message: Message, state: FSMContext) -> None:
    # Eng yuqori sifatli rasm — ro'yxatning oxirgi elementi
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await state.set_state(AddProductState.stock)
    await message.answer("📦 Stok miqdorini yozing:\nMisol: 50")


@router.message(AddProductState.photo, F.text)
async def add_product_photo_skip(message: Message, state: FSMContext) -> None:
    if message.text.strip() != "/skip":
        await message.answer("📸 Rasm yuboring yoki /skip yozing.")
        return

    await state.update_data(photo_id=None)
    await state.set_state(AddProductState.stock)
    await message.answer("📦 Stok miqdorini yozing:\nMisol: 50")


@router.message(AddProductState.stock, F.text)
async def add_product_stock(message: Message, state: FSMContext) -> None:
    """Oxirgi qadam — mahsulotni bazaga yozish."""
    qty, error = validate_stock(message.text)
    if error:
        await message.answer(error)
        return

    data = await state.get_data()
    await state.clear()

    product_id = await add_product({
        "category_id": data["category_id"],
        "name":        data["name"],
        "price":       data["price"],
        "description": data.get("description", ""),
        "photo_id":    data.get("photo_id"),
        "stock_qty":   qty,
        "is_active":   True,
    })

    await message.answer(
        f"✅ *Mahsulot qo'shildi!*\n\n"
        f"🆔 `#{product_id}`\n"
        f"📝 {data['name']}\n"
        f"💰 {int(data['price']):,} so'm\n"
        f"📦 Stok: {qty} dona",
        parse_mode="Markdown"
    )


# ============================================================
# MAHSULOT TAHRIRLASH — FSM
# ============================================================

EDIT_FIELDS = {
    "name":        "📝 Yangi nomni yozing:",
    "price":       "💰 Yangi narxni yozing (so'mda):",
    "description": "📋 Yangi tavsifni yozing:",
    "photo":       "🖼 Yangi rasmni yuboring:",
    "stock":       "📦 Yangi stok miqdorini yozing:",
    "category":    "📂 Yangi kategoriya ID sini yozing:",
}


@router.callback_query(ProductAdminCB.filter(F.action == "edit_field"))
async def cb_edit_field_start(
    callback: CallbackQuery,
    callback_data: ProductAdminCB,
    state: FSMContext
) -> None:
    """Tahrirlash — qaysi maydonni o'zgartirish."""
    product_id = callback_data.product_id
    builder = InlineKeyboardBuilder()

    fields = [
        ("name", "📝 Nom"), ("price", "💰 Narx"),
        ("description", "📋 Tavsif"), ("photo", "🖼 Rasm"),
        ("stock", "📦 Stok"), ("category", "📂 Kategoriya"),
    ]
    for field, label in fields:
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"edit_field:{product_id}:{field}"
        ))
    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data=ProductAdminCB(
            action="edit", product_id=product_id
        ).pack()
    ))

    await state.update_data(product_id=product_id, page=callback_data.page)
    await callback.message.edit_text(
        text="✏️ *Qaysi maydonni o'zgartirmoqchisiz?*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"))
async def cb_edit_field_choose(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    _, product_id, field = callback.data.split(":")
    await state.update_data(
        product_id=int(product_id),
        edit_field=field
    )
    await state.set_state(EditProductState.new_value)
    await callback.message.edit_text(
        text=EDIT_FIELDS.get(field, "Yangi qiymatni yozing:"),
        reply_markup=None,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(EditProductState.new_value)
async def process_edit_value(message: Message, state: FSMContext) -> None:
    """Yangi qiymatni qabul qilish va bazaga yozish."""
    data = await state.get_data()
    field = data["edit_field"]
    product_id = data["product_id"]

    update_data = {}

    if field == "name":
        value, error = validate_name(message.text)
        if error:
            await message.answer(error)
            return
        update_data["name"] = value

    elif field == "price":
        value, error = validate_price(message.text)
        if error:
            await message.answer(error)
            return
        update_data["price"] = value

    elif field == "description":
        update_data["description"] = message.text.strip()

    elif field == "photo":
        if not message.photo:
            await message.answer("❌ Rasm yuboring.")
            return
        update_data["photo_id"] = message.photo[-1].file_id

    elif field == "stock":
        value, error = validate_stock(message.text)
        if error:
            await message.answer(error)
            return
        update_data["stock_qty"] = value

    elif field == "category":
        try:
            update_data["category_id"] = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Faqat raqam kiriting.")
            return

    await update_product(product_id, update_data)
    await state.clear()
    await message.answer(f"✅ Mahsulot #{product_id} yangilandi!")


# ============================================================
# MAHSULOTNI O'CHIRISH
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "delete"))
async def cb_delete_confirm(
    callback: CallbackQuery,
    callback_data: ProductAdminCB
) -> None:
    """O'chirishni tasdiqlash so'rash."""
    product = await get_product(callback_data.product_id)
    if not product:
        await callback.answer("Topilmadi", show_alert=True)
        return

    await callback.message.edit_text(
        text=(
            f"⚠️ *Rostdan ham o'chirasizmi?*\n\n"
            f"#{product['id']} — {product['name']}\n\n"
            f"_Mahsulot ko'rinmay qoladi, lekin eski buyurtmalarda saqlanadi._"
        ),
        reply_markup=confirm_delete_kb(
            product_id=callback_data.product_id,
            page=callback_data.page
        ),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(ProductAdminCB.filter(F.action == "delete_confirm"))
async def cb_delete_execute(
    callback: CallbackQuery,
    callback_data: ProductAdminCB
) -> None:
    """Mahsulotni soft delete qilish."""
    await soft_delete_product(callback_data.product_id)
    await callback.message.edit_text(
        text=f"✅ Mahsulot #{callback_data.product_id} o'chirildi.",
        reply_markup=back_to_main_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# FAOL / NOFAOL TOGGLE
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "toggle"))
async def cb_toggle_active(
    callback: CallbackQuery,
    callback_data: ProductAdminCB
) -> None:
    """Mahsulotni faol/nofaol qilish."""
    product = await get_product(callback_data.product_id)
    if not product:
        await callback.answer("Topilmadi", show_alert=True)
        return

    new_status = not product["is_active"]
    await update_product(callback_data.product_id, {"is_active": new_status})

    status_text = "faol" if new_status else "nofaol"
    await callback.answer(f"✅ Mahsulot {status_text} qilindi")

    # Kartani yangilash
    updated = await get_product(callback_data.product_id)
    await callback.message.edit_text(
        text=fmt_product_admin(updated),
        reply_markup=product_detail_kb(
            product_id=callback_data.product_id,
            is_active=new_status,
            page=callback_data.page
        ),
        parse_mode="Markdown"
    )


# ============================================================
# CHEGIRMA BELGILASH — FSM
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "discount"))
async def cb_discount_start(
    callback: CallbackQuery,
    callback_data: ProductAdminCB,
    state: FSMContext
) -> None:
    """Chegirma belgilash — mahsulot ID so'rash."""
    if callback_data.product_id:
        # Mahsulot detail dan kelgan — ID allaqachon bor
        await state.update_data(product_id=callback_data.product_id)
        await state.set_state(DiscountState.value)
        await callback.message.edit_text(
            text=(
                "🏷 *Chegirma qiymatini yozing:*\n\n"
                "• 30 dan kam → foiz (%)\n"
                "  Misol: `30` → 30% chegirma\n\n"
                "• 100 va undan ko'p → aniq narx\n"
                "  Misol: `45000` → chegirma narxi 45,000 so'm"
            ),
            reply_markup=None,
            parse_mode="Markdown"
        )
    else:
        await state.set_state(DiscountState.choose_product)
        await callback.message.edit_text(
            text="🏷 *Chegirma belgilash*\n\nMahsulot ID sini yozing:",
            reply_markup=None,
            parse_mode="Markdown"
        )
    await callback.answer()


@router.message(DiscountState.choose_product, F.text)
async def discount_choose_product(message: Message, state: FSMContext) -> None:
    try:
        product_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")
        return

    product = await get_product(product_id)
    if not product:
        await message.answer("❌ Mahsulot topilmadi. ID ni tekshiring.")
        return

    await state.update_data(product_id=product_id)
    await state.set_state(DiscountState.value)
    await message.answer(
        f"✅ *{product['name']}* tanlandi.\n\n"
        "🏷 Chegirma qiymatini yozing:\n"
        "• 30 dan kam → foiz (%): `30`\n"
        "• 100 va undan ko'p → narx: `45000`",
        parse_mode="Markdown"
    )


@router.message(DiscountState.value, F.text)
async def discount_value(message: Message, state: FSMContext) -> None:
    value, dtype, error = validate_discount(message.text)
    if error:
        await message.answer(error)
        return

    await state.update_data(discount_value=value, discount_type=dtype)
    await state.set_state(DiscountState.duration)
    await message.answer(
        "⏰ *Qancha vaqt amal qilsin?*\n\n"
        "• Soat kiriting: `24` (24 soat)\n"
        "• Daqiqa: `30m` (30 daqiqa)\n"
        "• Doimiy bo'lsa: /skip",
        parse_mode="Markdown"
    )


@router.message(DiscountState.duration, F.text)
async def discount_duration(message: Message, state: FSMContext) -> None:
    """Chegirmani bazaga yozish."""
    data = await state.get_data()
    await state.clear()

    until = None
    if message.text.strip() != "/skip":
        until, error = validate_discount_duration(message.text)
        if error:
            await message.answer(error)
            return

    await update_product(data["product_id"], {
        "discount_value":  data["discount_value"],
        "discount_type":   data["discount_type"],
        "discount_until":  until,
        "discount_active": True,
    })

    dtype_text = "%" if data["discount_type"] == "percent" else "so'm"
    duration_text = "Doimiy" if not until else f"{message.text.strip()} ga"

    await message.answer(
        f"✅ *Chegirma belgilandi!*\n\n"
        f"🆔 #{data['product_id']}\n"
        f"🏷 {data['discount_value']} {dtype_text}\n"
        f"⏰ {duration_text}",
        parse_mode="Markdown"
    )


# ============================================================
# STOK YANGILASH — FSM
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "stock"))
async def cb_stock_start(
    callback: CallbackQuery,
    callback_data: ProductAdminCB,
    state: FSMContext
) -> None:
    if callback_data.product_id:
        await state.update_data(product_id=callback_data.product_id)
        await state.set_state(StockState.new_qty)
        product = await get_product(callback_data.product_id)
        await callback.message.edit_text(
            text=(
                f"📦 *Stok yangilash*\n\n"
                f"*{product['name']}*\n"
                f"Hozirgi stok: {product['stock_qty']} dona\n\n"
                f"Yangi miqdorni yozing:"
            ),
            reply_markup=None,
            parse_mode="Markdown"
        )
    else:
        await state.set_state(StockState.choose_product)
        await callback.message.edit_text(
            text="📦 *Stok yangilash*\n\nMahsulot ID sini yozing:",
            reply_markup=None,
            parse_mode="Markdown"
        )
    await callback.answer()


@router.message(StockState.choose_product, F.text)
async def stock_choose_product(message: Message, state: FSMContext) -> None:
    try:
        product_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")
        return

    product = await get_product(product_id)
    if not product:
        await message.answer("❌ Mahsulot topilmadi.")
        return

    await state.update_data(product_id=product_id)
    await state.set_state(StockState.new_qty)
    await message.answer(
        f"*{product['name']}*\n"
        f"Hozirgi stok: {product['stock_qty']} dona\n\n"
        f"Yangi miqdorni yozing:",
        parse_mode="Markdown"
    )


@router.message(StockState.new_qty, F.text)
async def stock_new_qty(message: Message, state: FSMContext) -> None:
    qty, error = validate_stock(message.text)
    if error:
        await message.answer(error)
        return

    data = await state.get_data()
    await state.clear()

    product = await get_product(data["product_id"])
    old_qty = product["stock_qty"]
    delta = qty - old_qty

    await update_stock(data["product_id"], delta)
    await message.answer(
        f"✅ Stok yangilandi!\n"
        f"📦 {old_qty} → *{qty}* dona",
        parse_mode="Markdown"
    )


# ============================================================
# QIDIRISH — FSM
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "search"))
async def cb_search_start(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    await state.set_state(SearchState.query)
    await callback.message.edit_text(
        text="🔍 *Mahsulot qidirish*\n\nNomini yoki ID sini yozing:",
        reply_markup=None,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(SearchState.query, F.text)
async def search_products_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    query = message.text.strip()

    # ID bo'yicha qidirish
    if query.isdigit():
        product = await get_product(int(query))
        products = [product] if product else []
    else:
        products = await search_products(query)

    if not products:
        await message.answer("🔍 Hech narsa topilmadi.")
        return

    lines = [f"🔍 *'{query}' bo'yicha natijalar:*\n"]
    for p in products:
        icon = "✅" if p["is_active"] else "🔴"
        lines.append(f"{icon} `#{p['id']}` — {p['name']} — {int(p['price']):,} so'm")

    await message.answer("\n".join(lines), parse_mode="Markdown")


# ============================================================
# KATEGORIYALAR BOSHQARUVI
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "categories"))
async def cb_categories(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Kategoriyalar ro'yxati va boshqaruv."""
    await state.clear()
    categories = await get_all_categories()

    lines = ["🗂 *Kategoriyalar:*\n"]
    for cat in categories:
        prefix = "  └ " if cat["parent_id"] else ""
        active = "" if cat["is_active"] else " 🔴"
        lines.append(f"`{cat['id']}` — {prefix}{cat['name']}{active}")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="➕ Kategoriya qo'shish",
            callback_data=ProductAdminCB(action="cat_add").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🗑 Kategoriya o'chirish",
            callback_data=ProductAdminCB(action="cat_delete").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data=AdminCB(section="products").pack()
        )
    )

    await callback.message.edit_text(
        text="\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(ProductAdminCB.filter(F.action == "cat_add"))
async def cb_cat_add_start(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    await state.set_state(CategoryState.name)
    await callback.message.edit_text(
        text=(
            "➕ *Yangi kategoriya*\n\n"
            "Kategoriya nomini yozing:\n"
            "_(Subkategoriya bo'lsa keyingi qadamda ota-kategoriyani ko'rsatasiz)_"
        ),
        reply_markup=None,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(CategoryState.name, F.text)
async def cat_add_name(message: Message, state: FSMContext) -> None:
    name, error = validate_name(message.text, max_len=64)
    if error:
        await message.answer(error)
        return

    await state.update_data(cat_name=name)
    await state.set_state(CategoryState.parent)

    categories = await get_all_categories()
    main_cats = [c for c in categories if not c["parent_id"]]

    if main_cats:
        lines = ["📂 *Ota-kategoriya tanlang* (ixtiyoriy):\n"]
        for c in main_cats:
            lines.append(f"`{c['id']}` — {c['name']}")
        lines.append("\nAgar asosiy kategoriya bo'lsa — /skip yozing")
        await message.answer("\n".join(lines), parse_mode="Markdown")
    else:
        await message.answer(
            "Ota-kategoriya yo'q.\nAsosiy kategoriya sifatida qo'shiladi.\n/skip yozing:"
        )


@router.message(CategoryState.parent, F.text)
async def cat_add_parent(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    parent_id = None
    if message.text.strip() != "/skip":
        try:
            parent_id = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Faqat raqam yoki /skip yozing.")
            return

    cat_id = await add_category(data["cat_name"], parent_id)
    cat_type = "subkategoriya" if parent_id else "kategoriya"
    await message.answer(
        f"✅ Yangi {cat_type} qo'shildi!\n"
        f"🆔 `{cat_id}` — {data['cat_name']}",
        parse_mode="Markdown"
    )


@router.callback_query(ProductAdminCB.filter(F.action == "cat_delete"))
async def cb_cat_delete_start(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    await callback.message.edit_text(
        text=(
            "🗑 *Kategoriya o'chirish*\n\n"
            "Kategoriya ID sini yozing:\n\n"
            "_Diqqat: Ichida mahsulot yoki subkategoriya bo'lsa o'chirilmaydi._"
        ),
        reply_markup=None,
        parse_mode="Markdown"
    )
    # Bu yerda FSM kerak emas — to'g'ri message handler bor
    await callback.answer()

