"""Explicit preview/confirmation of Dhan cash delivery limit buys, separate from paper."""

import json
import secrets
from datetime import time
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import dhan_execution as execution
from .db import get_db
from .dhan_client import DhanError
from .live_trading import _expire, _lock_user, _owned_session, _validate_dhan_session
from .models import AuditEvent, LiveOrder, now
from .schemas import Body
from .security import current_user, digest, fail, get_redis, rate_limit

router = APIRouter(prefix="/api/v1/gnkalgo/dhan", tags=["Dhan live execution"])


class Preview(Body):
    session_id: UUID
    security_id: str = Field(pattern=r"^[0-9]{1,20}$")
    quantity: int = Field(strict=True, ge=1, le=100)
    price: Decimal = Field(gt=0, le=10000000, decimal_places=2, max_digits=12)


class Confirmation(Body):
    preview_token: str = Field(min_length=32, max_length=128)
    confirmed: bool = Field(strict=True)


def market_open():
    local = now().astimezone(execution.IST)
    # Broker remains authoritative for holidays and exchange-specific suspensions.
    return local.weekday() < 5 and time(9, 15) <= local.time().replace(tzinfo=None) < time(15, 20)


def active_session(db, user, session_id, request):
    session = _owned_session(db, user.id, session_id, lock=True)
    if _expire(session, db, user.id, str(uuid4())) or session.status != "ACTIVE":
        raise DhanError("An active, confirmed Dhan live session is required.")
    if not user.enabled or not user.verified:
        raise DhanError("This GNK account is not enabled for trading.")
    connection, client = _validate_dhan_session(db, user, session)
    session.last_validated_at = now()
    return session, connection, client


@router.get("/instruments")
def instruments(user=Depends(current_user), db: Session = Depends(get_db)):
    del user
    return {
        "instruments": [
            {
                "security_id": item.security_id,
                "name": item.name,
                "tick_size": str(item.tick_size),
                "lower_limit": str(item.lower_limit),
                "upper_limit": str(item.upper_limit),
            }
            for item in execution.catalog(db)
        ],
        "segment": "NSE_EQ",
        "prices": "operator-entered-limit-only",
    }


@router.post("/orders/preview")
def preview(
    body: Preview,
    request: Request,
    user=Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    rate_limit(request, cache)
    user = _lock_user(db, user.id)
    try:
        if not market_open():
            raise DhanError(
                "New live orders are accepted on weekdays from 09:15 to 15:20 India time, subject to broker trading hours."
            )
        session, connection, client = active_session(db, user, str(body.session_id), request)
        item = execution.instrument(db, body.security_id, body.quantity, body.price)
        execution.budget(db, connection.account_digest, body.quantity * body.price)
        ticket = {
            "security_id": item.security_id,
            "name": item.name,
            "quantity": body.quantity,
            "price": str(body.price),
        }
        margin = execution.pretrade(client, ticket)
    except DhanError as exc:
        fail(409, "DHAN_PRETRADE_BLOCKED", str(exc))
    token = secrets.token_urlsafe(32)
    cache.setex(
        "dhan-preview:" + digest(token),
        90,
        json.dumps(
            {
                "user_id": user.id,
                "session_id": session.id,
                "version": session.version,
                "account_digest": connection.account_digest,
                "ticket": ticket,
            }
        ),
    )
    db.commit()
    return {
        "preview_token": token,
        "expires_in": 90,
        "account_mask": connection.account_id_last4,
        "ticket": ticket,
        "margin": margin,
        "mode": "LIVE",
        "side": "BUY",
        "product": "CNC",
        "type": "LIMIT",
    }


@router.post("/orders")
def submit(
    body: Confirmation,
    request: Request,
    user=Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    rate_limit(request, cache)
    if not body.confirmed:
        fail(400, "CONFIRMATION_REQUIRED", "Explicit confirmation of this live order is required.")
    try:
        key = str(UUID(request.headers.get("idempotency-key", "")))
    except ValueError:
        fail(422, "INVALID_REQUEST_KEY", "A UUID Idempotency-Key is required.")
    user = _lock_user(db, user.id)
    existing = db.scalar(
        select(LiveOrder).where(LiveOrder.user_id == user.id, LiveOrder.request_key == key)
    )
    preview_digest = digest(body.preview_token)
    if existing:
        if existing.ticket["preview_digest"] != preview_digest:
            fail(
                409,
                "IDEMPOTENCY_CONFLICT",
                "Request key already belongs to another live order preview.",
            )
        return execution.view(existing)
    raw = cache.getdel("dhan-preview:" + preview_digest)
    if not raw:
        fail(
            409, "PREVIEW_EXPIRED", "Preview expired or was already used. Preview the order again."
        )
    data = json.loads(raw)
    if data["user_id"] != user.id:
        fail(404, "PREVIEW_NOT_FOUND", "Preview not found for this account.")
    try:
        if not market_open():
            raise DhanError("The GNK live order window is closed. No order was submitted.")
        session, connection, client = active_session(db, user, data["session_id"], request)
        if (
            session.version != data["version"]
            or connection.account_digest != data["account_digest"]
        ):
            raise DhanError("Session or broker account changed. Create a fresh order preview.")
        ticket = data["ticket"]
        execution.instrument(
            db, ticket["security_id"], ticket["quantity"], Decimal(ticket["price"])
        )
        execution.budget(
            db, connection.account_digest, Decimal(ticket["price"]) * ticket["quantity"]
        )
        execution.pretrade(client, ticket)
    except DhanError as exc:
        fail(409, "DHAN_PRETRADE_BLOCKED", str(exc))
    order = LiveOrder(
        user_id=user.id,
        session_id=session.id,
        account_digest=connection.account_digest,
        request_key=key,
        correlation_id=uuid4().hex[:30],
        ticket={**ticket, "preview_digest": preview_digest},
        status="UNKNOWN",
        reason="Submission outcome requires broker reconciliation",
    )
    db.add(order)
    db.add(AuditEvent(user_id=user.id, action="Dhan live order intent recorded before dispatch"))
    db.commit()  # Durable uncertainty BEFORE any order placement call. A crash must never resubmit.
    user = _lock_user(db, user.id)
    try:
        # Recheck authority after committing the intent; hold the account lock through dispatch.
        session, connection, client = active_session(db, user, data["session_id"], request)
        if (
            session.version != data["version"]
            or connection.account_digest != data["account_digest"]
            or not market_open()
        ):
            raise DhanError("Live session changed before dispatch. No order was submitted.")
    except DhanError as exc:
        order.status = "BLOCKED"
        order.reason = str(exc)
        db.commit()
        return execution.view(order)
    try:
        ack = client.place(execution.payload(client, order.ticket, order.correlation_id))
        if (
            isinstance(ack, dict)
            and isinstance(ack.get("orderId"), str)
            and ack["orderId"].isalnum()
            and len(ack["orderId"]) <= 64
        ):
            order.broker_order_id = ack["orderId"]
            # An acknowledgement is not a fill. Require lookup even for an immediate terminal ACK.
            order.status = "PENDING"
            order.reason = "Broker acknowledgement received; reconcile cumulative fills"
    except DhanError:
        pass  # HTTP errors, timeouts and malformed responses all retain the durable UNKNOWN.
    db.add(
        AuditEvent(user_id=user.id, action="Dhan live order dispatched; broker outcome recorded")
    )
    db.commit()
    return execution.view(order)


@router.get("/orders")
def orders(user=Depends(current_user), db: Session = Depends(get_db)):
    return {
        "orders": [
            execution.view(order)
            for order in db.scalars(
                select(LiveOrder)
                .where(LiveOrder.user_id == user.id)
                .order_by(LiveOrder.created_at.desc())
            ).all()
        ]
    }


@router.post("/orders/{order_id}/reconcile")
def reconcile(
    order_id: str,
    request: Request,
    user=Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    rate_limit(request, cache)
    user = _lock_user(db, user.id)
    order = db.scalar(
        select(LiveOrder)
        .where(LiveOrder.id == order_id, LiveOrder.user_id == user.id)
        .with_for_update()
    )
    if not order:
        fail(404, "LIVE_ORDER_NOT_FOUND", "Live order not found.")
    if order.status == "BLOCKED":
        return execution.view(order)
    try:
        _, client = execution.connection_client(db, user.id, order.account_digest)
        execution.reconcile_order(order, client.lookup(order.correlation_id), client)
    except DhanError as exc:
        fail(409, "DHAN_RECONCILIATION_REQUIRED", str(exc))
    db.add(AuditEvent(user_id=user.id, action="Dhan live order reconciled against broker record"))
    db.commit()
    return execution.view(order)
