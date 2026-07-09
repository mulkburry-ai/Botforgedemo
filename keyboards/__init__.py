# ============================================================
# BOTFORGE — keyboards/__init__.py
# ============================================================

# Foydalanuvchi klaviaturalari
from .user import (
    # CallbackData classlari
    CatalogCB, ProductCB, CartCB, OrderCB, InfoCB,
    # Reply
    main_menu_kb, phone_kb,
    # Katalog
    categories_kb, subcategories_kb, products_list_kb,
    # Mahsulot
    product_card_kb, variant_select_kb, qty_select_kb,
    # Savat
    cart_kb, checkout_confirm_kb, order_final_confirm_kb,
    # Buyurtmalar
    orders_list_kb, order_detail_kb,
    # Ma'lumot
    info_kb, info_back_kb,
)

# Admin klaviaturalari
from .admin import (
    # CallbackData classlari
    AdminCB, ProductAdminCB, OrderAdminCB, UserAdminCB, StatsAdminCB,
    # Panel
    admin_panel_kb,
    # Mahsulotlar
    products_menu_kb, products_list_kb as admin_products_list_kb,
    product_detail_kb, confirm_delete_kb,
    # Buyurtmalar
    orders_menu_kb, orders_list_kb as admin_orders_list_kb,
    order_detail_kb as admin_order_detail_kb,
    # Foydalanuvchilar
    users_menu_kb, user_detail_kb, confirm_ban_kb,
    # Statistika
    stats_menu_kb, stats_back_kb,
    # Yordamchi
    back_to_main_kb,
)
