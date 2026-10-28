import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from redis import Redis
from sqlalchemy import select
from test_api import P, login, order

from app import worker
from app.models import EmailToken, MailOutbox


@pytest.mark.skipif(not os.getenv("TEST_REDIS_URL"), reason="Requires disposable Redis 8 service")
def test_real_redis_expiring_cache_and_queue():
    cache = Redis.from_url(os.environ["TEST_REDIS_URL"])
    key = "gnk-test:" + str(uuid4())
    try:
        assert cache.set(key, "fixture", ex=30)
        assert cache.get(key) == b"fixture" and cache.ttl(key) > 0
        cache.rpush(key + ":queue", "fixture-job")
        assert cache.blpop(key + ":queue", timeout=1)[1] == b"fixture-job"
    finally:
        cache.delete(key, key + ":queue")


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Requires disposable PostgreSQL 17 row locks"
)
def test_concurrent_postgres_idempotency(client):
    login(client)
    client.post(P + "/brokers/paper/connect")
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    P + "/paper/orders", json=order(), headers={"Idempotency-Key": key}
                ),
                range(2),
            )
        )
    assert all(r.status_code == 200 for r in responses)
    data = client.get(P + "/workspace").json()
    assert len(data["orders"]) == 1 and data["balance"] == 239783.5


def test_worker_delivers_single_use_link_without_persisting_plain_token(client, monkeypatch):
    client.post(
        P + "/auth/register",
        json={"name": "Paper", "email": "paper@example.com", "password": "FictionalTest!2026"},
    )
    smtp = MagicMock()
    monkeypatch.setattr(worker, "SessionLocal", client.db)
    monkeypatch.setattr(worker.smtplib, "SMTP", smtp)
    assert worker.process_one()
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    link = message.get_content().split("#token=")[1].splitlines()[0]
    with client.db() as db:
        assert db.scalar(select(MailOutbox)).sent
        assert not db.get(EmailToken, link)
    assert client.post(P + "/auth/verify", json={"token": link}).status_code == 200
    assert client.post(P + "/auth/verify", json={"token": link}).status_code == 400
