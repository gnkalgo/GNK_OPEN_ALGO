import secrets
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from app.models import EmailToken, User, now
from app.security import digest

P = "/api/gnk/v1"
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
