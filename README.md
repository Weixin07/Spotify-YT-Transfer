# Spotify-YT-Transfer

A production-ready FastAPI service for migrating Spotify playlists to YouTube Music with intelligent track matching, built with industrial-grade architecture.

✨ Features

- 🎵 Playlist Migration: Migrate Spotify playlists to YouTube Music
- 🎯 Intelligent Matching: Fuzzy matching algorithm for accurate track identification
- 💾 Caching: SQLite database caches matched tracks to avoid redundant API calls
- 📊 Missing Track Detection: Identify tracks that failed migration for retry
- 🖼️ Cover Art Download: Download Spotify playlist cover images
- ✂️ Liked Songs Splitting: Split large liked songs collection into manageable playlists
- 📈 Monitoring: Prometheus metrics, health checks, and structured logging
- 🔒 OAuth Authentication: Secure authentication with both Spotify and YouTube APIs

🏗️ Architecture

Built with clean architecture principles and modern Python best practices:

- Layered Architecture: API → Services → Repository → Database
- Dependency Injection: FastAPI Depends system
- Type Safety: Comprehensive type hints (~90% coverage)
- API Versioning: `/v1/` prefix for future compatibility
- Repository Pattern: Clean database abstraction
- Pydantic Validation: Request/response schema validation

🚀 Quick Start

Installation

```bash
# Install package with development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional)
pre-commit install
```

Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API credentials
# - Spotify: client_id, client_secret, redirect_uri
# - YouTube: client_id, client_secret
```

Running the Service

```bash
# Method 1: Using uvicorn directly
uvicorn spotify_yt_transfer.main:app --reload --port 8001

# Method 2: Using the CLI entry point
spotify-yt-transfer

# Method 3: As a Python module
python -m spotify_yt_transfer.main
```

Access API Documentation

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc
- OpenAPI Schema: http://localhost:8001/openapi.json

📡 API Endpoints

Health & Monitoring
- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /metrics` - Prometheus metrics

Authentication
- `GET /v1/spotify/callback` - Spotify OAuth callback

Migration
- `GET /v1/migrate` - Migrate Spotify playlist to YouTube
- `GET /v1/check-missing` - Find missing/duplicate tracks

Utilities
- `GET /v1/youtube/playlist` - Find YouTube playlist by name
- `POST /v1/split-liked-songs` - Split liked songs into playlists
- `GET /v1/download-cover` - Download playlist cover image

🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov

# Run specific test file
pytest tests/test_migration.py -v
```

Current Status: ✅ All 13 tests passing | Coverage: 49.59%

🔧 Development

Code Quality

```bash
# Auto-format code
black src/ tests/

# Lint code
ruff check src/ tests/ --fix

# Type check
mypy src/

# Run all pre-commit hooks
pre-commit run --all-files
```

Project Structure

```
src/spotify_yt_transfer/
├── main.py                    # FastAPI application entry point
├── core/                      # Configuration and logging
├── database/                  # SQLAlchemy models and repository
├── clients/                   # Spotify and YouTube API clients
├── services/                  # Business logic layer
├── schemas/                   # Pydantic validation schemas
└── api/                       # HTTP routes and dependencies
    └── v1/routes/             # Versioned API endpoints
```

📊 Monitoring

Prometheus Metrics

Access metrics at `/metrics` for:
- Request counts and latencies
- Error rates
- Active requests
- Custom application metrics

YouTube API Quotas

Monitor your YouTube API quota:
https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas

🐛 Troubleshooting

Common Issues

Import Errors: Ensure you installed with `pip install -e .`

Database Errors: Delete `data/matched_tracks.db` and restart

OAuth Errors: Verify credentials in `.env` and callback URLs match API console

YouTube Quota: The service includes retry logic and quota management

📝 License

MIT License - See LICENSE file for details

🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and quality checks
5. Submit a pull request

📚 Documentation

- [Architecture Guide](ARCHITECTURE.md) - Technical architecture and design patterns
- [Installation Guide](INSTALLATION.md) - Detailed setup instructions
- [Database Migrations](DATABASE_MIGRATIONS.md) - Alembic migration guide

---

Built with ❤️ using FastAPI, SQLAlchemy, and modern Python tooling
