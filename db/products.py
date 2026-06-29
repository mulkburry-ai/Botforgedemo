# ============================================================
# BOTFORGE — db/products.py
# Mahsulot so'rovlari
# ============================================================

from .pool import get_pool


# ── Foydalanuvchi uchun ─────────────────────────────────────

async def get_products(category_id: int) -> list:
    """Kategoriya bo'yicha aktiv mahsulotlar."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, price,
                   discount_value, discount_type, discount_active,
                   photo_id, stock_qty, is_active
            FROM products
            WHERE category_id = $1
              AND is_active = TRUE
              AND is_deleted = FALSE
            ORDER BY name
        """, category_id)
    return [dict(r) for r in rows]


async def get_product(product_id: int) -> dict | None:
    """ID bo'yicha bitta mahsulot (to'liq ma'lumot)."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT p.*,
                   c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.id = $1 AND p.is_deleted = FALSE
        """, product_id)
    return dict(row) if row else None


async def get_variants(product_id: int) -> list:
    """Mahsulot turlari."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, price, photo_id, stock_qty
            FROM variants
            WHERE product_id = $1 AND is_active = TRUE
            ORDER BY id
        """, product_id)
    return [dict(r) for r in rows]




async def search_products(query: str) -> list:
    """Nom bo'yicha qidirish (foydalanuvchi uchun)."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, price,
                   discount_value, discount_type, discount_active,
                   photo_id, stock_qty
            FROM products
            WHERE is_active = TRUE AND is_deleted = FALSE
              AND name ILIKE $1
            ORDER BY name
            LIMIT 20
        """, f"%{query}%")
    return [dict(r) for r in rows]


# ── Sevimlilar ──────────────────────────────────────────────

async def add_favorite(user_id: int, product_id: int) -> None:
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO favorites (user_id, product_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """, user_id, product_id)


async def remove_favorite(user_id: int, product_id: int) -> None:
    async with get_pool().acquire() as conn:
        await conn.execute("""
            DELETE FROM favorites
            WHERE user_id = $1 AND product_id = $2
        """, user_id, product_id)


async def get_favorites(user_id: int) -> list:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.id, p.name, p.price, p.photo_id,
                   p.discount_value, p.discount_type, p.discount_active
            FROM favorites f
            JOIN products p ON p.id = f.product_id
            WHERE f.user_id = $1
              AND p.is_active = TRUE
              AND p.is_deleted = FALSE
            ORDER BY f.added_at DESC
        """, user_id)
    return [dict(r) for r in rows]


async def is_favorite(user_id: int, product_id: int) -> bool:
    async with get_pool().acquire() as conn:
        row = await conn.fetchval("""
            SELECT 1 FROM favorites
            WHERE user_id = $1 AND product_id = $2
        """, user_id, product_id)
    return bool(row)


# ── Oxirgi ko'rilganlar (max 10 ta) ─────────────────────────

async def add_last_seen(user_id: int, product_id: int) -> None:
    async with get_pool().acquire() as conn:
        # Qo'shish yoki vaqtni yangilash
        await conn.execute("""
            INSERT INTO last_seen (user_id, product_id, seen_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (user_id, product_id)
            DO UPDATE SET seen_at = NOW()
        """, user_id, product_id)

        # 10 tadan ortiq bo'lsa eskisini o'chirish
        await conn.execute("""
            DELETE FROM last_seen
            WHERE user_id = $1
              AND product_id NOT IN (
                  SELECT product_id FROM last_seen
                  WHERE user_id = $1
                  ORDER BY seen_at DESC
                  LIMIT 10
              )
        """, user_id)


async def get_last_seen(user_id: int) -> list:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.id, p.name, p.price, p.photo_id,
                   p.discount_value, p.discount_type, p.discount_active
            FROM last_seen ls
            JOIN products p ON p.id = ls.product_id
            WHERE ls.user_id = $1
              AND p.is_active = TRUE
              AND p.is_deleted = FALSE
            ORDER BY ls.seen_at DESC
            LIMIT 10
        """, user_id)
    return [dict(r) for r in rows]


# ── Admin uchun ─────────────────────────────────────────────

async def get_all_products_admin(
    category_id: int | None = None,
    offset: int = 0,
    limit: int = 20
) -> list:
    """
    Admin uchun — o\'chirilmagan barcha mahsulotlar.
    offset/limit — pagination uchun (20 tadan ko\'rsatiladi).
    """
    async with get_pool().acquire() as conn:
        if category_id:
            rows = await conn.fetch("""
                SELECT id, name, price, stock_qty, is_active, category_id
                FROM products
                WHERE is_deleted = FALSE AND category_id = $1
                ORDER BY id DESC
                LIMIT $2 OFFSET $3
            """, category_id, limit, offset)
        else:
            rows = await conn.fetch("""
                SELECT id, name, price, stock_qty, is_active, category_id
                FROM products
                WHERE is_deleted = FALSE
                ORDER BY id DESC
                LIMIT $1 OFFSET $2
            """, limit, offset)
    return [dict(r) for r in rows]


async def count_products_admin(category_id: int | None = None) -> int:
    """Pagination uchun — jami mahsulotlar soni."""
    async with get_pool().acquire() as conn:
        if category_id:
            return await conn.fetchval("""
                SELECT COUNT(*) FROM products
                WHERE is_deleted = FALSE AND category_id = $1
            """, category_id)
        return await conn.fetchval("""
            SELECT COUNT(*) FROM products
            WHERE is_deleted = FALSE
        """)


async def add_product(data: dict) -> int:
    """Yangi mahsulot qo'shish. ID qaytaradi."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO products
                (category_id, name, description, price,
                 photo_id, gallery_ids, stock_qty, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """,
            data.get("category_id"),
            data["name"],
            data.get("description", ""),
            data["price"],
            data.get("photo_id"),
            data.get("gallery_ids", []),
            data.get("stock_qty", 0),
            data.get("is_active", True)
        )
    return row["id"]


async def update_product(product_id: int, data: dict) -> None:
    """Mahsulot maydonlarini yangilash."""
    allowed = {
        "name", "description", "price", "category_id",
        "photo_id", "gallery_ids", "stock_qty", "is_active",
        "discount_value", "discount_type",
        "discount_until", "discount_active"
    }
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return

    # sorted() — har safar bir xil tartib, xavfsiz
    sorted_fields = sorted(fields.items())
    set_clause = ", ".join(
        f"{k} = ${i+2}" for i, (k, _) in enumerate(sorted_fields)
    )
    values = [v for _, v in sorted_fields]

    async with get_pool().acquire() as conn:
        await conn.execute(
            f"UPDATE products SET {set_clause} WHERE id = $1",
            product_id, *values
        )


async def soft_delete_product(product_id: int) -> None:
    """Mahsulotni o'chirish (soft delete — bazadan ketmaydi)."""
    async with get_pool().acquire() as conn:
        await conn.execute("""
            UPDATE products SET is_deleted = TRUE WHERE id = $1
        """, product_id)


async def add_variant(product_id: int, data: dict) -> int:
    """Mahsulotga tur qo'shish."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO variants (product_id, name, price, photo_id, stock_qty)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """,
            product_id,
            data["name"],
            data.get("price"),
            data.get("photo_id"),
            data.get("stock_qty", 0)
        )
    return row["id"]


async def update_stock(product_id: int, qty_delta: int,
                       variant_id: int | None = None) -> None:
    """
    Stokni kamaytirish yoki oshirish.
    qty_delta: -2 = 2 ta kamaydi, +5 = 5 ta qo'shildi
    """
    async with get_pool().acquire() as conn:
        if variant_id:
            await conn.execute("""
                UPDATE variants
                SET stock_qty = stock_qty + $1
                WHERE id = $2
            """, qty_delta, variant_id)
        else:
            await conn.execute("""
                UPDATE products
                SET stock_qty = stock_qty + $1
                WHERE id = $2
            """, qty_delta, product_id)


async def deactivate_discount(product_id: int) -> None:
    """Vaqtli chegirmani o'chirish (scheduler chaqiradi)."""
    async with get_pool().acquire() as conn:
        await conn.execute("""
            UPDATE products
            SET discount_active = FALSE,
                discount_until = NULL
            WHERE id = $1
        """, product_id)


async def get_expired_discounts() -> list:
    """Vaqti o'tgan chegirmalar (scheduler uchun)."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id FROM products
            WHERE discount_active = TRUE
              AND discount_until IS NOT NULL
              AND discount_until < NOW()
              AND is_deleted = FALSE
        """)
    return [r["id"] for r in rows]


async def get_low_stock_products(threshold: int = 5) -> list:
    """Stok kam mahsulotlar (admin ogohlantirish uchun)."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, stock_qty FROM products
            WHERE is_deleted = FALSE
              AND is_active = TRUE
              AND stock_qty <= $1
              AND stock_qty > 0
            ORDER BY stock_qty ASC
        """, threshold)
    return [dict(r) for r in rows]
