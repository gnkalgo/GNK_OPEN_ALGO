import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="trader")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    session_version: Mapped[int] = mapped_column(default=0)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("245680.50"))
    broker: Mapped[str] = mapped_column(String(20), default="Disconnected")
    emergency_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    watchlist: Mapped[list] = mapped_column(
        JSON, default=lambda: ["RELIANCE", "TCS", "HDFCBANK", "INFY"]
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RiskPolicy(Base):
    __tablename__ = "risk_policies"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    max_order_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("1000000"))
    max_daily_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("5000000"))
    max_quantity: Mapped[int] = mapped_column(default=1000)
    halted: Mapped[bool] = mapped_column(Boolean, default=False)


class BrokerConnection(Base):
    __tablename__ = "broker_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "broker_code", name="uq_broker_connection_user_code"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    broker_code: Mapped[str] = mapped_column(String(20))
    account_id_last4: Mapped[str] = mapped_column(String(4))
    account_name: Mapped[str] = mapped_column(String(120))
    account_id_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_digest: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LiveTradingSession(Base):
    __tablename__ = "live_trading_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    broker_connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="SET NULL"), index=True, nullable=True
    )
    broker_code: Mapped[str] = mapped_column(String(20))
    broker_account_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    broker_account_last4: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspension_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    version: Mapped[int] = mapped_column(default=1)


class LiveTradingSessionEvent(Base):
    __tablename__ = "live_trading_session_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("live_trading_sessions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(48))
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    request_id: Mapped[str] = mapped_column(String(36))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class EmailToken(Base):
    __tablename__ = "email_tokens"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class PaperOrder(Base):
    __tablename__ = "paper_orders"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_order_user_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    ticket: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Strategy(Base):
    __tablename__ = "strategies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    config: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="Draft")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MailOutbox(Base):
    __tablename__ = "mail_outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    token_digest: Mapped[str] = mapped_column(ForeignKey("email_tokens.digest"))
    # Plain tokens are deliberately NOT persisted here. Worker generates a fresh token.
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(default=0)


class DhanInstrument(Base):
    __tablename__ = "dhan_instruments"
    security_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    lot_size: Mapped[int] = mapped_column()
    tick_size: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    lower_limit: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    upper_limit: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    freeze_quantity: Mapped[int] = mapped_column()
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LiveOrder(Base):
    __tablename__ = "live_orders"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_live_order_user_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("live_trading_sessions.id"))
    account_digest: Mapped[str] = mapped_column(String(64), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    correlation_id: Mapped[str] = mapped_column(String(30), unique=True)
    ticket: Mapped[dict] = mapped_column(JSON)
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    filled_quantity: Mapped[int] = mapped_column(default=0)
    average_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
