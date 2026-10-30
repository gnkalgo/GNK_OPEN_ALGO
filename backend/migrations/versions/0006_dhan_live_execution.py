"""Account-bound Dhan identity, vetted instruments and durable live order intents."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "live_trading_sessions", sa.Column("broker_account_digest", sa.String(64), nullable=True)
    )
    with op.batch_alter_table("broker_connections") as batch:
        batch.add_column(sa.Column("account_id_encrypted", sa.Text(), nullable=True))
        batch.add_column(sa.Column("account_digest", sa.String(64), nullable=True))
        batch.create_unique_constraint("uq_broker_connection_account_digest", ["account_digest"])
    op.create_table(
        "dhan_instruments",
        sa.Column("security_id", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("lot_size", sa.Integer(), nullable=False),
        sa.Column("tick_size", sa.Numeric(12, 4), nullable=False),
        sa.Column("lower_limit", sa.Numeric(18, 4), nullable=False),
        sa.Column("upper_limit", sa.Numeric(18, 4), nullable=False),
        sa.Column("freeze_quantity", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "live_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "session_id", sa.String(36), sa.ForeignKey("live_trading_sessions.id"), nullable=False
        ),
        sa.Column("account_digest", sa.String(64), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("correlation_id", sa.String(30), unique=True, nullable=False),
        sa.Column("ticket", sa.JSON(), nullable=False),
        sa.Column("broker_order_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("filled_quantity", sa.Integer(), nullable=False),
        sa.Column("average_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("reason", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "request_key", name="uq_live_order_user_key"),
    )
    op.create_index("ix_live_orders_user_id", "live_orders", ["user_id"])
    op.create_index("ix_live_orders_account_digest", "live_orders", ["account_digest"])


def downgrade():
    op.drop_column("live_trading_sessions", "broker_account_digest")
    op.drop_table("live_orders")
    op.drop_table("dhan_instruments")
    with op.batch_alter_table("broker_connections") as batch:
        batch.drop_constraint("uq_broker_connection_account_digest", type_="unique")
        batch.drop_column("account_digest")
        batch.drop_column("account_id_encrypted")
