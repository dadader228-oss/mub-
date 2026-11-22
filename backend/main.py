from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from database.session import get_session, init_db
from database.models import (
    Category, Product, User, Order, OrderItem, Cart, CartItem,
    Payment, Ticket, TicketMessage, PromoCode, Favorite, Review,
    OrderStatus, PaymentMethod, TicketStatus, TicketCategory, Setting, AuditLog,
)
from services.telegram_auth import validate_init_data, InitDataError, is_admin
from services.order_service import (
    get_or_create_user, get_or_create_cart, create_order_from_cart, mark_order_paid,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="BOT STORE API", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== AUTH ====================

class AuthUser(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_admin: bool = False


async def get_current_user(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
) -> AuthUser:
    if not x_telegram_init_data:
        raise HTTPException(401, "Missing initData")
    try:
        data = validate_init_data(x_telegram_init_data)
    except InitDataError as e:
        raise HTTPException(401, str(e))
    user = data.get("user")
    if not user or "id" not in user:
        raise HTTPException(401, "No user in initData")
    return AuthUser(
        telegram_id=user["id"],
        username=user.get("username"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
        is_admin=is_admin(user["id"]),
    )


async def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not user.is_admin:
        raise HTTPException(403, "Admin only")
    return user


# ==================== SCHEMAS ====================

class ProductOut(BaseModel):
    id: int
    name: str
    slug: str
    short_description: Optional[str] = None
    price_rub: float
    price_stars: int
    image_url: Optional[str] = None
    is_featured: bool = False
    is_new: bool = False
    category_id: int
    delivery_mode: str = "auto"
    stock: int = -1
    guarantee_days: int = 0

    class Config:
        from_attributes = True


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    icon: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class CartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(1, ge=1, le=99)


class OrderCreateIn(BaseModel):
    payment_method: str
    promo_code: Optional[str] = None


class ProductCreateIn(BaseModel):
    category_id: int
    name: str
    slug: str
    description: str
    short_description: Optional[str] = None
    price_rub: float
    price_stars: int
    delivery_mode: str = "auto"
    stock: int = -1
    is_active: bool = True
    is_featured: bool = False
    is_new: bool = False
    guarantee_days: int = 0
    features: Optional[str] = None
    specs: Optional[str] = None
    image_url: Optional[str] = None
    demo_url: Optional[str] = None
    file_path: Optional[str] = None


class TicketCreateIn(BaseModel):
    category: str
    subject: str
    text: str
    order_id: Optional[int] = None


class TicketMessageIn(BaseModel):
    text: str


class ConfirmPaymentIn(BaseModel):
    order_id: int
    approve: bool
    reason: Optional[str] = None


# ==================== PUBLIC ====================

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "BOT STORE", "version": "1.1.0"}


@app.get("/api/categories", response_model=List[CategoryOut])
async def list_categories(session: AsyncSession = Depends(get_session)):
    r = await session.execute(
        select(Category).where(Category.is_active == True).order_by(Category.sort_order)
    )
    return r.scalars().all()


@app.get("/api/products", response_model=List[ProductOut])
async def list_products(
    category: Optional[str] = None,
    featured: Optional[bool] = None,
    is_new: Optional[bool] = None,
    q: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Product).where(Product.is_active == True)
    if category:
        stmt = stmt.join(Category).where(Category.slug == category)
    if featured is not None:
        stmt = stmt.where(Product.is_featured == featured)
    if is_new is not None:
        stmt = stmt.where(Product.is_new == is_new)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Product.sort_order, Product.id.desc())
    r = await session.execute(stmt)
    return r.scalars().all()


@app.get("/api/products/{product_id}")
async def get_product(product_id: int, session: AsyncSession = Depends(get_session)):
    p = await session.get(Product, product_id)
    if not p or not p.is_active:
        raise HTTPException(404, "Product not found")
    p.views_count += 1
    await session.commit()
    return {
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "description": p.description,
        "short_description": p.short_description,
        "price_rub": float(p.price_rub),
        "price_stars": p.price_stars,
        "delivery_mode": p.delivery_mode,
        "stock": p.stock,
        "guarantee_days": p.guarantee_days,
        "features": p.features,
        "specs": p.specs,
        "image_url": p.image_url,
        "demo_url": p.demo_url,
        "is_featured": p.is_featured,
        "is_new": p.is_new,
        "category_id": p.category_id,
        "sales_count": p.sales_count,
    }


# ==================== USER (auth) ====================

@app.get("/api/me")
async def me(user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    db = await get_or_create_user(session, user.telegram_id, user.username, user.first_name, user.last_name)
    await session.commit()
    return {
        "telegram_id": db.telegram_id,
        "username": db.username,
        "first_name": db.first_name,
        "balance": float(db.balance),
        "is_admin": user.is_admin,
        "created_at": db.created_at.isoformat() if db.created_at else None,
    }


@app.post("/api/cart/add")
async def add_to_cart(
    body: CartItemIn,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    db = await get_or_create_user(session, user.telegram_id, user.username, user.first_name, user.last_name)
    cart = await get_or_create_cart(session, db)
    product = await session.get(Product, body.product_id)
    if not product or not product.is_active:
        raise HTTPException(400, "Product unavailable")
    if product.stock == 0:
        raise HTTPException(400, "Out of stock")

    existing = next((i for i in cart.items if i.product_id == body.product_id), None)
    if existing:
        existing.quantity += body.quantity
    else:
        session.add(CartItem(cart_id=cart.id, product_id=body.product_id, quantity=body.quantity))
    await session.commit()
    return {"ok": True}


@app.post("/api/cart/remove")
async def remove_from_cart(
    body: CartItemIn,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    db = await get_or_create_user(session, user.telegram_id)
    cart = await get_or_create_cart(session, db)
    for item in list(cart.items):
        if item.product_id == body.product_id:
            await session.delete(item)
            break
    await session.commit()
    return {"ok": True}


@app.get("/api/cart")
async def get_cart(user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    db = await get_or_create_user(session, user.telegram_id)
    cart = await get_or_create_cart(session, db)
    items, total_rub, total_stars = [], 0.0, 0
    for item in cart.items:
        p = await session.get(Product, item.product_id)
        if not p:
            continue
        items.append({
            "product_id": p.id,
            "name": p.name,
            "price_rub": float(p.price_rub),
            "price_stars": p.price_stars,
            "quantity": item.quantity,
            "image_url": p.image_url,
        })
        total_rub += float(p.price_rub) * item.quantity
        total_stars += p.price_stars * item.quantity
    return {"items": items, "total_rub": total_rub, "total_stars": total_stars}


@app.post("/api/orders")
async def create_order(
    body: OrderCreateIn,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if body.payment_method not in ("stars", "rub"):
        raise HTTPException(400, "Invalid payment_method")
    db = await get_or_create_user(session, user.telegram_id, user.username, user.first_name, user.last_name)
    try:
        order = await create_order_from_cart(session, db, body.payment_method, body.promo_code)
        if body.payment_method == "rub":
            order.status = OrderStatus.AWAITING_PAYMENT_CHECK.value
        await session.commit()
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "total_rub": float(order.total_rub),
        "total_stars": order.total_stars,
        "status": order.status,
        "payment_method": order.payment_method,
    }


@app.get("/api/orders")
async def my_orders(user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    db = await get_or_create_user(session, user.telegram_id)
    r = await session.execute(
        select(Order).where(Order.user_id == db.id).order_by(desc(Order.created_at)).limit(50)
    )
    return [
        {
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "total_rub": float(o.total_rub),
            "total_stars": o.total_stars,
            "payment_method": o.payment_method,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in r.scalars().all()
    ]


@app.get("/api/orders/{order_id}")
async def order_detail(
    order_id: int,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    db = await get_or_create_user(session, user.telegram_id)
    order = await session.get(Order, order_id)
    if not order or order.user_id != db.id:
        raise HTTPException(404, "Order not found")
    r = await session.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    items = [
        {
            "product_name": i.product_name,
            "price_rub": float(i.price_rub),
            "price_stars": i.price_stars,
            "quantity": i.quantity,
            "delivery_mode": i.delivery_mode,
        }
        for i in r.scalars().all()
    ]
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "total_rub": float(order.total_rub),
        "total_stars": order.total_stars,
        "payment_method": order.payment_method,
        "items": items,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    }


# ==================== FAVORITES ====================

@app.post("/api/favorites/{product_id}")
async def toggle_favorite(
    product_id: int,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    db = await get_or_create_user(session, user.telegram_id)
    r = await session.execute(
        select(Favorite).where(Favorite.user_id == db.id, Favorite.product_id == product_id)
    )
    fav = r.scalar_one_or_none()
    if fav:
        await session.delete(fav)
        await session.commit()
        return {"favorited": False}
    session.add(Favorite(user_id=db.id, product_id=product_id))
    await session.commit()
    return {"favorited": True}


@app.get("/api/favorites")
async def list_favorites(user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    db = await get_or_create_user(session, user.telegram_id)
    r = await session.execute(
        select(Favorite).where(Favorite.user_id == db.id)
    )
    ids = [f.product_id for f in r.scalars().all()]
    if not ids:
        return []
    r2 = await session.execute(select(Product).where(Product.id.in_(ids), Product.is_active == True))
    return [
        {
            "id": p.id, "name": p.name, "price_rub": float(p.price_rub),
            "price_stars": p.price_stars, "image_url": p.image_url,
        }
        for p in r2.scalars().all()
    ]


# ==================== TICKETS ====================

@app.post("/api/tickets")
async def create_ticket(
    body: TicketCreateIn,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    db = await get_or_create_user(session, user.telegram_id, user.username, user.first_name, user.last_name)
    import secrets
    ticket = Ticket(
        ticket_number=f"T-{secrets.token_hex(3).upper()}",
        user_id=db.id,
        category=body.category,
        subject=body.subject,
        order_id=body.order_id,
        status=TicketStatus.OPEN.value,
    )
    session.add(ticket)
    await session.flush()
    session.add(TicketMessage(
        ticket_id=ticket.id,
        sender_id=user.telegram_id,
        is_admin=False,
        text=body.text,
    ))
    await session.commit()
    return {"ticket_id": ticket.id, "ticket_number": ticket.ticket_number}


@app.get("/api/tickets")
async def my_tickets(user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    db = await get_or_create_user(session, user.telegram_id)
    r = await session.execute(
        select(Ticket).where(Ticket.user_id == db.id).order_by(desc(Ticket.created_at))
    )
    return [
        {
            "id": t.id, "ticket_number": t.ticket_number, "subject": t.subject,
            "status": t.status, "category": t.category,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in r.scalars().all()
    ]


@app.get("/api/tickets/{ticket_id}")
async def ticket_detail(
    ticket_id: int,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    db = await get_or_create_user(session, user.telegram_id)
    t = await session.get(Ticket, ticket_id)
    if not t or (t.user_id != db.id and not user.is_admin):
        raise HTTPException(404, "Ticket not found")
    r = await session.execute(
        select(TicketMessage).where(TicketMessage.ticket_id == t.id).order_by(TicketMessage.created_at)
    )
    messages = [
        {
            "id": m.id, "text": m.text, "is_admin": m.is_admin,
            "sender_id": m.sender_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in r.scalars().all()
    ]
    return {
        "id": t.id, "ticket_number": t.ticket_number, "subject": t.subject,
        "status": t.status, "category": t.category, "messages": messages,
    }


@app.post("/api/tickets/{ticket_id}/messages")
async def add_ticket_message(
    ticket_id: int,
    body: TicketMessageIn,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    db = await get_or_create_user(session, user.telegram_id)
    t = await session.get(Ticket, ticket_id)
    if not t or (t.user_id != db.id and not user.is_admin):
        raise HTTPException(404, "Ticket not found")
    if t.status == TicketStatus.CLOSED.value:
        raise HTTPException(400, "Ticket closed")
    session.add(TicketMessage(
        ticket_id=t.id,
        sender_id=user.telegram_id,
        is_admin=user.is_admin,
        text=body.text,
    ))
    t.status = TicketStatus.WAITING_ADMIN.value if not user.is_admin else TicketStatus.WAITING_USER.value
    await session.commit()
    return {"ok": True}


# ==================== ADMIN ====================

@app.get("/api/admin/stats")
async def admin_stats(admin: AuthUser = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    orders = (await session.execute(select(func.count(Order.id)))).scalar() or 0
    paid = (await session.execute(
        select(func.count(Order.id)).where(Order.status.in_([
            OrderStatus.PAID.value, OrderStatus.PROCESSING.value,
            OrderStatus.READY.value, OrderStatus.COMPLETED.value,
        ]))
    )).scalar() or 0
    revenue = (await session.execute(
        select(func.coalesce(func.sum(Order.total_rub), 0)).where(
            Order.status.in_([OrderStatus.PAID.value, OrderStatus.COMPLETED.value, OrderStatus.PROCESSING.value])
        )
    )).scalar() or 0
    products = (await session.execute(select(func.count(Product.id)))).scalar() or 0
    open_tickets = (await session.execute(
        select(func.count(Ticket.id)).where(Ticket.status != TicketStatus.CLOSED.value)
    )).scalar() or 0
    return {
        "users": users,
        "orders": orders,
        "paid_orders": paid,
        "revenue_rub": float(revenue),
        "products": products,
        "open_tickets": open_tickets,
    }


@app.get("/api/admin/orders")
async def admin_orders(
    status: Optional[str] = None,
    admin: AuthUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Order).order_by(desc(Order.created_at)).limit(100)
    if status:
        stmt = stmt.where(Order.status == status)
    r = await session.execute(stmt)
    result = []
    for o in r.scalars().all():
        u = await session.get(User, o.user_id)
        result.append({
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "total_rub": float(o.total_rub),
            "total_stars": o.total_stars,
            "payment_method": o.payment_method,
            "user_telegram_id": u.telegram_id if u else None,
            "username": u.username if u else None,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })
    return result


@app.post("/api/admin/orders/confirm-payment")
async def admin_confirm_payment(
    body: ConfirmPaymentIn,
    admin: AuthUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    order = await session.get(Order, body.order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if order.payment_method != PaymentMethod.RUB.value:
        raise HTTPException(400, "Only RUB manual payments")
    if order.status != OrderStatus.AWAITING_PAYMENT_CHECK.value:
        raise HTTPException(400, f"Invalid status: {order.status}")

    if body.approve:
        payment = Payment(
            order_id=order.id,
            method=PaymentMethod.RUB.value,
            amount_rub=order.total_rub,
            currency="RUB",
            status="succeeded",
            confirmed_by=admin.telegram_id,
            confirmed_at=datetime.now(timezone.utc),
        )
        session.add(payment)
        await mark_order_paid(session, order, payment)
        session.add(AuditLog(
            actor_id=admin.telegram_id,
            action="confirm_payment",
            entity="order",
            entity_id=order.id,
            details=f"Approved RUB payment {order.order_number}",
        ))
    else:
        order.status = OrderStatus.CANCELLED.value
        order.admin_note = body.reason or "Payment rejected"
        session.add(AuditLog(
            actor_id=admin.telegram_id,
            action="reject_payment",
            entity="order",
            entity_id=order.id,
            details=body.reason,
        ))
    await session.commit()
    return {"ok": True, "status": order.status}


@app.get("/api/admin/products")
async def admin_products(admin: AuthUser = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    r = await session.execute(select(Product).order_by(desc(Product.id)))
    return [
        {
            "id": p.id, "name": p.name, "slug": p.slug,
            "price_rub": float(p.price_rub), "price_stars": p.price_stars,
            "is_active": p.is_active, "stock": p.stock,
            "delivery_mode": p.delivery_mode, "category_id": p.category_id,
        }
        for p in r.scalars().all()
    ]


@app.post("/api/admin/products")
async def admin_create_product(
    body: ProductCreateIn,
    admin: AuthUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    p = Product(
        category_id=body.category_id,
        name=body.name,
        slug=body.slug,
        description=body.description,
        short_description=body.short_description,
        price_rub=Decimal(str(body.price_rub)),
        price_stars=body.price_stars,
        delivery_mode=body.delivery_mode,
        stock=body.stock,
        is_active=body.is_active,
        is_featured=body.is_featured,
        is_new=body.is_new,
        guarantee_days=body.guarantee_days,
        features=body.features,
        specs=body.specs,
        image_url=body.image_url,
        demo_url=body.demo_url,
        file_path=body.file_path,
    )
    session.add(p)
    session.add(AuditLog(
        actor_id=admin.telegram_id, action="create_product",
        entity="product", details=body.name,
    ))
    await session.commit()
    await session.refresh(p)
    return {"id": p.id, "name": p.name}


@app.patch("/api/admin/products/{product_id}")
async def admin_update_product(
    product_id: int,
    body: ProductCreateIn,
    admin: AuthUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    p = await session.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump().items():
        if k == "price_rub":
            setattr(p, k, Decimal(str(v)))
        else:
            setattr(p, k, v)
    session.add(AuditLog(
        actor_id=admin.telegram_id, action="update_product",
        entity="product", entity_id=p.id,
    ))
    await session.commit()
    return {"ok": True}


@app.delete("/api/admin/products/{product_id}")
async def admin_delete_product(
    product_id: int,
    admin: AuthUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    p = await session.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Not found")
    p.is_active = False  # soft delete
    session.add(AuditLog(
        actor_id=admin.telegram_id, action="hide_product",
        entity="product", entity_id=p.id,
    ))
    await session.commit()
    return {"ok": True}


@app.get("/api/admin/tickets")
async def admin_tickets(
    status: Optional[str] = None,
    admin: AuthUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Ticket).order_by(desc(Ticket.updated_at)).limit(50)
    if status:
        stmt = stmt.where(Ticket.status == status)
    r = await session.execute(stmt)
    return [
        {
            "id": t.id, "ticket_number": t.ticket_number, "subject": t.subject,
            "status": t.status, "category": t.category,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in r.scalars().all()
    ]


@app.get("/api/admin/payments")
async def admin_payments(admin: AuthUser = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    r = await session.execute(select(Payment).order_by(desc(Payment.created_at)).limit(100))
    return [
        {
            "id": p.id, "order_id": p.order_id, "method": p.method,
            "amount_rub": float(p.amount_rub) if p.amount_rub else None,
            "amount_stars": p.amount_stars,
            "status": p.status,
            "telegram_payment_charge_id": p.telegram_payment_charge_id,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in r.scalars().all()
    ]


@app.get("/api/admin/users")
async def admin_users(admin: AuthUser = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    r = await session.execute(select(User).order_by(desc(User.created_at)).limit(100))
    return [
        {
            "id": u.id, "telegram_id": u.telegram_id, "username": u.username,
            "first_name": u.first_name, "balance": float(u.balance),
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in r.scalars().all()
    ]


# Settings helper
@app.get("/api/settings/payment_instructions")
async def payment_instructions(session: AsyncSession = Depends(get_session)):
    r = await session.execute(select(Setting).where(Setting.key == "rub_payment_instructions"))
    s = r.scalar_one_or_none()
    return {"text": s.value if s else "Свяжитесь с администратором для реквизитов оплаты."}


@app.post("/api/admin/settings/payment_instructions")
async def set_payment_instructions(
    body: dict,
    admin: AuthUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    text = body.get("text", "")
    r = await session.execute(select(Setting).where(Setting.key == "rub_payment_instructions"))
    s = r.scalar_one_or_none()
    if s:
        s.value = text
    else:
        session.add(Setting(key="rub_payment_instructions", value=text))
    await session.commit()
    return {"ok": True}


# Static Mini App
try:
    app.mount("/", StaticFiles(directory="miniapp", html=True), name="miniapp")
except Exception:
    pass
