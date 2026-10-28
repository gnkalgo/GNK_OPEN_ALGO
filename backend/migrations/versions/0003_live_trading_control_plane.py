"""Persist fail-closed live trading session controls."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("emergency_stop", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "live_trading_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "broker_connection_id",
            sa.String(36),
            sa.ForeignKey("broker_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("broker_code", sa.String(20), nullable=False),
        sa.Column("broker_account_last4", sa.String(4), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("last_validated_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("suspension_reason", sa.String(80)),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_live_trading_sessions_user_id", "live_trading_sessions", ["user_id"]
    )
    op.create_index(
        "ix_live_trading_sessions_broker_connection_id",
        "live_trading_sessions",
        ["broker_connection_id"],
    )
    op.create_index("ix_live_trading_sessions_status", "live_trading_sessions", ["status"])
    op.create_table(
        "live_trading_session_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("live_trading_sessions.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason_code", sa.String(80)),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_live_trading_session_events_session_id",
        "live_trading_session_events",
        ["session_id"],
    )
    op.create_index(
        "ix_live_trading_session_events_user_id",
        "live_trading_session_events",
        ["user_id"],
    )


def downgrade():
    op.drop_table("live_trading_session_events")
    op.drop_table("live_trading_sessions")
    op.drop_column("users", "emergency_stop")
