from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_api import GNK_ALGO as P
from test_api import login

from app import dhan_execution as execution
from app import dhan_live
from app.config import settings
from app.dhan_client import DhanClient, DhanError
from app.models import BrokerConnection, DhanInstrument, LiveOrder, LiveTradingSession, User, now
from app.security import digest
from app.token_vault import encrypt_access_token

KEY = "MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI="
ACCOUNT = "1000000001"
IP = "203.0.113.10"


@pytest.fixture
def live(client, monkeypatch):
    config = settings().model_copy(
        update={
            "dhan_token_encryption_key": KEY,
            "dhan_live_enabled": True,
            "dhan_live_approved": True,
            "dhan_execution_ip": IP,
            "dhan_live_account_ids": ACCOUNT,
            "dhan_live_security_ids": "900001",
            "dhan_live_max_order_value": Decimal("50000"),
            "dhan_live_max_daily_value": Decimal("50000"),
            "dhan_live_max_quantity": 10,
        }
    )
    import app.live_trading

    monkeypatch.setattr(execution, "settings", lambda: config)
    monkeypatch.setattr(app.live_trading, "settings", lambda: config)
    monkeypatch.setattr(dhan_live, "market_open", lambda: True)
    login(client)
    with client.db() as db:
        user = db.scalar(select(User))
        db.add(
            BrokerConnection(
                user_id=user.id,
                broker_code="dhan",
                account_id_last4=ACCOUNT[-4:],
                account_name="Fictional Dhan account",
                account_id_encrypted=encrypt_access_token(ACCOUNT, config),
                account_digest=digest("dhan:" + ACCOUNT),
                access_token_encrypted=encrypt_access_token("fictional-token", config),
                access_token_expires_at=now() + timedelta(hours=2),
            )
        )
        db.add(
            DhanInstrument(
                security_id="900001",
                name="Fictional test equity",
                lot_size=1,
                tick_size=Decimal("0.05"),
                lower_limit=Decimal("90"),
                upper_limit=Decimal("110"),
                freeze_quantity=100,
                enabled=True,
                synced_at=now(),
            )
        )
        db.commit()
    calls = []

    def fake(self, method, path, payload=None):
        calls.append((method, path, payload))
        if path == "/profile":
            return {
                "dhanClientId": ACCOUNT,
                "tokenValidity": "31/12/2099 15:30",
                "activeSegment": "Equity, Derivative",
            }
        if path == "/ip/getIP":
            return {"primaryIP": IP, "secondaryIP": ""}
        if path == "/fundlimit":
            return {"dhanClientId": ACCOUNT, "availabelBalance": 100000}
        if path == "/margincalculator":
            return {
                "totalMargin": 1000,
                "availableBalance": 100000,
                "insufficientBalance": 0,
                "brokerage": 5,
            }
        if path == "/orders":
            return {"orderId": "10001", "orderStatus": "PENDING"}
        if path.startswith("/orders/external/"):
            sent = next(
                body for method, url, body in calls if method == "POST" and url == "/orders"
            )
            return {
                **sent,
                "orderId": "10001",
                "orderStatus": "TRADED",
                "filledQty": sent["quantity"],
                "averageTradedPrice": 99,
            }
        raise AssertionError("Unexpected broker call")

    monkeypatch.setattr(DhanClient, "call", fake)
    session_id = client.post(P + "/live-sessions", json={"broker_code": "dhan"}).json()["session"][
        "id"
    ]
    return {
        "client": client,
        "config": config,
        "calls": calls,
        "fake": fake,
        "session_id": session_id,
    }


def activate(live):
    result = live["client"].post(
        P + f"/live-sessions/{live['session_id']}/confirm", json={"confirmed": True}
    )
    assert result.status_code == 200, result.text
    assert result.json()["live_orders_enabled"] is True
    return result


def preview(live, **changes):
    return live["client"].post(
        P + "/dhan/orders/preview",
        json={
            "session_id": live["session_id"],
            "security_id": "900001",
            "quantity": 2,
            "price": "100.00",
            **changes,
        },
    )


def submit(live, token, key=None, confirmed=True):
    return live["client"].post(
        P + "/dhan/orders",
        json={"preview_token": token, "confirmed": confirmed},
        headers={"Idempotency-Key": key or str(uuid4())},
    )


def test_activation_validates_identity_ip_and_expiry_then_paper_selection_suspends(live):
    activate(live)
    status = live["client"].get(P + "/trading-mode").json()
    assert status["mode"] == "LIVE" and status["broker_auth_valid"]
    assert status["session"]["last_validated_at"]
    assert not any(path == "/orders" for _, path, _ in live["calls"])
    assert live["client"].put(P + "/trading-mode", json={"mode": "PAPER"}).json()["mode"] == "PAPER"
    assert preview(live).status_code == 409


@pytest.mark.parametrize(
    "failure",
    ["identity", "ip", "segment", "expiry", "disabled", "unapproved", "account", "master", "token"],
)
def test_activation_fails_closed(live, monkeypatch, failure):
    config = live["config"]
    if failure == "disabled":
        config.dhan_live_enabled = False
    if failure == "unapproved":
        config.dhan_live_approved = False
    if failure == "account":
        config.dhan_live_account_ids = "other-account"
    if failure in {"master", "token"}:
        with live["client"].db() as db:
            if failure == "master":
                db.get(DhanInstrument, "900001").synced_at = now() - timedelta(days=1)
            else:
                db.scalar(select(BrokerConnection)).access_token_expires_at = now() - timedelta(
                    seconds=1
                )
            db.commit()

    def fake(self, method, path, payload=None):
        result = live["fake"](self, method, path, payload)
        if path == "/profile":
            if failure == "identity":
                result["dhanClientId"] = "another-account"
            if failure == "segment":
                result["activeSegment"] = "Derivative"
            if failure == "expiry":
                result["tokenValidity"] = "01/01/2000 00:00"
        if path == "/ip/getIP" and failure == "ip":
            result["primaryIP"] = "203.0.113.20"
        return result

    monkeypatch.setattr(DhanClient, "call", fake)
    result = live["client"].post(
        P + f"/live-sessions/{live['session_id']}/confirm", json={"confirmed": True}
    )
    assert result.status_code == 409
    assert not any(path == "/orders" for _, path, _ in live["calls"])
    assert "fictional-token" not in result.text and ACCOUNT not in result.text


def test_preview_confirmation_durable_replay_and_real_fill_reconciliation(live):
    activate(live)
    result = preview(live)
    assert result.status_code == 200, result.text
    token = result.json()["preview_token"]
    assert not any(path == "/orders" for _, path, _ in live["calls"])
    assert submit(live, token, confirmed=False).status_code == 400
    key = str(uuid4())
    placed = submit(live, token, key)
    assert placed.status_code == 200, placed.text
    order = placed.json()
    assert order["status"] == "PENDING" and order["filled_quantity"] == 0
    assert submit(live, token, key).json() == order
    assert submit(live, "different-preview-token-with-valid-length", key).status_code == 409
    assert sum(path == "/orders" for _, path, _ in live["calls"]) == 1
    assert preview(live).status_code == 409
    reconciled = live["client"].post(P + f"/dhan/orders/{order['id']}/reconcile")
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["status"] == "TRADED" and reconciled.json()["filled_quantity"] == 2
    assert live["client"].get(P + "/workspace").json()["orders"] == []
    with live["client"].db() as db:
        assert db.query(LiveOrder).count() == 1
        assert db.scalar(select(User)).balance == Decimal("245680.50")


def test_ambiguous_submission_keeps_intent_and_never_retries_broker(live, monkeypatch):
    activate(live)
    token = preview(live).json()["preview_token"]

    def lose_response(self, payload):
        with live["client"].db() as db:
            assert db.scalar(select(LiveOrder)).status == "UNKNOWN"
        live["calls"].append(("POST", "/orders", payload))
        raise DhanError("Response lost")

    monkeypatch.setattr(DhanClient, "place", lose_response)
    key = str(uuid4())
    order = submit(live, token, key).json()
    assert order["status"] == "UNKNOWN"
    assert submit(live, token, key).json()["id"] == order["id"]
    assert preview(live).status_code == 409
    assert sum(path == "/orders" for _, path, _ in live["calls"]) == 1
    assert (
        live["client"].post(P + f"/dhan/orders/{order['id']}/reconcile").json()["status"]
        == "TRADED"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"price": "100.01"},
        {"price": "120"},
        {"quantity": 11},
        {"security_id": "999999"},
        {"side": "SELL"},
        {"product": "INTRADAY"},
    ],
)
def test_invalid_or_unsupported_orders_never_dispatch(live, changes):
    activate(live)
    assert preview(live, **changes).status_code in {409, 422}
    assert not any(path == "/orders" for _, path, _ in live["calls"])


def test_stop_between_preview_and_confirmation_blocks_dispatch(live):
    activate(live)
    token = preview(live).json()["preview_token"]
    live["client"].post(P + "/emergency-stop")
    assert submit(live, token).status_code == 409
    assert not any(path == "/orders" for _, path, _ in live["calls"])


def test_margin_and_profile_are_rechecked_at_confirmation(live, monkeypatch):
    activate(live)
    token = preview(live).json()["preview_token"]

    def fake(self, method, path, payload=None):
        result = live["fake"](self, method, path, payload)
        if path == "/fundlimit":
            result["availabelBalance"] = 0
        return result

    monkeypatch.setattr(DhanClient, "call", fake)
    assert submit(live, token).status_code == 409
    assert not any(path == "/orders" for _, path, _ in live["calls"])


def test_preview_replay_and_csrf_owner_checks(live):
    activate(live)
    token = preview(live).json()["preview_token"]
    assert (
        live["client"]
        .post(
            P + "/dhan/orders",
            json={"preview_token": token, "confirmed": True},
            headers={"X-CSRF-Token": "wrong", "Idempotency-Key": str(uuid4())},
        )
        .status_code
        == 403
    )
    assert submit(live, token).status_code == 200
    assert submit(live, token).status_code == 409
    assert live["client"].post(P + f"/dhan/orders/{uuid4()}/reconcile").status_code == 404


def test_daily_budget_includes_prior_live_orders(live):
    activate(live)
    token = preview(live).json()["preview_token"]
    order = submit(live, token).json()
    live["client"].post(P + f"/dhan/orders/{order['id']}/reconcile")
    live["config"].dhan_live_max_daily_value = Decimal("300")
    assert preview(live).status_code == 409


def test_session_version_change_invalidates_preview(live):
    activate(live)
    token = preview(live).json()["preview_token"]
    with live["client"].db() as db:
        db.get(LiveTradingSession, live["session_id"]).version += 1
        db.commit()
    assert submit(live, token).status_code == 409
    assert not any(path == "/orders" for _, path, _ in live["calls"])


def test_suspension_after_durable_intent_prevents_broker_dispatch(live, monkeypatch):
    from sqlalchemy import update
    from sqlalchemy.orm import Session

    activate(live)
    token = preview(live).json()["preview_token"]
    original = Session.commit

    def commit_then_suspend(self):
        intent_created = any(isinstance(value, LiveOrder) for value in self.new)
        original(self)
        if intent_created:
            with live["client"].db() as other:
                other.execute(
                    update(LiveTradingSession)
                    .where(LiveTradingSession.id == live["session_id"])
                    .values(status="SUSPENDED")
                )
                original(other)

    monkeypatch.setattr(Session, "commit", commit_then_suspend)
    result = submit(live, token)
    assert result.status_code == 200
    assert result.json()["status"] == "BLOCKED"
    assert not any(path == "/orders" for _, path, _ in live["calls"])


def test_reconciliation_rejects_account_mismatch_and_decreasing_fills(live, monkeypatch):
    activate(live)
    token = preview(live).json()["preview_token"]
    order = submit(live, token).json()

    def mismatch(self, correlation):
        result = live["fake"](self, "GET", "/orders/external/" + correlation)
        result["dhanClientId"] = "other-account"
        return result

    monkeypatch.setattr(DhanClient, "lookup", mismatch)
    assert live["client"].post(P + f"/dhan/orders/{order['id']}/reconcile").status_code == 409
    monkeypatch.setattr(
        DhanClient, "lookup", lambda self, c: live["fake"](self, "GET", "/orders/external/" + c)
    )
    assert (
        live["client"].post(P + f"/dhan/orders/{order['id']}/reconcile").json()["status"]
        == "TRADED"
    )

    def decreasing(self, correlation):
        result = live["fake"](self, "GET", "/orders/external/" + correlation)
        result.update(orderStatus="PENDING", filledQty=0, averageTradedPrice=0)
        return result

    monkeypatch.setattr(DhanClient, "lookup", decreasing)
    assert live["client"].post(P + f"/dhan/orders/{order['id']}/reconcile").status_code == 409
    assert live["client"].get(P + "/dhan/orders").json()["orders"][0]["filled_quantity"] == 2


def test_preview_expiry_and_outside_order_window_cannot_place(live, monkeypatch):
    activate(live)
    token = preview(live).json()["preview_token"]
    live["client"].cache.delete("dhan-preview:" + digest(token))
    assert submit(live, token).status_code == 409
    monkeypatch.setattr(dhan_live, "market_open", lambda: False)
    assert preview(live).status_code == 409
    assert not any(path == "/orders" for _, path, _ in live["calls"])


def test_other_user_cannot_read_preview_or_reconcile_a_live_order(live):
    client = live["client"]
    activate(live)
    token = preview(live).json()["preview_token"]
    order = submit(live, token).json()
    with client.db() as db:
        owner = db.scalar(select(User))
        db.add(
            User(
                email="different@example.com",
                name="Different user",
                verified=True,
                password_hash=owner.password_hash,
            )
        )
        db.commit()
    client.post(P + "/auth/logout")
    response = client.post(
        P + "/auth/login", json={"email": "different@example.com", "password": "FictionalTest!2026"}
    )
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    assert client.get(P + "/dhan/orders").json()["orders"] == []
    assert client.post(P + f"/dhan/orders/{order['id']}/reconcile").status_code == 404
    assert preview(live).status_code == 404
