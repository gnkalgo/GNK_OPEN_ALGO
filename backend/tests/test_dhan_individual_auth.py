import httpx
import pytest

from app import broker_auth
from app.config import Settings


def config():
    return Settings(
        _env_file=None,
        dhan_auth_mode="individual",
        dhan_client_id="1000000001",
        dhan_api_key="fictional-key",
        dhan_api_secret="fictional-secret",
        dhan_token_encryption_key="MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI=",
    )


def test_individual_consent_uses_application_contract(monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json={"consentAppId": "fictional-consent"})

    monkeypatch.setattr(broker_auth.httpx, "post", post)
    value = config()
    assert broker_auth.is_configured("dhan", value)
    url, _ = broker_auth.start_authorization("dhan", "state", value)
    assert url == "https://auth.dhan.co/login/consentApp-login?consentAppId=fictional-consent"
    assert calls[0][0] == "https://auth.dhan.co/app/generate-consent"
    assert calls[0][1]["params"] == {"client_id": value.dhan_client_id}
    assert calls[0][1]["headers"] == {"app_id": value.dhan_api_key, "app_secret": value.dhan_api_secret}


@pytest.mark.parametrize("account", ["1000000001", "1000000002"])
def test_individual_callback_checks_account_identity(monkeypatch, account):
    def get(url, **kwargs):
        assert url == "https://auth.dhan.co/app/consumeApp-consent"
        assert kwargs["params"] == {"tokenId": "fictional-token-id"}
        assert "app_id" in kwargs["headers"]
        assert "partner_id" not in kwargs["headers"]
        return httpx.Response(200, json={
            "dhanClientId": account, "dhanClientName": "Fictional account",
            "accessToken": "fictional-token", "expiryTime": "2099-12-31T15:30:00",
        })

    monkeypatch.setattr(broker_auth.httpx, "get", get)
    if account != config().dhan_client_id:
        with pytest.raises(broker_auth.BrokerAuthError, match="different"):
            broker_auth.complete_authorization("dhan", {"tokenId": "fictional-token-id"}, config())
    else:
        profile = broker_auth.complete_authorization("dhan", {"tokenId": "fictional-token-id"}, config())
        assert profile.account_id == account
        assert profile.access_token == "fictional-token"
