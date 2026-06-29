# ============================================================
# BOTFORGE — db/pool.py
# Neon PostgreSQL ulanish va pool boshqaruvi
# ============================================================

import asyncpg
import logging
from config import DATABASE_URL

logger = logging.getLogger(__name__)

# Global pool — butun bot davomida bitta ishlatiladi
_pool: asyncpg.Pool = None


async def create_pool() -> None:
    """
    Bot ishga tushganda bir marta chaqiriladi.
    Neon bilan 2-10 ta parallel ulanish ochadi.
    """
    global _pool
    _pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60,
        ssl="require"          # Neon majburiy SSL talab qiladi
    )
    logger.info("✅ Neon PostgreSQL pool yaratildi")


async def close_pool() -> None:
    """Bot to'xtaganda chaqiriladi — ulanishlar yopiladi."""
    global _pool
    if _pool:
        await _pool.close()
        logger.info("🔌 Neon PostgreSQL pool yopildi")


def get_pool() -> asyncpg.Pool:
    """
    Har bir DB so'rovdan oldin chaqiriladi.
    Pool tayyor bo'lmasa — tushunarli xato beradi.
    """
    if _pool is None:
        raise RuntimeError(
            "❌ DB pool hali yaratilmagan!\n"
            "   main.py da create_pool() chaqirilganini tekshiring."
        )
    return _pool
