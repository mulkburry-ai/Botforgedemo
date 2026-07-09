# ============================================================
# BOTFORGE — keyboards/admin.py
# Admin uchun barcha klaviaturalar
# aiogram 3.x CallbackData
# ============================================================

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.formatters import fmt_price


# ============================================================
# CALLBACK DATA CLASSLARI
# ============================================================

class AdminCB(CallbackData, prefix="adm"):
    """Admin panel asosiy bo'limlari."""
    section: str    # "products" | "orders" | "users" | "stats"


class ProductAdminCB(CallbackData, prefix="padm"):
    """Mahsulot boshqaruvi."""
    action: str     # "list"|"add"|"edit"|"delete"|"discount"|"stock"|"search"|"categories"
    product_id: int = 0
    page: int = 1


class OrderAdminCB(CallbackData, prefix="oadm"):
    """Buyurtma boshqaruvi."""
    action: str     # "list"|"detail"|"status"
    order_id: int = 0
    status: str = ""
    page: int = 1


class UserAdminCB(CallbackData, prefix="uadm"):
    """Foydalanuvchi boshqaruvi."""
    action: str     # "list"|"search"|"ban"|"unban"|"msg"|"broadcast"
    user_id: int = 0
    page: int = 1


class StatsAdminCB(CallbackData, prefix="sadm"):
    """Ma'lumotlar bo'limi."""
    section: str    # "general"|"revenue"|"top"|"least"|"export"|"settings"


def _home_btn() -> InlineKeyboardButton:
    """
    Barcha "chuqur" sahifalarda ishlatiladigan "Bosh menyu" tugmasi.
    Menyu darajasidagi sahifalarda (masalan Mahsulotlar bo'limi) kerak
    emas — u yerda "Orqaga" allaqachon Bosh menyuga olib boradi.
    Faqat 2 va undan ortiq qadam chuqurlikdagi sahifalarda qo'llanadi.
    """
    return InlineKeyboardButton(
        text="🏠 Bosh menyu",
        callback_data=AdminCB(section="main").pack()
    )


# ============================================================
# ADMIN PANEL — Asosiy menyu
# ============================================================

def admin_panel_kb() -> InlineKeyboardMarkup:
    """
    Admin paneli 4 asosiy bo'lim.
    Dashboard matni handler tomonidan yuboriladi,
    bu faqat tugmalar.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📦 Mahsulotlar",
            callback_data=AdminCB(section="products").pack()
        ),
        InlineKeyboardButton(
            text="👥 Boshqaruv",
            callback_data=AdminCB(section="users").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Buyurtmalar",
            callback_data=AdminCB(section="orders").pack()
        ),
        InlineKeyboardButton(
            text="📊 Ma'lumotlar",
            callback_data=AdminCB(section="stats").pack()
        )
    )
    return builder.as_markup()


# ============================================================
# MAHSULOTLAR BO'LIMI
# ============================================================

def products_menu_kb() -> InlineKeyboardMarkup:
    """Mahsulotlar bo'limi menyusi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="➕ Qo'shish",
            callback_data=ProductAdminCB(action="add").pack()
        ),
        InlineKeyboardButton(
            text="🔍 Qidirish",
            callback_data=ProductAdminCB(action="search").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Ro'yxat",
            callback_data=ProductAdminCB(action="list").pack()
        ),
        InlineKeyboardButton(
            text="🏷 Chegirma",
            callback_data=ProductAdminCB(action="discount").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📦 Stok",
            callback_data=ProductAdminCB(action="stock").pack()
        ),
        InlineKeyboardButton(
            text="🗂 Kategoriyalar",
            callback_data=ProductAdminCB(action="categories").pack()
        )
    )
    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data=AdminCB(section="main").pack()
    ))
    return builder.as_markup()


def products_list_kb(
    products: list,
    page: int,
    total_pages: int,
    cat_id: int = 0
) -> InlineKeyboardMarkup:
    """
    Admin uchun mahsulotlar ro'yxati.
    Har mahsulot — bir qator, bosса detail ochiladi.
    """
    builder = InlineKeyboardBuilder()

    for p in products:
        stock_icon = "🚫" if p["stock_qty"] == 0 else ("⚠️" if p["stock_qty"] <= 5 else "✅")
        active_icon = "" if p["is_active"] else " 🔴"
        builder.row(InlineKeyboardButton(
            text=f"{stock_icon} #{p['id']} {p['name']}{active_icon}",
            callback_data=ProductAdminCB(
                action="edit",
                product_id=p["id"],
                page=page
            ).pack()
        ))

    # Pagination
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(
            text="◀️",
            callback_data=ProductAdminCB(action="list", page=page - 1).pack()
        ))
    nav.append(InlineKeyboardButton(
        text=f"{page}/{total_pages}",
        callback_data="noop"
    ))
    if page < total_pages:
        nav.append(InlineKeyboardButton(
            text="▶️",
            callback_data=ProductAdminCB(action="list", page=page + 1).pack()
        ))
    if nav:
        builder.row(*nav)

    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data=AdminCB(section="products").pack()
        ),
        _home_btn()
    )
    return builder.as_markup()


def product_detail_kb(
    product_id: int,
    is_active: bool,
    page: int = 1,
    has_variants: bool = False
) -> InlineKeyboardMarkup:
    """
    Bitta mahsulot detail sahifasi — barcha amallar.

    has_variants — True bo'lsa, "📦 Stok" o'rniga turlar bilan ishlash
    tugmalari ko'rsatiladi ("➕ Yangi tur qo'shish" qo'shiladi).
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✏️ Tahrirlash",
            callback_data=ProductAdminCB(
                action="edit", product_id=product_id, page=page
            ).pack()
        ),
        InlineKeyboardButton(
            text="🏷 Chegirma",
            callback_data=ProductAdminCB(
                action="discount", product_id=product_id
            ).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📦 Stok",
            callback_data=ProductAdminCB(
                action="stock", product_id=product_id
            ).pack()
        ),
        InlineKeyboardButton(
            text="🔴 Nofaol" if is_active else "🟢 Faol",
            callback_data=ProductAdminCB(
                action="toggle", product_id=product_id, page=page
            ).pack()
        )
    )
    if has_variants:
        builder.row(InlineKeyboardButton(
            text="➕ Yangi tur qo'shish",
            callback_data=ProductAdminCB(
                action="add_variant", product_id=product_id, page=page
            ).pack()
        ))
    builder.row(InlineKeyboardButton(
        text="🗑 O'chirish",
        callback_data=ProductAdminCB(
            action="delete", product_id=product_id, page=page
        ).pack()
    ))
    builder.row(
        InlineKeyboardButton(
            text="🔙 Ro'yxatga",
            callback_data=ProductAdminCB(action="list", page=page).pack()
        ),
        _home_btn()
    )
    return builder.as_markup()


def confirm_delete_kb(product_id: int, page: int = 1) -> InlineKeyboardMarkup:
    """Mahsulot o'chirishni tasdiqlash."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Ha, o'chir",
            callback_data=ProductAdminCB(
                action="delete_confirm", product_id=product_id, page=page
            ).pack()
        ),
        InlineKeyboardButton(
            text="❌ Yo'q",
            callback_data=ProductAdminCB(
                action="edit", product_id=product_id, page=page
            ).pack()
        )
    )
    return builder.as_markup()


# ============================================================
# BUYURTMALAR BO'LIMI
# ============================================================

def orders_menu_kb(counts: dict) -> InlineKeyboardMarkup:
    """
    Buyurtmalar bo'limi — holat bo'yicha filtrlash.
    counts: {"pending": 3, "confirmed": 5, ...}
    """
    builder = InlineKeyboardBuilder()

    statuses = [
        ("pending",   "🆕 Yangi"),
        ("confirmed", "✅ Tasdiqlangan"),
        ("shipping",  "🚚 Yo'lda"),
        ("delivered", "📦 Yetkazilgan"),
        ("cancelled", "❌ Bekor"),
        ("problem",   "⚠️ Muammo"),
    ]

    for status, label in statuses:
        count = counts.get(status, 0)
        builder.row(InlineKeyboardButton(
            text=f"{label} ({count})",
            callback_data=OrderAdminCB(
                action="list", status=status, page=1
            ).pack()
        ))

    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data=AdminCB(section="main").pack()
    ))
    return builder.as_markup()


def orders_list_kb(
    orders: list,
    status: str,
    page: int,
    total_pages: int
) -> InlineKeyboardMarkup:
    """Holat bo'yicha buyurtmalar ro'yxati."""
    builder = InlineKeyboardBuilder()

    for order in orders:
        builder.row(InlineKeyboardButton(
            text=f"#{order['order_code']} — {order['full_name']} — {fmt_price(order['total_price'])}",
            callback_data=OrderAdminCB(
                action="detail",
                order_id=order["id"],
                status=status,
                page=page
            ).pack()
        ))

    # Pagination
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(
            text="◀️",
            callback_data=OrderAdminCB(
                action="list", status=status, page=page - 1
            ).pack()
        ))
    nav.append(InlineKeyboardButton(
        text=f"{page}/{total_pages}",
        callback_data="noop"
    ))
    if page < total_pages:
        nav.append(InlineKeyboardButton(
            text="▶️",
            callback_data=OrderAdminCB(
                action="list", status=status, page=page + 1
            ).pack()
        ))
    if nav:
        builder.row(*nav)

    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data=AdminCB(section="orders").pack()
        ),
        _home_btn()
    )
    return builder.as_markup()


def order_detail_kb(order_id: int, current_status: str, page: int = 1) -> InlineKeyboardMarkup:
    """
    Buyurtma detail — holat o'zgartirish tugmalari.
    Faqat mantiqiy keyingi holatlarga o'tish mumkin.

    Diqqat: "confirmed" holatida "Yo'lga chiqarish" tugmasi maxsus —
    u to'g'ridan-to'g'ri holatni o'zgartirmaydi, balki yetkazib berish
    narxi/vaqti so'raladigan alohida jarayonni (FSM) boshlaydi.
    Shu sababli bu tugma uchun action="ship" ishlatiladi, boshqalari
    uchun action="status".
    """
    builder = InlineKeyboardBuilder()

    if current_status == "pending":
        builder.row(InlineKeyboardButton(
            text="✅ Qabul qilish",
            callback_data=OrderAdminCB(
                action="status", order_id=order_id, status="confirmed"
            ).pack()
        ))
        builder.row(InlineKeyboardButton(
            text="❌ Rad etish",
            callback_data=OrderAdminCB(
                action="status", order_id=order_id, status="cancelled"
            ).pack()
        ))

    elif current_status == "confirmed":
        builder.row(InlineKeyboardButton(
            text="🚚 Yo'lga chiqarish",
            callback_data=OrderAdminCB(
                action="ship", order_id=order_id, page=page
            ).pack()
        ))
        builder.row(InlineKeyboardButton(
            text="⚠️ Muammo",
            callback_data=OrderAdminCB(
                action="status", order_id=order_id, status="problem"
            ).pack()
        ))

    elif current_status == "shipping":
        builder.row(InlineKeyboardButton(
            text="📦 Yetkazildi",
            callback_data=OrderAdminCB(
                action="status", order_id=order_id, status="delivered"
            ).pack()
        ))
        builder.row(InlineKeyboardButton(
            text="⚠️ Muammo",
            callback_data=OrderAdminCB(
                action="status", order_id=order_id, status="problem"
            ).pack()
        ))

    elif current_status == "problem":
        builder.row(InlineKeyboardButton(
            text="✅ Qayta qabul",
            callback_data=OrderAdminCB(
                action="status", order_id=order_id, status="confirmed"
            ).pack()
        ))
        builder.row(InlineKeyboardButton(
            text="❌ Bekor",
            callback_data=OrderAdminCB(
                action="status", order_id=order_id, status="cancelled"
            ).pack()
        ))

    # "delivered" va "cancelled" holatlarida holat o'zgartirish tugmasi yo'q —
    # bular yakuniy holatlar.

    builder.row(
        InlineKeyboardButton(
            text="🔙 Ro'yxatga",
            callback_data=OrderAdminCB(
                action="list", status=current_status, page=page
            ).pack()
        ),
        _home_btn()
    )
    return builder.as_markup()


# ============================================================
# BOSHQARUV BO'LIMI (Foydalanuvchilar)
# ============================================================

def users_menu_kb() -> InlineKeyboardMarkup:
    """Boshqaruv bo'limi menyusi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="👥 Foydalanuvchilar",
            callback_data=UserAdminCB(action="list").pack()
        ),
        InlineKeyboardButton(
            text="🔍 Qidirish",
            callback_data=UserAdminCB(action="search").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🚫 Bloklash",
            callback_data=UserAdminCB(action="ban").pack()
        ),
        InlineKeyboardButton(
            text="✅ Blokdan chiqarish",
            callback_data=UserAdminCB(action="unban").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✉️ Mijozga xabar",
            callback_data=UserAdminCB(action="msg").pack()
        ),
        InlineKeyboardButton(
            text="📢 Ommaviy xabar",
            callback_data=UserAdminCB(action="broadcast").pack()
        )
    )
    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data=AdminCB(section="main").pack()
    ))
    return builder.as_markup()


def user_detail_kb(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    """Foydalanuvchi detail sahifasi."""
    builder = InlineKeyboardBuilder()
    if is_banned:
        builder.row(InlineKeyboardButton(
            text="✅ Blokdan chiqarish",
            callback_data=UserAdminCB(
                action="unban", user_id=user_id
            ).pack()
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🚫 Bloklash",
            callback_data=UserAdminCB(
                action="ban", user_id=user_id
            ).pack()
        ))
    builder.row(InlineKeyboardButton(
        text="✉️ Xabar yuborish",
        callback_data=UserAdminCB(
            action="msg", user_id=user_id
        ).pack()
    ))
    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data=AdminCB(section="users").pack()
        ),
        _home_btn()
    )
    return builder.as_markup()


def confirm_ban_kb(user_id: int) -> InlineKeyboardMarkup:
    """Bloklashni tasdiqlash."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Ha, bloklash",
            callback_data=UserAdminCB(
                action="ban_confirm", user_id=user_id
            ).pack()
        ),
        InlineKeyboardButton(
            text="❌ Yo'q",
            callback_data=AdminCB(section="users").pack()
        )
    )
    return builder.as_markup()


# ============================================================
# MA'LUMOTLAR BO'LIMI
# ============================================================

def stats_menu_kb() -> InlineKeyboardMarkup:
    """Ma'lumotlar bo'limi menyusi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📊 Statistika",
            callback_data=StatsAdminCB(section="general").pack()
        ),
        InlineKeyboardButton(
            text="💰 Daromad",
            callback_data=StatsAdminCB(section="revenue").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏆 Top mahsulot",
            callback_data=StatsAdminCB(section="top").pack()
        ),
        InlineKeyboardButton(
            text="📉 Kam sotilgan",
            callback_data=StatsAdminCB(section="least").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💾 Excel bekap",
            callback_data=StatsAdminCB(section="export").pack()
        ),
        InlineKeyboardButton(
            text="⚙️ Sozlamalar",
            callback_data=StatsAdminCB(section="settings").pack()
        )
    )
    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data=AdminCB(section="main").pack()
    ))
    return builder.as_markup()


def stats_back_kb() -> InlineKeyboardMarkup:
    """Ma'lumotlar ichki sahifalarida orqaga tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data=AdminCB(section="stats").pack()
        ),
        _home_btn()
    )
    return builder.as_markup()


# ============================================================
# YORDAMCHI
# ============================================================

def back_to_main_kb() -> InlineKeyboardMarkup:
    """Asosiy admin panelga qaytish."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔙 Asosiy menyu",
        callback_data=AdminCB(section="main").pack()
    ))
    return builder.as_markup()
