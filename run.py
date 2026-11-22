#!/usr/bin/env python3
"""
Single entry point for BotHost / local development.

Runs:
  1. FastAPI (uvicorn) in background or main process
  2. aiogram bot polling

For production on BotHost prefer process manager or separate processes.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import get_settings
from database.session import init_db
from bot.handlers import router as bot_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("bot_store")


async def start_bot() -> None:
    settings = get_settings()
    if not settings.BOT_TOKEN or settings.BOT_TOKEN.startswith("your_"):
        logger.error("Set BOT_TOKEN in .env")
        return

    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(bot_router)

    logger.info("Bot starting (polling)...")
    await dp.start_polling(bot)


def start_api() -> None:
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        workers=1 if settings.RELOAD else settings.WORKERS,
        log_level="info",
    )


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "bot"

    if mode == "api":
        start_api()
    elif mode == "bot":
        asyncio.run(start_bot())
    elif mode == "all":
        # Development convenience: bot only in this process.
        # Run API separately: python run.py api
        logger.warning("Mode 'all' runs bot only. Start API in another process.")
        asyncio.run(start_bot())
    else:
        print("Usage: python run.py [bot|api|all]")
        sys.exit(1)
