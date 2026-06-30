# ============================================================
# BOTFORGE — utils/validators.py
# Admin input tekshirish
# FSM jarayonida foydalanuvchi kiritgan ma'lumotlarni
# handler ga yetib kelishidan oldin tekshiradi
# ============================================================


# ── NARX ────────────────────────────────────────────────────

def validate_price(text: str) -> tuple[float | None, str | None]:
    """
    Narxni tekshirish.
    "85000" yoki "85 000" → 85000.0
    Xato bo'lsa → (None, xato matni)

    Qaytaradi: (narx, None) yoki (None, xato)
    """
    # Bo'shliq va vergullarni tozalash
    cleaned = text.strip().replace(" ", "").replace(",", "")

    try:
        price = float(cleaned)
    except ValueError:
        return None, "❌ Narx faqat raqam bo'lishi kerak.\nMisol: 85000"

    if price <= 0:
        return None, "❌ Narx 0 dan katta bo'lishi kerak."

    if price > 999_999_999:
        return None, "❌ Narx juda katta. Qaytadan kiriting."

    return price, None


# ── CHEGIRMA ────────────────────────────────────────────────

def validate_discount(text: str) -> tuple[float | None, str | None, str | None]:
    """
    Chegirmani tekshirish va turini aniqlash.

    < 100  → foiz (percent)
    >= 100 → aniq narx (fixed)

    Qaytaradi: (qiymat, tur, None) yoki (None, None, xato)
    """
    cleaned = text.strip().replace(" ", "").replace(",", "")

    try:
        value = float(cleaned)
    except ValueError:
        return None, None, (
            "❌ Chegirma faqat raqam bo'lishi kerak.\n"
            "Misol: 30 (foiz) yoki 45000 (narx)"
        )

    if value <= 0:
        return None, None, "❌ Chegirma 0 dan katta bo'lishi kerak."

    if value >= 100:
        dtype = "fixed"
    else:
        dtype = "percent"

    return value, dtype, None


# ── STOK ────────────────────────────────────────────────────

def validate_stock(text: str) -> tuple[int | None, str | None]:
    """
    Stok miqdorini tekshirish.
    Qaytaradi: (miqdor, None) yoki (None, xato)
    """
    cleaned = text.strip().replace(" ", "")

    try:
        qty = int(cleaned)
    except ValueError:
        return None, "❌ Stok faqat butun son bo'lishi kerak.\nMisol: 50"

    if qty < 0:
        return None, "❌ Stok manfiy bo'lishi mumkin emas."

    if qty > 999_999:
        return None, "❌ Stok juda katta. Qaytadan kiriting."

    return qty, None


# ── MAHSULOT NOMI ────────────────────────────────────────────

def validate_name(text: str, max_len: int = 128) -> tuple[str | None, str | None]:
    """
    Mahsulot yoki kategoriya nomini tekshirish.
    Qaytaradi: (nom, None) yoki (None, xato)
    """
    name = text.strip()

    if not name:
        return None, "❌ Nom bo'sh bo'lishi mumkin emas."

    if len(name) < 2:
        return None, "❌ Nom kamida 2 ta harf bo'lishi kerak."

    if len(name) > max_len:
        return None, f"❌ Nom {max_len} ta belgidan oshmasligi kerak."

    return name, None


# ── TELEFON RAQAMI ───────────────────────────────────────────

def validate_phone(text: str) -> tuple[str | None, str | None]:
    """
    Telefon raqamini tekshirish va formatlash.
    +998901234567 yoki 998901234567 yoki 901234567
    → +998901234567

    Qaytaradi: (raqam, None) yoki (None, xato)
    """
    cleaned = text.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Faqat + va raqamlar
    digits = cleaned.lstrip("+")
    if not digits.isdigit():
        return None, (
            "❌ Telefon raqam noto'g'ri formatda.\n"
            "Misol: +998901234567"
        )

    # O'zbek raqami
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}", None

    # 9 ta raqam (998 siz)
    if len(digits) == 9:
        return f"+998{digits}", None

    return None, (
        "❌ Telefon raqam noto'g'ri.\n"
        "Misol: +998901234567"
    )


# ── VAQT ─────────────────────────────────────────────────────

from datetime import datetime, timedelta


def validate_discount_duration(text: str) -> tuple[datetime | None, str | None]:
    """
    Chegirma davomiyligini tekshirish.
    Admin "24" yoki "2" (soat) yoki "30m" (daqiqa) kiritadi.

    Qaytaradi: (tugash_vaqti, None) yoki (None, xato)
    """
    text = text.strip().lower()

    try:
        if text.endswith("m"):
            minutes = int(text[:-1])
            if minutes < 1 or minutes > 10080:  # max 1 hafta
                raise ValueError
            until = datetime.utcnow() + timedelta(minutes=minutes)
        else:
            hours = int(text)
            if hours < 1 or hours > 168:  # max 1 hafta
                raise ValueError
            until = datetime.utcnow() + timedelta(hours=hours)
    except ValueError:
        return None, (
            "❌ Vaqt noto'g'ri.\n"
            "Soat kiriting: 24 (24 soat)\n"
            "Yoki daqiqa: 30m (30 daqiqa)\n"
            "Maksimum: 168 soat (1 hafta)"
        )

    return until, None


# ── TELEGRAM ID ──────────────────────────────────────────────

def validate_user_id(text: str) -> tuple[int | None, str | None]:
    """
    Telegram foydalanuvchi ID sini tekshirish.
    Admin bloklash yoki xabar yuborishda ishlatadi.
    Qaytaradi: (id, None) yoki (None, xato)
    """
    cleaned = text.strip()

    try:
        user_id = int(cleaned)
    except ValueError:
        return None, (
            "❌ ID faqat raqam bo'lishi kerak.\n"
            "Misol: 123456789"
        )

    if user_id <= 0:
        return None, "❌ ID noto'g'ri."

    return user_id, None
