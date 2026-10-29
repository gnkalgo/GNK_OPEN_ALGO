from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from test_api import GNK_ALGO as P
from test_api import login, order

from app.models import AuditEvent, PaperOrder, User
from app.risk import daily_value


def policy(**changes):
    return {
        "max_order_value": "5000",
        "max_daily_value": "9000",
        "max_quantity": 2,
        "halted": False,
        **changes,
    }


def submit(client, ticket=None, key=None):
    return client.post(
        P + "/orders", json=ticket or order(), headers={"Idempotency-Key": key or str(uuid4())}
    )


def test_risk_requires_auth_csrf_and_rejects_owner_injection(client):
    assert client.get(P + "/risk-policy").status_code == 401
    login(client)
    assert (
        client.put(P + "/risk-policy", json=policy(), headers={"X-CSRF-Token": "bad"}).status_code
        == 403
    )
    assert client.put(P + "/risk-policy", json=policy(user_id="other")).status_code == 422
    assert client.put(P + "/risk-policy", json=policy(max_quantity=1001)).status_code == 422
    assert client.put(P + "/risk-policy", json=policy(max_order_value="NaN")).status_code == 422


def test_rejected_order_is_durable_and_replay_does_not_bypass_policy(client):
    login(client)
    client.post(P + "/brokers/paper/connect")
    assert client.put(P + "/risk-policy", json=policy()).status_code == 200
    before = client.get(P + "/workspace").json()["balance"]
    key = str(uuid4())
    rejected = submit(client, key=key).json()
    assert rejected["status"] == "Rejected"
    assert "Order value" in rejected["reason"]
    client.put(P + "/risk-policy", json=policy(max_order_value="10000"))
    assert submit(client, key=key).json() == rejected
    assert client.get(P + "/workspace").json()["balance"] == before
    assert client.get(P + "/risk-policy").json()["daily_value_used"] == "0"


def test_gross_daily_budget_and_halt_are_enforced(client):
    login(client)
    client.post(P + "/brokers/paper/connect")
    client.put(P + "/risk-policy", json=policy(max_order_value="9000"))
    first = submit(client).json()
    assert first["status"] == "Filled"
    sell = {**order(), "side": "SELL"}
    blocked = submit(client, sell).json()
    assert blocked["status"] == "Rejected" and "Daily gross" in blocked["reason"]
    client.put(P + "/risk-policy", json=policy(halted=True))
    assert "halt" in submit(client).json()["reason"]
    with client.db() as db:
        assert db.scalar(
            select(AuditEvent).where(AuditEvent.action == "Paper account risk policy updated")
        )


def test_quantity_emergency_stop_and_live_boundary(client):
    login(client)
    client.post(P + "/brokers/paper/connect")
    client.put(P + "/risk-policy", json=policy(max_quantity=1))
    assert "Quantity" in submit(client).json()["reason"]
    with client.db() as db:
        user = db.scalar(select(User))
        user.emergency_stop = True
        db.commit()
    client.put(P + "/risk-policy", json=policy(halted=False))
    assert submit(client).json()["status"] == "Rejected"  # Order-value cap still applies.
    assert client.get(P + "/risk-policy").json()["emergency_stop"] is True
    assert client.get(P + "/platform").json()["live_orders_enabled"] is False
    assert client.put(P + "/trading-mode", json={"mode": "LIVE"}).status_code == 409


def test_policy_and_turnover_are_isolated_by_account(client):
    login(client)
    client.put(P + "/risk-policy", json=policy(halted=True))
    with client.db() as db:
        first = db.scalar(select(User))
        second = User(
            email="second@example.com",
            name="Second User",
            password_hash=first.password_hash,
            verified=True,
        )
        db.add(second)
        db.flush()
        second_id = second.id
        db.add(
            PaperOrder(
                user_id=second_id,
                request_key=str(uuid4()),
                ticket={**order(), "price": 100},
                status="Filled",
            )
        )
        db.commit()
        assert daily_value(db, first.id, datetime.now(UTC)) == Decimal(0)
    client.post(P + "/auth/logout")
    response = client.post(
        P + "/auth/login", json={"email": "second@example.com", "password": "FictionalTest!2026"}
    )
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    second_policy = client.get(P + "/risk-policy").json()
    assert second_policy["halted"] is False and Decimal(second_policy["daily_value_used"]) == 200


def test_turnover_rolls_at_india_midnight_and_ignores_rejections(client):
    login(client)
    with client.db() as db:
        user = db.scalar(select(User))
        for at, state in [
            (datetime(2026, 10, 28, 18, 29, tzinfo=UTC), "Filled"),
            (datetime(2026, 10, 28, 18, 30, tzinfo=UTC), "Filled"),
            (datetime(2026, 10, 28, 19, 0, tzinfo=UTC), "Rejected"),
        ]:
            db.add(
                PaperOrder(
                    user_id=user.id,
                    request_key=str(uuid4()),
                    ticket={**order(), "price": 100},
                    status=state,
                    created_at=at,
                )
            )
        db.commit()
        assert daily_value(db, user.id, datetime(2026, 10, 29, 0, 0, tzinfo=UTC)) == Decimal(200)
