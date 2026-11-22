# BOT STORE — магазин под ключ

Telegram-магазин готовых ботов, VPN, исходников и услуг разработки.

**Стек:** Python 3.11+ · aiogram 3 · FastAPI · SQLAlchemy (SQLite) · Telegram Mini App (HTML/CSS/JS)

Оптимизирован под **BotHost Basic** (2 vCPU / 1 GB RAM).

---

## Возможности

- Telegram-бот (меню, заказы, профиль, поддержка, админка)
- Mini App: главная, каталог, корзина, заказы, профиль, тикеты
- Каталог с категориями, поиском, избранным (API)
- Корзина и оформление заказа
- **Оплата Telegram Stars** (pre_checkout + successful_payment, идемпотентность)
- **Оплата в рублях** (ручное подтверждение админом)
- Авто- и ручная выдача товаров
- Система тикетов
- Админ: статистика, заказы, подтверждение ₽, товары, тикеты, рассылка
- Промокоды / рефералы / отзывы — модели готовы, точки расширения в API
- Валидация `initData` на сервере
- Журнал действий (audit_logs)

---

## Быстрый старт

```bash
cd BOT_STORE
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Отредактируйте `.env`:

```env
BOT_TOKEN=...
ADMIN_IDS=ВАШ_TELEGRAM_ID
WEBAPP_URL=https://your-domain.com
API_URL=https://your-domain.com/api
SECRET_KEY=длинная_случайная_строка_32+
DATABASE_URL=sqlite+aiosqlite:///./storage/bot_store.db
```

Заполните демо-данные:

```bash
python seed.py
```

Запуск:

```bash
# терминал 1
python run.py api

# терминал 2
python run.py bot
```

---

## Telegram

1. @BotFather → бот + Payments (Stars).
2. Menu Button / Web App → `WEBAPP_URL`.
3. `ADMIN_IDS` — ваш Telegram ID.
4. HTTPS-домен обязателен для Mini App.

### Stars

- Цены в каталоге: `price_rub` и `price_stars` хранятся **отдельно**.
- После создания заказа со способом `stars` админ может отправить инвойс: `/pay ORDER_ID`.
- Или интегрируйте автоматическую отправку инвойса после `POST /api/orders`.

### Рубли

1. Пользователь выбирает «Оплата в рублях».
2. Статус → `awaiting_payment_check`.
3. Админ: `/admin` → Заказы → ✅ / ❌.
4. После ✅ — выдача (auto/manual).

---

## BotHost

1. Загрузить проект, Python 3.11+.
2. `pip install -r requirements.txt`
3. Переменные окружения как в `.env`.
4. Два процесса: `python run.py api` и `python run.py bot`.
5. HTTPS-домен на порт API.
6. `WORKERS=1`, без `RELOAD` в проде.

---

## Структура

```
BOT_STORE/
├── bot/           # aiogram handlers + keyboards
├── backend/       # FastAPI
├── database/      # models + session
├── miniapp/       # WebApp UI
├── services/      # auth, orders, delivery, notifications
├── storage/       # SQLite + uploads
├── seed.py
├── run.py
├── backup.py
├── config.py
├── requirements.txt
└── README.md
```

---

## API (кратко)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/health | Health |
| GET | /api/categories | Категории |
| GET | /api/products | Каталог |
| GET | /api/products/{id} | Карточка |
| POST | /api/cart/add | В корзину (auth) |
| GET | /api/cart | Корзина |
| POST | /api/orders | Создать заказ |
| GET | /api/orders | Мои заказы |
| POST | /api/tickets | Тикет |
| GET | /api/admin/stats | Статистика (admin) |
| POST | /api/admin/orders/confirm-payment | Подтвердить ₽ |
| POST | /api/admin/products | Создать товар |

Auth: заголовок `X-Telegram-Init-Data` (валидируется на сервере).

---

## Безопасность

- `initData` проверяется HMAC-подписью.
- Цены и наличие — только с сервера.
- Повтор Stars-платежа блокируется по `telegram_payment_charge_id`.
- Админ — только `ADMIN_IDS`.
- Секреты в `.env`.

---

## Тестирование

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/categories
curl http://127.0.0.1:8000/api/products
```

Полный цикл Stars и initData — только внутри Telegram.

---

После заполнения `.env`, `seed.py` и привязки HTTPS/WebApp магазин готов к использованию.
