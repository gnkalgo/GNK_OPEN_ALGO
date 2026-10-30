"""GNK account risk policy. Call under the account row lock before booking a fill.

Paper limits are deliberately separate from any future broker margin/risk service.
No value in this module grants live execution permission.
"""

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuditEvent, PaperOrder, RiskPolicy, User, now
from .schemas import Body
from .security import current_user

router = APIRouter(prefix="/api/v1/gnkalgo", tags=["account risk"])
IST = ZoneInfo("Asia/Kolkata")


class PolicyInput(Body):
    max_order_value: Decimal = Field(gt=0, le=1000000, decimal_places=2)
    max_daily_value: Decimal = Field(gt=0, le=5000000, decimal_places=2)
    max_quantity: int = Field(strict=True, ge=1, le=1000)
    halted: bool


def policy_view(policy: RiskPolicy | None):
    return {
        "max_order_value": str(policy.max_order_value) if policy else "1000000.00",
        "max_daily_value": str(policy.max_daily_value) if policy else "5000000.00",
        "max_quantity": policy.max_quantity if policy else 1000,
        "halted": policy.halted if policy else False,
        "currency": "INR",
        "scope": "paper",
        "day_timezone": "Asia/Kolkata",
    }


def daily_value(db: Session, user_id: str, at: datetime) -> Decimal:
    start = at.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    orders = db.scalars(
        select(PaperOrder).where(
            PaperOrder.user_id == user_id,
            PaperOrder.status == "Filled",
            PaperOrder.created_at >= start.astimezone(UTC),
            PaperOrder.created_at <= at,
        )
    )
    # Gross turnover: buys AND sells consume the limit; rejected orders do not.
    return sum((Decimal(str(o.ticket["price"])) * o.ticket["quantity"] for o in orders), Decimal(0))


def rejection(db: Session, user: User, quantity: int, price: Decimal) -> str | None:
    policy = policy_view(db.get(RiskPolicy, user.id))
    if policy["halted"]:
        return "Account risk halt is active"
    if quantity > policy["max_quantity"]:
        return "Quantity exceeds account risk limit"
    value = price * quantity
    if value > Decimal(policy["max_order_value"]):
        return "Order value exceeds account risk limit"
    if daily_value(db, user.id, now()) + value > Decimal(policy["max_daily_value"]):
        return "Daily gross order value exceeds account risk limit"
    return None


@router.get("/risk-policy")
def get_policy(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {
        **policy_view(db.get(RiskPolicy, user.id)),
        "daily_value_used": str(daily_value(db, user.id, now())),
        "emergency_stop": user.emergency_stop,
        "live_orders_enabled": False,
    }


@router.put("/risk-policy")
def set_policy(
    body: PolicyInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    # Same lock order as order submission: account, then policy. Client cannot choose an owner.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    policy = db.get(RiskPolicy, user.id)
    if policy is None:
        policy = RiskPolicy(user_id=user.id)
        db.add(policy)
    for key, value in body.model_dump().items():
        setattr(policy, key, value)
    db.add(AuditEvent(user_id=user.id, action="Paper account risk policy updated"))
    db.commit()
    return get_policy(user, db)


@router.get("/platform")
def platform(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from .live_trading import _control_status, _lock_user, _request_id

    state = _control_status(db, _lock_user(db, user.id), _request_id(request))
    return {
        "platform": "GNK ALGO",
        "contract_version": 1,
        "deployment_stage": "development",
        "execution": state["execution"],
        "live_orders_enabled": state["live_orders_enabled"],
        "paper_trading_enabled": state["paper_trading_enabled"],
        "capabilities": [
            {"name": "Paper order ledger", "status": "available" if state["paper_trading_enabled"] else "read_only"},
            {"name": "Account risk limits", "status": "available"},
            {"name": "Broker account linking", "status": "configuration_required"},
            {"name": "Live market data", "status": "unavailable"},
            {
                "name": "Dhan delivery BUY LIMIT",
                "status": "available" if state["live_orders_enabled"] else "activation_required",
            },
            {"name": "Strategy execution engine", "status": "unavailable"},
        ],
        "release_blockers": [
            "DHAN_PILOT_DEPLOYMENT_ACCEPTANCE",
            "LICENSED_MARKET_DATA_AND_INSTRUMENTS",
            "LIVE_MARGIN_AND_RISK_VALIDATION",
            "BROKER_AND_EXCHANGE_APPROVAL",
            "DEPENDENCY_AND_IP_RELEASE_REVIEW",
            "SECURITY_AND_RECOVERY_ACCEPTANCE",
        ],
    }
