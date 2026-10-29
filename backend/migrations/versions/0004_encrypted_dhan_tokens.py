"""Store encrypted Dhan access tokens and their expiry."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "broker_connections",
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "broker_connections",
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("broker_connections", "access_token_expires_at")
    op.drop_column("broker_connections", "access_token_encrypted")
