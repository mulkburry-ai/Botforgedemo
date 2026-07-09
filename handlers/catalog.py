# ============================================================
# BOTFORGE — handlers/catalog.py
# Katalog, mahsulot ko'rish, galereya
# edit_message orqali — chat toza qoladi
# ============================================================

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from db import (
    get_main_categories, get_subcategories,
    get_products, get_product, get_variants,
    get_effective_stock, get_available_stock,
    is_favorite, add_last_seen, get_setting,
    add_favorite, remove_favorite,
)
from keyboards import (
    CatalogCB, ProductCB,
    categories_kb, subcategories_kb, products_list_kb,
    product_card_kb, variant_select_kb, qty_select_kb,
)
from utils import fmt_product_card

logger = logging.getLogger(__name__)
router = Router()

# Bir sahifada nechta mahsulot ko'rsatiladi
PRODUCTS_PER_PAGE = 8


# ============================================================
# ASOSIY MENYU — "🛍 Katalog" tugmasi
# ============================================================

@router.message(F.text == "🛍 Katalog")
async def show_catalog(message: Message, state: FSMContext) -> None:
    """
    Foydalanuvchi "Katalog" tugmasini bosganida
    asosiy kategoriyalar chiqadi.
    Bitta yangi xabar yuboriladi — keyingi barcha
    navigatsiya shu xabarnigina yangilaydi.
    """
    await state.clear()
    categories = await get_main_categories()

    if not categories:
        await message.answer("📭 Hozircha kategoriyalar yo'q.")
        return

    await message.answer(
        text="🛍 *Katalog*\nKategoriyani tanlang:",
        reply_markup=categories_kb(categories),
        parse_mode="Markdown"
    )


# ============================================================
# KATEGORIYA → SUBKATEGORIYA YOKI MAHSULOTLAR
# ============================================================

@router.callback_query(CatalogCB.filter(F.action == "main"))
async def cb_main_categories(callback: CallbackQuery) -> None:
    """Asosiy kategoriyalarga qaytish."""
    categories = await get_main_categories()

    if not categories:
        await callback.answer("Kategoriyalar yo'q", show_alert=True)
        return

    await callback.message.edit_text(
        text="🛍 *Katalog*\nKategoriyani tanlang:",
        reply_markup=categories_kb(categories),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(CatalogCB.filter(F.action == "sub"))
async def cb_subcategories(
    callback: CallbackQuery,
    callback_data: CatalogCB
) -> None:
    """
    Kategoriya bosilganda:
    - Subkategoriyalar bor → subkategoriyalar ko'rsatiladi
    - Yo'q → to'g'ridan mahsulotlar ko'rsatiladi
    """
    cat_id = callback_data.cat_id
    subs = await get_subcategories(cat_id)

    if subs:
        # Subkategoriyalar bor
        await callback.message.edit_text(
            text="📂 Bo'limni tanlang:",
            reply_markup=subcategories_kb(subs, parent_id=cat_id),
            parse_mode="Markdown"
        )
    else:
        # Subkategoriya yo'q — to'g'ri mahsulotlarga
        await _show_products(callback, cat_id=cat_id, page=1)

    await callback.answer()


@router.callback_query(CatalogCB.filter(F.action == "products"))
async def cb_products(
    callback: CallbackQuery,
    callback_data: CatalogCB
) -> None:
    """Mahsulotlar ro'yxatini ko'rsatish (pagination bilan)."""
    await _show_products(
        callback,
        cat_id=callback_data.cat_id,
        page=callback_data.page
    )
    await callback.answer()


async def _show_products(
    callback: CallbackQuery,
    cat_id: int,
    page: int
) -> None:
    """
    Mahsulotlar ro'yxatini ko'rsatadigan ichki funksiya.
    Pagination hisoblash va xabarni yangilash.
    """
    all_products = await get_products(cat_id)

    if not all_products:
        await callback.message.edit_text(
            text="📭 Bu bo'limda hozircha mahsulotlar yo'q.",
            reply_markup=None
        )
        return

    # Pagination hisoblash
    total = len(all_products)
    total_pages = max(1, (total + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PRODUCTS_PER_PAGE
    end = start + PRODUCTS_PER_PAGE
    page_products = all_products[start:end]

    await callback.message.edit_text(
        text=f"📦 *Mahsulotlar* ({total} ta)",
        reply_markup=products_list_kb(
            products=page_products,
            cat_id=cat_id,
            page=page,
            total_pages=total_pages
        ),
        parse_mode="Markdown"
    )


# ============================================================
# MAHSULOT KARTASI
# ============================================================

@router.callback_query(ProductCB.filter(F.action == "detail"))
async def cb_product_detail(
    callback: CallbackQuery,
    callback_data: ProductCB
) -> None:
    """
    Mahsulot kartasini ko'rsatish.
    Oxirgi ko'rilganlarga qo'shiladi.
    """
    product_id = callback_data.product_id
    page = callback_data.page

    product = await get_product(product_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    # Oxirgi ko'rilganlarga qo'shish
    await add_last_seen(callback.from_user.id, product_id)

    # Turlar va haqiqiy stok — bitta manbadan (db/products.py)
    effective = await get_effective_stock(product_id)

    # Sevimlilar holati
    fav = await is_favorite(callback.from_user.id, product_id)

    # Low stock threshold
    threshold = int(await get_setting("low_stock_threshold", "5"))

    # Galereya
    gallery = product.get("gallery_ids") or []
    gallery_total = len(gallery) + (1 if product.get("photo_id") else 0)

    in_stock = effective["total_stock"] > 0

    text = fmt_product_card(
        product, low_stock_threshold=threshold, effective_stock=effective
    )

    # Rasmli yoki rasmsiz
    photo = product.get("photo_id")
    kb = product_card_kb(
        product_id=product_id,
        gallery_total=gallery_total,
        is_favorite=fav,
        in_stock=in_stock,
        has_variants=effective["has_variants"],
        back_cat_id=product.get("category_id", 0),
        page=page
    )

    if photo:
        try:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=kb,
                parse_mode="Markdown"
            )
        except Exception:
            # Oldingi xabar rasmsiz bo'lsa
            await callback.message.edit_text(
                text=text,
                reply_markup=kb,
                parse_mode="Markdown"
            )
    else:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb,
            parse_mode="Markdown"
        )

    await callback.answer()


@router.callback_query(ProductCB.filter(F.action == "variant"))
async def cb_variant_select(
    callback: CallbackQuery,
    callback_data: ProductCB
) -> None:
    """Mahsulot turlari ro'yxatini ko'rsatish."""
    product_id = callback_data.product_id
    variants = await get_variants(product_id)

    if not variants:
        await callback.answer("Bu mahsulotda turlar yo'q", show_alert=True)
        return

    await callback.message.edit_text(
        text="🎨 *Tur tanlang:*",
        reply_markup=variant_select_kb(variants, product_id),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(ProductCB.filter(F.action == "variant_pick"))
async def cb_variant_pick(
    callback: CallbackQuery,
    callback_data: ProductCB
) -> None:
    """
    Mijoz ro'yxatdan bitta turni tanladi — endi miqdor tanlash
    ekraniga o'tamiz, shu turning HOZIRGI stokiga bog'liq holda.
    """
    available = await get_available_stock(
        callback_data.product_id, callback_data.variant_id
    )
    if available <= 0:
        await callback.answer("😔 Bu tur tugagan", show_alert=True)
        return

    await callback.message.edit_text(
        text="🔢 *Miqdorni tanlang:*",
        reply_markup=qty_select_kb(
            product_id=callback_data.product_id,
            variant_id=callback_data.variant_id,
            qty=1,
            max_stock=available,
            back_action="variant"
        ),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(ProductCB.filter(F.action == "qty_start"))
async def cb_qty_start(
    callback: CallbackQuery,
    callback_data: ProductCB
) -> None:
    """
    Turlarsiz mahsulotda "Savatga solish" bosilganda —
    to'g'ridan miqdor tanlash ekraniga o'tamiz.
    """
    available = await get_available_stock(callback_data.product_id)
    if available <= 0:
        await callback.answer("😔 Mahsulot tugagan", show_alert=True)
        return

    await callback.message.edit_text(
        text="🔢 *Miqdorni tanlang:*",
        reply_markup=qty_select_kb(
            product_id=callback_data.product_id,
            variant_id=0,
            qty=1,
            max_stock=available,
            back_action="detail"
        ),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(ProductCB.filter(F.action == "qty"))
async def cb_qty_change(
    callback: CallbackQuery,
    callback_data: ProductCB
) -> None:
    """
    ➖ yoki ➕ bosilganda. Har safar HOZIRGI stok qayta tekshiriladi
    (Burry talabi: "iloji boricha tez-tez tekshirish") — chunki
    mijoz ekranda turgan payt boshqa birov sotib olishi mumkin.
    """
    available = await get_available_stock(
        callback_data.product_id, callback_data.variant_id
    )

    if available <= 0:
        await callback.answer(
            "😔 Bu mahsulot/tur tugab qoldi.", show_alert=True
        )
        return

    # Agar tanlangan son yangi stokdan oshib qolgan bo'lsa — moslashtiramiz
    qty = min(callback_data.qty, available)
    qty = max(1, qty)

    back_action = "variant" if callback_data.variant_id else "detail"

    try:
        await callback.message.edit_text(
            text="🔢 *Miqdorni tanlang:*",
            reply_markup=qty_select_kb(
                product_id=callback_data.product_id,
                variant_id=callback_data.variant_id,
                qty=qty,
                max_stock=available,
                back_action=back_action
            ),
            parse_mode="Markdown"
        )
    except Exception:
        # Xabar o'zgarmagan bo'lsa (masalan allaqachon chegarada) — jim o'tamiz
        pass

    if callback_data.qty > available:
        await callback.answer(f"⚠️ Faqat {available} dona bor")
    else:
        await callback.answer()


@router.callback_query(ProductCB.filter(F.action == "gallery"))
async def cb_gallery(
    callback: CallbackQuery,
    callback_data: ProductCB
) -> None:
    """
    Galereya navigatsiyasi — rasm almashish.
    edit_message_media orqali bitta xabar yangilanadi.
    """
    product_id = callback_data.product_id
    gallery_idx = callback_data.gallery_idx

    product = await get_product(product_id)
    if not product:
        await callback.answer()
        return

    # Barcha rasmlar ro'yxati
    all_photos = []
    if product.get("photo_id"):
        all_photos.append(product["photo_id"])
    all_photos.extend(product.get("gallery_ids") or [])

    if gallery_idx >= len(all_photos):
        await callback.answer()
        return

    photo_id = all_photos[gallery_idx]
    fav = await is_favorite(callback.from_user.id, product_id)
    threshold = int(await get_setting("low_stock_threshold", "5"))
    effective = await get_effective_stock(product_id)
    in_stock = effective["total_stock"] > 0

    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=photo_id,
            caption=fmt_product_card(
                product, low_stock_threshold=threshold, effective_stock=effective
            ),
            parse_mode="Markdown"
        ),
        reply_markup=product_card_kb(
            product_id=product_id,
            gallery_idx=gallery_idx,
            gallery_total=len(all_photos),
            is_favorite=fav,
            in_stock=in_stock,
            has_variants=effective["has_variants"],
            back_cat_id=product.get("category_id", 0),
        )
    )
    await callback.answer()


# ============================================================
# SEVIMLILAR
# ============================================================

@router.callback_query(ProductCB.filter(F.action == "favorite"))
async def cb_toggle_favorite(
    callback: CallbackQuery,
    callback_data: ProductCB
) -> None:
    """Sevimlilarga qo'shish yoki olib tashlash."""
    user_id = callback.from_user.id
    product_id = callback_data.product_id

    fav = await is_favorite(user_id, product_id)
    if fav:
        await remove_favorite(user_id, product_id)
        await callback.answer("💔 Sevimlilardan olib tashlandi")
    else:
        await add_favorite(user_id, product_id)
        await callback.answer("❤️ Sevimlilarga qo'shildi")

    # Kartani yangilash — sevimli tugmasi o'zgaradi
    product = await get_product(product_id)
    if not product:
        return

    effective = await get_effective_stock(product_id)
    in_stock = effective["total_stock"] > 0
    gallery = product.get("gallery_ids") or []
    gallery_total = len(gallery) + (1 if product.get("photo_id") else 0)

    kb = product_card_kb(
        product_id=product_id,
        gallery_total=gallery_total,
        is_favorite=not fav,
        in_stock=in_stock,
        has_variants=effective["has_variants"],
        back_cat_id=product.get("category_id", 0),
    )

    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
