import csv
import io

import httpx
import pytest

from app.dhan_client import DhanClient, DhanError, money
from app.dhan_instruments import parse_rows


def rows(**changes):
    row = {
        "EXCH_ID": "NSE",
        "SEGMENT": "E",
        "SECURITY_ID": "900001",
        "SERIES": "EQ",
        "INSTRUMENT": "EQUITY",
        "LOT_SIZE": "1.0",
        "TICK_SIZE": "5.0000",
        "SM_LOWER_LIMIT": "90",
        "SM_UPPER_LIMIT": "110",
        "SM_FREEZE_QTY": "100",
        "SYMBOL_NAME": "Fictional test equity",
        "ASM_GSM_FLAG": "N",
        "BUY_SELL_INDICATOR": "A",
        **changes,
    }
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    return output.getvalue().splitlines()


def test_master_tick_sizes_are_converted_from_paise_and_flags_are_enforced():
    item = parse_rows(rows(), {"900001"})["900001"]
    assert str(item["tick_size"]) == "0.0500"
    assert item["lot_size"] == 1
    assert parse_rows(rows(ASM_GSM_FLAG="Y"), {"900001"})["900001"]["enabled"] is False


@pytest.mark.parametrize(
    "changes",
    [
        {"LOT_SIZE": "10"},
        {"TICK_SIZE": "NaN"},
        {"SM_LOWER_LIMIT": "120"},
        {"SM_FREEZE_QTY": "0"},
        {"SERIES": "BE"},
        {"INSTRUMENT": "FUTSTK"},
    ],
)
def test_master_fails_closed_for_unsupported_or_invalid_instruments(changes):
    with pytest.raises((ValueError, ArithmeticError)):
        parse_rows(rows(**changes), {"900001"})


@pytest.mark.parametrize("value", [None, "NaN", "Infinity", "-1", True])
def test_broker_financial_values_must_be_finite_and_nonnegative(value):
    with pytest.raises(DhanError):
        money(value)


def test_client_sanitizes_errors_and_never_retries_or_follows_redirects(monkeypatch):
    import app.dhan_client as adapter

    original = httpx.Client
    requests = []

    def respond(request):
        requests.append(request)
        assert request.url.host == "api.dhan.co"
        assert request.headers["access-token"] == "fixture-secret"
        return httpx.Response(503, json={"secret": "must-not-leak"})

    def create(**kwargs):
        assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
        return original(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(adapter.httpx, "Client", create)
    client = DhanClient("fixture-client", "fixture-secret")
    with pytest.raises(DhanError) as error:
        client.place({"fixture": "payload"})
    assert len(requests) == 1
    assert "must-not-leak" not in str(error.value)
    assert "fixture-secret" not in repr(client)
