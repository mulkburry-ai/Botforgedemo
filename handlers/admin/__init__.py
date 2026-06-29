# ============================================================
# BOTFORGE — handlers/admin/__init__.py
# Barcha admin routerlarni bitta router ga yig'ish
# ============================================================

from aiogram import Router

from . import panel, products, orders, users, stats

admin_router = Router()
admin_router.include_router(panel.router)
admin_router.include_router(products.router)
admin_router.include_router(orders.router)
admin_router.include_router(users.router)
admin_router.include_router(stats.router)
