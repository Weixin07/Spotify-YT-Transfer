# Database Migrations Guide

Guide to managing database schema changes using Alembic.

---

Overview

This project uses Alembic for database schema migrations. Alembic allows you to:
- Track database schema changes over time
- Apply changes incrementally
- Rollback changes if needed
- Maintain schema version history

Database: SQLite (default) - can be changed to PostgreSQL/MySQL

Migration Location: `src/spotify_yt_transfer/database/migrations/`

---

Current Database Schema

The application uses two main tables:

`matched_tracks`
Caches Spotify-to-YouTube track matches to avoid redundant API calls.

```sql
CREATE TABLE matched_tracks (
    spotify_id TEXT PRIMARY KEY,
    song_name TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT,
    youtube_id TEXT NOT NULL
);
```

`failed_tracks`
Stores tracks that failed to migrate for debugging and retry.

```sql
CREATE TABLE failed_tracks (
    spotify_id TEXT PRIMARY KEY,
    youtube_id TEXT,
    reason TEXT
);
```

---

Alembic Configuration

Configuration File
Located at: `src/spotify_yt_transfer/database/alembic.ini`

Key settings:
```ini
[alembic]
script_location = src/spotify_yt_transfer/database/migrations
sqlalchemy.url = sqlite:///data/matched_tracks.db
```

Migration Environment
Located at: `src/spotify_yt_transfer/database/migrations/env.py`

This file connects Alembic to your SQLAlchemy models.

---

Common Migration Tasks

1. Viewing Current Migration Status

Check which migrations have been applied:

```bash
# View current database version
alembic -c src/spotify_yt_transfer/database/alembic.ini current

# View migration history
alembic -c src/spotify_yt_transfer/database/alembic.ini history
```

2. Creating a New Migration

When you modify your SQLAlchemy models in `src/spotify_yt_transfer/database/models.py`:

```bash
# Auto-generate migration from model changes
alembic -c src/spotify_yt_transfer/database/alembic.ini revision --autogenerate -m "Descriptive message"

# Example:
alembic -c src/spotify_yt_transfer/database/alembic.ini revision --autogenerate -m "Add index to song_name column"
```

This creates a new migration file in `migrations/versions/`.

Important: Always review auto-generated migrations before applying!

3. Applying Migrations

Apply pending migrations to bring database up to date:

```bash
# Upgrade to latest version
alembic -c src/spotify_yt_transfer/database/alembic.ini upgrade head

# Upgrade one version
alembic -c src/spotify_yt_transfer/database/alembic.ini upgrade +1

# Upgrade to specific revision
alembic -c src/spotify_yt_transfer/database/alembic.ini upgrade <revision_id>
```

4. Rolling Back Migrations

Revert to a previous schema version:

```bash
# Downgrade one version
alembic -c src/spotify_yt_transfer/database/alembic.ini downgrade -1

# Downgrade to specific revision
alembic -c src/spotify_yt_transfer/database/alembic.ini downgrade <revision_id>

# Downgrade to base (empty database)
alembic -c src/spotify_yt_transfer/database/alembic.ini downgrade base
```

5. Viewing Migration Details

```bash
# Show details of specific migration
alembic -c src/spotify_yt_transfer/database/alembic.ini show <revision_id>

# List all revisions
alembic -c src/spotify_yt_transfer/database/alembic.ini heads
```

---

Migration Examples

Example 1: Adding a Column

1. Modify your model:

```python
# src/spotify_yt_transfer/database/models.py
class MatchedTrack(Base):
    __tablename__ = "matched_tracks"

    spotify_id = Column(String, primary_key=True)
    song_name = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    album = Column(String)
    youtube_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)  # NEW COLUMN
```

2. Generate migration:

```bash
alembic -c src/spotify_yt_transfer/database/alembic.ini revision --autogenerate -m "Add created_at column to matched_tracks"
```

3. Review the generated file in `migrations/versions/`

4. Apply the migration:

```bash
alembic -c src/spotify_yt_transfer/database/alembic.ini upgrade head
```

Example 2: Adding an Index

1. Modify your model:

```python
class MatchedTrack(Base):
    __tablename__ = "matched_tracks"
    __table_args__ = (
        Index('ix_matched_tracks_song_name', 'song_name'),  # NEW INDEX
    )

    spotify_id = Column(String, primary_key=True)
    song_name = Column(String, nullable=False)
    # ... rest of columns
```

2. Generate and apply:

```bash
alembic -c src/spotify_yt_transfer/database/alembic.ini revision --autogenerate -m "Add index on song_name"
alembic -c src/spotify_yt_transfer/database/alembic.ini upgrade head
```

Example 3: Creating a Manual Migration

Sometimes you need to write custom migration logic:

```bash
# Create empty migration
alembic -c src/spotify_yt_transfer/database/alembic.ini revision -m "Custom data migration"
```

Edit the generated file:

```python
"""Custom data migration

Revision ID: abc123
"""

def upgrade():
    # Add custom upgrade logic
    op.execute("UPDATE matched_tracks SET album = 'Unknown' WHERE album IS NULL")

def downgrade():
    # Add custom downgrade logic
    op.execute("UPDATE matched_tracks SET album = NULL WHERE album = 'Unknown'")
```

---

Migration Best Practices

1. Always Review Auto-Generated Migrations

Alembic's autogenerate is helpful but not perfect. Always review generated migrations:

```bash
# After generating migration
cat src/spotify_yt_transfer/database/migrations/versions/<new_revision>.py
```

Check for:
- Correct table/column names
- Proper data types
- Missing indexes or constraints

2. Test Migrations in Development First

```bash
# Backup your database first
cp data/matched_tracks.db data/matched_tracks_backup.db

# Apply migration
alembic -c src/spotify_yt_transfer/database/alembic.ini upgrade head

# Test the application
pytest

# If issues occur, rollback
alembic -c src/spotify_yt_transfer/database/alembic.ini downgrade -1

# Restore backup if needed
cp data/matched_tracks_backup.db data/matched_tracks.db
```

3. Use Descriptive Migration Messages

Good:
```bash
alembic revision --autogenerate -m "Add email column to users table"
alembic revision -m "Migrate legacy playlist format to new schema"
```

Bad:
```bash
alembic revision --autogenerate -m "update"
alembic revision -m "fix"
```

4. One Logical Change Per Migration

Don't combine unrelated changes:

Good: Separate migrations for separate features
```bash
alembic revision -m "Add user_preferences table"
alembic revision -m "Add index to matched_tracks.youtube_id"
```

Bad: Everything in one migration
```bash
alembic revision -m "Add tables and indexes and fix data"
```

5. Always Implement Downgrade

Every migration should have a working `downgrade()` function:

```python
def upgrade():
    op.add_column('matched_tracks', sa.Column('created_at', sa.DateTime))

def downgrade():
    op.drop_column('matched_tracks', 'created_at')  # Don't forget this!
```

---

Switching to PostgreSQL

To use PostgreSQL instead of SQLite:

1. Update Configuration

Edit `src/spotify_yt_transfer/core/config.py`:

```python
@dataclass(frozen=True)
class DatabaseConfig:
    # Change from SQLite to PostgreSQL
    url: str = "postgresql://user:password@localhost:5432/spotify_yt_transfer"
```

2. Update Alembic Configuration

Edit `src/spotify_yt_transfer/database/alembic.ini`:

```ini
sqlalchemy.url = postgresql://user:password@localhost:5432/spotify_yt_transfer
```

3. Install PostgreSQL Driver

```bash
pip install psycopg2-binary
```

4. Create Database

```bash
# In PostgreSQL
createdb spotify_yt_transfer
```

5. Apply Migrations

```bash
alembic -c src/spotify_yt_transfer/database/alembic.ini upgrade head
```

---

Troubleshooting

Migration Out of Sync

Problem: "Can't locate revision identified by 'abc123'"

Solution:
```bash
# Check current database version
alembic -c src/spotify_yt_transfer/database/alembic.ini current

# Stamp database with correct version
alembic -c src/spotify_yt_transfer/database/alembic.ini stamp head
```

Migration Fails Halfway

Problem: Migration fails, database is in inconsistent state

Solution:
```bash
# For SQLite, restore from backup
cp data/matched_tracks_backup.db data/matched_tracks.db

# For PostgreSQL, use transaction rollback
# (PostgreSQL automatically rolls back failed migrations)

# Fix the migration file
# Try again
alembic -c src/spotify_yt_transfer/database/alembic.ini upgrade head
```

Can't Autogenerate Migrations

Problem: `--autogenerate` doesn't detect changes

Solution:
- Ensure models inherit from `Base`
- Check that `env.py` imports your models
- Verify `target_metadata` is set correctly in `env.py`

```python
# In migrations/env.py
from spotify_yt_transfer.database.models import Base
target_metadata = Base.metadata  # Must be set!
```

Accidental Migration to Production

Problem: Applied wrong migration to production database

Solution:
```bash
# Immediately rollback
alembic -c src/spotify_yt_transfer/database/alembic.ini downgrade <previous_revision>

# Restore from production backup
# Apply correct migration
```

---

Migration Workflow

Development Workflow

1. Make changes to models in `models.py`
2. Generate migration: `alembic revision --autogenerate -m "message"`
3. Review generated migration file
4. Test locally: `alembic upgrade head`
5. Test application: `pytest`
6. Commit migration file to git
7. Push to repository

Production Deployment Workflow

1. Pull latest code with new migration
2. Backup database before applying
3. Test migration on staging environment
4. Apply to production: `alembic upgrade head`
5. Verify application works correctly
6. Monitor for errors

---

Reference

Alembic Commands Quick Reference

| Command | Description |
|---------|-------------|
| `alembic current` | Show current revision |
| `alembic history` | Show revision history |
| `alembic heads` | Show head revision(s) |
| `alembic revision --autogenerate -m "msg"` | Create auto migration |
| `alembic revision -m "msg"` | Create empty migration |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic upgrade +1` | Apply next migration |
| `alembic downgrade -1` | Revert last migration |
| `alembic downgrade base` | Revert all migrations |
| `alembic show <revision>` | Show migration details |
| `alembic stamp <revision>` | Set database version without running migration |

Configuration Paths

| Item | Path |
|------|------|
| Alembic Config | `src/spotify_yt_transfer/database/alembic.ini` |
| Migration Scripts | `src/spotify_yt_transfer/database/migrations/versions/` |
| Migration Environment | `src/spotify_yt_transfer/database/migrations/env.py` |
| SQLAlchemy Models | `src/spotify_yt_transfer/database/models.py` |
| Database File (SQLite) | `data/matched_tracks.db` |

---

Additional Resources

- Alembic Documentation: https://alembic.sqlalchemy.org/
- SQLAlchemy Documentation: https://docs.sqlalchemy.org/
- Database Design: See `ARCHITECTURE.md` for schema design decisions

---

Next Steps

- Review current database schema in `models.py`
- Understand migration history with `alembic history`
- Practice creating a test migration in development
- Set up database backups before production migrations
- Document any custom migration logic in migration file comments
