# ============================================================
# BOTFORGE — config.py
# Barcha sozlamalar va .env validatsiya
# ============================================================

import os
import logging

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ── Yordamchi funksiya ───────────────────────────────────────
def _require(key: str) -> str:
    """
    .env da majburiy o'zgaruvchini oladi.
    Topilmasa — bot ishga tushmaydi va xato ko'rsatadi.
    """
    value = os.environ.get(key, "").strip()
    if not value:
        raise ValueError(
            f"\n❌ XATO: '{key}' topilmadi!\n"
            f"   .env faylida yoki Render Environment da '{key}' ni yozing.\n"
            f"   Namuna uchun .env.example faylini ko'ring."
        )
    return value


def _optional(key: str, default: str = "") -> str:
    """Ixtiyoriy o'zgaruvchi — topilmasa default qiymat qaytaradi."""
    return os.environ.get(key, default).strip()


# ── Majburiy o'zgaruvchilar ──────────────────────────────────
BOT_TOKEN    = _require("BOT_TOKEN")       # Telegram bot tokeni
DATABASE_URL = _require("DATABASE_URL")    # Neon PostgreSQL URL
ADMIN_ID     = int(_require("ADMIN_ID"))   # Admin Telegram ID (raqam)

# ── Ixtiyoriy o'zgaruvchilar ────────────────────────────────
ADMIN_USERNAME     = _optional("ADMIN_USERNAME", "@admin")
WEBHOOK_HOST       = _optional("WEBHOOK_HOST")   # Render URL (webhook uchun)
MIN_ORDER_SUM      = int(_optional("MIN_ORDER_SUM", "0"))   # Minimal buyurtma summasi
LOW_STOCK_ALERT    = int(_optional("LOW_STOCK_ALERT", "5")) # Stok ogohlantirish chegarasi

# ── Webhook sozlamalari ──────────────────────────────────────
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL  = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else None

# Webhook URL yo'q bo'lsa — polling rejimida ishlaydi
USE_WEBHOOK = bool(WEBHOOK_HOST)

# ── Tekshiruv natijasi ───────────────────────────────────────
logger.info("✅ config.py yuklandi")
logger.info(f"   ADMIN_ID     : {ADMIN_ID}")
logger.info(f"   USE_WEBHOOK  : {USE_WEBHOOK}")
logger.info(f"   MIN_ORDER_SUM: {MIN_ORDER_SUM} so'm")
logger.info(f"   LOW_STOCK    : {LOW_STOCK_ALERT} donadan kam bo'lsa ogohlantirish")
