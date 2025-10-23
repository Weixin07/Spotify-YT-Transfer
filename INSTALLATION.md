# Installation & Setup Guide

Complete guide to installing and configuring Spotify-YT-Transfer.

---

Prerequisites

Required Software
- Python 3.10 or higher - Download from [python.org](https://www.python.org/downloads/)
- pip - Usually included with Python
- Git (optional) - For version control

API Credentials Required
You'll need API credentials from both platforms:

1. Spotify Developer Account
   - Create at: https://developer.spotify.com/dashboard
   - Create an app to get Client ID and Client Secret
   - Set redirect URI to: `http://localhost:8001/v1/spotify/callback`

2. Google Cloud Console Account
   - Create at: https://console.cloud.google.com/
   - Enable YouTube Data API v3
   - Create OAuth 2.0 credentials
   - Download client secrets

---

Installation Steps

1. Clone or Download the Project

```bash
# If using git
git clone https://github.com/yourusername/spotify-yt-transfer.git
cd spotify-yt-transfer

# Or download and extract the ZIP file
```

2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On Linux/Mac:
source venv/bin/activate
```

3. Install the Package

```bash
# Install with all dependencies
pip install -e ".[dev]"
```

This installs:
- Runtime dependencies: FastAPI, Uvicorn, SQLAlchemy, Spotipy, etc.
- Development tools: Black, Ruff, MyPy, Pytest, pre-commit
- Package in editable mode: Code changes take effect immediately

4. Configure Environment Variables

```bash
# Copy the template file
# On Windows:
copy .env.example .env

# On Linux/Mac:
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Spotify API Configuration
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8001/v1/spotify/callback

# YouTube API Configuration
YOUTUBE_CLIENT_ID=your_youtube_client_id_here
YOUTUBE_CLIENT_SECRET=your_youtube_client_secret_here
YOUTUBE_REDIRECT_URI=http://localhost:8002

# Application Configuration
DEBUG=False
APP_ENV=development
DB_PATH=data/matched_tracks.db

# Optional: Customize settings
MATCH_FUZZ_THRESHOLD=70
LOG_FILE_NAME=migration.log
HTTP_REQUEST_TIMEOUT=30
```

5. Initialize Database

The database will be created automatically on first run. To manually initialize:

```python
from spotify_yt_transfer.database import init_db
init_db()
```

---

Running the Application

Start the Server

Choose one of these methods:

Method 1: Using Uvicorn directly
```bash
uvicorn spotify_yt_transfer.main:app --reload --port 8001
```

Method 2: Using the CLI command
```bash
spotify-yt-transfer
```

Method 3: As Python module
```bash
python -m spotify_yt_transfer.main
```

Access the Application

Once running, access these URLs:

- Interactive API Documentation: http://localhost:8001/docs
- Alternative Docs (ReDoc): http://localhost:8001/redoc
- OpenAPI Schema: http://localhost:8001/openapi.json
- Health Check: http://localhost:8001/health
- Prometheus Metrics: http://localhost:8001/metrics

---

Verification

Test the Installation

1. Check Health Endpoint
```bash
curl http://localhost:8001/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "spotify-yt-transfer"
}
```

2. Check Readiness
```bash
curl http://localhost:8001/ready
```

3. View API Documentation

Open http://localhost:8001/docs in your browser to see all available endpoints.

Test OAuth Flow

1. Navigate to http://localhost:8001/docs
2. Try the `/v1/spotify/callback` endpoint
3. You'll be redirected to Spotify for authorization
4. After authorization, the service can access your Spotify data

---

Development Setup

Install Pre-commit Hooks

```bash
# One-time setup
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

Code Quality Tools

Format Code
```bash
black src/ tests/
```

Lint Code
```bash
ruff check src/ tests/ --fix
```

Type Check
```bash
mypy src/
```

Run All Checks
```bash
pre-commit run --all-files
```

Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/test_spotify_client.py

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

---

Project Structure

After installation, your directory structure:

```
spotify-yt-transfer/
├── .env                       # Your credentials (not in git)
├── .env.example               # Template file
├── .gitignore                 # Git ignore rules
├── .pre-commit-config.yaml    # Code quality hooks
├── pyproject.toml             # Project configuration
├── README.md                  # Main documentation
├── ARCHITECTURE.md            # Architecture details
├── INSTALLATION.md            # This file
├── DATABASE_MIGRATIONS.md     # Alembic migration guide
│
├── src/
│   └── spotify_yt_transfer/   # Main package
│       ├── __init__.py
│       ├── main.py            # FastAPI application
│       ├── core/              # Configuration & logging
│       ├── database/          # Models & repository
│       ├── schemas/           # Pydantic schemas
│       ├── clients/           # API clients
│       ├── services/          # Business logic
│       └── api/               # HTTP routes
│           └── v1/routes/     # Versioned endpoints
│
├── tests/                     # Test suite
├── data/                      # Database storage
│   └── matched_tracks.db      # SQLite database
│
└── venv/                      # Virtual environment (not in git)
```

---

Troubleshooting

Import Errors

Problem: `ModuleNotFoundError: No module named 'spotify_yt_transfer'`

Solution:
```bash
# Ensure you're in the project root
# Ensure virtual environment is activated
# Reinstall the package
pip install -e .
```

Database Errors

Problem: `OperationalError: no such table`

Solution:
```bash
# Delete the database file
rm data/matched_tracks.db  # Linux/Mac
del data\matched_tracks.db  # Windows

# Restart the application (tables will be recreated)
uvicorn spotify_yt_transfer.main:app --reload
```

Port Already in Use

Problem: `[Errno 48] Address already in use`

Solution:
```bash
# Find process using port 8001
# On Windows:
netstat -ano | findstr :8001

# On Linux/Mac:
lsof -i :8001

# Kill the process or use different port
uvicorn spotify_yt_transfer.main:app --port 8002
```

OAuth Errors

Problem: OAuth redirect fails

Solutions:
- Verify redirect URI in `.env` matches Spotify/YouTube console
- Check that Client ID and Secret are correct
- Ensure no extra spaces in `.env` file
- Try re-creating OAuth credentials in developer console

YouTube Quota Exceeded

Problem: `quotaExceeded` error from YouTube API

Solution:
- Check quota usage: https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas
- Daily limit is 10,000 units
- Wait 24 hours for reset
- See `ARCHITECTURE.md` for quota optimization strategies

Type Checking Errors

Problem: MyPy shows errors for third-party libraries

Solution:
```bash
# Use --ignore-missing-imports flag
mypy src/ --ignore-missing-imports

# Or it's already configured in pyproject.toml
```

Python Version Issues

Problem: Code doesn't work on older Python versions

Solution:
```bash
# This project requires Python 3.10+
python --version  # Check your version

# Upgrade Python or use pyenv/conda for version management
```

---

Configuration Details

Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SPOTIFY_CLIENT_ID` | Yes | - | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Yes | - | Spotify app client secret |
| `SPOTIFY_REDIRECT_URI` | Yes | - | OAuth callback URL |
| `YOUTUBE_CLIENT_ID` | Yes | - | Google OAuth client ID |
| `YOUTUBE_CLIENT_SECRET` | Yes | - | Google OAuth client secret |
| `DEBUG` | No | False | Enable debug mode |
| `APP_ENV` | No | development | Environment name |
| `DB_PATH` | No | data/matched_tracks.db | Database file path |
| `MATCH_FUZZ_THRESHOLD` | No | 70 | Fuzzy match threshold (0-100) |
| `LOG_FILE_NAME` | No | migration.log | Log file name |
| `HTTP_REQUEST_TIMEOUT` | No | 30 | HTTP timeout in seconds |

Database Configuration

The application uses SQLite by default with these tables:
- `matched_tracks`: Cache for Spotify↔YouTube track matches
- `failed_tracks`: Tracks that failed to migrate

Database location: `data/matched_tracks.db`

To use PostgreSQL instead, modify `core/config.py` database settings.

---

Production Deployment

Preparation

1. Set Production Environment
```bash
# In .env
DEBUG=False
APP_ENV=production
```

2. Use Production Server
```bash
# Install production server
pip install gunicorn

# Run with multiple workers
gunicorn spotify_yt_transfer.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001
```

3. Set Up Reverse Proxy

Example Nginx configuration:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

4. Enable HTTPS
```bash
# Use Let's Encrypt
sudo certbot --nginx -d yourdomain.com
```

5. Configure Logging
- Use centralized logging (e.g., ELK stack, CloudWatch)
- Set up log rotation
- Monitor error logs

6. Set Up Monitoring
- Use Prometheus to scrape `/metrics`
- Set up Grafana dashboards
- Configure alerts for errors/downtime

7. Database Backups
```bash
# Automated daily backup
0 2 * * * cp data/matched_tracks.db backups/matched_tracks_$(date +\%Y\%m\%d).db
```

---

Next Steps

1. ✅ Installation complete
2. ✅ Application running
3. 📖 Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system
4. 🧪 Test endpoints using Swagger UI at `/docs`
5. 🔧 Customize configuration as needed
6. 🚀 Deploy to production following the guide above

For more information:
- Architecture: See [ARCHITECTURE.md](ARCHITECTURE.md)
- API Reference: Visit `/docs` when app is running
- Database Migrations: See [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md)
