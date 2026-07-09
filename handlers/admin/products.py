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

from db import (
    get_all_products_admin, count_products_admin,
    get_product, add_product, update_product,
    soft_delete_product, add_variant, update_stock,
    get_all_categories, add_category, delete_category,
    search_products, get_effective_stock, get_available_stock,
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
# YORDAMCHI — Bekor qilish tugmasi
# Har bir FSM bosqichida ko'rsatiladi, admin istalgan payt
# jarayonni to'xtatib chiqa olishi uchun.
# ============================================================

def _cancel_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="admin_cancel_fsm"
    ))
    return builder.as_markup()


@router.callback_query(F.data == "admin_cancel_fsm")
async def cb_cancel_fsm(callback: CallbackQuery, state: FSMContext) -> None:
    """Istalgan FSM jarayonini bekor qilib, mahsulotlar menyusiga qaytaradi."""
    await state.clear()
    await callback.message.edit_text(
        text="❌ Bekor qilindi.",
        reply_markup=products_menu_kb()
    )
    await callback.answer()


# ============================================================
# FSM HOLATLARI
# ============================================================

class AddProductState(StatesGroup):
    category      = State()   # Kategoriya tanlash
    name          = State()   # Nom
    price         = State()   # Narx
    description   = State()   # Tavsif (ixtiyoriy)
    photo         = State()   # Rasm (ixtiyoriy)
    has_variants  = State()   # "Turlari bormi?" — Ha/Yo'q
    stock         = State()   # Stok miqdori (faqat turlar YO'Q bo'lsa)
    variant_name  = State()   # Tur nomi (turlar BOR bo'lsa, takrorlanadi)
    variant_stock = State()   # Tur stoki (turlar BOR bo'lsa, takrorlanadi)


class EditProductState(StatesGroup):
    choose_field = State()  # Qaysi maydonni o'zgartirish
    new_value    = State()  # Yangi qiymat


class DiscountState(StatesGroup):
    value          = State()  # Chegirma qiymati
    duration       = State()  # Vaqt (soat)


class StockState(StatesGroup):
    """
    Diqqat: bu holat endi "yangi umumiy son" emas, balki
    "nechta SOTILDI" (ayiriladigan son) uchun ishlatiladi —
    Burry so'ragan soddalashtirilgan oqim.
    """
    choose_variant = State()  # Tur tanlash (turlar bo'lsa)
    sold_qty       = State()  # Nechta sotildi


class AddVariantState(StatesGroup):
    """Mavjud mahsulotga YANGI tur qo'shish (mahsulot allaqachon bor)."""
    name  = State()   # Tur nomi
    stock = State()   # Boshlang'ich stok


class AddVariantState(StatesGroup):
    """Mavjud mahsulotga keyinroq yangi tur qo'shish uchun."""
    name  = State()
    stock = State()


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

    effective = await get_effective_stock(callback_data.product_id)
    text = fmt_product_admin(product, effective_stock=effective)

    if effective["has_variants"]:
        text += "\n\n*Turlar:*"
        for v in effective["variants"]:
            stock_icon = "🚫" if v["stock_qty"] == 0 else "✅"
            price = f"{int(v['price']):,} so'm" if v.get("price") else "asosiy narx"
            text += f"\n{stock_icon} {v['name']} — {price} — {v['stock_qty']} dona"

    await callback.message.edit_text(
        text=text,
        reply_markup=product_detail_kb(
            product_id=callback_data.product_id,
            is_active=product["is_active"],
            page=callback_data.page,
            has_variants=effective["has_variants"]
        ),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================
# MAVJUD MAHSULOTGA YANGI TUR QO'SHISH
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "add_variant"))
async def cb_add_variant_start(
    callback: CallbackQuery,
    callback_data: ProductAdminCB,
    state: FSMContext
) -> None:
    """Mahsulot detail sahifasidan 'Yangi tur qo'shish' bosilganda."""
    product = await get_product(callback_data.product_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    await state.update_data(
        variant_product_id=callback_data.product_id,
        variant_page=callback_data.page,
        variant_product_name=product["name"]
    )
    await state.set_state(AddVariantState.name)
    await callback.message.edit_text(
        text=(
            f"➕ *{product['name']}* — yangi tur\n\n"
            f"🎨 Tur nomini yozing:\nMisol: XL yoki Sariq"
        ),
        reply_markup=_cancel_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(AddVariantState.name, F.text)
async def add_variant_existing_name(message: Message, state: FSMContext) -> None:
    name, error = validate_name(message.text, max_len=64)
    if error:
        await message.answer(error, reply_markup=_cancel_kb())
        return

    await state.update_data(new_variant_name=name)
    await state.set_state(AddVariantState.stock)
    await message.answer(
        f"📦 *{name}* uchun stok miqdorini yozing:\nMisol: 10",
        reply_markup=_cancel_kb(),
        parse_mode="Markdown"
    )


@router.message(AddVariantState.stock, F.text)
async def add_variant_existing_stock(message: Message, state: FSMContext) -> None:
    qty, error = validate_stock(message.text)
    if error:
        await message.answer(error, reply_markup=_cancel_kb())
        return

    data = await state.get_data()
    product_id = data["variant_product_id"]
    name = data["new_variant_name"]
    await state.clear()

    await add_variant(product_id, {"name": name, "stock_qty": qty})

    effective = await get_effective_stock(product_id)
    await message.answer(
        f"✅ *{name}* qo'shildi!\n\n"
        f"📦 {data['variant_product_name']} — umumiy: *{effective['total_stock']} dona*",
        reply_markup=back_to_main_kb(),
        parse_mode="Markdown"
    )


# ============================================================
# MAHSULOT QO'SHISH — FSM
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "add"))
async def cb_add_product_start(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Mahsulot qo'shish jarayonini boshlash — kategoriya tugma orqali tanlanadi."""
    categories = await get_all_categories()

    if not categories:
        await callback.answer(
            "Avval kategoriya qo'shing!",
            show_alert=True
        )
        return

    await state.set_state(AddProductState.category)
    builder = InlineKeyboardBuilder()
    for cat in categories:
        prefix = "  └ " if cat["parent_id"] else ""
        builder.row(InlineKeyboardButton(
            text=f"{prefix}{cat['name']}",
            callback_data=f"pick_addcat:{cat['id']}"
        ))
    builder.row(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="admin_cancel_fsm"
    ))

    await callback.message.edit_text(
        text="📂 *Kategoriyani tanlang:*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(AddProductState.category, F.data.startswith("pick_addcat:"))
async def add_product_category(callback: CallbackQuery, state: FSMContext) -> None:
    cat_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await state.set_state(AddProductState.name)
    await callback.message.edit_text(
        text="📝 Mahsulot nomini yozing:",
        reply_markup=_cancel_kb()
    )
    await callback.answer()


@router.message(AddProductState.name, F.text)
async def add_product_name(message: Message, state: FSMContext) -> None:
    name, error = validate_name(message.text)
    if error:
        await message.answer(error, reply_markup=_cancel_kb())
        return

    await state.update_data(name=name)
    await state.set_state(AddProductState.price)
    await message.answer(
        "💰 Narxini yozing (so'mda):\nMisol: 85000",
        reply_markup=_cancel_kb()
    )


@router.message(AddProductState.price, F.text)
async def add_product_price(message: Message, state: FSMContext) -> None:
    price, error = validate_price(message.text)
    if error:
        await message.answer(error, reply_markup=_cancel_kb())
        return

    await state.update_data(price=price)
    await state.set_state(AddProductState.description)
    await message.answer(
        "📋 Tavsif yozing (ixtiyoriy):\n"
        "Yo'q bo'lsa — /skip yozing",
        reply_markup=_cancel_kb()
    )


@router.message(AddProductState.description, F.text)
async def add_product_description(message: Message, state: FSMContext) -> None:
    desc = "" if message.text.strip() == "/skip" else message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(AddProductState.photo)
    await message.answer(
        "🖼 Rasm yuboring (ixtiyoriy):\n"
        "Yo'q bo'lsa — /skip yozing",
        reply_markup=_cancel_kb()
    )


@router.message(AddProductState.photo, F.photo)
async def add_product_photo(message: Message, state: FSMContext) -> None:
    # Eng yuqori sifatli rasm — ro'yxatning oxirgi elementi
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await _ask_has_variants(message, state)


@router.message(AddProductState.photo, F.text)
async def add_product_photo_skip(message: Message, state: FSMContext) -> None:
    if message.text.strip() != "/skip":
        await message.answer("📸 Rasm yuboring yoki /skip yozing.", reply_markup=_cancel_kb())
        return

    await state.update_data(photo_id=None)
    await _ask_has_variants(message, state)


async def _ask_has_variants(message: Message, state: FSMContext) -> None:
    """
    Yangi qadam: mahsulotda turlar (rang/o'lcham) bormi deb so'raladi.
    Javobga qarab ikki xil yo'lga bo'linadi:
      - Yo'q → hozirgidek, bitta umumiy stok soni so'raladi
      - Ha   → har bir tur uchun nom + stok ketma-ket so'raladi
    """
    await state.set_state(AddProductState.has_variants)
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎨 Ha, turlari bor", callback_data="addprod_var_yes"),
        InlineKeyboardButton(text="📦 Yo'q, oddiy", callback_data="addprod_var_no"),
    )
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel_fsm"))
    await message.answer(
        "🎨 *Bu mahsulotda turlar bormi?*\n"
        "_(rang, o'lcham va h.k. — har biriga alohida stok)_",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(AddProductState.has_variants, F.data == "addprod_var_no")
async def add_product_no_variants(callback: CallbackQuery, state: FSMContext) -> None:
    """Oddiy mahsulot — bitta umumiy stok soni so'raladi (hozirgidek)."""
    await state.set_state(AddProductState.stock)
    await callback.message.edit_text(
        "📦 Stok miqdorini yozing:\nMisol: 50"
    )
    await callback.answer()


@router.callback_query(AddProductState.has_variants, F.data == "addprod_var_yes")
async def add_product_has_variants(callback: CallbackQuery, state: FSMContext) -> None:
    """Turlar qo'shish jarayoni boshlanadi."""
    await state.update_data(variants_list=[])
    await state.set_state(AddProductState.variant_name)
    await callback.message.edit_text(
        "🎨 *1-tur nomini yozing:*\nMisol: S, M, L yoki Qizil, Ko'k",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(AddProductState.variant_name, F.text)
async def add_variant_name_step(message: Message, state: FSMContext) -> None:
    name, error = validate_name(message.text, max_len=64)
    if error:
        await message.answer(error, reply_markup=_cancel_kb())
        return

    await state.update_data(current_variant_name=name)
    await state.set_state(AddProductState.variant_stock)
    await message.answer(
        f"📦 *{name}* uchun stok miqdorini yozing:\nMisol: 10",
        reply_markup=_cancel_kb(),
        parse_mode="Markdown"
    )


@router.message(AddProductState.variant_stock, F.text)
async def add_variant_stock_step(message: Message, state: FSMContext) -> None:
    qty, error = validate_stock(message.text)
    if error:
        await message.answer(error, reply_markup=_cancel_kb())
        return

    data = await state.get_data()
    variants_list = data.get("variants_list", [])
    variants_list.append({
        "name": data["current_variant_name"],
        "stock_qty": qty,
    })
    await state.update_data(variants_list=variants_list)

    lines = "\n".join(
        f"• {v['name']} — {v['stock_qty']} dona" for v in variants_list
    )
    total = sum(v["stock_qty"] for v in variants_list)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Yana tur qo'shish", callback_data="addvar_more"),
        InlineKeyboardButton(text="✅ Tugatish", callback_data="addvar_done"),
    )
    await message.answer(
        f"✅ Qo'shildi!\n\n🎨 *Hozirgacha:*\n{lines}\n\n📦 Jami: *{total} dona*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(AddProductState.variant_stock, F.data == "addvar_more")
async def add_variant_more(callback: CallbackQuery, state: FSMContext) -> None:
    """Yana bitta tur qo'shish — nom so'raladi."""
    await state.set_state(AddProductState.variant_name)
    await callback.message.edit_text(
        "🎨 *Keyingi tur nomini yozing:*",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(AddProductState.variant_stock, F.data == "addvar_done")
async def add_variant_done(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Turlar qo'shish tugadi — mahsulot bazaga yoziladi (stock_qty=0,
    chunki turlar bo'lgani uchun umumiy stok ulardan hisoblanadi),
    keyin har bir tur alohida yoziladi.
    """
    data = await state.get_data()
    variants_list = data.get("variants_list", [])
    await state.clear()

    if not variants_list:
        await callback.answer("Kamida bitta tur qo'shing", show_alert=True)
        return

    product_id = await add_product({
        "category_id": data["category_id"],
        "name":        data["name"],
        "price":       data["price"],
        "description": data.get("description", ""),
        "photo_id":    data.get("photo_id"),
        "stock_qty":   0,   # Turlar bor — umumiy stok ulardan hisoblanadi
        "is_active":   True,
    })

    for v in variants_list:
        await add_variant(product_id, {
            "name": v["name"],
            "stock_qty": v["stock_qty"],
        })

    lines = "\n".join(
        f"• {v['name']} — {v['stock_qty']} dona" for v in variants_list
    )
    total = sum(v["stock_qty"] for v in variants_list)

    await callback.message.edit_text(
        f"✅ *Mahsulot qo'shildi!*\n\n"
        f"🆔 `#{product_id}`\n"
        f"📝 {data['name']}\n"
        f"💰 {int(data['price']):,} so'm\n\n"
        f"🎨 *Turlar:*\n{lines}\n\n"
        f"📦 Umumiy: *{total} dona*",
        reply_markup=back_to_main_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(AddProductState.stock, F.text)
async def add_product_stock(message: Message, state: FSMContext) -> None:
    """Oxirgi qadam (turlar YO'Q holat) — mahsulotni bazaga yozish."""
    qty, error = validate_stock(message.text)
    if error:
        await message.answer(error, reply_markup=_cancel_kb())
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
        reply_markup=back_to_main_kb(),
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
    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data=ProductAdminCB(
                action="edit", product_id=product_id
            ).pack()
        ),
        InlineKeyboardButton(
            text="🏠 Bosh menyu",
            callback_data=AdminCB(section="main").pack()
        )
    )

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

    # Kategoriya — alohida, tugma orqali tanlanadi (ID yozish shart emas)
    if field == "category":
        categories = await get_all_categories()
        if not categories:
            await callback.answer("Kategoriyalar yo'q", show_alert=True)
            return

        await state.update_data(product_id=int(product_id))
        builder = InlineKeyboardBuilder()
        for cat in categories:
            prefix = "  └ " if cat["parent_id"] else ""
            builder.row(InlineKeyboardButton(
                text=f"{prefix}{cat['name']}",
                callback_data=f"pick_editcat:{cat['id']}"
            ))
        builder.row(InlineKeyboardButton(
            text="❌ Bekor qilish", callback_data="admin_cancel_fsm"
        ))
        await callback.message.edit_text(
            text="📂 *Yangi kategoriyani tanlang:*",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    await state.update_data(
        product_id=int(product_id),
        edit_field=field
    )
    await state.set_state(EditProductState.new_value)
    await callback.message.edit_text(
        text=EDIT_FIELDS.get(field, "Yangi qiymatni yozing:"),
        reply_markup=_cancel_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pick_editcat:"))
async def cb_pick_editcat(callback: CallbackQuery, state: FSMContext) -> None:
    """Tahrirlashda yangi kategoriya tugma orqali tanlandi."""
    cat_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    product_id = data.get("product_id")
    await state.clear()

    if not product_id:
        await callback.answer("Xatolik, qaytadan urinib ko'ring", show_alert=True)
        return

    await update_product(product_id, {"category_id": cat_id})
    await callback.message.edit_text(
        text=f"✅ Mahsulot #{product_id} kategoriyasi yangilandi!",
        reply_markup=back_to_main_kb()
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
            await message.answer(error, reply_markup=_cancel_kb())
            return
        update_data["name"] = value

    elif field == "price":
        value, error = validate_price(message.text)
        if error:
            await message.answer(error, reply_markup=_cancel_kb())
            return
        update_data["price"] = value

    elif field == "description":
        update_data["description"] = message.text.strip()

    elif field == "photo":
        if not message.photo:
            await message.answer("❌ Rasm yuboring.", reply_markup=_cancel_kb())
            return
        update_data["photo_id"] = message.photo[-1].file_id

    elif field == "stock":
        value, error = validate_stock(message.text)
        if error:
            await message.answer(error, reply_markup=_cancel_kb())
            return
        update_data["stock_qty"] = value

    await update_product(product_id, update_data)
    await state.clear()
    await message.answer(
        f"✅ Mahsulot #{product_id} yangilandi!",
        reply_markup=back_to_main_kb()
    )


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
# CHEGIRMA BELGILASH — Ro'yxatdan tanlab, bekor qilish bilan
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "discount"))
async def cb_discount_start(
    callback: CallbackQuery,
    callback_data: ProductAdminCB,
    state: FSMContext
) -> None:
    """
    Chegirma belgilash.
    Mahsulot detail dan kelgan bo'lsa — to'g'ridan qiymat so'raladi.
    Aks holda — mahsulotlar ro'yxati ko'rsatiladi, tugma bosib tanlanadi.
    """
    if callback_data.product_id:
        await state.update_data(product_id=callback_data.product_id, page=callback_data.page)
        await state.set_state(DiscountState.value)
        await callback.message.edit_text(
            text=(
                "🏷 *Chegirma qiymatini yozing:*\n\n"
                "• 100 dan kam → foiz (%)\n"
                "  Misol: `30` → 30% chegirma\n\n"
                "• 100 va undan ko'p → aniq narx\n"
                "  Misol: `45000` → chegirma narxi 45,000 so'm"
            ),
            reply_markup=_cancel_kb(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    await _show_discount_pick_list(callback, page=1)
    await callback.answer()


async def _show_discount_pick_list(callback: CallbackQuery, page: int) -> None:
    """Mahsulotlar ro'yxati — stok va narx ko'rinib turadi, tugma bosib tanlanadi."""
    total = await count_products_admin()
    if total == 0:
        await callback.message.edit_text(
            text="📭 Hozircha mahsulotlar yo'q.",
            reply_markup=back_to_main_kb()
        )
        return

    total_pages = max(1, (total + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * PRODUCTS_PER_PAGE
    products = await get_all_products_admin(offset=offset, limit=PRODUCTS_PER_PAGE)

    builder = InlineKeyboardBuilder()
    for p in products:
        stock_icon = "🚫" if p["stock_qty"] == 0 else ("⚠️" if p["stock_qty"] <= 5 else "✅")
        builder.row(InlineKeyboardButton(
            text=f"{stock_icon} #{p['id']} {p['name']} — {int(p['price']):,} so'm",
            callback_data=f"pick_discount:{p['id']}:{page}"
        ))

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"discount_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"discount_page:{page + 1}"))
    if nav:
        builder.row(*nav)

    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data=AdminCB(section="products").pack()
        ),
        InlineKeyboardButton(
            text="🏠 Bosh menyu",
            callback_data=AdminCB(section="main").pack()
        )
    )

    await callback.message.edit_text(
        text=f"🏷 *Chegirma uchun mahsulotni tanlang:* ({total} ta)",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("discount_page:"))
async def cb_discount_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    await _show_discount_pick_list(callback, page)
    await callback.answer()


@router.callback_query(F.data.startswith("pick_discount:"))
async def cb_pick_discount(callback: CallbackQuery, state: FSMContext) -> None:
    """Ro'yxatdan mahsulot tanlandi — chegirma qiymatini so'raymiz."""
    _, product_id, page = callback.data.split(":")
    product = await get_product(int(product_id))
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    await state.update_data(product_id=int(product_id), page=int(page))
    await state.set_state(DiscountState.value)
    await callback.message.edit_text(
        text=(
            f"✅ *{product['name']}* tanlandi.\n\n"
            "🏷 Chegirma qiymatini yozing:\n"
            "• 100 dan kam → foiz (%): `30`\n"
            "• 100 va undan ko'p → narx: `45000`"
        ),
        reply_markup=_cancel_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(DiscountState.value, F.text)
async def discount_value(message: Message, state: FSMContext) -> None:
    value, dtype, error = validate_discount(message.text)
    if error:
        await message.answer(error, reply_markup=_cancel_kb())
        return

    await state.update_data(discount_value=value, discount_type=dtype)
    await state.set_state(DiscountState.duration)
    await message.answer(
        "⏰ *Qancha vaqt amal qilsin?*\n\n"
        "• Soat kiriting: `24` (24 soat)\n"
        "• Daqiqa: `30m` (30 daqiqa)\n"
        "• Doimiy bo'lsa: /skip",
        reply_markup=_cancel_kb(),
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
            await message.answer(error, reply_markup=_cancel_kb())
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
        reply_markup=back_to_main_kb(),
        parse_mode="Markdown"
    )


# ============================================================
# STOK AYIRISH — "Nechta sotildi?" (Burry so'ragan sodda oqim)
# Bo'limga kirish → mahsulot tanlash → (tur bo'lsa) tur tanlash
# → nechta sotildi → bot o'zi ayiradi
# ============================================================

@router.callback_query(ProductAdminCB.filter(F.action == "stock"))
async def cb_stock_start(
    callback: CallbackQuery,
    callback_data: ProductAdminCB,
    state: FSMContext
) -> None:
    if callback_data.product_id:
        await _start_stock_for_product(
            callback, state, callback_data.product_id, callback_data.page
        )
        return

    await _show_stock_pick_list(callback, page=1)
    await callback.answer()


async def _show_stock_pick_list(callback: CallbackQuery, page: int) -> None:
    """Mahsulotlar ro'yxati — haqiqiy (turlar bilan hisoblangan) stok ko'rinadi."""
    total = await count_products_admin()
    if total == 0:
        await callback.message.edit_text(
            text="📭 Hozircha mahsulotlar yo'q.",
            reply_markup=back_to_main_kb()
        )
        return

    total_pages = max(1, (total + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * PRODUCTS_PER_PAGE
    products = await get_all_products_admin(offset=offset, limit=PRODUCTS_PER_PAGE)

    builder = InlineKeyboardBuilder()
    for p in products:
        # Turlar bo'lsa — yig'indi, bo'lmasa — o'z soni (yagona manba)
        effective = await get_effective_stock(p["id"])
        stock = effective["total_stock"]
        stock_icon = "🚫" if stock == 0 else ("⚠️" if stock <= 5 else "✅")
        builder.row(InlineKeyboardButton(
            text=f"{stock_icon} #{p['id']} {p['name']} — {stock} dona",
            callback_data=f"pick_stock:{p['id']}:{page}"
        ))

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"stock_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"stock_page:{page + 1}"))
    if nav:
        builder.row(*nav)

    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data=AdminCB(section="products").pack()
        ),
        InlineKeyboardButton(
            text="🏠 Bosh menyu",
            callback_data=AdminCB(section="main").pack()
        )
    )

    await callback.message.edit_text(
        text=f"📦 *Qaysi mahsulot sotildi?* ({total} ta)",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("stock_page:"))
async def cb_stock_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    await _show_stock_pick_list(callback, page)
    await callback.answer()


@router.callback_query(F.data.startswith("pick_stock:"))
async def cb_pick_stock(callback: CallbackQuery, state: FSMContext) -> None:
    """Ro'yxatdan mahsulot tanlandi."""
    _, product_id, page = callback.data.split(":")
    await _start_stock_for_product(callback, state, int(product_id), int(page))


async def _start_stock_for_product(
    callback: CallbackQuery,
    state: FSMContext,
    product_id: int,
    page: int
) -> None:
    """
    Mahsulot tanlangandan keyin:
      - Turlar bo'lsa → qaysi tur sotilganini so'raydi
      - Turlar bo'lmasa → to'g'ridan "nechta sotildi" so'raydi
    """
    product = await get_product(product_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    effective = await get_effective_stock(product_id)
    await state.update_data(
        stock_product_id=product_id,
        stock_page=page,
        stock_product_name=product["name"]
    )

    if effective["has_variants"]:
        builder = InlineKeyboardBuilder()
        for v in effective["variants"]:
            builder.row(InlineKeyboardButton(
                text=f"{v['name']} — {v['stock_qty']} dona",
                callback_data=f"pick_stockvar:{v['id']}"
            ))
        builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel_fsm"))
        await state.set_state(StockState.choose_variant)
        await callback.message.edit_text(
            text=f"🎨 *{product['name']}*\n\nQaysi tur sotildi?",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    else:
        await state.set_state(StockState.sold_qty)
        await callback.message.edit_text(
            text=(
                f"*{product['name']}*\n"
                f"Hozirgi stok: {product['stock_qty']} dona\n\n"
                f"📦 Nechta sotildi?"
            ),
            reply_markup=_cancel_kb(),
            parse_mode="Markdown"
        )
    await callback.answer()


@router.callback_query(StockState.choose_variant, F.data.startswith("pick_stockvar:"))
async def cb_pick_stock_variant(callback: CallbackQuery, state: FSMContext) -> None:
    """Tur tanlandi — endi nechta sotilganini so'raymiz."""
    variant_id = int(callback.data.split(":")[1])
    data = await state.get_data()

    # Tur nomi va joriy stokini ko'rsatish uchun ro'yxatdan qidiramiz
    effective = await get_effective_stock(data["stock_product_id"])
    variant = next((v for v in effective["variants"] if v["id"] == variant_id), None)
    if not variant:
        await callback.answer("Tur topilmadi", show_alert=True)
        return

    await state.update_data(
        stock_variant_id=variant_id,
        stock_variant_name=variant["name"]
    )
    await state.set_state(StockState.sold_qty)
    await callback.message.edit_text(
        text=(
            f"*{data['stock_product_name']}* — {variant['name']}\n"
            f"Hozirgi stok: {variant['stock_qty']} dona\n\n"
            f"📦 Nechta sotildi?"
        ),
        reply_markup=_cancel_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(StockState.sold_qty, F.text)
async def process_sold_qty(message: Message, state: FSMContext) -> None:
    """
    Nechta sotilganini qabul qilib, stokdan AYIRADI.
    Omborda yetarli bo'lmasa — xato ko'rsatiladi, ayirilmaydi.
    """
    qty, error = validate_stock(message.text)
    if error:
        await message.answer(error, reply_markup=_cancel_kb())
        return

    if qty == 0:
        await message.answer(
            "❌ 0 dona sotilgan bo'lishi mumkin emas. Boshqa son yozing.",
            reply_markup=_cancel_kb()
        )
        return

    data = await state.get_data()
    product_id = data["stock_product_id"]
    variant_id = data.get("stock_variant_id")

    available = await get_available_stock(product_id, variant_id)

    if qty > available:
        await message.answer(
            f"❌ Omborda faqat *{available} dona* bor.\n"
            f"{qty} dona ayira olmaysiz. Qaytadan yozing:",
            reply_markup=_cancel_kb(),
            parse_mode="Markdown"
        )
        return

    await update_stock(product_id, -qty, variant_id)
    await state.clear()

    new_available = available - qty
    name = data["stock_product_name"]
    if data.get("stock_variant_name"):
        name += f" — {data['stock_variant_name']}"

    await message.answer(
        f"✅ *{qty} dona ayirildi!*\n\n"
        f"{name}\n"
        f"📦 {available} → *{new_available} dona*",
        reply_markup=back_to_main_kb(),
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
        reply_markup=_cancel_kb(),
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
        ),
        InlineKeyboardButton(
            text="🏠 Bosh menyu",
            callback_data=AdminCB(section="main").pack()
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
        reply_markup=_cancel_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(CategoryState.name, F.text)
async def cat_add_name(message: Message, state: FSMContext) -> None:
    name, error = validate_name(message.text, max_len=64)
    if error:
        await message.answer(error, reply_markup=_cancel_kb())
        return

    await state.update_data(cat_name=name)

    categories = await get_all_categories()
    main_cats = [c for c in categories if not c["parent_id"]]

    if not main_cats:
        # Ota-kategoriya yo'q — to'g'ridan asosiy kategoriya sifatida qo'shiladi
        await state.clear()
        cat_id = await add_category(name, None)
        await message.answer(
            f"✅ Yangi kategoriya qo'shildi!\n🆔 `{cat_id}` — {name}",
            reply_markup=back_to_main_kb(),
            parse_mode="Markdown"
        )
        return

    await state.set_state(CategoryState.parent)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📁 Asosiy kategoriya (ota yo'q)",
        callback_data="pick_catparent:0"
    ))
    for c in main_cats:
        builder.row(InlineKeyboardButton(
            text=c["name"],
            callback_data=f"pick_catparent:{c['id']}"
        ))
    builder.row(InlineKeyboardButton(
        text="❌ Bekor qilish", callback_data="admin_cancel_fsm"
    ))
    await message.answer(
        "📂 *Ota-kategoriyani tanlang:*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(CategoryState.parent, F.data.startswith("pick_catparent:"))
async def cat_add_parent(callback: CallbackQuery, state: FSMContext) -> None:
    parent_id = int(callback.data.split(":")[1]) or None
    data = await state.get_data()
    await state.clear()

    cat_id = await add_category(data["cat_name"], parent_id)
    cat_type = "subkategoriya" if parent_id else "kategoriya"
    await callback.message.edit_text(
        text=f"✅ Yangi {cat_type} qo'shildi!\n🆔 `{cat_id}` — {data['cat_name']}",
        reply_markup=back_to_main_kb(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(ProductAdminCB.filter(F.action == "cat_delete"))
async def cb_cat_delete_start(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Kategoriya o'chirish — ro'yxatdan tugma bosib tanlanadi."""
    categories = await get_all_categories()
    if not categories:
        await callback.answer("Kategoriyalar yo'q", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for cat in categories:
        prefix = "  └ " if cat["parent_id"] else ""
        builder.row(InlineKeyboardButton(
            text=f"🗑 {prefix}{cat['name']}",
            callback_data=f"pick_catdel:{cat['id']}"
        ))
    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data=ProductAdminCB(action="categories").pack()
    ))

    await callback.message.edit_text(
        text=(
            "🗑 *Qaysi kategoriyani o'chiramiz?*\n\n"
            "_Diqqat: Ichida mahsulot yoki subkategoriya bo'lsa o'chirilmaydi._"
        ),
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pick_catdel:"))
async def cb_pick_catdel(callback: CallbackQuery) -> None:
    """Tanlangan kategoriyani o'chirishga urinish."""
    cat_id = int(callback.data.split(":")[1])
    success = await delete_category(cat_id)

    if success:
        await callback.answer("✅ Kategoriya o'chirildi", show_alert=True)
    else:
        await callback.answer(
            "❌ Bu kategoriya ichida mahsulot yoki subkategoriya bor — avval ularni ko'chiring/o'chiring.",
            show_alert=True
        )
        return

    # Ro'yxatni yangilab qayta ko'rsatish
    categories = await get_all_categories()
    if not categories:
        await callback.message.edit_text(
            text="📭 Kategoriyalar tugadi.",
            reply_markup=back_to_main_kb()
        )
        return

    builder = InlineKeyboardBuilder()
    for cat in categories:
        prefix = "  └ " if cat["parent_id"] else ""
        builder.row(InlineKeyboardButton(
            text=f"🗑 {prefix}{cat['name']}",
            callback_data=f"pick_catdel:{cat['id']}"
        ))
    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data=ProductAdminCB(action="categories").pack()
    ))
    await callback.message.edit_text(
        text="🗑 *Qaysi kategoriyani o'chiramiz?*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

