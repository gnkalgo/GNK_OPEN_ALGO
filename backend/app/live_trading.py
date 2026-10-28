from datetime import UTC, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import (
    AuditEvent,
    BrokerConnection,
    LiveTradingSession,
    LiveTradingSessionEvent,
    User,
    now,
)
from .schemas import LiveSessionConfirmation, LiveSessionRequest, TradingModeRequest
from .security import admin_user, current_user, fail, get_redis, rate_limit

router = APIRouter(prefix="/api/v1/gnkalgo", tags=["live trading control"])
LIVE_UNAVAILABLE = "OPENALGO_PER_USER_ISOLATION_UNAVAILABLE"


def _iso(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _request_id(request: Request) -> str:
    value = request.headers.get("x-request-id", "")
    try:
        return str(UUID(value))
    except ValueError:
        return str(uuid4())


def _event(
    db: Session,
    session: LiveTradingSession,
    user_id: str,
    event_type: str,
    request_id: str,
    reason_code: str | None = None,
):
    db.add(
        LiveTradingSessionEvent(
            session_id=session.id,
            user_id=user_id,
            event_type=event_type,
            reason_code=reason_code,
            request_id=request_id,
            metadata_json={},
        )
    )


def _audit(db: Session, user_id: str, action: str):
    db.add(AuditEvent(user_id=user_id, action=action))


def _lock_user(db: Session, user_id: str) -> User:
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not user:
        fail(401, "SESSION_EXPIRED", "Session expired. Sign in again.")
    return user


def _expire(session: LiveTradingSession, db: Session, user_id: str, request_id: str):
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if session.status in {"PENDING_CONFIRMATION", "ACTIVE", "SUSPENDED"} and expires_at <= now():
        session.status = "EXPIRED"
        session.ended_at = now()
        session.suspension_reason = "SESSION_EXPIRED"
        session.version += 1
        _event(db, session, user_id, "SESSION_EXPIRED", request_id, "SESSION_EXPIRED")
        _audit(db, user_id, "Live trading session expired")
        db.commit()
        return True
    return False


def _session_view(session: LiveTradingSession | None):
    if session is None:
        return None
    return {
        "id": session.id,
        "broker_code": session.broker_code,
        "broker_account_mask": (
            f"•••• {session.broker_account_last4}"
        ),
        "status": session.status,
        "created_at": _iso(session.created_at),
        "confirmed_at": _iso(session.confirmed_at) if session.confirmed_at else None,
        "activated_at": _iso(session.activated_at) if session.activated_at else None,
        "last_validated_at": (
            _iso(session.last_validated_at) if session.last_validated_at else None
        ),
        "expires_at": _iso(session.expires_at),
        "ended_at": _iso(session.ended_at) if session.ended_at else None,
        "suspension_reason": session.suspension_reason,
        "broker_auth_valid": False,
        "live_orders_enabled": False,
    }


def _latest_session(db: Session, user_id: str, *, lock: bool = False):
    query = (
        select(LiveTradingSession)
        .where(LiveTradingSession.user_id == user_id)
        .order_by(LiveTradingSession.created_at.desc())
        .limit(1)
    )
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


def _control_status(db: Session, user: User, request_id: str):
    session = _latest_session(db, user.id, lock=True)
    if session and _expire(session, db, user.id, request_id):
        session = _latest_session(db, user.id, lock=True)
    connections = db.scalars(
        select(BrokerConnection)
        .where(BrokerConnection.user_id == user.id)
        .order_by(BrokerConnection.broker_code)
    ).all()
    return {
        "mode": "PAPER",
        "live_available": False,
        "live_orders_enabled": False,
        "execution": "paper-only",
        "emergency_stop": user.emergency_stop,
        "session_status": session.status if session else "INACTIVE",
        "last_connection_check": None,
        "broker_auth_valid": False,
        "risk_limits": None,
        "blockers": [
            "OPENALGO_PER_USER_ISOLATION_UNAVAILABLE",
            "BROKER_AUTH_SESSION_NOT_RETAINED",
            "LIVE_ORDER_EXECUTION_DISABLED",
        ],
        "brokers": [
            {
                "code": item.broker_code,
                "name": item.account_name,
                "account_mask": f"•••• {item.account_id_last4}",
                "account_linked": True,
                "broker_auth_valid": False,
            }
            for item in connections
        ],
        "session": _session_view(session),
    }


def _owned_session(db: Session, user_id: str, session_id: str, *, lock: bool = False):
    query = select(LiveTradingSession).where(
        LiveTradingSession.id == session_id,
        LiveTradingSession.user_id == user_id,
    )
    if lock:
        query = query.with_for_update()
    session = db.scalar(query)
    if not session:
        fail(404, "LIVE_SESSION_NOT_FOUND", "Live trading session not found.")
    return session


def _limit(request: Request, cache: Redis):
    rate_limit(request, cache)


@router.get("/trading-mode")
def get_trading_mode(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    user = _lock_user(db, user.id)
    return _control_status(db, user, _request_id(request))


@router.put("/trading-mode")
def set_trading_mode(
    body: TradingModeRequest,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    _limit(request, cache)
    if body.mode == "LIVE":
        _audit(db, user.id, "Live mode selection blocked: live execution unavailable")
        db.commit()
        fail(
            409,
            "LIVE_TRADING_UNAVAILABLE",
            "Live trading is disabled until isolated OpenAlgo sessions and broker authentication are configured.",
        )
    _audit(db, user.id, "Trading mode set to paper")
    db.commit()
    return _control_status(db, user, _request_id(request))


@router.post("/live-sessions", status_code=201)
def create_live_session(
    body: LiveSessionRequest,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    _limit(request, cache)
    user = _lock_user(db, user.id)
    if user.emergency_stop:
        fail(409, "EMERGENCY_STOP_ACTIVE", "An administrator must clear the emergency stop first.")
    existing = _latest_session(db, user.id, lock=True)
    request_id = _request_id(request)
    if existing and not _expire(existing, db, user.id, request_id):
        if existing.status not in {"EXPIRED", "REVOKED"}:
            fail(
                409,
                "LIVE_SESSION_EXISTS",
                "End the existing live-session request before starting another.",
            )
    connection = db.scalar(
        select(BrokerConnection).where(
            BrokerConnection.user_id == user.id,
            BrokerConnection.broker_code == body.broker_code,
        )
    )
    if not connection:
        fail(409, "BROKER_ACCOUNT_NOT_LINKED", "Link this broker account before requesting a live session.")
    created = now()
    session = LiveTradingSession(
        user_id=user.id,
        broker_connection_id=connection.id,
        broker_code=connection.broker_code,
        broker_account_last4=connection.account_id_last4,
        status="PENDING_CONFIRMATION",
        created_at=created,
        expires_at=created + timedelta(seconds=settings().live_session_ttl_seconds),
    )
    db.add(session)
    db.flush()
    _event(db, session, user.id, "SESSION_REQUESTED", request_id)
    _audit(db, user.id, f"{connection.broker_code} live-session request created")
    db.commit()
    return {
        "session": _session_view(session),
        "live_available": False,
        "live_orders_enabled": False,
        "blockers": [
            "OPENALGO_PER_USER_ISOLATION_UNAVAILABLE",
            "BROKER_AUTH_SESSION_NOT_RETAINED",
        ],
    }


@router.get("/live-sessions/current")
def current_live_session(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    user = _lock_user(db, user.id)
    return _control_status(db, user, _request_id(request))


@router.get("/live-sessions/{session_id}")
def get_live_session(
    session_id: str,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(db, user.id, session_id, lock=True)
    _expire(session, db, user.id, _request_id(request))
    return {
        "session": _session_view(session),
        "live_available": False,
        "live_orders_enabled": False,
    }


@router.post("/live-sessions/{session_id}/confirm")
def confirm_live_session(
    session_id: str,
    body: LiveSessionConfirmation,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    _limit(request, cache)
    user = _lock_user(db, user.id)
    session = _owned_session(db, user.id, session_id, lock=True)
    request_id = _request_id(request)
    if _expire(session, db, user.id, request_id):
        fail(409, "LIVE_SESSION_EXPIRED", "The live-session confirmation expired.")
    if not body.confirmed:
        fail(400, "CONFIRMATION_REQUIRED", "Explicit live-trading confirmation is required.")
    if session.status != "PENDING_CONFIRMATION":
        fail(409, "INVALID_LIVE_SESSION_STATE", "This session is not awaiting confirmation.")
    session.confirmed_at = now()
    session.status = "SUSPENDED"
    session.suspension_reason = LIVE_UNAVAILABLE
    session.version += 1
    _event(db, session, user.id, "CONFIRMATION_BLOCKED", request_id, LIVE_UNAVAILABLE)
    _audit(db, user.id, "Live-session activation blocked: OpenAlgo isolation unavailable")
    db.commit()
    fail(
        409,
        "LIVE_TRADING_UNAVAILABLE",
        "Confirmation was recorded, but live trading remains suspended because per-user OpenAlgo isolation and broker authentication are unavailable.",
    )


@router.post("/live-sessions/{session_id}/suspend")
def suspend_live_session(
    session_id: str,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    _limit(request, cache)
    user = _lock_user(db, user.id)
    session = _owned_session(db, user.id, session_id, lock=True)
    request_id = _request_id(request)
    if _expire(session, db, user.id, request_id):
        fail(409, "LIVE_SESSION_EXPIRED", "The live trading session has expired.")
    if session.status == "SUSPENDED":
        return {"session": _session_view(session), "live_orders_enabled": False}
    if session.status not in {"PENDING_CONFIRMATION", "ACTIVE"}:
        fail(409, "INVALID_LIVE_SESSION_STATE", "This session cannot be suspended.")
    session.status = "SUSPENDED"
    session.suspension_reason = "USER_REQUESTED"
    session.version += 1
    _event(db, session, user.id, "SESSION_SUSPENDED", request_id, "USER_REQUESTED")
    _audit(db, user.id, "Live trading session suspended")
    db.commit()
    return {"session": _session_view(session), "live_orders_enabled": False}


@router.post("/live-sessions/{session_id}/resume")
def resume_live_session(
    session_id: str,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    _limit(request, cache)
    user = _lock_user(db, user.id)
    session = _owned_session(db, user.id, session_id, lock=True)
    request_id = _request_id(request)
    if _expire(session, db, user.id, request_id):
        fail(409, "LIVE_SESSION_EXPIRED", "The live trading session has expired.")
    if session.status != "SUSPENDED":
        fail(409, "INVALID_LIVE_SESSION_STATE", "Only a suspended session can be resumed.")
    reason = "EMERGENCY_STOP_ACTIVE" if user.emergency_stop else LIVE_UNAVAILABLE
    _event(db, session, user.id, "RESUME_BLOCKED", request_id, reason)
    _audit(db, user.id, f"Live-session resume blocked: {reason}")
    db.commit()
    fail(
        409,
        "LIVE_TRADING_UNAVAILABLE",
        "The session cannot resume until broker authentication and per-user OpenAlgo isolation are verified.",
    )


@router.post("/live-sessions/{session_id}/end")
def end_live_session(
    session_id: str,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    _limit(request, cache)
    user = _lock_user(db, user.id)
    session = _owned_session(db, user.id, session_id, lock=True)
    request_id = _request_id(request)
    if _expire(session, db, user.id, request_id):
        return {"session": _session_view(session), "live_orders_enabled": False}
    if session.status == "REVOKED":
        return {"session": _session_view(session), "live_orders_enabled": False}
    if session.status == "EXPIRED":
        return {"session": _session_view(session), "live_orders_enabled": False}
    session.status = "REVOKED"
    session.ended_at = now()
    session.suspension_reason = None
    session.version += 1
    _event(db, session, user.id, "SESSION_REVOKED", request_id, "USER_ENDED")
    _audit(db, user.id, "Live trading session ended")
    db.commit()
    return {"session": _session_view(session), "live_orders_enabled": False}


@router.get("/live-sessions/{session_id}/events")
def live_session_events(
    session_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _owned_session(db, user.id, session_id)
    events = db.scalars(
        select(LiveTradingSessionEvent)
        .where(
            LiveTradingSessionEvent.session_id == session_id,
            LiveTradingSessionEvent.user_id == user.id,
        )
        .order_by(LiveTradingSessionEvent.event_timestamp)
    ).all()
    return {
        "events": [
            {
                "event_type": event.event_type,
                "event_timestamp": _iso(event.event_timestamp),
                "reason_code": event.reason_code,
                "request_id": event.request_id,
            }
            for event in events
        ]
    }


@router.post("/emergency-stop")
def activate_emergency_stop(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    _limit(request, cache)
    user = _lock_user(db, user.id)
    request_id = _request_id(request)
    user.emergency_stop = True
    sessions = db.scalars(
        select(LiveTradingSession)
        .where(
            LiveTradingSession.user_id == user.id,
            LiveTradingSession.status.in_(("PENDING_CONFIRMATION", "ACTIVE")),
        )
        .with_for_update()
    ).all()
    for session in sessions:
        session.status = "SUSPENDED"
        session.suspension_reason = "EMERGENCY_STOP_ACTIVE"
        session.version += 1
        _event(db, session, user.id, "EMERGENCY_STOP_ACTIVATED", request_id, "EMERGENCY_STOP_ACTIVE")
    _audit(db, user.id, "Emergency stop activated; live orders disabled")
    db.commit()
    return {"emergency_stop": True, "live_orders_enabled": False}


@router.delete("/admin/users/{target_user_id}/emergency-stop")
def clear_emergency_stop(
    target_user_id: str,
    request: Request,
    administrator: User = Depends(admin_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    _limit(request, cache)
    target = _lock_user(db, target_user_id)
    target.emergency_stop = False
    session = _latest_session(db, target.id, lock=True)
    request_id = _request_id(request)
    if session:
        _event(
            db,
            session,
            target.id,
            "EMERGENCY_STOP_CLEARED",
            request_id,
            "ADMIN_RESET",
        )
    _audit(db, administrator.id, f"Emergency stop cleared for user {target.id}")
    db.commit()
    return {"emergency_stop": False, "live_orders_enabled": False}
