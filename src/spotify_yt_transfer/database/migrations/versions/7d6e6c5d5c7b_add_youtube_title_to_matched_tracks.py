"""Add youtube_title column to matched_tracks

Revision ID: 7d6e6c5d5c7b
Revises: 63d7ab0fd8b0
Create Date: 2025-12-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d6e6c5d5c7b"
down_revision: str | None = "63d7ab0fd8b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add youtube_title column to matched_tracks."""
    op.add_column("matched_tracks", sa.Column("youtube_title", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove youtube_title column."""
    op.drop_column("matched_tracks", "youtube_title")

