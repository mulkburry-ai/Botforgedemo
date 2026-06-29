# ============================================================
# BOTFORGE — db/categories.py
# Kategoriya va subkategoriya so'rovlari
# ============================================================

from .pool import get_pool


async def get_main_categories() -> list:
    """Asosiy kategoriyalar (parent_id = NULL)."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, sort_order
            FROM categories
            WHERE parent_id IS NULL AND is_active = TRUE
            ORDER BY sort_order, name
        """)
    return [dict(r) for r in rows]


async def get_subcategories(parent_id: int) -> list:
    """Berilgan kategoriyaning subkategoriyalari."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, sort_order
            FROM categories
            WHERE parent_id = $1 AND is_active = TRUE
            ORDER BY sort_order, name
        """, parent_id)
    return [dict(r) for r in rows]


async def get_category(cat_id: int) -> dict | None:
    """ID bo'yicha bitta kategoriya."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, name, parent_id, is_active
            FROM categories WHERE id = $1
        """, cat_id)
    return dict(row) if row else None


async def get_all_categories() -> list:
    """Admin uchun — barcha kategoriyalar (aktiv va passiv)."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT c.id, c.name, c.parent_id, c.is_active,
                   p.name AS parent_name
            FROM categories c
            LEFT JOIN categories p ON p.id = c.parent_id
            ORDER BY c.parent_id NULLS FIRST, c.sort_order, c.name
        """)
    return [dict(r) for r in rows]


async def add_category(name: str, parent_id: int | None = None) -> int:
    """Yangi kategoriya yoki subkategoriya qo'shish. ID qaytaradi."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO categories (name, parent_id)
            VALUES ($1, $2)
            RETURNING id
        """, name, parent_id)
    return row["id"]


async def delete_category(cat_id: int) -> bool:
    """
    Kategoriyani o'chirish.
    Ichida mahsulot YOKI subkategoriya bo'lsa — o'chmaydi, False qaytaradi.
    """
    async with get_pool().acquire() as conn:
        # Mahsulot borligini tekshirish
        product_count = await conn.fetchval("""
            SELECT COUNT(*) FROM products
            WHERE category_id = $1 AND is_deleted = FALSE
        """, cat_id)
        if product_count > 0:
            return False

        # Subkategoriya borligini tekshirish
        sub_count = await conn.fetchval("""
            SELECT COUNT(*) FROM categories
            WHERE parent_id = $1
        """, cat_id)
        if sub_count > 0:
            return False

        await conn.execute("""
            DELETE FROM categories WHERE id = $1
        """, cat_id)
    return True


async def has_subcategories(cat_id: int) -> bool:
    """Kategoriyada subkategoriya borligini tekshirish."""
    async with get_pool().acquire() as conn:
        count = await conn.fetchval("""
            SELECT COUNT(*) FROM categories
            WHERE parent_id = $1 AND is_active = TRUE
        """, cat_id)
    return count > 0
