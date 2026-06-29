# ============================================================
# BOTFORGE — db/users.py
# Foydalanuvchi so'rovlari
# ============================================================

from .pool import get_pool


# ── Asosiy ──────────────────────────────────────────────────

async def get_or_create_user(
    user_id: int,
    username: str | None,
    full_name: str
) -> dict:
    """
    Foydalanuvchi botga kirganida chaqiriladi.
    Bor bo'lsa — last_seen yangilanadi.
    Yo'q bo'lsa — yangi yozuv yaratiladi.
    """
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO users (id, username, full_name, last_seen)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (id) DO UPDATE
                SET username  = EXCLUDED.username,
                    full_name = EXCLUDED.full_name,
                    last_seen = NOW()
            RETURNING *
        """, user_id, username, full_name)
    return dict(row)


async def get_user(user_id: int) -> dict | None:
    """ID bo'yicha foydalanuvchi."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM users WHERE id = $1
        """, user_id)
    return dict(row) if row else None


async def save_phone(user_id: int, phone: str) -> None:
    """
    Foydalanuvchi telefon raqamini bir marta saqlaydi.
    Keyingi buyurtmalarda avtomatik olinadi.
    """
    async with get_pool().acquire() as conn:
        await conn.execute("""
            UPDATE users SET phone = $1 WHERE id = $2
        """, phone, user_id)


async def is_banned(user_id: int) -> bool:
    """Foydalanuvchi bloklanganlgini tekshirish."""
    async with get_pool().acquire() as conn:
        result = await conn.fetchval("""
            SELECT is_banned FROM users WHERE id = $1
        """, user_id)
    # Bazada yo'q bo'lsa — bloklanmagan
    return bool(result)


# ── Admin uchun ─────────────────────────────────────────────

async def get_all_users(offset: int = 0, limit: int = 20) -> list:
    """Barcha foydalanuvchilar (pagination bilan)."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, username, full_name, phone,
                   is_banned, created_at, last_seen
            FROM users
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """, limit, offset)
    return [dict(r) for r in rows]


async def count_users() -> int:
    """Jami foydalanuvchilar soni."""
    async with get_pool().acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")


async def count_new_users_today() -> int:
    """Bugun ro'yxatdan o'tganlar soni."""
    async with get_pool().acquire() as conn:
        return await conn.fetchval("""
            SELECT COUNT(*) FROM users
            WHERE created_at >= CURRENT_DATE
        """)


async def search_user(query: str) -> list:
    """
    ID, username yoki ism bo'yicha qidirish.
    Admin foydalanuvchini topishi uchun.
    """
    async with get_pool().acquire() as conn:
        # Agar to'liq raqam bo'lsa — ID bo'yicha qidirish
        if query.lstrip("-").isdigit():
            rows = await conn.fetch("""
                SELECT id, username, full_name, phone, is_banned
                FROM users WHERE id = $1
            """, int(query))
        else:
            rows = await conn.fetch("""
                SELECT id, username, full_name, phone, is_banned
                FROM users
                WHERE username ILIKE $1
                   OR full_name ILIKE $1
                LIMIT 10
            """, f"%{query}%")
    return [dict(r) for r in rows]


async def ban_user(user_id: int) -> bool:
    """
    Foydalanuvchini bloklash.
    Topilmasa — False qaytaradi.
    """
    async with get_pool().acquire() as conn:
        result = await conn.execute("""
            UPDATE users SET is_banned = TRUE
            WHERE id = $1 AND is_banned = FALSE
        """, user_id)
    # "UPDATE 1" → muvaffaqiyatli, "UPDATE 0" → topilmadi yoki allaqachon ban
    return result == "UPDATE 1"


async def unban_user(user_id: int) -> bool:
    """
    Foydalanuvchini blokdan chiqarish.
    Topilmasa — False qaytaradi.
    """
    async with get_pool().acquire() as conn:
        result = await conn.execute("""
            UPDATE users SET is_banned = FALSE
            WHERE id = $1 AND is_banned = TRUE
        """, user_id)
    return result == "UPDATE 1"


async def get_all_user_ids() -> list[int]:
    """
    Barcha aktiv (banlanmagan) foydalanuvchilar ID lari.
    Broadcast (ommaviy xabar) uchun ishlatiladi.
    """
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id FROM users
            WHERE is_banned = FALSE
            ORDER BY id
        """)
    return [r["id"] for r in rows]


# ── SOZLAMALAR ───────────────────────────────────────────────
# Bu funksiya settings jadvalidan qiymat oladi.
# users.py da emas, aslida alohida db/settings.py bo'lishi kerak edi,
# lekin loyiha hajmiga qarab shu yerga qo'shildi.

async def get_setting(key: str, default: str = "") -> str:
    """settings jadvalidan qiymat olish."""
    async with get_pool().acquire() as conn:
        value = await conn.fetchval("""
            SELECT value FROM settings WHERE key = $1
        """, key)
    return value if value is not None else default


async def set_setting(key: str, value: str) -> None:
    """settings jadvalida qiymat yangilash."""
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO settings (key, value)
            VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, key, value)
