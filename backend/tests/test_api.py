import json
import secrets
from datetime import UTC, datetime, timedelta
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
        dhan_token_encryption_key="MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI=",
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
    assert "access_token_encrypted" in columns
    linked = client.get(P + "/brokers").json()
    zerodha = next(item for item in linked["providers"] if item["code"] == "zerodha")
    assert zerodha["connection"]["account_name"] == "Paper Test Account"
    assert linked["live_orders_enabled"] is False
    assert client.delete(P + "/brokers/zerodha").status_code == 200


def test_dhan_link_stores_only_encrypted_access_token(client, monkeypatch):
    from types import SimpleNamespace
    from urllib.parse import parse_qs, urlsplit

    import app.main
    from app import broker_auth
    from app.models import BrokerConnection
    from app.security import digest
    from app.token_vault import decrypt_access_token

    key = "MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI="
    config = SimpleNamespace(
        frontend_url="http://testserver",
        cookie_secure=False,
        session_ttl=28800,
        dhan_partner_id="dhan-id",
        dhan_partner_secret="dhan-secret",
        dhan_token_encryption_key=key,
        fyers_client_id="",
        fyers_app_secret="",
        zerodha_api_key="",
        zerodha_api_secret="",
    )
    token = "secret-dhan-access-token"
    expires_at = datetime(2026, 10, 30, 10, tzinfo=UTC)
    monkeypatch.setattr(app.main, "settings", lambda: config)
    monkeypatch.setattr(
        broker_auth,
        "start_authorization",
        lambda code, state, settings: ("https://dhan.example/consent", {}),
    )
    monkeypatch.setattr(
        broker_auth,
        "complete_authorization",
        lambda code, params, settings: broker_auth.BrokerProfile(
            "1234", "Dhan Test Account", token, expires_at
        ),
    )
    login(client)

    assert client.post(P + "/brokers/dhan/authorization").status_code == 200
    state = client.cookies.get("gnk_broker_state_dhan")
    callback = client.get(
        P + "/brokers/dhan/callback",
        params={"status": "success", "tokenId": "one-time-token"},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    pending_token = parse_qs(urlsplit(callback.headers["location"]).fragment)["pending"][0]
    pending_key = "broker-pending:" + digest(pending_token)
    pending_data = json.loads(client.cache.get(pending_key))
    assert pending_data["access_token_encrypted"] != token
    assert token not in client.cache.get(pending_key)
    assert pending_data["access_token_expires_at"] == expires_at.isoformat()
    assert client.post(P + "/brokers/pending", json={"token": pending_token}).json()[
        "account_mask"
    ] == "•••• 1234"

    confirmed = client.post(P + "/brokers/dhan/confirm", json={"token": pending_token})
    assert confirmed.status_code == 200
    with client.db() as db:
        connection = db.query(BrokerConnection).one()
        assert connection.access_token_encrypted != token
        assert decrypt_access_token(connection.access_token_encrypted, config) == token
        assert connection.access_token_expires_at is not None
        assert connection.access_token_expires_at.replace(tzinfo=UTC) == expires_at
    public = client.get(P + "/brokers").json()
    assert token not in json.dumps(public)
    assert public["live_orders_enabled"] is False
    assert client.delete(P + "/brokers/dhan").status_code == 200
    with client.db() as db:
        assert db.query(BrokerConnection).count() == 0
    assert state


def test_broker_authorization_rejects_unconfigured_provider(client, monkeypatch):
    from types import SimpleNamespace

    import app.main

    config = SimpleNamespace(
        frontend_url="http://testserver",
        cookie_secure=False,
        session_ttl=28800,
        dhan_partner_id="",
        dhan_partner_secret="",
        dhan_token_encryption_key="",
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


def test_live_trading_control_plane_records_requests_but_never_activates(client):
    from app.models import BrokerConnection, LiveTradingSession, LiveTradingSessionEvent

    login(client)
    status = client.get(GNK_ALGO + "/trading-mode")
    assert status.status_code == 200
    assert status.json()["mode"] == "PAPER"
    assert status.json()["live_orders_enabled"] is False
    assert status.json()["session_status"] == "INACTIVE"

    live_mode = client.put(GNK_ALGO + "/trading-mode", json={"mode": "LIVE"})
    assert live_mode.status_code == 409
    assert live_mode.json()["detail"]["code"] == "LIVE_TRADING_UNAVAILABLE"
    assert (
        client.post(GNK_ALGO + "/live-sessions", json={"broker_code": "dhan"}).status_code
        == 409
    )

    with client.db() as db:
        user = db.scalar(select(User))
        db.add(
            BrokerConnection(
                user_id=user.id,
                broker_code="dhan",
                account_id_last4="4321",
                account_name="Linked Dhan Account",
            )
        )
        db.commit()

    requested = client.post(
        GNK_ALGO + "/live-sessions",
        json={"broker_code": "dhan"},
        headers={"X-Request-ID": str(uuid4())},
    )
    assert requested.status_code == 201
    pending = requested.json()["session"]
    assert pending["status"] == "PENDING_CONFIRMATION"
    assert pending["broker_account_mask"] == "•••• 4321"
    assert pending["broker_auth_valid"] is False
    assert pending["live_orders_enabled"] is False

    missing_confirmation = client.post(
        GNK_ALGO + f"/live-sessions/{pending['id']}/confirm",
        json={"confirmed": False},
    )
    assert missing_confirmation.status_code == 400
    blocked_confirmation = client.post(
        GNK_ALGO + f"/live-sessions/{pending['id']}/confirm",
        json={"confirmed": True},
    )
    assert blocked_confirmation.status_code == 409
    assert blocked_confirmation.json()["detail"]["code"] == "LIVE_TRADING_UNAVAILABLE"
    assert (
        client.get(GNK_ALGO + "/live-sessions/current").json()["session"]["status"]
        == "SUSPENDED"
    )
    assert (
        client.post(GNK_ALGO + f"/live-sessions/{pending['id']}/resume").status_code
        == 409
    )

    stop = client.post(GNK_ALGO + "/emergency-stop")
    assert stop.status_code == 200
    assert stop.json() == {"emergency_stop": True, "live_orders_enabled": False}
    assert client.post(P + "/brokers/paper/connect").status_code == 200
    paper_result = client.post(
        P + "/paper/orders",
        json=order(),
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert paper_result.status_code == 200
    assert paper_result.json()["status"] == "Filled"
    ended = client.post(GNK_ALGO + f"/live-sessions/{pending['id']}/end")
    assert ended.status_code == 200
    assert ended.json()["session"]["status"] == "REVOKED"

    events = client.get(GNK_ALGO + f"/live-sessions/{pending['id']}/events")
    assert events.status_code == 200
    assert [event["event_type"] for event in events.json()["events"]] == [
        "SESSION_REQUESTED",
        "CONFIRMATION_BLOCKED",
        "RESUME_BLOCKED",
        "SESSION_REVOKED",
    ]
    with client.db() as db:
        session = db.scalar(select(LiveTradingSession))
        assert session.activated_at is None
        assert session.status == "REVOKED"
        assert db.query(LiveTradingSessionEvent).count() == 4
        assert db.scalar(select(User)).emergency_stop is True


def test_live_session_expiry_and_ownership_are_enforced(client):
    from datetime import timedelta

    from app.models import BrokerConnection, LiveTradingSession

    login(client)
    with client.db() as db:
        user = db.scalar(select(User))
        connection = BrokerConnection(
            user_id=user.id,
            broker_code="dhan",
            account_id_last4="1234",
            account_name="Linked Dhan Account",
        )
        db.add(connection)
        db.flush()
        session = LiveTradingSession(
            user_id=user.id,
            broker_connection_id=connection.id,
            broker_code="dhan",
            broker_account_last4="1234",
            status="PENDING_CONFIRMATION",
            expires_at=now() + timedelta(minutes=5),
        )
        db.add(session)
        db.commit()
        session_id = session.id
        user_id = user.id

    with client.db() as db:
        target = db.get(LiveTradingSession, session_id)
        target.expires_at = now() - timedelta(seconds=1)
        other_user = User(
            name="Other Account",
            email="other@example.com",
            password_hash="unused-test-hash",
            verified=True,
        )
        db.add(other_user)
        db.commit()
        other_user_id = other_user.id

    from app.security import COOKIE, digest

    other_session = secrets.token_urlsafe(48)
    client.cache.set(
        "session:" + digest(other_session),
        json.dumps(
            {"user_id": other_user_id, "version": 0, "csrf": "other-csrf"}
        ),
        ex=3600,
    )
    client.cookies.set(COOKIE, other_session)
    client.headers["X-CSRF-Token"] = "other-csrf"
    assert client.get(GNK_ALGO + f"/live-sessions/{session_id}").status_code == 404

    own_session = secrets.token_urlsafe(48)
    client.cache.set(
        "session:" + digest(own_session),
        json.dumps(
            {"user_id": user_id, "version": 0, "csrf": "owner-csrf"}
        ),
        ex=3600,
    )
    client.cookies.set(COOKIE, own_session)
    client.headers["X-CSRF-Token"] = "owner-csrf"
    status = client.get(GNK_ALGO + "/live-sessions/current")
    assert status.status_code == 200
    assert status.json()["session"]["status"] == "EXPIRED"


def test_emergency_stop_suspends_pending_session_and_requires_admin_reset(client):
    from app.models import BrokerConnection

    login(client)
    with client.db() as db:
        user = db.scalar(select(User))
        db.add(
            BrokerConnection(
                user_id=user.id,
                broker_code="dhan",
                account_id_last4="6789",
                account_name="Linked Dhan Account",
            )
        )
        db.commit()
        user_id = user.id

    requested = client.post(
        GNK_ALGO + "/live-sessions",
        json={"broker_code": "dhan"},
    )
    session_id = requested.json()["session"]["id"]
    assert client.post(GNK_ALGO + "/emergency-stop").status_code == 200
    status = client.get(GNK_ALGO + "/live-sessions/current").json()
    assert status["emergency_stop"] is True
    assert status["session"]["status"] == "SUSPENDED"
    assert status["session"]["suspension_reason"] == "EMERGENCY_STOP_ACTIVE"
    assert (
        client.delete(GNK_ALGO + f"/admin/users/{user_id}/emergency-stop").status_code
        == 403
    )
    assert (
        client.post(GNK_ALGO + f"/live-sessions/{session_id}/resume").status_code
        == 409
    )

    with client.db() as db:
        db.get(User, user_id).role = "admin"
        db.commit()
    cleared = client.delete(GNK_ALGO + f"/admin/users/{user_id}/emergency-stop")
    assert cleared.status_code == 200
    status = client.get(GNK_ALGO + "/trading-mode").json()
    assert status["emergency_stop"] is False
    assert status["session"]["status"] == "SUSPENDED"
    assert status["live_orders_enabled"] is False


def test_unlinking_broker_suspends_and_detaches_live_session_request(client):
    from app.models import BrokerConnection, LiveTradingSession, LiveTradingSessionEvent

    login(client)
    with client.db() as db:
        user = db.scalar(select(User))
        db.add(
            BrokerConnection(
                user_id=user.id,
                broker_code="dhan",
                account_id_last4="9876",
                account_name="Linked Dhan Account",
            )
        )
        db.commit()
    session_id = client.post(
        GNK_ALGO + "/live-sessions",
        json={"broker_code": "dhan"},
    ).json()["session"]["id"]

    unlinked = client.delete(P + "/brokers/dhan")
    assert unlinked.status_code == 200
    status = client.get(GNK_ALGO + "/live-sessions/current").json()
    assert status["session"]["id"] == session_id
    assert status["session"]["status"] == "SUSPENDED"
    assert status["session"]["suspension_reason"] == "BROKER_ACCOUNT_UNLINKED"
    assert status["session"]["broker_account_mask"] == "•••• 9876"
    with client.db() as db:
        session = db.get(LiveTradingSession, session_id)
        assert session.broker_connection_id is None
        assert (
            db.scalar(
                select(LiveTradingSessionEvent).where(
                    LiveTradingSessionEvent.event_type == "BROKER_ACCOUNT_UNLINKED"
                )
            ).event_type
            == "BROKER_ACCOUNT_UNLINKED"
        )
