# ============================================================
# BOTFORGE — utils/formatters.py
# Barcha matn va raqamlarni chiroyli formatlash
# Barcha handlerlar shu fayldan foydalanadi
# ============================================================

from datetime import datetime


# ── NARX ────────────────────────────────────────────────────

def fmt_price(amount: float | int) -> str:
    """
    Narxni o'qilishi qulay formatga o'tkazish.
    85000 → "85 000 so'm"
    """
    return f"{int(amount):,} so'm".replace(",", " ")


def fmt_price_with_discount(price: float, discount_value: float,
                             discount_type: str) -> str:
    """
    Chegirmali narxni ko'rsatish.
    Eski narx ustiga chiziladi, yangi narx ko'rsatiladi.
    Misol: ~~100 000 so'm~~ → 70 000 so'm
    """
    if discount_type == "percent":
        final = price - (price * discount_value / 100)
    else:
        final = discount_value

    return f"~~{fmt_price(price)}~~ → *{fmt_price(final)}*"


def calc_final_price(price: float, discount_value: float | None,
                     discount_type: str | None,
                     discount_active: bool) -> float:
    """
    Chegirma hisoblab yakuniy narxni qaytaradi.
    Handler va keyboard uchun ochiq versiya.
    (orders.py dagi _calc_price ichki versiya — u tashqaridan chaqirilmaydi)
    """
    if not discount_active or not discount_value:
        return price
    if discount_type == "percent":
        return price - (price * discount_value / 100)
    if discount_type == "fixed":
        return float(discount_value)
    return price


# ── SANA VA VAQT ─────────────────────────────────────────────

MONTHS = {
    1: "yanvar", 2: "fevral",  3: "mart",
    4: "aprel",  5: "may",     6: "iyun",
    7: "iyul",   8: "avgust",  9: "sentabr",
    10: "oktabr", 11: "noyabr", 12: "dekabr"
}


def fmt_date(dt: datetime) -> str:
    """27 iyun, 14:30"""
    return f"{dt.day} {MONTHS[dt.month]}, {dt.strftime('%H:%M')}"


def fmt_date_short(dt: datetime) -> str:
    """27.06.2024"""
    return dt.strftime("%d.%m.%Y")


# ── BUYURTMA HOLATI ──────────────────────────────────────────

ORDER_STATUS = {
    "pending":   ("🆕", "Yangi"),
    "confirmed": ("✅", "Tasdiqlandi"),
    "shipping":  ("🚚", "Yo'lda"),
    "delivered": ("📦", "Yetkazildi"),
    "cancelled": ("❌", "Bekor qilindi"),
    "problem":   ("⚠️", "Muammo bor"),
}


def fmt_status(status: str) -> str:
    """'shipping' → '🚚 Yo'lda'"""
    emoji, text = ORDER_STATUS.get(status, ("❓", status))
    return f"{emoji} {text}"


def fmt_order_progress(status: str) -> str:
    """
    Foydalanuvchiga buyurtma bosqichlari ko'rsatiladi.

    ✅ Qabul qilindi
    ✅ Tasdiqlandi
    🚚 Yo'lda  ← hozir
    ⚪ Yetkazildi
    """
    if status == "cancelled":
        return "❌ Buyurtma bekor qilindi"
    if status == "problem":
        return "⚠️ Buyurtmada muammo bor — admin bilan bog'laning"

    steps = ["pending", "confirmed", "shipping", "delivered"]
    lines = []
    reached = False

    for step in steps:
        emoji, label = ORDER_STATUS[step]
        if step == status:
            lines.append(f"{emoji} *{label}*  ← hozir")
            reached = True
        elif not reached:
            lines.append(f"✅ {label}")
        else:
            lines.append(f"⚪ {label}")

    return "\n".join(lines)


# ── MAHSULOT KARTASI ─────────────────────────────────────────

def fmt_product_card(p: dict, variant: dict | None = None,
                     low_stock_threshold: int = 5,
                     effective_stock: dict | None = None) -> str:
    """
    Foydalanuvchiga ko'rsatiladigan mahsulot kartasi matni.
    p — mahsulot, variant — tanlangan tur (ixtiyoriy).

    effective_stock — get_effective_stock() natijasi (ixtiyoriy).
    Agar variant tanlanmagan bo'lsa-yu, mahsulotda turlar bo'lsa,
    stok shu yerdan (turlar yig'indisi) olinadi — p['stock_qty']
    emas, chunki u turlar bo'lganda ma'nosiz (odatda 0) bo'ladi.
    """
    if variant:
        price = float(variant["price"] if variant["price"] else p["price"])
        stock = int(variant["stock_qty"])
    elif effective_stock and effective_stock.get("has_variants"):
        price = float(p["price"])
        stock = int(effective_stock["total_stock"])
    else:
        price = float(p["price"])
        stock = int(p["stock_qty"])

    lines = [f"*{p['name']}*", f"🆔 `#{p['id']}`"]

    # Narx
    if p.get("discount_active") and p.get("discount_value"):
        lines.append(
            f"💰 {fmt_price_with_discount(price, p['discount_value'], p['discount_type'])}"
        )
    else:
        lines.append(f"💰 *{fmt_price(price)}*")

    # Stok holati
    if stock == 0:
        lines.append("🚫 *Mahsulot tugagan*")
    elif stock <= low_stock_threshold:
        lines.append(f"⚠️ Faqat *{stock} dona* qoldi!")

    # Tavsif
    if p.get("description"):
        lines.append(f"\n📋 {p['description']}")

    # Tanlangan tur
    if variant:
        lines.append(f"\n🎨 Tur: *{variant['name']}*")

    return "\n".join(lines)


def fmt_product_admin(p: dict, effective_stock: dict | None = None) -> str:
    """
    Admin uchun mahsulot ma'lumotlari.

    effective_stock — get_effective_stock() natijasi (ixtiyoriy).
    Berilsa va turlar mavjud bo'lsa, "umumiy stok" turlar yig'indisidan
    ko'rsatiladi (p['stock_qty'] emas — u turlar bo'lganda 0 va
    ma'nosiz bo'ladi).
    """
    lines = [
        f"*{p['name']}*",
        f"🆔 `#{p['id']}`",
        f"💰 {fmt_price(p['price'])}",
    ]

    if effective_stock and effective_stock.get("has_variants"):
        lines.append(f"📦 Umumiy stok: *{effective_stock['total_stock']} dona* (turlardan)")
    else:
        lines.append(f"📦 Stok: {p['stock_qty']} dona")

    if p.get("discount_active") and p.get("discount_value"):
        val = p["discount_value"]
        if p["discount_type"] == "percent":
            lines.append(f"🏷 Chegirma: {int(val)}%")
        else:
            lines.append(f"🏷 Chegirma narxi: {fmt_price(val)}")
        if p.get("discount_until"):
            lines.append(f"⏰ Tugaydi: {fmt_date(p['discount_until'])}")

    if not p.get("is_active"):
        lines.append("🔴 *Nofaol*")

    return "\n".join(lines)


# ── SAVAT ────────────────────────────────────────────────────

def fmt_cart(items: list, total: float) -> str:
    """Savat tarkibini chiroyli ko'rsatish."""
    if not items:
        return "🧺 Savatingiz bo'sh"

    lines = ["🧺 *Savat:*\n"]
    for i, item in enumerate(items, 1):
        price = calc_final_price(
            float(item["unit_price"]),
            item.get("discount_value"),
            item.get("discount_type"),
            item.get("discount_active", False)
        )
        name = item["product_name"]
        if item.get("variant_name"):
            name += f" ({item['variant_name']})"
        lines.append(
            f"{i}. {name}\n"
            f"   {item['qty']} × {fmt_price(price)} = *{fmt_price(price * item['qty'])}*"
        )

    lines.append(f"\n💳 *Jami: {fmt_price(total)}*")
    return "\n".join(lines)


# ── BUYURTMA ─────────────────────────────────────────────────

def fmt_order_card(order: dict, items: list) -> str:
    """Buyurtma kartasi — foydalanuvchi va admin uchun."""
    lines = [
        f"🧾 *Buyurtma #{order['order_code']}*",
        f"📅 {fmt_date(order['created_at'])}",
        f"📊 {fmt_status(order['status'])}",
        "\n*Tarkibi:*"
    ]

    for item in items:
        name = item["product_name"]
        if item.get("variant_name"):
            name += f" ({item['variant_name']})"
        lines.append(f"• {name} × {item['qty']} = {fmt_price(item['subtotal'])}")

    lines += [
        f"\n💳 *Jami: {fmt_price(order['total_price'])}*",
        f"📍 Manzil: {order.get('address', '—')}",
        f"📱 Telefon: {order.get('phone', '—')}",
    ]

    if order.get("note"):
        lines.append(f"📝 Izoh: {order['note']}")

    return "\n".join(lines)


# ── ADMIN DASHBOARD ──────────────────────────────────────────

def fmt_dashboard(data: dict) -> str:
    """Admin paneli ochilganda ko'rinadigan mini dashboard."""
    lines = [
        "━━━━━━━━━━━━━━━━━━",
        f"🛍 Buyurtmalar: *{data['orders_today']}*    "
        f"💰 *{fmt_price(data['revenue_today'])}*",
        f"👥 Yangi: *{data['new_users_today']}*         "
        f"⚠️ Tugayapti: *{data['low_stock_count']}*",
    ]
    if data["pending_orders"] > 0:
        lines.append(
            f"\n🔔 Tasdiqlanmagan: *{data['pending_orders']} ta buyurtma*"
        )
    lines.append("━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
