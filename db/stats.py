# ============================================================
# BOTFORGE — db/stats.py
# Statistika so'rovlari (admin Ma'lumotlar bo'limi)
# ============================================================

from .pool import get_pool


# ── MINI DASHBOARD (admin panelni ochganda) ─────────────────

async def get_dashboard() -> dict:
    """
    Admin panelini ochganda ko'rinadigan qisqa ma'lumotlar.
    Barcha so'rovlar bitta ulanishda bajariladi — tez ishlaydi.
    """
    async with get_pool().acquire() as conn:

        orders_today = await conn.fetchval("""
            SELECT COUNT(*) FROM orders
            WHERE created_at >= CURRENT_DATE
              AND status != 'cancelled'
        """)

        revenue_today = await conn.fetchval("""
            SELECT COALESCE(SUM(total_price), 0)
            FROM orders
            WHERE created_at >= CURRENT_DATE
              AND status IN ('confirmed', 'shipping', 'delivered')
        """)

        new_users_today = await conn.fetchval("""
            SELECT COUNT(*) FROM users
            WHERE created_at >= CURRENT_DATE
        """)

        low_stock_count = await conn.fetchval("""
            SELECT COUNT(*) FROM products
            WHERE is_deleted = FALSE
              AND is_active = TRUE
              AND stock_qty > 0
              AND stock_qty <= 5
        """)

        pending_orders = await conn.fetchval("""
            SELECT COUNT(*) FROM orders
            WHERE status = 'pending'
        """)

    return {
        "orders_today":    int(orders_today),
        "revenue_today":   float(revenue_today),
        "new_users_today": int(new_users_today),
        "low_stock_count": int(low_stock_count),
        "pending_orders":  int(pending_orders),
    }


# ── TO'LIQ STATISTIKA ───────────────────────────────────────

async def get_full_stats() -> dict:
    """
    Admin 'Statistika' tugmasini bosganida ko'rinadigan
    kengaytirilgan ma'lumotlar.
    """
    async with get_pool().acquire() as conn:

        total_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users"
        )
        banned_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE is_banned = TRUE"
        )
        total_products = await conn.fetchval(
            "SELECT COUNT(*) FROM products WHERE is_deleted = FALSE"
        )
        active_products = await conn.fetchval("""
            SELECT COUNT(*) FROM products
            WHERE is_deleted = FALSE AND is_active = TRUE
        """)
        total_orders = await conn.fetchval(
            "SELECT COUNT(*) FROM orders"
        )
        delivered_orders = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE status = 'delivered'"
        )
        cancelled_orders = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE status = 'cancelled'"
        )
        total_revenue = await conn.fetchval("""
            SELECT COALESCE(SUM(total_price), 0)
            FROM orders
            WHERE status IN ('confirmed', 'shipping', 'delivered')
        """)

        # Umumiy tovarlar qiymati (stok * narx)
        total_stock_value = await conn.fetchval("""
            SELECT COALESCE(
                SUM(
                    CASE
                        WHEN discount_active = TRUE AND discount_type = 'fixed'
                            THEN discount_value * stock_qty
                        WHEN discount_active = TRUE AND discount_type = 'percent'
                            THEN (price - price * discount_value / 100) * stock_qty
                        ELSE price * stock_qty
                    END
                ), 0
            )
            FROM products
            WHERE is_deleted = FALSE AND is_active = TRUE
        """)

    return {
        "total_users":      int(total_users),
        "banned_users":     int(banned_users),
        "total_products":   int(total_products),
        "active_products":  int(active_products),
        "total_orders":     int(total_orders),
        "delivered_orders": int(delivered_orders),
        "cancelled_orders": int(cancelled_orders),
        "total_revenue":    float(total_revenue),
        "total_stock_value": float(total_stock_value),
    }


# ── DAROMAD ─────────────────────────────────────────────────

async def get_revenue_stats() -> dict:
    """
    Daromad: bugun, bu hafta, bu oy, jami.
    """
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(CASE
                    WHEN created_at >= CURRENT_DATE
                    THEN total_price END), 0)          AS today,

                COALESCE(SUM(CASE
                    WHEN created_at >= DATE_TRUNC('week', NOW())
                    THEN total_price END), 0)          AS this_week,

                COALESCE(SUM(CASE
                    WHEN created_at >= DATE_TRUNC('month', NOW())
                    THEN total_price END), 0)          AS this_month,

                COALESCE(SUM(total_price), 0)          AS total

            FROM orders
            WHERE status IN ('confirmed', 'shipping', 'delivered')
        """)

    return {
        "today":      float(row["today"]),
        "this_week":  float(row["this_week"]),
        "this_month": float(row["this_month"]),
        "total":      float(row["total"]),
    }


# ── TOP VA KAM SOTILGANLAR ───────────────────────────────────

async def get_top_products(limit: int = 5) -> list:
    """Eng ko'p sotilgan mahsulotlar."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                p.id,
                p.name,
                p.price,
                SUM(oi.qty)      AS total_qty,
                SUM(oi.subtotal) AS total_revenue
            FROM order_items oi
            JOIN products p ON p.id = oi.product_id
            JOIN orders o   ON o.id = oi.order_id
            WHERE o.status IN ('confirmed', 'shipping', 'delivered')
              AND p.is_deleted = FALSE
            GROUP BY p.id, p.name, p.price
            ORDER BY total_qty DESC
            LIMIT $1
        """, limit)
    return [dict(r) for r in rows]


async def get_least_products(limit: int = 5) -> list:
    """Eng kam sotilgan (yoki umuman sotilmagan) mahsulotlar."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                p.id,
                p.name,
                p.price,
                p.stock_qty,
                COALESCE(SUM(oi.qty), 0) AS total_qty
            FROM products p
            LEFT JOIN order_items oi ON oi.product_id = p.id
            LEFT JOIN orders o       ON o.id = oi.order_id
                AND o.status IN ('confirmed', 'shipping', 'delivered')
            WHERE p.is_deleted = FALSE
              AND p.is_active = TRUE
            GROUP BY p.id, p.name, p.price, p.stock_qty
            ORDER BY total_qty ASC
            LIMIT $1
        """, limit)
    return [dict(r) for r in rows]


# ── EXCEL BEKAP UCHUN ────────────────────────────────────────

async def get_all_orders_for_export() -> list:
    """
    Barcha buyurtmalar — Excel ga eksport qilish uchun.
    scheduler.py va admin handler chaqiradi.
    """
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                o.order_code,
                o.status,
                o.total_price,
                o.address,
                o.phone        AS order_phone,
                o.note,
                o.created_at,
                u.full_name,
                u.username,
                u.phone        AS user_phone
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            ORDER BY o.created_at DESC
        """)
    return [dict(r) for r in rows]


async def get_all_products_for_export() -> list:
    """
    Barcha mahsulotlar — Excel ga eksport qilish uchun.
    """
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                p.id,
                p.name,
                c.name    AS category,
                p.price,
                p.stock_qty,
                p.discount_active,
                p.discount_value,
                p.discount_type,
                p.is_active,
                p.created_at
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.is_deleted = FALSE
            ORDER BY p.id
        """)
    return [dict(r) for r in rows]
