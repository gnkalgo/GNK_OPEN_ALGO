import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx

from .config import Settings

TIMEOUT = 10.0
CALLBACK_PREFIX = "/api/gnk/v1/brokers"
BROKERS = {
    "dhan": "Dhan",
    "fyers": "FYERS",
    "zerodha": "Zerodha",
}


class BrokerAuthError(Exception):
    pass


class BrokerNotConfigured(BrokerAuthError):
    pass


@dataclass(frozen=True)
class BrokerProfile:
    account_id_last4: str
    account_name: str
    access_token: str | None = field(default=None, repr=False)
    access_token_expires_at: datetime | None = None
    account_id: str | None = field(default=None, repr=False)


def is_configured(code: str, config: Settings) -> bool:
    if code == "dhan" and config.dhan_auth_mode == "individual":
        return all((config.dhan_client_id, config.dhan_api_key, config.dhan_api_secret, config.dhan_token_encryption_key))
    required = {
        "dhan": (
            config.dhan_partner_id,
            config.dhan_partner_secret,
            config.dhan_token_encryption_key,
        ),
        "fyers": (config.fyers_client_id, config.fyers_app_secret),
        "zerodha": (config.zerodha_api_key, config.zerodha_api_secret),
    }
    return all(required[code])


def callback_uri(code: str, config: Settings) -> str:
    return f"{config.frontend_url}{CALLBACK_PREFIX}/{code}/callback"


def _json(response: httpx.Response) -> dict:
    if not response.is_success:
        raise BrokerAuthError("The broker did not complete account authorization.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise BrokerAuthError("The broker returned an invalid authorization response.") from exc
    if not isinstance(payload, dict):
        raise BrokerAuthError("The broker returned an invalid authorization response.")
    return payload


def _call(request, *args, **kwargs) -> dict:
    try:
        return _json(request(*args, timeout=TIMEOUT, **kwargs))
    except httpx.HTTPError as exc:
        raise BrokerAuthError("The broker could not be reached. Please retry.") from exc


def start_authorization(code: str, state: str, config: Settings) -> tuple[str, dict]:
    if code not in BROKERS or not is_configured(code, config):
        raise BrokerNotConfigured("This broker is not configured for account linking.")

    callback = callback_uri(code, config)
    if code == "dhan":
        if config.dhan_auth_mode == "individual":
            payload = _call(
                httpx.post,
                "https://auth.dhan.co/app/generate-consent",
                params={"client_id": config.dhan_client_id},
                headers={"app_id": config.dhan_api_key, "app_secret": config.dhan_api_secret},
            )
            consent_id = payload.get("consentAppId")
            if not isinstance(consent_id, str) or not consent_id:
                raise BrokerAuthError("Dhan did not start an application authorization session.")
            return (
                "https://auth.dhan.co/login/consentApp-login?" + urlencode({"consentAppId": consent_id}),
                {"consent_id": consent_id},
            )
        payload = _call(
            httpx.post,
            "https://auth.dhan.co/partner/generate-consent",
            headers={
                "partner_id": config.dhan_partner_id,
                "partner_secret": config.dhan_partner_secret,
            },
        )
        consent_id = payload.get("consentId")
        if not isinstance(consent_id, str) or not consent_id:
            raise BrokerAuthError("Dhan did not start an authorization session.")
        return (
            "https://auth.dhan.co/consent-login?" + urlencode({"consentId": consent_id}),
            {"consent_id": consent_id},
        )

    if code == "fyers":
        return (
            "https://api-t1.fyers.in/api/v3/generate-authcode?"
            + urlencode(
                {
                    "client_id": config.fyers_client_id,
                    "redirect_uri": callback,
                    "response_type": "code",
                    "state": state,
                }
            ),
            {},
        )

    redirect_params = urlencode({"state": state})
    return (
        "https://kite.zerodha.com/connect/login?"
        + urlencode(
            {
                "v": "3",
                "api_key": config.zerodha_api_key,
                "redirect_params": redirect_params,
            }
        ),
        {},
    )


def _profile(code: str, account_id: object, account_name: object) -> BrokerProfile:
    if not isinstance(account_id, str) or not account_id.strip():
        raise BrokerAuthError("The broker response did not include an account identifier.")
    if not isinstance(account_name, str) or not account_name.strip():
        account_name = BROKERS[code]
    return BrokerProfile(
        account_id_last4=account_id.strip()[-4:],
        account_name=account_name.strip()[:120],
    )


def complete_authorization(
    code: str, callback_params: dict[str, str], config: Settings
) -> BrokerProfile:
    if code not in BROKERS or not is_configured(code, config):
        raise BrokerNotConfigured("This broker is not configured for account linking.")

    if code == "dhan":
        token_id = callback_params.get("tokenId", "")
        if not token_id or len(token_id) > 512:
            raise BrokerAuthError("Dhan authorization was cancelled or expired.")
        payload = _call(
            httpx.get,
            "https://auth.dhan.co/app/consumeApp-consent" if config.dhan_auth_mode == "individual" else "https://auth.dhan.co/partner/consume-consent",
            params={"tokenId": token_id},
            headers={"app_id": config.dhan_api_key, "app_secret": config.dhan_api_secret} if config.dhan_auth_mode == "individual" else {
                "partner_id": config.dhan_partner_id,
                "partner_secret": config.dhan_partner_secret,
            },
        )
        access_token = payload.get("accessToken")
        expiry_time = payload.get("expiryTime")
        if not isinstance(access_token, str) or not access_token or len(access_token) > 4096:
            raise BrokerAuthError("Dhan did not issue an account access token.")
        if not isinstance(expiry_time, str):
            raise BrokerAuthError("Dhan returned an invalid access-token expiry.")
        try:
            expires_at = datetime.fromisoformat(expiry_time)
        except ValueError as exc:
            raise BrokerAuthError("Dhan returned an invalid access-token expiry.") from exc
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        profile = _profile(code, payload.get("dhanClientId"), payload.get("dhanClientName"))
        if config.dhan_auth_mode == "individual" and payload["dhanClientId"].strip() != config.dhan_client_id:
            raise BrokerAuthError("Dhan returned an account different from the configured individual account.")
        return BrokerProfile(
            account_id_last4=profile.account_id_last4,
            account_name=profile.account_name,
            account_id=payload["dhanClientId"].strip(),
            access_token=access_token,
            access_token_expires_at=expires_at.astimezone(UTC),
        )

    if code == "fyers":
        auth_code = callback_params.get("auth_code", "")
        if not auth_code or len(auth_code) > 4096:
            raise BrokerAuthError("FYERS authorization was cancelled or expired.")
        app_id_hash = hashlib.sha256(
            f"{config.fyers_client_id}:{config.fyers_app_secret}".encode()
        ).hexdigest()
        token_payload = _call(
            httpx.post,
            "https://api-t1.fyers.in/api/v3/validate-authcode",
            json={
                "grant_type": "authorization_code",
                "appIdHash": app_id_hash,
                "code": auth_code,
            },
        )
        access_token = token_payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise BrokerAuthError("FYERS did not issue an account access token.")
        profile = _call(
            httpx.get,
            "https://api-t1.fyers.in/api/v3/profile",
            headers={"Authorization": f"{config.fyers_client_id}:{access_token}"},
        )
        data = profile.get("data")
        if not isinstance(data, dict):
            raise BrokerAuthError("FYERS returned an invalid account profile.")
        return _profile(code, data.get("fy_id"), data.get("name"))

    request_token = callback_params.get("request_token", "")
    if not request_token or len(request_token) > 4096:
        raise BrokerAuthError("Zerodha authorization was cancelled or expired.")
    checksum = hashlib.sha256(
        f"{config.zerodha_api_key}{request_token}{config.zerodha_api_secret}".encode()
    ).hexdigest()
    payload = _call(
        httpx.post,
        "https://api.kite.trade/session/token",
        headers={"X-Kite-Version": "3"},
        data={
            "api_key": config.zerodha_api_key,
            "request_token": request_token,
            "checksum": checksum,
        },
    )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise BrokerAuthError("Zerodha returned an invalid account profile.")
    return _profile(code, data.get("user_id"), data.get("user_name"))
