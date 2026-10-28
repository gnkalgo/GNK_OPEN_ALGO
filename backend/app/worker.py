"""Durable DB outbox with Redis queue hints; SMTP payloads are never logged."""

import secrets
import smtplib
import ssl
import time
from datetime import timedelta
from email.message import EmailMessage

from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .models import EmailToken, MailOutbox, User, now
from .security import digest, get_redis


def process_one():
    with SessionLocal() as db:
        item = db.scalar(
            select(MailOutbox)
            .where(MailOutbox.sent.is_(False), MailOutbox.attempts < 5)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not item:
            return False
        original = db.get(EmailToken, item.token_digest)
        user = db.get(User, original.user_id)
        if not user or not user.enabled:
            item.sent = True
            db.commit()
            return True
        raw = secrets.token_urlsafe(32)
        original.used = True
        token = EmailToken(
            digest=digest(raw),
            user_id=user.id,
            purpose=original.purpose,
            expires_at=now() + timedelta(minutes=30),
        )
        db.add(token)
        db.flush()
        item.attempts += 1
        # Commit the token before delivery, so a received link is immediately usable.
        item.token_digest = token.digest
        db.commit()
        route = "verify-email" if token.purpose == "verify" else "reset-password"
        message = EmailMessage()
        message["From"] = settings().smtp_from
        message["To"] = user.email
        message["Subject"] = (
            "GNK ALGO: verify your email"
            if token.purpose == "verify"
            else "GNK ALGO: password reset"
        )
        message.set_content(
            f"Open this single-use link within 30 minutes:\n{settings().frontend_url}/{route}#token={raw}\nIf you did not request this, ignore this message."
        )
        try:
            with smtplib.SMTP(settings().smtp_host, settings().smtp_port, timeout=15) as smtp:
                if settings().smtp_starttls:
                    smtp.starttls(context=ssl.create_default_context())
                if settings().smtp_username:
                    smtp.login(settings().smtp_username, settings().smtp_password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException):
            # Bounded retries; the durable outbox survives Redis loss/restarts.
            return True
        item.sent = True
        db.commit()
        return True


def main():
    cache = get_redis()
    while True:
        try:
            with SessionLocal() as db:
                ids = db.scalars(
                    select(MailOutbox.id)
                    .where(MailOutbox.sent.is_(False), MailOutbox.attempts < 5)
                    .limit(100)
                ).all()
                if ids:
                    with cache.pipeline() as pipe:
                        pipe.delete("gnk:mail")
                        pipe.lpush("gnk:mail", *ids)
                        pipe.execute()
            job = cache.brpop("gnk:mail", timeout=5)
            if job:
                lock = cache.lock("gnk:mail-worker", timeout=45, blocking_timeout=1)
                if lock.acquire(blocking=False):
                    try:
                        process_one()
                    finally:
                        lock.release()
            time.sleep(2)
        except Exception:
            # No exception values: SMTP messages, DB params and tokens must stay private.
            time.sleep(5)


if __name__ == "__main__":
    main()
