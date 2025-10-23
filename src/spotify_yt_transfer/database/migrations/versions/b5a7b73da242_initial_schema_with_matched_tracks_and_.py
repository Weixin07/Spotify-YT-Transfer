"""Initial schema with matched_tracks and failed_tracks tables

Revision ID: b5a7b73da242
Revises: 
Create Date: 2025-10-21 14:53:16.308627

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5a7b73da242"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial database schema."""
    # Create matched_tracks table
    op.create_table(
        "matched_tracks",
        sa.Column("spotify_id", sa.String(), nullable=False),
        sa.Column("song_name", sa.String(), nullable=False),
        sa.Column("artist", sa.String(), nullable=False),
        sa.Column("album", sa.String(), nullable=True),
        sa.Column("youtube_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("spotify_id"),
    )
    op.create_index("ix_matched_tracks_spotify_id", "matched_tracks", ["spotify_id"], unique=False)

    # Create failed_tracks table
    op.create_table(
        "failed_tracks",
        sa.Column("spotify_id", sa.String(), nullable=False),
        sa.Column("youtube_id", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("spotify_id"),
    )
    op.create_index("ix_failed_tracks_spotify_id", "failed_tracks", ["spotify_id"], unique=False)


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index("ix_failed_tracks_spotify_id", table_name="failed_tracks")
    op.drop_table("failed_tracks")
    op.drop_index("ix_matched_tracks_spotify_id", table_name="matched_tracks")
    op.drop_table("matched_tracks")
