# ============================================================
# BOTFORGE — handlers/__init__.py
# Barcha handlerlarni bitta router ga yig'ish
# main.py shu router ni ishlatadi
# ============================================================

from aiogram import Router

# Har bir modul alohida import qilinadi — chuqur importlar
# (masalan cart.py -> keyboards -> keyboards.admin) bilan
# to'qnashmasligi uchun bitta qatorga yig'ilmaydi.
from . import common
from . import catalog
from . import cart
from . import profile
from . import info
from .admin import admin_router

main_router = Router()

# Foydalanuvchi handlerlari
main_router.include_router(common.router)
main_router.include_router(catalog.router)
main_router.include_router(cart.router)
main_router.include_router(profile.router)
main_router.include_router(info.router)

# Admin handlerlari (ichida o'z routerlari bor)
main_router.include_router(admin_router)
