# ============================================================
# BOTFORGE — db/__init__.py
# Barcha DB funksiyalarini bir joydan import qilish uchun
# ============================================================

# Ulanish
from .pool import create_pool, close_pool, get_pool

# Kategoriyalar
from .categories import (
    get_main_categories, get_subcategories, get_category,
    get_all_categories, add_category, delete_category,
    has_subcategories,
)

# Mahsulotlar
from .products import (
    get_products, get_product, get_variants,
    search_products,
    add_favorite, remove_favorite, get_favorites, is_favorite,
    add_last_seen, get_last_seen,
    get_all_products_admin, count_products_admin,
    add_product, update_product, soft_delete_product,
    add_variant, update_stock,
    deactivate_discount, get_expired_discounts,
    get_low_stock_products,
)

# Foydalanuvchilar
from .users import (
    get_or_create_user, get_user, save_phone, is_banned,
    get_all_users, count_users, count_new_users_today,
    search_user, ban_user, unban_user, get_all_user_ids,
    get_setting, set_setting,
)

# Buyurtmalar va savat
from .orders import (
    get_cart, add_to_cart, update_cart_qty,
    remove_from_cart, clear_cart, get_cart_total,
    create_order, get_order, get_order_by_code,
    get_order_items, get_user_orders,
    get_orders_by_status, count_orders_by_status,
    update_order_status, save_payment_photo,
    count_orders_today, sum_orders_today,
)

# Statistika
from .stats import (
    get_dashboard, get_full_stats, get_revenue_stats,
    get_top_products, get_least_products,
    get_all_orders_for_export, get_all_products_for_export,
)
