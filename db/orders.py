# ============================================================
# BOTFORGE — db/orders.py
# Buyurtma va savat so'rovlari
# ============================================================

from .pool import get_pool


# ── SAVAT ───────────────────────────────────────────────────

async def get_cart(user_id: int) -> list:
    """
    Foydalanuvchi savatidagi mahsulotlar.
    Narx va stok ma'lumotlari ham birga olinadi.
    """
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                c.id        AS cart_id,
                c.qty,
                p.id        AS product_id,
                p.name      AS product_name,
                p.photo_id,
                p.stock_qty AS product_stock,
                p.discount_active,
                p.discount_value,
                p.discount_type,
                v.id        AS variant_id,
                v.name      AS variant_name,
                v.stock_qty AS variant_stock,
                COALESCE(v.price, p.price) AS unit_price
            FROM cart c
            JOIN products p ON p.id = c.product_id
            LEFT JOIN variants v ON v.id = c.variant_id
            WHERE c.user_id = $1
              AND p.is_deleted = FALSE
              AND p.is_active = TRUE
            ORDER BY c.added_at
        """, user_id)
    return [dict(r) for r in rows]


async def add_to_cart(
    user_id: int,
    product_id: int,
    variant_id: int | None = None,
    qty: int = 1
) -> None:
    """
    Savatga mahsulot qo'shish.
    Allaqachon bor bo'lsa — miqdori oshiriladi.
    """
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO cart (user_id, product_id, variant_id, qty)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, product_id, variant_id)
            DO UPDATE SET qty = cart.qty + EXCLUDED.qty
        """, user_id, product_id, variant_id, qty)


async def update_cart_qty(cart_id: int, qty: int) -> None:
    """Savat elementining miqdorini o'zgartirish."""
    async with get_pool().acquire() as conn:
        await conn.execute("""
            UPDATE cart SET qty = $1 WHERE id = $2
        """, qty, cart_id)


async def remove_from_cart(cart_id: int) -> None:
    """Savatdan bitta mahsulotni o'chirish."""
    async with get_pool().acquire() as conn:
        await conn.execute("""
            DELETE FROM cart WHERE id = $1
        """, cart_id)


async def clear_cart(user_id: int) -> None:
    """Savatni to'liq tozalash."""
    async with get_pool().acquire() as conn:
        await conn.execute("""
            DELETE FROM cart WHERE user_id = $1
        """, user_id)


async def get_cart_total(user_id: int) -> dict:
    """
    Savat umumiy narxi va mahsulotlar soni.
    Chegirma hisobga olinadi.
    """
    cart = await get_cart(user_id)
    total = 0
    item_count = 0

    for item in cart:
        price = float(item["unit_price"])

        if item["discount_active"] and item["discount_value"]:
            val = float(item["discount_value"])
            if item["discount_type"] == "percent":
                price = price - (price * val / 100)
            elif item["discount_type"] == "fixed":
                price = val

        total += price * item["qty"]
        item_count += item["qty"]

    return {
        "total": round(total, 2),
        "item_count": item_count,
        "lines": len(cart)
    }


def _calc_price(item: dict) -> float:
    """
    Mahsulot narxini chegirma bilan hisoblash.
    Ichki yordamchi — tashqaridan chaqirilmaydi.
    """
    price = float(item["unit_price"])
    if item["discount_active"] and item["discount_value"]:
        val = float(item["discount_value"])
        if item["discount_type"] == "percent":
            price = price - (price * val / 100)
        elif item["discount_type"] == "fixed":
            price = val
    return price


# ── BUYURTMALAR ─────────────────────────────────────────────

async def create_order(
    user_id: int,
    total_price: float,
    address: str,
    phone: str,
    note: str | None = None
) -> dict:
    """
    Yangi buyurtma yaratish — bitta transaction ichida:
    1. Savatni o'qish
    2. orders jadvaliga qo'shish
    3. order_items ga ko'chirish
    4. Savatni tozalash
    Biror qadam muvaffaqiyatsiz bo'lsa — hammasi bekor qilinadi.
    """
    # Avval savatni tashqarida o'qiymiz
    cart = await get_cart(user_id)
    if not cart:
        raise ValueError("Savat bo'sh")

    async with get_pool().acquire() as conn:
        async with conn.transaction():

            # 1. Buyurtma yaratish
            order = await conn.fetchrow("""
                INSERT INTO orders
                    (user_id, total_price, address, phone, note)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, order_code
            """, user_id, total_price, address, phone, note)

            order_id = order["id"]

            # 2. Savat → order_items
            for item in cart:
                price = _calc_price(item)
                subtotal = round(price * item["qty"], 2)

                await conn.execute("""
                    INSERT INTO order_items
                        (order_id, product_id, variant_id,
                         product_name, variant_name,
                         price, qty, subtotal)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                    order_id,
                    item["product_id"],
                    item["variant_id"],
                    item["product_name"],
                    item["variant_name"],
                    price,
                    item["qty"],
                    subtotal
                )

            # 3. Savatni tozalash
            await conn.execute("""
                DELETE FROM cart WHERE user_id = $1
            """, user_id)

    return dict(order)


async def get_order(order_id: int) -> dict | None:
    """ID bo'yicha buyurtma (to'liq ma'lumot)."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT o.*,
                   u.username, u.full_name
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            WHERE o.id = $1
        """, order_id)
    return dict(row) if row else None


async def get_order_by_code(order_code: str) -> dict | None:
    """Kod bo'yicha buyurtma (#B10042)."""
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT o.*,
                   u.username, u.full_name
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            WHERE o.order_code = $1
        """, order_code.upper())
    return dict(row) if row else None


async def get_order_items(order_id: int) -> list:
    """Buyurtma tarkibi."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM order_items
            WHERE order_id = $1
            ORDER BY id
        """, order_id)
    return [dict(r) for r in rows]


async def get_user_orders(user_id: int, limit: int = 5) -> list:
    """Foydalanuvchining oxirgi buyurtmalari."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, order_code, status,
                   total_price, created_at
            FROM orders
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """, user_id, limit)
    return [dict(r) for r in rows]


async def get_orders_by_status(
    status: str,
    offset: int = 0,
    limit: int = 10
) -> list:
    """Admin uchun — holat bo'yicha buyurtmalar."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT o.id, o.order_code, o.status,
                   o.total_price, o.created_at,
                   u.full_name, u.phone
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            WHERE o.status = $1
            ORDER BY o.created_at DESC
            LIMIT $2 OFFSET $3
        """, status, limit, offset)
    return [dict(r) for r in rows]


async def count_orders_by_status(status: str) -> int:
    """Holat bo'yicha buyurtmalar soni (pagination uchun)."""
    async with get_pool().acquire() as conn:
        return await conn.fetchval("""
            SELECT COUNT(*) FROM orders WHERE status = $1
        """, status)


async def update_order_status(order_id: int, new_status: str) -> None:
    """
    Buyurtma holatini yangilash.
    pending → confirmed bo'lganda stok kamayadi.
    GREATEST(..., 0) — stok manfiy bo'lmaydi.
    """
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            old = await conn.fetchval("""
                SELECT status FROM orders WHERE id = $1
            """, order_id)

            await conn.execute("""
                UPDATE orders SET status = $1 WHERE id = $2
            """, new_status, order_id)

            if old == "pending" and new_status == "confirmed":
                items = await conn.fetch("""
                    SELECT product_id, variant_id, qty
                    FROM order_items WHERE order_id = $1
                """, order_id)

                for item in items:
                    if item["variant_id"]:
                        await conn.execute("""
                            UPDATE variants
                            SET stock_qty = GREATEST(stock_qty - $1, 0)
                            WHERE id = $2
                        """, item["qty"], item["variant_id"])
                    else:
                        await conn.execute("""
                            UPDATE products
                            SET stock_qty = GREATEST(stock_qty - $1, 0)
                            WHERE id = $2
                        """, item["qty"], item["product_id"])


async def save_payment_photo(order_id: int, file_id: str) -> None:
    """To'lov screenshot ni saqlash."""
    async with get_pool().acquire() as conn:
        await conn.execute("""
            UPDATE orders SET payment_photo = $1 WHERE id = $2
        """, file_id, order_id)


# ── STATISTIKA UCHUN ─────────────────────────────────────────

async def count_orders_today() -> int:
    """Bugungi buyurtmalar soni (mini dashboard)."""
    async with get_pool().acquire() as conn:
        return await conn.fetchval("""
            SELECT COUNT(*) FROM orders
            WHERE created_at >= CURRENT_DATE
              AND status != 'cancelled'
        """)


async def sum_orders_today() -> float:
    """Bugungi daromad (mini dashboard)."""
    async with get_pool().acquire() as conn:
        result = await conn.fetchval("""
            SELECT COALESCE(SUM(total_price), 0)
            FROM orders
            WHERE created_at >= CURRENT_DATE
              AND status IN ('confirmed', 'shipping', 'delivered')
        """)
    return float(result)
