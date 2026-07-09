# ============================================================
# BOTFORGE — main.py
# Botning asosiy fayli — hammani bir joyga yig'adi
# ============================================================

import logging
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler, setup_application
)

from config import (
    BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH,
    USE_WEBHOOK, ADMIN_ID
)
from db import create_pool, close_pool
from handlers import main_router
from handlers.common import error_handler
from middlewares import RateLimitMiddleware
from scheduler import create_scheduler

logger = logging.getLogger(__name__)


# ============================================================
# BOT VA DISPATCHER
# ============================================================

def create_bot() -> Bot:
    return Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Xavfsizlik to'ri — kutilmagan xatolarni tutib, botni "jim qolishdan" saqlaydi
    dp.error.register(error_handler)

    # Middleware — har bir xabar va callback dan oldin ishlaydi
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())

    # Barcha handlerlar
    dp.include_router(main_router)

    return dp


# ============================================================
# LIFESPAN — Bot ishga tushganda va to'xtaganda
# ============================================================

async def on_startup(bot: Bot, dp: Dispatcher) -> None:
    """
    Bot ishga tushganda:
    1. Neon ulanish pool yaratiladi
    2. Scheduler ishga tushadi
    3. Webhook o'rnatiladi (agar USE_WEBHOOK=True)
    4. Adminga xabar yuboriladi
    """
    # 1. DB pool
    await create_pool()
    logger.info("✅ DB pool yaratildi")

    # 2. Scheduler
    scheduler = create_scheduler(bot)
    scheduler.start()
    dp["scheduler"] = scheduler
    logger.info("✅ Scheduler ishga tushdi")

    # 3. Webhook
    if USE_WEBHOOK:
        await bot.set_webhook(
            url=WEBHOOK_URL,
            drop_pending_updates=True
        )
        logger.info(f"✅ Webhook o'rnatildi: {WEBHOOK_URL}")
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Polling rejimi")

    # 4. Adminga xabar
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text="🟢 Bot ishga tushdi!"
        )
    except Exception as e:
        logger.warning(f"Adminga xabar yuborib bo'lmadi: {e}")


async def on_shutdown(bot: Bot, dp: Dispatcher) -> None:
    """
    Bot to'xtaganda:
    1. Scheduler to'xtatiladi
    2. Webhook o'chiriladi
    3. DB pool yopiladi
    4. Adminga xabar yuboriladi
    """
    # 1. Scheduler
    scheduler = dp.get("scheduler")
    if scheduler:
        scheduler.shutdown()
        logger.info("🔴 Scheduler to'xtatildi")

    # 2. Webhook
    if USE_WEBHOOK:
        await bot.delete_webhook()

    # 3. DB pool
    await close_pool()
    logger.info("🔴 DB pool yopildi")

    # 4. Adminga xabar
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text="🔴 Bot to'xtatildi."
        )
    except Exception:
        pass


# ============================================================
# WEBHOOK REJIMI — Render Web Service
# ============================================================

async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    """
    Render da webhook orqali ishlash.
    UptimeRobot /health ga ping yuboradi — bot uyquga ketmaydi.
    """
    app = web.Application()

    # Health check endpoint — UptimeRobot uchun
    async def health_check(request: web.Request) -> web.Response:
        return web.Response(text="OK")

    app.router.add_get("/health", health_check)
    app.router.add_get("/", health_check)

    # Webhook handler
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Startup va shutdown
    app.on_startup.append(lambda _: on_startup(bot, dp))
    app.on_cleanup.append(lambda _: on_shutdown(bot, dp))

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()

    logger.info("🌐 Web server 0.0.0.0:8080 da ishga tushdi")

    # Bot ishlayveradi
    await asyncio.Event().wait()


# ============================================================
# POLLING REJIMI — Lokal test uchun
# ============================================================

async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    """
    Lokal test uchun polling rejimi.
    WEBHOOK_HOST .env da bo'lmasa shu rejim ishlatiladi.
    """
    await on_startup(bot, dp)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await on_shutdown(bot, dp)


# ============================================================
# ASOSIY FUNKSIYA
# ============================================================

async def main() -> None:
    bot = create_bot()
    dp  = create_dispatcher()

    if USE_WEBHOOK:
        logger.info("🚀 Webhook rejimida ishga tushmoqda...")
        await run_webhook(bot, dp)
    else:
        logger.info("🚀 Polling rejimida ishga tushmoqda...")
        await run_polling(bot, dp)


if __name__ == "__main__":
    asyncio.run(main())
