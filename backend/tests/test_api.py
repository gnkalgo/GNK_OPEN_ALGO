import secrets
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from app.models import EmailToken, User, now
from app.security import digest

P = "/api/gnk/v1"
GNK_ALGO = "/api/v1/gnkalgo"
PASSWORD = "FictionalTest!2026"


def token_for(client, purpose="verify", expired=False):
    raw = secrets.token_urlsafe(32)
    with client.db() as db:
        user = db.scalar(select(User))
        db.add(
            EmailToken(
                digest=digest(raw),
                user_id=user.id,
                purpose=purpose,
                expires_at=now() + timedelta(minutes=-1 if expired else 30),
            )
        )
        db.commit()
    return raw


def login(client):
    client.post(
        P + "/auth/register",
        json={
            "name": "Paper Trader",
            "email": "paper@example.com",
            "password": PASSWORD,
        },
    )
    assert client.post(P + "/auth/verify", json={"token": token_for(client)}).status_code == 200
    response = client.post(
        P + "/auth/login", json={"email": "paper@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    return response


def order():
    return {
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "product": "Delivery",
        "side": "BUY",
        "quantity": 2,
        "type": "MARKET",
        "price": 0,
    }


def test_registration_verification_login_and_revocation(client):
    response = login(client)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert client.get(P + "/workspace").json()["session"]["role"] == "trader"
    assert client.post(P + "/auth/logout").status_code == 200
    assert client.get(P + "/workspace").status_code == 401


def test_registration_cannot_inject_role_or_return_secrets(client):
    response = client.post(
        P + "/auth/register",
        json={
            "name": "Demo",
            "email": "demo@example.com",
            "password": PASSWORD,
            "role": "admin",
        },
    )
    assert response.status_code == 422
    assert PASSWORD not in response.text and "input" not in response.text


def test_csrf_origin_and_admin_are_enforced_by_server(client):
    login(client)
    assert client.get(P + "/admin/users").status_code == 403
    assert (
        client.post(P + "/brokers/paper/connect", headers={"X-CSRF-Token": "bad"}).status_code
        == 403
    )
    assert (
        client.post(
            P + "/brokers/paper/connect", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.post(P + "/brokers/paper/connect").status_code == 200


def test_broker_account_link_is_confirmed_and_never_persists_tokens(client, monkeypatch):
    from types import SimpleNamespace
    from urllib.parse import parse_qs, urlencode, urlsplit

    import app.main
    from app import broker_auth
    from app.models import BrokerConnection

    config = SimpleNamespace(
        frontend_url="http://testserver",
        cookie_secure=False,
        session_ttl=28800,
        dhan_partner_id="dhan-id",
        dhan_partner_secret="dhan-secret",
        fyers_client_id="fyers-id",
        fyers_app_secret="fyers-secret",
        zerodha_api_key="zerodha-key",
        zerodha_api_secret="zerodha-secret",
    )
    monkeypatch.setattr(app.main, "settings", lambda: config)
    monkeypatch.setattr(
        broker_auth,
        "start_authorization",
        lambda code, state, settings: ("https://kite.example/login", {}),
    )
    monkeypatch.setattr(
        broker_auth,
        "complete_authorization",
        lambda code, params, settings: broker_auth.BrokerProfile(
            "1234", "Paper Test Account"
        ),
    )
    login(client)

    start = client.post(P + "/brokers/zerodha/authorization")
    assert start.status_code == 200
    assert start.json()["authorization_url"] == "https://kite.example/login"
    state = client.cookies.get("gnk_broker_state_zerodha")
    assert state

    callback = client.get(
        P + "/brokers/zerodha/callback",
        params={
            "status": "success",
            "request_token": "one-time-request-token",
            "redirect_params": urlencode({"state": state}),
        },
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"].startswith(
        "http://testserver/app/brokers/callback#pending="
    )
    pending_token = parse_qs(urlsplit(callback.headers["location"]).fragment)["pending"][0]
    with client.db() as db:
        assert db.query(BrokerConnection).count() == 0

    pending = client.post(P + "/brokers/pending", json={"token": pending_token})
    assert pending.status_code == 200
    assert pending.json()["account_mask"] == "•••• 1234"
    assert pending.json()["account_name"] == "Paper Test Account"

    confirmed = client.post(
        P + "/brokers/zerodha/confirm", json={"token": pending_token}
    )
    assert confirmed.status_code == 200
    assert client.post(
        P + "/brokers/zerodha/confirm", json={"token": pending_token}
    ).status_code == 404

    columns = BrokerConnection.__table__.columns.keys()
    assert "access_token" not in columns and "api_secret" not in columns
    linked = client.get(P + "/brokers").json()
    zerodha = next(item for item in linked["providers"] if item["code"] == "zerodha")
    assert zerodha["connection"]["account_name"] == "Paper Test Account"
    assert linked["live_orders_enabled"] is False
    assert client.delete(P + "/brokers/zerodha").status_code == 200


def test_broker_authorization_rejects_unconfigured_provider(client, monkeypatch):
    from types import SimpleNamespace

    import app.main

    config = SimpleNamespace(
        frontend_url="http://testserver",
        cookie_secure=False,
        session_ttl=28800,
        dhan_partner_id="",
        dhan_partner_secret="",
        fyers_client_id="",
        fyers_app_secret="",
        zerodha_api_key="",
        zerodha_api_secret="",
    )
    monkeypatch.setattr(app.main, "settings", lambda: config)
    login(client)
    response = client.post(P + "/brokers/dhan/authorization")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "BROKER_NOT_CONFIGURED"


def test_registration_accepts_apex_and_www_frontend_origins(client, monkeypatch):
    from types import SimpleNamespace

    import app.security

    monkeypatch.setattr(
        app.security,
        "settings",
        lambda: SimpleNamespace(frontend_url="https://gnkalgo.com"),
    )
    for origin, email in (
        ("https://gnkalgo.com", "apex@example.com"),
        ("https://www.gnkalgo.com", "www@example.com"),
    ):
        assert (
            client.post(
                P + "/auth/register",
                headers={"Origin": origin},
                json={"name": "Demo", "email": email, "password": PASSWORD},
            ).status_code
            == 202
        )
    assert (
        client.post(
            P + "/auth/register",
            headers={"Origin": "https://evil.example"},
            json={"name": "Demo", "email": "evil@example.com", "password": PASSWORD},
        ).status_code
        == 403
    )


def test_expired_and_replayed_email_links(client):
    client.post(
        P + "/auth/register",
        json={"name": "Paper", "email": "paper@example.com", "password": PASSWORD},
    )
    assert (
        client.post(P + "/auth/verify", json={"token": token_for(client, expired=True)}).status_code
        == 400
    )
    raw = token_for(client)
    assert client.post(P + "/auth/verify", json={"token": raw}).status_code == 200
    assert client.post(P + "/auth/verify", json={"token": raw}).status_code == 400


def test_password_reset_invalidates_existing_session(client):
    login(client)
    raw = token_for(client, purpose="reset")
    assert (
        client.post(
            P + "/auth/reset", json={"token": raw, "password": "DifferentTest!2026"}
        ).status_code
        == 200
    )
    assert client.get(P + "/workspace").status_code == 401
    assert (
        client.post(P + "/auth/reset", json={"token": raw, "password": PASSWORD}).status_code == 400
    )


def test_idempotent_paper_orders_and_conflict(client):
    login(client)
    assert (
        client.post(
            P + "/paper/orders", json=order(), headers={"Idempotency-Key": str(uuid4())}
        ).status_code
        == 409
    )
    client.post(P + "/brokers/paper/connect")
    key = str(uuid4())
    first = client.post(P + "/paper/orders", json=order(), headers={"Idempotency-Key": key})
    assert first.status_code == 200 and first.json()["status"] == "Filled"
    assert (
        client.post(P + "/paper/orders", json=order(), headers={"Idempotency-Key": key}).json()[
            "id"
        ]
        == key
    )
    assert (
        client.post(
            P + "/paper/orders",
            json={**order(), "quantity": 3},
            headers={"Idempotency-Key": key},
        ).status_code
        == 409
    )
    workspace = client.get(P + "/workspace").json()
    assert len(workspace["orders"]) == 1 and workspace["balance"] == 239783.5
    assert client.get(P + f"/paper/orders/{key}").json()["status"] == "Filled"
    assert client.get(P + f"/paper/orders/{uuid4()}").status_code == 404


def test_server_rejects_invalid_quantities_and_insufficient_balance(client):
    login(client)
    client.post(P + "/brokers/paper/connect")
    for value in [0, -1, 1.5, True, 1001]:
        assert (
            client.post(
                P + "/paper/orders",
                json={**order(), "quantity": value},
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 422
        )
    response = client.post(
        P + "/paper/orders",
        json={**order(), "quantity": 1000},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.json()["status"] == "Rejected"
    assert client.get(P + "/workspace").json()["balance"] == 245680.5


def test_strategy_lifecycle_and_edit_invalidates_tests(client):
    login(client)
    client.post(P + "/brokers/paper/connect")
    config = {
        "name": "Momentum",
        "symbol": "RELIANCE",
        "quantity": 2,
        "loss": 500,
        "signal": "EMA crossover",
    }
    sid = client.post(P + "/strategies", json=config).json()["id"]
    path = P + f"/strategies/{sid}"
    assert client.post(path + "/transition", json={"status": "Active"}).status_code == 409
    for status in ["Validated", "Tested", "Active"]:
        assert client.post(path + "/transition", json={"status": status}).status_code == 200
    assert client.put(path, json=config).status_code == 409
    assert client.post(path + "/transition", json={"status": "Paused"}).status_code == 200
    assert client.put(path, json=config).status_code == 200
    assert client.get(P + "/workspace").json()["strategies"][0]["status"] == "Draft"


def test_cross_account_order_and_strategy_access_denied(client):
    login(client)
    client.post(P + "/brokers/paper/connect")
    key = str(uuid4())
    client.post(P + "/paper/orders", json=order(), headers={"Idempotency-Key": key})
    sid = client.post(
        P + "/strategies",
        json={
            "name": "Momentum",
            "symbol": "RELIANCE",
            "quantity": 2,
            "loss": 500,
            "signal": "EMA crossover",
        },
    ).json()["id"]
    with client.db() as db:
        user = db.scalar(select(User))
        # Ownership is checked from the session, never from the request body.
        other = User(
            name="Other",
            email="other@example.com",
            password_hash=user.password_hash,
            verified=True,
        )
        db.add(other)
        db.commit()
    response = client.post(
        P + "/auth/login", json={"email": "other@example.com", "password": PASSWORD}
    )
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    assert client.get(P + f"/paper/orders/{key}").status_code == 404
    assert (
        client.post(P + f"/strategies/{sid}/transition", json={"status": "Validated"}).status_code
        == 404
    )


def test_rate_limit_and_generic_login_failure(client):
    for _ in range(15):
        assert (
            client.post(
                P + "/auth/login",
                json={"email": "unknown@example.com", "password": PASSWORD},
            ).status_code
            == 401
        )
    assert (
        client.post(
            P + "/auth/login",
            json={"email": "unknown@example.com", "password": PASSWORD},
        ).status_code
        == 429
    )


def test_admin_permission_comes_from_database(client):
    login(client)
    with client.db() as db:
        user = db.scalar(select(User))
        user.role = "admin"
        db.commit()
    response = client.get(P + "/admin/users")
    assert response.status_code == 200
    assert "password_hash" not in response.text
    assert client.get(P + "/admin/audit").status_code == 200


def test_account_disable_revokes_session(client):
    login(client)
    with client.db() as db:
        db.scalar(select(User)).enabled = False
        db.commit()
    assert client.get(P + "/session").status_code == 401


def test_gnkalgo_namespace_uses_authenticated_paper_services(client):
    assert client.get(GNK_ALGO + "/health").json()["execution"] == "paper-only"
    quote = client.get(GNK_ALGO + "/market/quote", params={"symbol": "TCS"})
    assert quote.status_code == 200
    assert quote.json()["source"] == "paper-fixture"
    assert client.get(GNK_ALGO + "/brokers").status_code == 401

    login(client)
    unavailable = client.post(GNK_ALGO + "/brokers/dhan/connect")
    assert unavailable.status_code == 409
    assert unavailable.json()["detail"]["code"] == "BROKER_EXECUTION_UNAVAILABLE"
    assert (
        client.get(GNK_ALGO + "/brokers/paper/status").json()["connected"] is False
    )
    assert client.post(GNK_ALGO + "/brokers/paper/connect").status_code == 200

    key = str(uuid4())
    submitted = client.post(
        GNK_ALGO + "/orders",
        json=order(),
        headers={"Idempotency-Key": key},
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "Filled"

    update = client.put(GNK_ALGO + f"/orders/{key}")
    assert update.status_code == 409
    assert update.json()["detail"]["code"] == "ORDER_NOT_MODIFIABLE"
    cancel = client.delete(GNK_ALGO + f"/orders/{key}")
    assert cancel.status_code == 409
    assert cancel.json()["detail"]["code"] == "ORDER_NOT_CANCELLABLE"
    assert len(client.get(GNK_ALGO + "/orders").json()["orders"]) == 1
