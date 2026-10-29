"""Add per-account paper risk policies; absence uses conservative service defaults."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "risk_policies",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("max_order_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("max_daily_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("max_quantity", sa.Integer(), nullable=False),
        sa.Column("halted", sa.Boolean(), nullable=False),
    )


def downgrade():
    op.drop_table("risk_policies")
