# ============================================================
# BOTFORGE — middlewares/rate_limit.py
# Spam himoya — foydalanuvchi xabarlarini cheklash
# aiogram 3.x BaseMiddleware
# ============================================================

import logging
from typing import Any, Awaitable, Callable
from datetime import datetime, timedelta

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from db import is_banned
from config import ADMIN_USERNAME

logger = logging.getLogger(__name__)

# Har bir foydalanuvchi uchun xabar vaqtlari saqlanadi
# { user_id: [vaqt1, vaqt2, ...] }
_message_timestamps: dict[int, list[datetime]] = {}

# Sozlamalar
RATE_LIMIT_COUNT    = 5     # Qancha xabar
RATE_LIMIT_SECONDS  = 3     # Necha soniya ichida
CLEANUP_EVERY       = 1000  # Har N xabarda eski yozuvlar tozalanadi
_call_count         = 0


def _is_rate_limited(user_id: int) -> bool:
    """
    Foydalanuvchi so'nggi N soniya ichida
    limitdan ko'p xabar yuborganini tekshiradi.
    """
    now = datetime.utcnow()
    window = now - timedelta(seconds=RATE_LIMIT_SECONDS)

    timestamps = _message_timestamps.get(user_id, [])

    # Oyna tashqarisidagi eski vaqtlarni tozalash
    timestamps = [t for t in timestamps if t > window]
    timestamps.append(now)
    _message_timestamps[user_id] = timestamps

    return len(timestamps) > RATE_LIMIT_COUNT


def _cleanup_old_entries() -> None:
    """
    RAM da yig'ilib qolgan eski foydalanuvchi
    yozuvlarini tozalaydi. Har 1000 xabarda bir marta.
    """
    now = datetime.utcnow()
    window = now - timedelta(seconds=RATE_LIMIT_SECONDS * 2)
    to_delete = [
        uid for uid, times in _message_timestamps.items()
        if not any(t > window for t in times)
    ]
    for uid in to_delete:
        del _message_timestamps[uid]


class RateLimitMiddleware(BaseMiddleware):
    """
    Har bir Message va CallbackQuery uchun:
    1. Foydalanuvchi banlanganlıgini tekshiradi
    2. Spam limitini tekshiradi
    Ikkalasi ham o'tsa — handlerga yo'l beradi.
    """

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any]
    ) -> Any:
        global _call_count
        _call_count += 1

        # Vaqti-vaqti bilan RAM tozalash
        if _call_count % CLEANUP_EVERY == 0:
            _cleanup_old_entries()

        # Foydalanuvchi ID si
        user = event.from_user
        if not user:
            return await handler(event, data)

        user_id = user.id

        # 1. Ban tekshirish
        try:
            if await is_banned(user_id):
                if isinstance(event, Message):
                    await event.answer(
                        f"🚫 Siz botdan bloklangansiz.\nMurojaat uchun: {ADMIN_USERNAME}"
                    )
                # CallbackQuery uchun jim o'tamiz — xabar chiqarmaylik
                return
        except Exception as e:
            logger.error(f"Ban tekshirishda xato: {e}")

        # 2. Rate limit tekshirish
        if _is_rate_limited(user_id):
            if isinstance(event, Message):
                await event.answer(
                    "⏳ Juda tez yozyapsiz. Biroz kuting."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⏳ Juda tez. Biroz kuting.",
                    show_alert=False
                )
            return

        # Hammasi yaxshi — handlerga yo'l berish
        return await handler(event, data)
