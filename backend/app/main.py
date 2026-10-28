import json
import secrets
from datetime import UTC, timedelta
from decimal import Decimal
from urllib.parse import parse_qs
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from . import broker_auth
from .config import settings
from .db import get_db
from .live_trading import router as live_trading_router
from .models import (
    AuditEvent,
    BrokerConnection,
    EmailToken,
    LiveTradingSession,
    LiveTradingSessionEvent,
    MailOutbox,
    PaperOrder,
    Strategy,
    User,
    now,
)
from .schemas import (
    BrokerConfirmation,
    Email,
    Login,
    Profile,
    Registration,
    Reset,
    StrategyConfig,
    Ticket,
    Token,
    Transition,
    UserStatus,
)
from .security import (
    COOKIE,
    DUMMY_HASH,
    admin_user,
    current_user,
    digest,
    fail,
    get_redis,
    passwords,
    rate_limit,
    same_origin,
    verify_password,
)

app = FastAPI(
    title="GNK ALGO API",
    version="1.0.0",
    docs_url="/api/docs" if settings().environment != "production" else None,
    redoc_url=None,
)
app.include_router(live_trading_router)
PREFIX = "/api/gnk/v1"
GNK_ALGO_PREFIX = "/api/v1/gnkalgo"
BROKER_OAUTH_TTL = 300
QUOTES = {
    "RELIANCE": "2948.50",
    "TCS": "4125.80",
    "HDFCBANK": "1726.35",
    "INFY": "1864.20",
    "ICICIBANK": "1285.40",
    "BHARTIARTL": "1620.75",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic errors may include submitted passwords. Return only field paths.
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid fields: "
                + ", ".join(".".join(map(str, e["loc"][1:])) for e in exc.errors()),
            }
        },
    )


@app.exception_handler(RedisError)
async def redis_error(request, exc):
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "Session service unavailable. Please retry later.",
            }
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "Data service unavailable. Please retry later.",
            }
        },
    )


def audit(db, user, action):
    db.add(AuditEvent(user_id=user.id, action=action))


def public_user(user):
    return {"name": user.name, "email": user.email, "role": user.role}


def order_view(o):
    return {
        **{k: v for k, v in o.ticket.items() if k != "request"},
        "id": o.request_key,
        "status": o.status,
        "time": o.created_at.isoformat(),
        "reason": o.reason,
    }


def queue_email(db, user, purpose):
    token = EmailToken(
        digest=digest(secrets.token_urlsafe(32)),
        user_id=user.id,
        purpose=purpose,
        expires_at=now() + timedelta(minutes=30),
    )
    db.add(token)
    db.flush()
    db.add(MailOutbox(token_digest=token.digest))


def consume_token(db, raw, purpose):
    token = db.scalar(
        select(EmailToken)
        .where(EmailToken.digest == digest(raw), EmailToken.purpose == purpose)
        .with_for_update()
    )
    if not token or token.used or token.expires_at.replace(tzinfo=UTC) <= now():
        fail(400, "LINK_EXPIRED", "Link is invalid or expired. Request a new link.")
    token.used = True
    return db.scalar(select(User).where(User.id == token.user_id).with_for_update())


@app.get("/api/health/live")
def live():
    return {"status": "ok", "execution": "paper-only"}


@app.get("/api/health/ready")
def ready(db: Session = Depends(get_db), cache: Redis = Depends(get_redis)):
    db.execute(text("SELECT 1"))
    cache.ping()
    return {"status": "ready", "execution": "paper-only"}


def broker_callback_paths() -> tuple[str, ...]:
    return ("/api",)


@app.get(f"{GNK_ALGO_PREFIX}/health")
def gnkalgo_health():
    return {"status": "ok", "execution": "paper-only"}


@app.get(f"{GNK_ALGO_PREFIX}/status")
def gnkalgo_status(db: Session = Depends(get_db), cache: Redis = Depends(get_redis)):
    return ready(db=db, cache=cache)


@app.get(f"{GNK_ALGO_PREFIX}/brokers")
def gnkalgo_broker_list(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return broker_list(user=user, db=db)


@app.get(f"{GNK_ALGO_PREFIX}/brokers/{{broker_id}}/status")
def gnkalgo_broker_status(
    broker_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if broker_id == "paper":
        return {
            "code": "paper",
            "name": "Paper Trading",
            "configured": True,
            "connected": user.broker == "Connected",
            "connection": None,
        }
    providers = broker_list(user=user, db=db)["providers"]
    provider = next((item for item in providers if item["code"] == broker_id), None)
    if not provider:
        fail(404, "BROKER_NOT_FOUND", "This broker is not supported.")
    return {
        "code": broker_id,
        "name": provider["name"],
        "configured": provider["configured"],
        "connected": provider["connection"] is not None,
        "connection": provider["connection"],
    }


@app.post(f"{GNK_ALGO_PREFIX}/brokers/{{broker_id}}/connect")
def gnkalgo_connect(
    broker_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if broker_id == "paper":
        return connect(user=user, db=db)
    if broker_id not in broker_auth.BROKERS:
        fail(404, "BROKER_NOT_FOUND", "This broker is not supported.")
    fail(
        409,
        "BROKER_EXECUTION_UNAVAILABLE",
        "This broker supports account linking only; broker order sessions are not available.",
    )


@app.post(f"{GNK_ALGO_PREFIX}/brokers/{{broker_id}}/disconnect")
def gnkalgo_disconnect(
    broker_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if broker_id == "paper":
        user.broker = "Disconnected"
        audit(db, user, "Paper broker disconnected")
        db.commit()
        return {"status": "Disconnected", "source": "paper-simulator"}
    if broker_id not in broker_auth.BROKERS:
        fail(404, "BROKER_NOT_FOUND", "This broker is not supported.")
    return broker_disconnect(code=broker_id, user=user, db=db)


@app.post(f"{GNK_ALGO_PREFIX}/brokers/{{code}}/authorization")
def gnkalgo_authorization(
    code: str,
    response: Response,
    user: User = Depends(current_user),
    cache: Redis = Depends(get_redis),
):
    return broker_authorization(code=code, response=response, user=user, cache=cache)


@app.get(f"{GNK_ALGO_PREFIX}/brokers/{{code}}/callback")
def gnkalgo_callback(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    return broker_callback(code=code, request=request, db=db, cache=cache)


@app.post(f"{GNK_ALGO_PREFIX}/brokers/pending")
def gnkalgo_pending(
    body: BrokerConfirmation,
    user: User = Depends(current_user),
    cache: Redis = Depends(get_redis),
):
    return broker_pending(body=body, user=user, cache=cache)


@app.post(f"{GNK_ALGO_PREFIX}/brokers/{{code}}/confirm")
def gnkalgo_confirm(
    code: str,
    body: BrokerConfirmation,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    return broker_confirm(code=code, body=body, user=user, db=db, cache=cache)


@app.delete(f"{GNK_ALGO_PREFIX}/brokers/{{code}}")
def gnkalgo_delete_broker(
    code: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return broker_disconnect(code=code, user=user, db=db)


@app.get(f"{GNK_ALGO_PREFIX}/market/quote")
def gnkalgo_market_quote(
    symbol: str | None = None,
):
    if symbol:
        key = symbol.upper()
        if key not in QUOTES:
            fail(404, "INVALID_INSTRUMENT", "Instrument not listed.")
        return {
            "symbol": key,
            "exchange": "NSE",
            "last_price": float(QUOTES[key]),
            "source": "paper-fixture",
        }
    return {
        "quotes": [
            {"symbol": key, "exchange": "NSE", "last_price": float(value)}
            for key, value in QUOTES.items()
        ]
    }


@app.get(f"{GNK_ALGO_PREFIX}/market/depth")
def gnkalgo_market_depth(symbol: str = "RELIANCE"):
    key = symbol.upper()
    if key not in QUOTES:
        fail(404, "INVALID_INSTRUMENT", "Instrument not listed.")
    price = float(QUOTES[key])
    return {
        "symbol": key,
        "exchange": "NSE",
        "bids": [{"price": price - 0.1, "quantity": 10}],
        "asks": [{"price": price + 0.1, "quantity": 12}],
        "last_price": price,
    }


@app.get(f"{GNK_ALGO_PREFIX}/market/history")
def gnkalgo_market_history(symbol: str = "RELIANCE"):
    key = symbol.upper()
    if key not in QUOTES:
        fail(404, "INVALID_INSTRUMENT", "Instrument not listed.")
    price = float(QUOTES[key])
    return {
        "symbol": key,
        "exchange": "NSE",
        "points": [
            {"time": "2024-01-01T09:15:00Z", "price": price},
            {"time": "2024-01-01T09:30:00Z", "price": price * 0.995},
            {"time": "2024-01-01T09:45:00Z", "price": price},
        ],
    }


@app.get(f"{GNK_ALGO_PREFIX}/market/search")
def gnkalgo_market_search(symbol: str = "RELIANCE"):
    key = symbol.upper()
    return {
        "query": key,
        "matches": [
            {"symbol": item, "exchange": "NSE", "last_price": float(value)}
            for item, value in QUOTES.items()
            if key in item or item.startswith(key[:2])
        ],
    }


@app.get(f"{GNK_ALGO_PREFIX}/orders")
def gnkalgo_orders(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    orders = db.scalars(
        select(PaperOrder)
        .where(PaperOrder.user_id == user.id)
        .order_by(PaperOrder.created_at.desc())
    ).all()
    return {"orders": [order_view(order) for order in orders]}


@app.post(f"{GNK_ALGO_PREFIX}/orders")
def gnkalgo_submit_order(
    body: Ticket,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return submit(body=body, request=request, user=user, db=db)


@app.get(f"{GNK_ALGO_PREFIX}/orders/{{order_id}}")
def gnkalgo_order_detail(
    order_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return reconcile(key=order_id, user=user, db=db)


@app.put(f"{GNK_ALGO_PREFIX}/orders/{{order_id}}")
def gnkalgo_update_order(
    order_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    order = db.scalar(
        select(PaperOrder).where(
            PaperOrder.user_id == user.id,
            PaperOrder.request_key == order_id,
        )
    )
    if not order:
        fail(404, "ORDER_NOT_FOUND", "Order not found.")
    fail(409, "ORDER_NOT_MODIFIABLE", "Paper orders fill immediately and cannot be modified.")


@app.delete(f"{GNK_ALGO_PREFIX}/orders/{{order_id}}")
def gnkalgo_delete_order(
    order_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    order = db.scalar(
        select(PaperOrder).where(
            PaperOrder.user_id == user.id,
            PaperOrder.request_key == order_id,
        )
    )
    if not order:
        fail(404, "ORDER_NOT_FOUND", "Order not found.")
    fail(409, "ORDER_NOT_CANCELLABLE", "Paper orders fill immediately and cannot be cancelled.")


@app.get(f"{GNK_ALGO_PREFIX}/portfolio/positions")
def gnkalgo_positions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    del db
    return {"positions": [], "session": public_user(user)}


@app.get(f"{GNK_ALGO_PREFIX}/portfolio/holdings")
def gnkalgo_holdings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    del db
    return {"holdings": [], "session": public_user(user)}


@app.get(f"{GNK_ALGO_PREFIX}/portfolio/funds")
def gnkalgo_funds(user: User = Depends(current_user), db: Session = Depends(get_db)):
    del db
    return {"available_balance": float(user.balance), "currency": "INR"}


@app.get(f"{GNK_ALGO_PREFIX}/session")
def gnkalgo_session(request: Request, user: User = Depends(current_user)):
    return session(request=request, user=user)


@app.post(f"{GNK_ALGO_PREFIX}/auth/register", dependencies=[Depends(same_origin)], status_code=202)
def gnkalgo_register(
    body: Registration,
    request: Request,
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    return register(body=body, request=request, db=db, cache=cache)


@app.post(f"{GNK_ALGO_PREFIX}/auth/verify", dependencies=[Depends(same_origin)])
def gnkalgo_verify(body: Token, db: Session = Depends(get_db)):
    return verify(body=body, db=db)


@app.post(f"{GNK_ALGO_PREFIX}/auth/login", dependencies=[Depends(same_origin)])
def gnkalgo_login(
    body: Login,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    return login(body=body, request=request, response=response, db=db, cache=cache)


@app.post(f"{GNK_ALGO_PREFIX}/auth/logout")
def gnkalgo_logout(
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    cache: Redis = Depends(get_redis),
):
    return logout(request=request, response=response, user=user, cache=cache)


@app.post(f"{GNK_ALGO_PREFIX}/auth/forgot", dependencies=[Depends(same_origin)], status_code=202)
def gnkalgo_forgot(
    body: Email,
    request: Request,
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    return forgot(body=body, request=request, db=db, cache=cache)


@app.post(f"{GNK_ALGO_PREFIX}/auth/resend", dependencies=[Depends(same_origin)], status_code=202)
def gnkalgo_resend(
    body: Email,
    request: Request,
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    return resend(body=body, request=request, db=db, cache=cache)


@app.post(f"{GNK_ALGO_PREFIX}/auth/reset", dependencies=[Depends(same_origin)])
def gnkalgo_reset(body: Reset, db: Session = Depends(get_db)):
    return reset(body=body, db=db)


@app.get(f"{GNK_ALGO_PREFIX}/workspace")
def gnkalgo_workspace(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return workspace(user=user, db=db)


@app.put(f"{GNK_ALGO_PREFIX}/profile")
def gnkalgo_profile(body: Profile, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return profile(body=body, user=user, db=db)


@app.put(f"{GNK_ALGO_PREFIX}/watchlist/{{symbol}}")
def gnkalgo_watchlist(symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return watchlist(symbol=symbol, user=user, db=db)


@app.post(PREFIX + "/auth/register", dependencies=[Depends(same_origin)], status_code=202)
def register(
    body: Registration,
    request: Request,
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    rate_limit(request, cache)
    encoded = passwords.hash(body.password)
    if not db.scalar(select(User).where(User.email == body.email)):
        user = User(name=body.name.strip(), email=body.email, password_hash=encoded)
        db.add(user)
        try:
            db.flush()
            queue_email(db, user, "verify")
            audit(db, user, "Account registration requested")
            db.commit()
        except IntegrityError:
            db.rollback()
    return {"message": "If eligible, a verification email will be sent."}


@app.post(PREFIX + "/auth/verify", dependencies=[Depends(same_origin)])
def verify(body: Token, db: Session = Depends(get_db)):
    user = consume_token(db, body.token, "verify")
    user.verified = True
    audit(db, user, "Email verified")
    db.commit()
    return {"message": "Email verified. Sign in."}


@app.post(PREFIX + "/auth/login", dependencies=[Depends(same_origin)])
def login(
    body: Login,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    rate_limit(request, cache)
    user = db.scalar(select(User).where(User.email == body.email))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if not user or not valid or not user.verified or not user.enabled:
        fail(
            401,
            "LOGIN_FAILED",
            "Email or password is incorrect, or the account is not verified.",
        )
    old = request.cookies.get(COOKIE)
    if old:
        cache.delete("session:" + digest(old))
    raw, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    cache.setex(
        "session:" + digest(raw),
        settings().session_ttl,
        json.dumps({"user_id": user.id, "version": user.session_version, "csrf": csrf}),
    )
    response.set_cookie(
        COOKIE,
        raw,
        max_age=settings().session_ttl,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="strict",
        path="/api",
    )
    audit(db, user, "Signed in")
    db.commit()
    return {"session": public_user(user), "csrf": csrf}


@app.get(PREFIX + "/session")
def session(request: Request, user: User = Depends(current_user)):
    return {"session": public_user(user), "csrf": request.state.csrf}


@app.post(PREFIX + "/auth/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    cache: Redis = Depends(get_redis),
):
    cache.delete("session:" + digest(request.cookies.get(COOKIE, "")))
    response.delete_cookie(
        COOKIE,
        path="/api",
        secure=settings().cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return {"message": "Signed out."}


@app.post(PREFIX + "/auth/forgot", dependencies=[Depends(same_origin)], status_code=202)
def forgot(
    body: Email,
    request: Request,
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    rate_limit(request, cache)
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user and user.enabled:
        queue_email(db, user, "reset")
        db.commit()
    return {"message": "If an account exists, a reset email will be sent."}


@app.post(PREFIX + "/auth/resend", dependencies=[Depends(same_origin)], status_code=202)
def resend(
    body: Email, request: Request, db: Session = Depends(get_db), cache: Redis = Depends(get_redis)
):
    rate_limit(request, cache)
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user and user.enabled and not user.verified:
        queue_email(db, user, "verify")
        db.commit()
    return {"message": "If eligible, a verification email will be sent."}


@app.post(PREFIX + "/auth/reset", dependencies=[Depends(same_origin)])
def reset(body: Reset, db: Session = Depends(get_db)):
    user = consume_token(db, body.token, "reset")
    user.password_hash = passwords.hash(body.password)
    user.session_version += 1
    db.execute(
        update(EmailToken)
        .where(EmailToken.user_id == user.id, EmailToken.purpose == "reset")
        .values(used=True)
    )
    audit(db, user, "Password reset; sessions revoked")
    db.commit()
    return {"message": "Password reset. Sign in again."}


@app.get(PREFIX + "/workspace")
def workspace(user: User = Depends(current_user), db: Session = Depends(get_db)):
    orders = db.scalars(
        select(PaperOrder)
        .where(PaperOrder.user_id == user.id)
        .order_by(PaperOrder.created_at.desc())
    ).all()
    strategies = db.scalars(select(Strategy).where(Strategy.user_id == user.id)).all()
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.user_id == user.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(20)
    ).all()
    return {
        "session": public_user(user),
        "broker": user.broker,
        "balance": float(user.balance),
        "orders": [order_view(o) for o in orders],
        "strategies": [{**s.config, "id": s.id, "status": s.status} for s in strategies],
        "watchlist": user.watchlist,
        "activity": [e.action for e in events],
        "scenario": "normal",
    }


@app.post(PREFIX + "/brokers/paper/connect")
def connect(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.broker = "Connected"
    audit(db, user, "Paper broker connected")
    db.commit()
    return {"status": "Connected", "source": "paper-simulator"}


@app.get(PREFIX + "/brokers")
def broker_list(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    connections = {
        item.broker_code: item
        for item in db.scalars(
            select(BrokerConnection).where(BrokerConnection.user_id == user.id)
        )
    }
    config = settings()
    return {
        "providers": [
            {
                "code": code,
                "name": name,
                "configured": broker_auth.is_configured(code, config),
                "connection": (
                    {
                        "account_name": connection.account_name,
                        "account_mask": f"•••• {connection.account_id_last4}",
                        "connected_at": connection.connected_at.isoformat(),
                    }
                    if (connection := connections.get(code))
                    else None
                ),
            }
            for code, name in broker_auth.BROKERS.items()
        ],
        "live_orders_enabled": False,
    }


@app.post(PREFIX + "/brokers/{code}/authorization")
def broker_authorization(
    code: str,
    response: Response,
    user: User = Depends(current_user),
    cache: Redis = Depends(get_redis),
):
    if code not in broker_auth.BROKERS:
        fail(404, "BROKER_NOT_FOUND", "This broker is not supported.")
    state = secrets.token_urlsafe(32)
    try:
        authorization_url, provider_data = broker_auth.start_authorization(
            code, state, settings()
        )
    except broker_auth.BrokerNotConfigured:
        fail(503, "BROKER_NOT_CONFIGURED", "This broker is not configured for account linking.")
    except broker_auth.BrokerAuthError:
        fail(502, "BROKER_AUTH_UNAVAILABLE", "Could not start broker authorization. Please retry.")
    cache.setex(
        "broker-oauth:" + digest(state),
        BROKER_OAUTH_TTL,
        json.dumps({"user_id": user.id, "code": code, "provider_data": provider_data}),
    )
    for callback_path in broker_callback_paths():
        response.set_cookie(
            f"gnk_broker_state_{code}",
            state,
            max_age=BROKER_OAUTH_TTL,
            httponly=True,
            secure=settings().cookie_secure,
            samesite="lax",
            path=callback_path,
        )
    return {"authorization_url": authorization_url}


@app.get(PREFIX + "/brokers/{code}/callback")
def broker_callback(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    cookie_name = f"gnk_broker_state_{code}"

    def redirect_result(*, pending_token: str | None = None, error: bool = False):
        destination = f"{settings().frontend_url}/app/brokers/callback"
        if error:
            destination += "?error=authorization_failed"
        if pending_token:
            destination += f"#pending={pending_token}"
        result = RedirectResponse(destination, status_code=303)
        for callback_path in broker_callback_paths():
            result.delete_cookie(
                cookie_name,
                path=callback_path,
                secure=settings().cookie_secure,
                httponly=True,
                samesite="lax",
            )
        return result

    if code not in broker_auth.BROKERS:
        return redirect_result(error=True)

    state = request.cookies.get(cookie_name, "")
    if not state:
        return redirect_result(error=True)
    stored = cache.getdel("broker-oauth:" + digest(state))
    if not stored:
        return redirect_result(error=True)
    try:
        oauth = json.loads(stored)
    except (TypeError, json.JSONDecodeError):
        return redirect_result(error=True)
    if oauth.get("user_id") is None or oauth.get("code") != code:
        return redirect_result(error=True)

    params = dict(request.query_params)
    if code == "fyers":
        returned_state = params.get("state", "")
    elif code == "zerodha":
        returned_state = params.get("state", "")
        if not returned_state:
            redirect_params = parse_qs(params.get("redirect_params", ""))
            returned_state = redirect_params.get("state", [""])[0]
    else:
        returned_state = state
    if (
        not returned_state
        or not secrets.compare_digest(state, returned_state)
        or params.get("error")
        or params.get("status", "success") != "success"
        or params.get("s", "ok") != "ok"
    ):
        return redirect_result(error=True)

    user = db.get(User, oauth["user_id"])
    if not user or not user.enabled or not user.verified:
        return redirect_result(error=True)
    try:
        profile = broker_auth.complete_authorization(code, params, settings())
    except broker_auth.BrokerAuthError:
        return redirect_result(error=True)

    pending_token = secrets.token_urlsafe(32)
    cache.setex(
        "broker-pending:" + digest(pending_token),
        BROKER_OAUTH_TTL,
        json.dumps(
            {
                "user_id": user.id,
                "code": code,
                "account_id_last4": profile.account_id_last4,
                "account_name": profile.account_name,
            }
        ),
    )
    return redirect_result(pending_token=pending_token)


@app.post(PREFIX + "/brokers/pending")
def broker_pending(
    body: BrokerConfirmation,
    user: User = Depends(current_user),
    cache: Redis = Depends(get_redis),
):
    pending = cache.get("broker-pending:" + digest(body.token))
    if not pending:
        fail(404, "BROKER_LINK_EXPIRED", "Broker account confirmation expired. Reconnect and retry.")
    data = json.loads(pending)
    if data.get("user_id") != user.id:
        fail(404, "BROKER_LINK_EXPIRED", "Broker account confirmation expired. Reconnect and retry.")
    return {
        "code": data["code"],
        "name": broker_auth.BROKERS[data["code"]],
        "account_name": data["account_name"],
        "account_mask": f"•••• {data['account_id_last4']}",
    }


@app.post(PREFIX + "/brokers/{code}/confirm")
def broker_confirm(
    code: str,
    body: BrokerConfirmation,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    if code not in broker_auth.BROKERS:
        fail(404, "BROKER_NOT_FOUND", "This broker is not supported.")
    pending_key = "broker-pending:" + digest(body.token)
    pending = cache.getdel(pending_key)
    if not pending:
        fail(404, "BROKER_LINK_EXPIRED", "Broker account confirmation expired. Reconnect and retry.")
    data = json.loads(pending)
    if data.get("user_id") != user.id or data.get("code") != code:
        fail(404, "BROKER_LINK_EXPIRED", "Broker account confirmation expired. Reconnect and retry.")
    user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    connection = db.scalar(
        select(BrokerConnection)
        .where(BrokerConnection.user_id == user.id, BrokerConnection.broker_code == code)
        .with_for_update()
    )
    if connection:
        connection.account_id_last4 = data["account_id_last4"]
        connection.account_name = data["account_name"]
        connection.connected_at = now()
    else:
        db.add(
            BrokerConnection(
                user_id=user.id,
                broker_code=code,
                account_id_last4=data["account_id_last4"],
                account_name=data["account_name"],
            )
        )
    live_sessions = db.scalars(
        select(LiveTradingSession)
        .where(
            LiveTradingSession.user_id == user.id,
            LiveTradingSession.broker_code == code,
            LiveTradingSession.status.in_(("PENDING_CONFIRMATION", "ACTIVE")),
        )
        .with_for_update()
    ).all()
    for session in live_sessions:
        session.status = "SUSPENDED"
        session.suspension_reason = "BROKER_ACCOUNT_RELINKED"
        session.version += 1
        db.add(
            LiveTradingSessionEvent(
                session_id=session.id,
                user_id=user.id,
                event_type="BROKER_ACCOUNT_RELINKED",
                reason_code="BROKER_ACCOUNT_RELINKED",
                request_id=str(uuid4()),
                metadata_json={},
            )
        )
    audit(db, user, f"{broker_auth.BROKERS[code]} account linked")
    db.commit()
    return {"status": "Connected"}


@app.delete(PREFIX + "/brokers/{code}")
def broker_disconnect(
    code: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if code not in broker_auth.BROKERS:
        fail(404, "BROKER_NOT_FOUND", "This broker is not supported.")
    user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    connection = db.scalar(
        select(BrokerConnection).where(
            BrokerConnection.user_id == user.id, BrokerConnection.broker_code == code
        )
    )
    if connection:
        linked_sessions = db.scalars(
            select(LiveTradingSession)
            .where(
                LiveTradingSession.user_id == user.id,
                LiveTradingSession.broker_code == code,
            )
            .with_for_update()
        ).all()
        for session in linked_sessions:
            session.broker_connection_id = None
            if session.status in {"PENDING_CONFIRMATION", "ACTIVE"}:
                session.status = "SUSPENDED"
                session.suspension_reason = "BROKER_ACCOUNT_UNLINKED"
                session.version += 1
                db.add(
                    LiveTradingSessionEvent(
                        session_id=session.id,
                        user_id=user.id,
                        event_type="BROKER_ACCOUNT_UNLINKED",
                        reason_code="BROKER_ACCOUNT_UNLINKED",
                        request_id=str(uuid4()),
                        metadata_json={},
                    )
                )
        db.delete(connection)
        audit(db, user, f"{broker_auth.BROKERS[code]} account unlinked")
        db.commit()
    return {"status": "Disconnected"}


@app.post(PREFIX + "/paper/orders")
def submit(
    body: Ticket,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    try:
        key = str(UUID(request.headers.get("idempotency-key", "")))
    except ValueError:
        fail(422, "INVALID_REQUEST_KEY", "A UUID Idempotency-Key is required.")
    # Lock the account before checking the key; this serializes balance effects per user.
    user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    existing = db.scalar(
        select(PaperOrder).where(PaperOrder.user_id == user.id, PaperOrder.request_key == key)
    )
    submitted = body.model_dump(mode="json")
    if existing:
        if existing.ticket.get("request") != submitted:
            fail(
                409,
                "IDEMPOTENCY_CONFLICT",
                "Request key was already used for different order parameters.",
            )
        return order_view(existing)
    if user.broker != "Connected":
        fail(409, "BROKER_EXPIRED", "Connect the paper broker first.")
    if (
        body.symbol not in QUOTES
        or body.exchange != "NSE"
        or (body.type == "LIMIT" and body.price <= 0)
    ):
        fail(422, "INVALID_INSTRUMENT", "Invalid listed instrument, exchange or price.")
    price = Decimal(QUOTES[body.symbol]) if body.type == "MARKET" else body.price
    value = price * body.quantity
    rejected = body.side == "BUY" and value > user.balance
    ticket = {**submitted, "price": float(price), "request": submitted}
    order = PaperOrder(
        user_id=user.id,
        request_key=key,
        ticket=ticket,
        status="Rejected" if rejected else "Filled",
        reason="Insufficient paper balance" if rejected else None,
    )
    db.add(order)
    if not rejected:
        user.balance -= value * (1 if body.side == "BUY" else -1)
    audit(db, user, f"{body.symbol} · {body.side} {body.quantity} · {order.status}")
    db.commit()
    return order_view(order)


@app.get(PREFIX + "/paper/orders/{key}")
def reconcile(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    order = db.scalar(
        select(PaperOrder).where(PaperOrder.user_id == user.id, PaperOrder.request_key == key)
    )
    if not order:
        fail(
            404,
            "ORDER_NOT_FOUND",
            "No committed order found for this request. Retry with the same request key.",
        )
    return order_view(order)


@app.put(PREFIX + "/profile")
def profile(body: Profile, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.name = body.name.strip()
    audit(db, user, "Profile updated")
    db.commit()
    return public_user(user)


@app.put(PREFIX + "/watchlist/{symbol}")
def watchlist(symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if symbol not in QUOTES:
        fail(422, "INVALID_INSTRUMENT", "Instrument not listed.")
    user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    user.watchlist = (
        [s for s in user.watchlist if s != symbol]
        if symbol in user.watchlist
        else [*user.watchlist, symbol]
    )
    db.commit()
    return user.watchlist


@app.post(PREFIX + "/strategies")
@app.put(PREFIX + "/strategies/{strategy_id}")
def save_strategy(
    body: StrategyConfig,
    strategy_id: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if body.symbol not in QUOTES or not body.name.strip():
        fail(
            422,
            "INVALID_CONFIGURATION",
            "Use a listed instrument and a nonempty strategy name.",
        )
    strategy = (
        db.scalar(
            select(Strategy)
            .where(Strategy.id == strategy_id, Strategy.user_id == user.id)
            .with_for_update()
        )
        if strategy_id
        else Strategy(user_id=user.id)
    )
    if not strategy:
        fail(404, "NOT_FOUND", "Strategy not found.")
    if strategy.status == "Active":
        fail(409, "ACTIVE_STRATEGY", "Pause the strategy before editing.")
    strategy.config = {**body.model_dump(mode="json"), "loss": float(body.loss)}
    strategy.status = "Draft"
    db.add(strategy)
    audit(db, user, "Strategy configuration saved")
    db.commit()
    return {"id": strategy.id}


@app.post(PREFIX + "/strategies/{strategy_id}/transition")
def transition(
    strategy_id: str,
    body: Transition,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    strategy = db.scalar(
        select(Strategy)
        .where(Strategy.id == strategy_id, Strategy.user_id == user.id)
        .with_for_update()
    )
    allowed = {
        "Draft": ["Validated"],
        "Validated": ["Tested"],
        "Tested": ["Active"],
        "Active": ["Paused", "Stopped"],
        "Paused": ["Active", "Stopped"],
        "Stopped": ["Validated"],
    }
    if not strategy:
        fail(404, "NOT_FOUND", "Strategy not found.")
    if body.status not in allowed[strategy.status]:
        fail(409, "INVALID_TRANSITION", "Validate and paper test before activation.")
    if body.status == "Active" and user.broker != "Connected":
        fail(409, "BROKER_EXPIRED", "Connect the paper broker first.")
    strategy.status = body.status
    audit(db, user, f"Strategy {body.status}")
    db.commit()
    return {"status": strategy.status, "engine": "lifecycle-only; no trading engine"}


@app.get(PREFIX + "/admin/users")
def users(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "enabled": u.enabled,
        }
        for u in db.scalars(select(User).limit(100)).all()
    ]


@app.patch(PREFIX + "/admin/users/{user_id}")
def user_status(
    user_id: str,
    body: UserStatus,
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        fail(404, "NOT_FOUND", "User not found.")
    if target.id == user.id:
        fail(409, "SELF_MODIFICATION", "Cannot change your own account status.")
    target.enabled = body.enabled
    target.session_version += 1
    audit(db, user, "User status updated")
    db.commit()
    return {"enabled": target.enabled}


@app.get(PREFIX + "/admin/audit")
def audits(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [
        {"id": e.id, "action": e.action, "time": e.created_at.isoformat()}
        for e in db.scalars(
            select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100)
        ).all()
    ]


@app.get(PREFIX + "/admin/status")
def system_status(
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    ready(db, cache)
    return {
        "database": "ready",
        "redis": "ready",
        "execution": "paper-only",
        "mail_queue": cache.llen("gnk:mail"),
    }
