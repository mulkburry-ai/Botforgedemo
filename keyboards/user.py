# ============================================================
# BOTFORGE — keyboards/user.py
# Foydalanuvchi uchun barcha klaviaturalar
# aiogram 3.x CallbackData + ReplyKeyboardMarkup
# ============================================================

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from utils.formatters import fmt_status


# ============================================================
# CALLBACK DATA CLASSLARI
# ============================================================

class CatalogCB(CallbackData, prefix="cat"):
    """Katalog navigatsiyasi."""
    action: str        # "main" | "sub" | "products" | "product"
    cat_id: int = 0
    page: int = 1


class ProductCB(CallbackData, prefix="prod"):
    """Mahsulot kartasi tugmalari."""
    action: str        # "gallery" | "cart" | "favorite" | "back"
    product_id: int = 0
    variant_id: int = 0
    gallery_idx: int = 0
    page: int = 1


class CartCB(CallbackData, prefix="cart"):
    """Savat tugmalari."""
    action: str        # "remove" | "clear" | "checkout" | "back"
    cart_id: int = 0


class OrderCB(CallbackData, prefix="order"):
    """Buyurtmalar tugmalari."""
    action: str        # "list" | "detail"
    order_id: int = 0


class InfoCB(CallbackData, prefix="info"):
    """Ma'lumot bo'limi tugmalari."""
    section: str       # "about"|"delivery"|"payment"|"contact"|"request"|"favorites"|"last_seen"


# ============================================================
# REPLY KEYBOARD — Doim pastda, 4 ta asosiy tugma
# ============================================================

def main_menu_kb() -> ReplyKeyboardMarkup:
    """
    Foydalanuvchi asosiy menyusi.
    Bot ochilganda va /start da ko'rsatiladi.
    """
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🛍 Katalog"),
        KeyboardButton(text="🧺 Savat"),
    )
    builder.row(
        KeyboardButton(text="📦 Buyurtmalarim"),
        KeyboardButton(text="ℹ️ Ma'lumot"),
    )
    return builder.as_markup(
        resize_keyboard=True,
        persistent=True
    )


def phone_kb() -> ReplyKeyboardMarkup:
    """
    Telefon raqami so'rashda ko'rsatiladi.
    Foydalanuvchi tugmani bossa, raqami avtomatik yuboriladi.
    """
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(
            text="📱 Telefon raqamni yuborish",
            request_contact=True
        )
    )
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)


# ============================================================
# KATALOG INLINE KLAVIATURALAR
# ============================================================

def categories_kb(categories: list) -> InlineKeyboardMarkup:
    """
    Asosiy kategoriyalar ro'yxati.
    categories: [{"id": 1, "name": "Erkaklar"}, ...]
    """
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.row(InlineKeyboardButton(
            text=cat["name"],
            callback_data=CatalogCB(
                action="sub", cat_id=cat["id"]
            ).pack()
        ))
    return builder.as_markup()


def subcategories_kb(subcategories: list, parent_id: int) -> InlineKeyboardMarkup:
    """
    Subkategoriyalar ro'yxati + Orqaga tugmasi.
    """
    builder = InlineKeyboardBuilder()
    for sub in subcategories:
        builder.row(InlineKeyboardButton(
            text=sub["name"],
            callback_data=CatalogCB(
                action="products", cat_id=sub["id"]
            ).pack()
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ Orqaga",
        callback_data=CatalogCB(action="main", cat_id=0).pack()
    ))
    return builder.as_markup()


def products_list_kb(
    products: list,
    cat_id: int,
    page: int,
    total_pages: int
) -> InlineKeyboardMarkup:
    """
    Mahsulotlar ro'yxati — musiqa bot uslubida.
    Har mahsulot alohida qator. Pastda pagination.
    """
    builder = InlineKeyboardBuilder()

    for p in products:
        # Stok holati belgisi
        if p["stock_qty"] == 0:
            stock_icon = "🚫"
        elif p["stock_qty"] <= 5:
            stock_icon = "⚠️"
        else:
            stock_icon = "✅"

        builder.row(InlineKeyboardButton(
            text=f"{stock_icon} {p['name']} — {int(p['price']):,} so'm",
            callback_data=ProductCB(
                action="detail",
                product_id=p["id"],
                page=page
            ).pack()
        ))

    # Pagination
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(
            text="◀️",
            callback_data=CatalogCB(
                action="products", cat_id=cat_id, page=page - 1
            ).pack()
        ))
    nav_row.append(InlineKeyboardButton(
        text=f"{page}/{total_pages}",
        callback_data="noop"
    ))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="▶️",
            callback_data=CatalogCB(
                action="products", cat_id=cat_id, page=page + 1
            ).pack()
        ))
    if nav_row:
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(
        text="◀️ Orqaga",
        callback_data=CatalogCB(action="sub", cat_id=cat_id).pack()
    ))
    return builder.as_markup()


# ============================================================
# MAHSULOT KARTASI
# ============================================================

def product_card_kb(
    product_id: int,
    variant_id: int = 0,
    gallery_idx: int = 0,
    gallery_total: int = 1,
    is_favorite: bool = False,
    in_stock: bool = True,
    back_cat_id: int = 0,
    page: int = 1
) -> InlineKeyboardMarkup:
    """
    Mahsulot kartasi tugmalari:
    - Galereya navigatsiyasi (rasm ko'p bo'lsa)
    - Savatga solish (stok bo'lsa)
    - Sevimli
    - Orqaga
    """
    builder = InlineKeyboardBuilder()

    # Galereya (bir nechta rasm bo'lsa)
    if gallery_total > 1:
        gallery_row = []
        if gallery_idx > 0:
            gallery_row.append(InlineKeyboardButton(
                text="◀️",
                callback_data=ProductCB(
                    action="gallery",
                    product_id=product_id,
                    gallery_idx=gallery_idx - 1
                ).pack()
            ))
        gallery_row.append(InlineKeyboardButton(
            text=f"🖼 {gallery_idx + 1}/{gallery_total}",
            callback_data="noop"
        ))
        if gallery_idx < gallery_total - 1:
            gallery_row.append(InlineKeyboardButton(
                text="▶️",
                callback_data=ProductCB(
                    action="gallery",
                    product_id=product_id,
                    gallery_idx=gallery_idx + 1
                ).pack()
            ))
        builder.row(*gallery_row)

    # Savatga solish
    if in_stock:
        builder.row(InlineKeyboardButton(
            text="🛒 Savatga solish",
            callback_data=ProductCB(
                action="cart",
                product_id=product_id,
                variant_id=variant_id
            ).pack()
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🚫 Mahsulot tugagan",
            callback_data="noop"
        ))

    # Sevimli + Orqaga
    fav_text = "❤️ Sevimlilardan chiqarish" if is_favorite else "🤍 Sevimlilarga qo'shish"
    builder.row(
        InlineKeyboardButton(
            text=fav_text,
            callback_data=ProductCB(
                action="favorite",
                product_id=product_id
            ).pack()
        )
    )
    builder.row(InlineKeyboardButton(
        text="◀️ Orqaga",
        callback_data=CatalogCB(
            action="products", cat_id=back_cat_id, page=page
        ).pack()
    ))
    return builder.as_markup()


def variant_select_kb(variants: list, product_id: int) -> InlineKeyboardMarkup:
    """
    Mahsulot turlari tanlash (rangi, o'lchami va h.k.)
    """
    builder = InlineKeyboardBuilder()
    for v in variants:
        stock_icon = "🚫" if v["stock_qty"] == 0 else "✅"
        price_text = f" — {int(v['price']):,} so'm" if v.get("price") else ""
        builder.row(InlineKeyboardButton(
            text=f"{stock_icon} {v['name']}{price_text}",
            callback_data=ProductCB(
                action="variant",
                product_id=product_id,
                variant_id=v["id"]
            ).pack()
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ Orqaga",
        callback_data=ProductCB(
            action="detail", product_id=product_id
        ).pack()
    ))
    return builder.as_markup()


# ============================================================
# SAVAT
# ============================================================

def cart_kb(cart_items: list) -> InlineKeyboardMarkup:
    """
    Savat tugmalari.
    Har bir mahsulot uchun o'chirish tugmasi + asosiy tugmalar.
    """
    builder = InlineKeyboardBuilder()

    # Har bir element uchun o'chirish
    for item in cart_items:
        name = item["product_name"]
        if item.get("variant_name"):
            name += f" ({item['variant_name']})"
        builder.row(InlineKeyboardButton(
            text=f"🗑 {name}",
            callback_data=CartCB(
                action="remove", cart_id=item["cart_id"]
            ).pack()
        ))

    # Asosiy tugmalar
    builder.row(InlineKeyboardButton(
        text="✅ Buyurtma berish",
        callback_data=CartCB(action="checkout", cart_id=0).pack()
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Savatni tozalash",
        callback_data=CartCB(action="clear", cart_id=0).pack()
    ))
    return builder.as_markup()


def checkout_confirm_kb(use_saved_phone: bool = False) -> InlineKeyboardMarkup:
    """Buyurtma tasdiqlash tugmalari."""
    builder = InlineKeyboardBuilder()
    if use_saved_phone:
        builder.row(
            InlineKeyboardButton(
                text="✅ Ha, shu raqam",
                callback_data=CartCB(action="phone_confirm", cart_id=0).pack()
            ),
            InlineKeyboardButton(
                text="📝 Boshqa raqam",
                callback_data=CartCB(action="phone_change", cart_id=0).pack()
            )
        )
    builder.row(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data=CartCB(action="back", cart_id=0).pack()
    ))
    return builder.as_markup()


def order_final_confirm_kb() -> InlineKeyboardMarkup:
    """Yakuniy tasdiqlash — buyurtma jo'natilishidan oldin."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Tasdiqlash",
            callback_data=CartCB(action="confirm", cart_id=0).pack()
        ),
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data=CartCB(action="back", cart_id=0).pack()
        )
    )
    return builder.as_markup()


# ============================================================
# BUYURTMALARIM
# ============================================================

def orders_list_kb(orders: list) -> InlineKeyboardMarkup:
    """Foydalanuvchi buyurtmalari ro'yxati."""
    builder = InlineKeyboardBuilder()
    for order in orders:
        builder.row(InlineKeyboardButton(
            text=f"#{order['order_code']} — {fmt_status(order['status'])}",
            callback_data=OrderCB(
                action="detail", order_id=order["id"]
            ).pack()
        ))
    return builder.as_markup()


def order_detail_kb(order_id: int) -> InlineKeyboardMarkup:
    """Buyurtma batafsil sahifasi — faqat orqaga tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ Orqaga",
        callback_data=OrderCB(action="list", order_id=0).pack()
    ))
    return builder.as_markup()


# ============================================================
# MA'LUMOT BO'LIMI
# ============================================================

def info_kb() -> InlineKeyboardMarkup:
    """Ma'lumot bo'limi asosiy menyusi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🏪 Do'kon haqida",
            callback_data=InfoCB(section="about").pack()
        ),
        InlineKeyboardButton(
            text="🚚 Yetkazib berish",
            callback_data=InfoCB(section="delivery").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💳 To'lov",
            callback_data=InfoCB(section="payment").pack()
        ),
        InlineKeyboardButton(
            text="📞 Aloqa",
            callback_data=InfoCB(section="contact").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💡 Mahsulot so'rovi",
            callback_data=InfoCB(section="request").pack()
        ),
        InlineKeyboardButton(
            text="❤️ Sevimlilar",
            callback_data=InfoCB(section="favorites").pack()
        )
    )
    builder.row(InlineKeyboardButton(
        text="🕐 Oxirgi ko'rilgan",
        callback_data=InfoCB(section="last_seen").pack()
    ))
    return builder.as_markup()


def info_back_kb() -> InlineKeyboardMarkup:
    """Ma'lumot ichki sahifalarida orqaga tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ Orqaga",
        callback_data=InfoCB(section="main").pack()
    ))
    return builder.as_markup()


# ============================================================
# YORDAMCHI
# ============================================================

def noop_kb() -> InlineKeyboardMarkup:
    """
    Hech narsa qilmaydigan tugma.
    Sahifa raqami kabi faqat ko'rinish uchun.
    """
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="·", callback_data="noop")
    ]])
