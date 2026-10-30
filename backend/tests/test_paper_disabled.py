from uuid import uuid4

from test_api import GNK_ALGO, P, login, order

from app.config import settings


def test_disabled_paper_blocks_new_orders_but_preserves_reconciliation(client, monkeypatch):
    import app.live_trading
    import app.main

    login(client)
    assert client.post(P + "/brokers/paper/connect").status_code == 200
    key = str(uuid4())
    first = client.post(P + "/paper/orders", json=order(), headers={"Idempotency-Key": key})
    assert first.status_code == 200
    config = settings().model_copy(update={"paper_trading_enabled": False})
    monkeypatch.setattr(app.main, "settings", lambda: config)
    monkeypatch.setattr(app.live_trading, "settings", lambda: config)
    for prefix in (P, GNK_ALGO):
        assert client.post(prefix + "/brokers/paper/connect").status_code == 409
    blocked = client.post(GNK_ALGO + "/orders", json=order(), headers={"Idempotency-Key": str(uuid4())})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "PAPER_TRADING_DISABLED"
    replay = client.post(P + "/paper/orders", json=order(), headers={"Idempotency-Key": key})
    assert replay.json() == first.json()
    state = client.get(GNK_ALGO + "/trading-mode").json()
    assert state["paper_trading_enabled"] is False
    assert state["mode"] == "DISABLED"
    assert state["live_orders_enabled"] is False
