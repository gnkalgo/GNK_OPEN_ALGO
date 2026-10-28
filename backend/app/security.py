import hashlib
import json
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from redis import Redis
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

passwords = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))
COOKIE = "gnk_session"


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def get_redis():
    return Redis.from_url(
        settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=5,
    )


def fail(status: int, code: str, message: str):
    raise HTTPException(status, detail={"code": code, "message": message})


def verify_password(encoded: str, raw: str):
    try:
        return passwords.verify(encoded, raw)
    except (VerificationError, InvalidHashError):
        return False


def same_origin(request: Request):
    if request.headers.get("origin") != settings().frontend_url:
        fail(403, "ORIGIN_DENIED", "Request origin is not allowed.")


def rate_limit(request: Request, cache: Redis):
    # Atomic increment + expiry; no credentials, tokens or email addresses in keys.
    key = f"rate:{digest(request.client.host if request.client else 'unknown')}:{request.url.path}"
    with cache.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, 300, nx=True)
        count = pipe.execute()[0]
    if int(count) > 15:
        fail(429, "RATE_LIMITED", "Too many attempts. Try again in five minutes.")


def current_user(
    request: Request, db: Session = Depends(get_db), cache: Redis = Depends(get_redis)
):
    raw = request.cookies.get(COOKIE, "")
    data = cache.get("session:" + digest(raw)) if raw else None
    if not data:
        fail(401, "SESSION_EXPIRED", "Session expired. Sign in again.")
    session = json.loads(data)
    user = db.get(User, session["user_id"])
    if (
        not user
        or not user.enabled
        or not user.verified
        or session["version"] != user.session_version
    ):
        fail(401, "SESSION_EXPIRED", "Session expired. Sign in again.")
    request.state.csrf = session["csrf"]
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        same_origin(request)
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf"]):
            fail(403, "CSRF_INVALID", "Request verification failed. Reload and retry.")
    return user


def admin_user(user: User = Depends(current_user)):
    if user.role != "admin":
        fail(403, "FORBIDDEN", "Administrator permission required.")
    return user
