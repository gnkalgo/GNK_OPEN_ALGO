"""Store broker account links without persisting broker tokens."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "broker_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("broker_code", sa.String(20), nullable=False),
        sa.Column("account_id_last4", sa.String(4), nullable=False),
        sa.Column("account_name", sa.String(120), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "broker_code", name="uq_broker_connection_user_code"),
    )
    op.create_index("ix_broker_connections_user_id", "broker_connections", ["user_id"])


def downgrade():
    op.drop_index("ix_broker_connections_user_id", table_name="broker_connections")
    op.drop_table("broker_connections")
