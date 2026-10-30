"""Dhan pilot execution boundaries. All broker effects are explicit and separately booked."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from ipaddress import ip_address
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .config import settings
from .dhan_client import DhanClient, DhanError, money
from .models import BrokerConnection, DhanInstrument, LiveOrder, now
from .security import digest
from .token_vault import TokenVaultError, decrypt_access_token

IST = ZoneInfo("Asia/Kolkata")
TERMINAL = {"TRADED", "CANCELLED", "REJECTED", "EXPIRED", "BLOCKED"}


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def selected(value):
    return {part.strip() for part in value.split(",") if part.strip()}


def connection_client(db, user_id, account_digest=None):
    connection = db.scalar(
        select(BrokerConnection).where(
            BrokerConnection.user_id == user_id, BrokerConnection.broker_code == "dhan"
        )
    )
    if (
        not connection
        or not connection.account_id_encrypted
        or not connection.access_token_encrypted
    ):
        raise DhanError("Reconnect Dhan to securely retain its full account identity and token.")
    if not connection.access_token_expires_at or utc(connection.access_token_expires_at) <= now():
        raise DhanError("Dhan access token expired. Reconnect the account.")
    try:
        account_id = decrypt_access_token(connection.account_id_encrypted, settings())
        token = decrypt_access_token(connection.access_token_encrypted, settings())
    except TokenVaultError as exc:
        raise DhanError("Dhan credentials could not be opened. Reconnect the account.") from exc
    if connection.account_digest != digest("dhan:" + account_id) or (
        account_digest and account_digest != connection.account_digest
    ):
        raise DhanError("The linked Dhan identity does not match this trading account.")
    return connection, DhanClient(account_id, token)


def catalog(db):
    ids = selected(settings().dhan_live_security_ids)
    return [
        item
        for item in db.scalars(select(DhanInstrument).where(DhanInstrument.enabled.is_(True))).all()
        if item.security_id in ids and fresh(item)
    ]


def fresh(item):
    return (
        timedelta(0) <= now() - utc(item.synced_at) <= timedelta(hours=18)
        and utc(item.synced_at).astimezone(IST).date() == now().astimezone(IST).date()
    )


def readiness(db, user, verify=False):
    config = settings()
    blockers = []
    if not config.dhan_live_enabled:
        blockers.append("DHAN_LIVE_DISABLED")
    if not config.dhan_live_approved:
        blockers.append("DHAN_DEPLOYMENT_APPROVAL_REQUIRED")
    if user.emergency_stop:
        blockers.append("EMERGENCY_STOP_ACTIVE")
    if not catalog(db):
        blockers.append("DHAN_INSTRUMENT_REFRESH_REQUIRED")
    try:
        ip_address(config.dhan_execution_ip)
    except ValueError:
        blockers.append("DHAN_EXECUTION_IP_REQUIRED")
    client = connection = None
    try:
        connection, client = connection_client(db, user.id)
        if client.client_id not in selected(config.dhan_live_account_ids):
            blockers.append("DHAN_ACCOUNT_NOT_APPROVED")
    except DhanError:
        blockers.append("DHAN_RECONNECT_REQUIRED")
    if verify and not blockers:
        validate_access(client)
    return blockers, connection, client


def validate_access(client):
    profile = client.profile()
    if not isinstance(profile, dict) or profile.get("dhanClientId") != client.client_id:
        raise DhanError("Dhan profile identity does not match the linked account.")
    if "equity" not in {
        part.strip().lower() for part in str(profile.get("activeSegment", "")).split(",")
    }:
        raise DhanError("Dhan equity segment is not enabled.")
    try:
        expiry = datetime.strptime(profile["tokenValidity"], "%d/%m/%Y %H:%M").replace(tzinfo=IST)
    except (KeyError, ValueError, TypeError) as exc:
        raise DhanError("Dhan token validity could not be verified.") from exc
    if expiry <= now():
        raise DhanError("Dhan profile reports an expired token.")
    ips = client.ips()
    if not isinstance(ips, dict):
        raise DhanError("Dhan IP registration could not be verified.")
    allowed = set()
    for key in ("primaryIP", "secondaryIP"):
        try:
            allowed.add(ip_address(ips.get(key, "")))
        except ValueError:
            pass
    if ip_address(settings().dhan_execution_ip) not in allowed:
        raise DhanError("Configured execution IP is not registered with Dhan.")


def ensure_ready(db, user):
    blockers, connection, client = readiness(db, user, verify=True)
    if blockers:
        raise DhanError("Dhan live requirements: " + ", ".join(blockers))
    return connection, client


def instrument(db, security_id, quantity, price):
    item = db.get(DhanInstrument, security_id)
    if (
        not item
        or not item.enabled
        or security_id not in selected(settings().dhan_live_security_ids)
        or not fresh(item)
    ):
        raise DhanError("Select an approved instrument from today's Dhan catalog.")
    if (
        quantity < 1
        or quantity > min(settings().dhan_live_max_quantity, item.freeze_quantity)
        or quantity % item.lot_size
    ):
        raise DhanError("Quantity exceeds the instrument or account limit.")
    if not item.lower_limit <= price <= item.upper_limit or price % item.tick_size:
        raise DhanError("Limit price must respect the current instrument tick and price band.")
    if price * quantity > settings().dhan_live_max_order_value:
        raise DhanError("Order value exceeds the Dhan live account cap.")
    return item


def budget(db, account_digest, value):
    orders = db.scalars(select(LiveOrder).where(LiveOrder.account_digest == account_digest)).all()
    if any(order.status not in TERMINAL for order in orders):
        raise DhanError("Resolve the outstanding live order before creating another.")
    today = now().astimezone(IST).date()
    used = sum(
        (
            Decimal(order.ticket["price"]) * order.ticket["quantity"]
            for order in orders
            if utc(order.created_at).astimezone(IST).date() == today
            and order.status not in {"REJECTED", "BLOCKED"}
        ),
        Decimal(0),
    )
    # Conservative reservation: cancelled/expired/part-filled orders retain full day notional.
    if used + value > settings().dhan_live_max_daily_value:
        raise DhanError("Daily live gross order cap would be exceeded.")


def payload(client, ticket, correlation_id=None):
    result = dict(
        dhanClientId=client.client_id,
        transactionType="BUY",
        exchangeSegment="NSE_EQ",
        productType="CNC",
        securityId=ticket["security_id"],
        quantity=ticket["quantity"],
        price=float(ticket["price"]),
        triggerPrice=0,
    )
    if correlation_id:
        result.update(
            correlationId=correlation_id,
            orderType="LIMIT",
            validity="DAY",
            afterMarketOrder=False,
            disclosedQuantity=0,
        )
    return result


def pretrade(client, ticket):
    funds = client.funds()
    if not isinstance(funds, dict) or funds.get("dhanClientId") != client.client_id:
        raise DhanError("Dhan funds identity could not be verified.")
    available = money(funds.get("availabelBalance"))
    margin = client.margin(payload(client, ticket))
    if not isinstance(margin, dict):
        raise DhanError("Dhan margin response could not be verified.")
    required = money(margin.get("totalMargin"))
    brokerage = money(margin.get("brokerage"))
    limit_value = Decimal(ticket["price"]) * ticket["quantity"]
    if (
        required <= 0
        or money(margin.get("insufficientBalance")) != 0
        or min(available, money(margin.get("availableBalance")))
        < max(required, limit_value) + brokerage
    ):
        raise DhanError("Dhan reports insufficient funds or margin for this delivery buy.")
    return {
        "available": str(available),
        "required_margin": str(required),
        "brokerage_estimate": str(brokerage),
    }


def reconcile_order(order, data, client):
    # A lookup must agree with the immutable request and authenticated broker account.
    if not isinstance(data, dict):
        raise DhanError("Dhan order lookup returned an invalid shape.")
    expected = payload(client, order.ticket, order.correlation_id)
    for key in (
        "dhanClientId",
        "correlationId",
        "securityId",
        "transactionType",
        "exchangeSegment",
        "productType",
        "orderType",
        "validity",
    ):
        if data.get(key) != expected[key]:
            raise DhanError("Dhan order lookup does not match the original request.")
    if data.get("quantity") != order.ticket["quantity"] or money(data.get("price")) != Decimal(
        order.ticket["price"]
    ):
        raise DhanError("Dhan order quantity or price differs from the confirmed request.")
    state = data.get("orderStatus")
    if state not in {
        "TRANSIT",
        "PENDING",
        "PART_TRADED",
        "TRADED",
        "CANCELLED",
        "REJECTED",
        "EXPIRED",
    }:
        raise DhanError("Dhan returned an unknown order state.")
    broker_id = data.get("orderId")
    if (
        not isinstance(broker_id, str)
        or not broker_id.isalnum()
        or len(broker_id) > 64
        or (order.broker_order_id and broker_id != order.broker_order_id)
    ):
        raise DhanError("Dhan returned an inconsistent order reference.")
    filled = data.get("filledQty")
    if type(filled) is not int or not order.filled_quantity <= filled <= order.ticket["quantity"]:
        raise DhanError("Dhan returned invalid cumulative fills.")
    average = money(data.get("averageTradedPrice"))
    if (filled and (average <= 0 or average > Decimal(order.ticket["price"]))) or (
        not filled and average != 0
    ):
        raise DhanError("Dhan fill prices could not be verified.")
    if (state == "TRADED" and filled != order.ticket["quantity"]) or (
        state == "REJECTED" and filled
    ):
        raise DhanError("Dhan terminal state conflicts with cumulative fills.")
    if order.status in TERMINAL and state != order.status:
        raise DhanError("Dhan order state regressed after a terminal outcome.")
    order.broker_order_id = broker_id
    order.status = "PENDING" if state == "TRANSIT" else state
    order.filled_quantity = filled
    order.average_price = average
    order.reconciled_at = now()
    order.reason = None


def view(order):
    return {
        "id": order.id,
        "session_id": order.session_id,
        "security_id": order.ticket["security_id"],
        "name": order.ticket["name"],
        "side": "BUY",
        "product": "CNC",
        "type": "LIMIT",
        "quantity": order.ticket["quantity"],
        "price": order.ticket["price"],
        "status": order.status,
        "broker_order_id": order.broker_order_id,
        "filled_quantity": order.filled_quantity,
        "average_price": format(order.average_price, ".4f"),
        "reason": order.reason,
        "created_at": utc(order.created_at).isoformat(),
    }
