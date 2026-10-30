"""Original GNK adapter for the official Dhan v2 HTTPS contract. No implicit retries."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import httpx

BASE_URL = "https://api.dhan.co/v2"


class DhanError(Exception):
    """Sanitized transport/contract error. Never include response bodies or credentials."""


def money(value) -> Decimal:
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0:
            raise ValueError
        return result
    except (ValueError, InvalidOperation) as exc:
        raise DhanError("Dhan returned invalid financial data.") from exc


@dataclass(repr=False)
class DhanClient:
    client_id: str = field(repr=False)
    token: str = field(repr=False)

    def call(self, method: str, path: str, payload=None):
        try:
            # Fixed origin and no redirects prevent credential forwarding to another host.
            with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
                response = client.request(
                    method,
                    BASE_URL + path,
                    headers={"access-token": self.token, "client-id": self.client_id},
                    json=payload,
                )
            if not response.is_success:
                raise DhanError(
                    "Dhan request failed. Check broker connectivity and account permissions."
                )
            data = response.json()
            if not isinstance(data, (dict, list)):
                raise ValueError
            return data
        except (httpx.HTTPError, ValueError) as exc:
            raise DhanError("Dhan response could not be verified.") from exc

    def profile(self):
        return self.call("GET", "/profile")

    def ips(self):
        return self.call("GET", "/ip/getIP")

    def funds(self):
        return self.call("GET", "/fundlimit")

    def margin(self, payload):
        return self.call("POST", "/margincalculator", payload)

    def place(self, payload):
        return self.call("POST", "/orders", payload)

    def lookup(self, correlation_id):
        if not correlation_id.isalnum() or len(correlation_id) > 30:
            raise DhanError("Invalid internal correlation reference.")
        return self.call("GET", "/orders/external/" + correlation_id)
