"""Add OAuth state table for tracking authorization flows

Revision ID: 63d7ab0fd8b0
Revises: b5a7b73da242
Create Date: 2025-10-23 16:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "63d7ab0fd8b0"
down_revision: str | None = "b5a7b73da242"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create oauth_states table for CSRF state storage."""
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.PrimaryKeyConstraint("state"),
    )
    op.create_index("ix_oauth_states_state", "oauth_states", ["state"], unique=False)
    op.create_index("ix_oauth_states_provider", "oauth_states", ["provider"], unique=False)


def downgrade() -> None:
    """Drop oauth_states table."""
    op.drop_index("ix_oauth_states_provider", table_name="oauth_states")
    op.drop_index("ix_oauth_states_state", table_name="oauth_states")
    op.drop_table("oauth_states")
