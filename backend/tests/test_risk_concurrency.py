import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import pytest
from test_api import GNK_ALGO as P
from test_api import login, order


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Requires disposable PostgreSQL row locks"
)
def test_concurrent_orders_cannot_overspend_daily_risk_budget(client):
    login(client)
    client.post(P + "/brokers/paper/connect")
    client.put(
        P + "/risk-policy",
        json={
            "max_order_value": "6000",
            "max_daily_value": "6000",
            "max_quantity": 2,
            "halted": False,
        },
    )

    def send(_):
        return client.post(
            P + "/orders", json=order(), headers={"Idempotency-Key": str(uuid4())}
        ).json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, range(2)))
    assert sorted(result["status"] for result in responses) == ["Filled", "Rejected"]
    assert Decimal(client.get(P + "/risk-policy").json()["daily_value_used"]) == Decimal("5897")
