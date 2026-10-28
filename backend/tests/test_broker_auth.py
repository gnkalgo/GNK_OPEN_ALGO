import hashlib
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx

from app import broker_auth


def credentials():
    return SimpleNamespace(
        frontend_url="https://gnkalgo.com",
        dhan_partner_id="dhan-id",
        dhan_partner_secret="dhan-secret",
        fyers_client_id="fyers-id-100",
        fyers_app_secret="fyers-secret",
        zerodha_api_key="zerodha-key",
        zerodha_api_secret="zerodha-secret",
    )


def test_authorization_urls_use_exact_provider_callback_and_code():
    config = credentials()

    fyers_url, _ = broker_auth.start_authorization("fyers", "state-value", config)
    fyers_query = parse_qs(urlparse(fyers_url).query)
    assert fyers_query["redirect_uri"] == [
        "https://gnkalgo.com/api/gnk/v1/brokers/fyers/callback"
    ]
    assert fyers_query["state"] == ["state-value"]

    zerodha_url, _ = broker_auth.start_authorization("zerodha", "state-value", config)
    zerodha_query = parse_qs(urlparse(zerodha_url).query)
    assert zerodha_query["redirect_params"] == ["state=state-value"]


def test_zerodha_token_exchange_uses_checksum_and_only_returns_masked_profile(monkeypatch):
    config = credentials()
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "user_id": "AB1234",
                    "user_name": "Test Trader",
                    "access_token": "must-not-be-returned",
                },
            },
        )

    monkeypatch.setattr(broker_auth.httpx, "post", fake_post)
    profile = broker_auth.complete_authorization(
        "zerodha", {"request_token": "single-use-token"}, config
    )

    expected = hashlib.sha256(
        b"zerodha-keysingle-use-tokenzerodha-secret"
    ).hexdigest()
    assert captured["url"] == "https://api.kite.trade/session/token"
    assert captured["data"]["checksum"] == expected
    assert profile.account_id_last4 == "1234"
    assert profile.account_name == "Test Trader"
    assert "access_token" not in profile.__dict__


def test_dhan_partner_consent_keeps_partner_credentials_server_side(monkeypatch):
    config = credentials()
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(200, json={"consentId": "consent-id"})

    monkeypatch.setattr(broker_auth.httpx, "post", fake_post)
    url, metadata = broker_auth.start_authorization("dhan", "state-value", config)

    assert url == "https://auth.dhan.co/consent-login?consentId=consent-id"
    assert metadata == {"consent_id": "consent-id"}
    assert captured["headers"] == {
        "partner_id": "dhan-id",
        "partner_secret": "dhan-secret",
    }


def test_fyers_exchange_discards_access_token_after_profile_lookup(monkeypatch):
    config = credentials()
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json={"access_token": "temporary-access-token"})

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(
            200,
            json={"s": "ok", "data": {"fy_id": "FY123456", "name": "Test Client"}},
        )

    monkeypatch.setattr(broker_auth.httpx, "post", fake_post)
    monkeypatch.setattr(broker_auth.httpx, "get", fake_get)
    profile = broker_auth.complete_authorization("fyers", {"auth_code": "one-use-code"}, config)

    assert calls[0][0] == "https://api-t1.fyers.in/api/v3/validate-authcode"
    assert calls[0][1]["json"]["appIdHash"] == hashlib.sha256(
        b"fyers-id-100:fyers-secret"
    ).hexdigest()
    assert calls[1][1]["headers"]["Authorization"] == (
        "fyers-id-100:temporary-access-token"
    )
    assert profile.account_id_last4 == "3456"
    assert profile.account_name == "Test Client"
    assert "access_token" not in profile.__dict__
