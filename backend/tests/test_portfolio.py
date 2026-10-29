from decimal import Decimal
from types import SimpleNamespace

from test_api import GNK_ALGO as P
from test_api import login, order

from app.portfolio import positions


def fill(side, quantity, price, product="Delivery", status="Filled"):
    return SimpleNamespace(
        status=status,
        ticket={
            "symbol": "RELIANCE",
            "exchange": "NSE",
            "product": product,
            "side": side,
            "quantity": quantity,
            "price": price,
        },
    )


def test_average_cost_partial_close_reversal_and_product_isolation():
    result = positions(
        [
            fill("BUY", 10, 100),
            fill("SELL", 4, 120),
            fill("SELL", 8, 90),
            fill("BUY", 1, 80),
            fill("BUY", 5, 70, "Intraday"),
            fill("BUY", 100, 1, status="Rejected"),
        ],
        {"RELIANCE": "100"},
    )
    delivery, intraday = result
    assert delivery["quantity"] == -1
    assert Decimal(delivery["average_price"]) == 90
    assert Decimal(delivery["realized_pnl"]) == 30
    assert Decimal(delivery["unrealized_pnl"]) == -10
    assert intraday["quantity"] == 5 and Decimal(intraday["realized_pnl"]) == 0


def test_positions_endpoint_derives_only_the_callers_paper_ledger(client):
    from uuid import uuid4

    login(client)
    client.post(P + "/brokers/paper/connect")
    client.post(P + "/orders", json=order(), headers={"Idempotency-Key": str(uuid4())})
    response = client.get(P + "/portfolio/positions").json()
    assert response["valuation"] == "fictional"
    assert response["positions"][0]["quantity"] == 2
    assert Decimal(response["positions"][0]["unrealized_pnl"]) == 0
