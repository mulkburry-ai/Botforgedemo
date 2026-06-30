# ============================================================
# BOTFORGE — utils/broadcast.py
# Ommaviy xabar yuborish (broadcast)
# Telegram ban oldini olish uchun har xabar orasida 0.05s
# ============================================================

import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

logger = logging.getLogger(__name__)


async def broadcast(
    bot: Bot,
    user_ids: list[int],
    text: str,
    photo_id: str | None = None,
    parse_mode: str = "Markdown"
) -> dict:
    """
    Barcha foydalanuvchilarga xabar yuborish.

    Qaytaradi:
    {
        "sent":    muvaffaqiyatli yuborilgan,
        "failed":  xato (blok, o'chirilgan akk),
        "total":   jami foydalanuvchilar
    }

    Telegram qoidasi: sekundiga 30 ta xabar limitini
    buzmaslik uchun har xabar orasida 0.05s kutiladi.
    """
    sent = 0
    failed = 0
    total = len(user_ids)

    logger.info(f"Broadcast boshlandi: {total} ta foydalanuvchi")

    for user_id in user_ids:
        try:
            if photo_id:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=photo_id,
                    caption=text,
                    parse_mode=parse_mode
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=parse_mode
                )
            sent += 1

        except TelegramForbiddenError:
            # Foydalanuvchi botni bloklagan — normal holat
            failed += 1

        except TelegramBadRequest as e:
            # Akkaunt o'chirilgan yoki ID noto'g'ri
            logger.warning(f"BadRequest {user_id}: {e}")
            failed += 1

        except Exception as e:
            # Kutilmagan xato — log qilib davom etamiz
            logger.error(f"Broadcast xato {user_id}: {e}")
            failed += 1

        # Telegram limit: sekundiga max 30 xabar
        # 0.05s = sekundiga 20 xabar — xavfsiz chegara
        await asyncio.sleep(0.05)

    logger.info(
        f"Broadcast tugadi: {sent} yuborildi, {failed} xato, jami {total}"
    )

    return {
        "sent":  sent,
        "failed": failed,
        "total": total
    }


async def send_to_user(
    bot: Bot,
    user_id: int,
    text: str,
    photo_id: str | None = None,
    parse_mode: str = "Markdown"
) -> bool:
    """
    Bitta foydalanuvchiga xabar yuborish.
    Admin "Mijozga xabar" funksiyasi uchun.
    Qaytaradi: True (muvaffaqiyatli) yoki False (xato)
    """
    try:
        if photo_id:
            await bot.send_photo(
                chat_id=user_id,
                photo=photo_id,
                caption=text,
                parse_mode=parse_mode
            )
        else:
            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode=parse_mode
            )
        return True

    except TelegramForbiddenError:
        logger.warning(f"Foydalanuvchi {user_id} botni bloklagan")
        return False

    except TelegramBadRequest as e:
        logger.warning(f"Xabar yuborib bo'lmadi {user_id}: {e}")
        return False

    except Exception as e:
        logger.error(f"send_to_user xato {user_id}: {e}")
        return False
