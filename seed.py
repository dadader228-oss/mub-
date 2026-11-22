#!/usr/bin/env python3
"""Seed categories and demo products."""
from __future__ import annotations

import asyncio
from decimal import Decimal

from database.session import init_db, async_session
from database.models import Category, Product, Setting


async def main() -> None:
    await init_db()
    async with async_session() as s:
        # Categories
        cats_data = [
            ("Telegram-боты", "telegram-bots", "🤖"),
            ("VPN-боты", "vpn-bots", "🔐"),
            ("Исходный код", "source-code", "💻"),
            ("Разработка под заказ", "custom-dev", "🛠"),
            ("Доработка ботов", "bot-upgrade", "🔧"),
            ("Хостинг и обслуживание", "hosting", "☁️"),
        ]
        cat_ids = {}
        for name, slug, icon in cats_data:
            existing = (await s.execute(
                __import__("sqlalchemy").select(Category).where(Category.slug == slug)
            )).scalar_one_or_none()
            if existing:
                cat_ids[slug] = existing.id
                continue
            c = Category(name=name, slug=slug, icon=icon, is_active=True)
            s.add(c)
            await s.flush()
            cat_ids[slug] = c.id

        products = [
            {
                "category_id": cat_ids["telegram-bots"],
                "name": "Готовый бот-магазин",
                "slug": "shop-bot",
                "description": "Полноценный Telegram-бот с каталогом, корзиной и оплатой Stars. Исходный код + инструкция.",
                "short_description": "Каталог + оплата Stars",
                "price_rub": Decimal("4990.00"),
                "price_stars": 2500,
                "delivery_mode": "auto",
                "is_featured": True,
                "is_new": True,
                "guarantee_days": 30,
            },
            {
                "category_id": cat_ids["vpn-bots"],
                "name": "VPN-бот с подписками",
                "slug": "vpn-bot",
                "description": "Бот для продажи VPN-доступов: тарифы, автовыдача ключей, учёт сроков.",
                "short_description": "Автовыдача VPN-ключей",
                "price_rub": Decimal("7990.00"),
                "price_stars": 4000,
                "delivery_mode": "auto",
                "is_featured": True,
                "is_new": False,
                "guarantee_days": 30,
            },
            {
                "category_id": cat_ids["source-code"],
                "name": "Шаблон aiogram 3 магазина",
                "slug": "aiogram-shop-template",
                "description": "Чистый шаблон магазина на aiogram 3 + FastAPI. Подходит как база для кастомизации.",
                "short_description": "Шаблон исходников",
                "price_rub": Decimal("2990.00"),
                "price_stars": 1500,
                "delivery_mode": "auto",
                "is_featured": False,
                "is_new": True,
                "guarantee_days": 14,
            },
            {
                "category_id": cat_ids["custom-dev"],
                "name": "Индивидуальная разработка бота",
                "slug": "custom-bot-dev",
                "description": "Разработка бота под ваши задачи. ТЗ, согласование, сдача, поддержка 14 дней.",
                "short_description": "Под ключ по ТЗ",
                "price_rub": Decimal("15000.00"),
                "price_stars": 7500,
                "delivery_mode": "manual",
                "is_featured": True,
                "is_new": False,
                "guarantee_days": 14,
            },
            {
                "category_id": cat_ids["bot-upgrade"],
                "name": "Доработка существующего бота",
                "slug": "bot-upgrade",
                "description": "Добавление функций, исправление багов, интеграция оплаты и БД.",
                "short_description": "Доработка / фиксы",
                "price_rub": Decimal("5000.00"),
                "price_stars": 2500,
                "delivery_mode": "manual",
                "is_featured": False,
                "is_new": False,
                "guarantee_days": 7,
            },
            {
                "category_id": cat_ids["hosting"],
                "name": "Хостинг бота на 1 месяц",
                "slug": "hosting-1m",
                "description": "Размещение и мониторинг бота на VPS. Бэкапы, перезапуск, базовая поддержка.",
                "short_description": "VPS + мониторинг",
                "price_rub": Decimal("990.00"),
                "price_stars": 500,
                "delivery_mode": "manual",
                "is_featured": False,
                "is_new": False,
                "guarantee_days": 0,
            },
        ]

        for pdata in products:
            exists = (await s.execute(
                __import__("sqlalchemy").select(Product).where(Product.slug == pdata["slug"])
            )).scalar_one_or_none()
            if exists:
                continue
            s.add(Product(**pdata, is_active=True))

        # Payment instructions
        from sqlalchemy import select
        r = await s.execute(select(Setting).where(Setting.key == "rub_payment_instructions"))
        if not r.scalar_one_or_none():
            s.add(Setting(
                key="rub_payment_instructions",
                value=(
                    "Оплата в рублях:\n"
                    "1. Переведите сумму на карту/счёт, указанный администратором.\n"
                    "2. Напишите боту номер заказа и сумму.\n"
                    "3. Дождитесь подтверждения (обычно до 24 ч).\n"
                    "Скриншот не является доказательством — нужна фактическая проверка."
                ),
            ))

        await s.commit()
    print("Seed completed: categories + products + payment instructions.")


if __name__ == "__main__":
    asyncio.run(main())
