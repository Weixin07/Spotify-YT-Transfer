# Architecture Documentation

System Architecture

High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         HTTP Clients                             │
│                    (Browsers, API Tools)                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                         │
│                         (main.py)                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Rate Limiting (10 req/min) │ Prometheus Metrics         │   │
│  │  Swagger/ReDoc Docs │ Health Checks │ API Versioning     │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Presentation Layer                            │
│                    (api/v1/routes/)                              │
│  ┌──────────┬──────────┬──────────────┬────────────────────┐    │
│  │ Health   │ Auth     │ Migration    │ Utilities          │    │
│  │ Routes   │ Routes   │ Routes       │ Routes             │    │
│  └──────────┴──────────┴──────────────┴────────────────────┘    │
└────────────────────────┬────────────────────────────────────────┘
                         │ (FastAPI Depends)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Dependency Injection                           │
│                    (api/dependencies.py)                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Singleton Clients │ Service Factories │ DB Sessions     │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Business Logic Layer                         │
│                       (services/)                                │
│  ┌──────────────────┬───────────────────┬──────────────────┐    │
│  │ MigrationService │ PlaylistService   │ TrackMatcher     │    │
│  │  - Orchestrates  │  - Playlist ops   │  - Fuzzy match   │    │
│  │    migration     │  - Missing tracks │  - Algorithm     │    │
│  │  - Retry logic   │  - Split songs    │  - Caching       │    │
│  └──────────────────┴───────────────────┴──────────────────┘    │
└────────┬────────────────────────────────┬───────────────────────┘
         │                                │
         ▼                                ▼
┌──────────────────────────┐    ┌─────────────────────────────────┐
│   Data Access Layer      │    │   External API Clients          │
│  (database/repository)   │    │      (clients/)                 │
│  ┌────────────────────┐  │    │  ┌───────────┬──────────────┐   │
│  │ TrackRepository    │  │    │  │  Spotify  │  YouTube     │   │
│  │  - get_matched     │  │    │  │  Client   │  Client      │   │
│  │  - save_matched    │  │    │  │           │              │   │
│  │  - failed_tracks   │  │    │  │  OAuth2   │  OAuth2      │   │
│  └────────────────────┘  │    │  │  Caching  │  Quota Mgmt  │   │
└────────┬─────────────────┘    │  └───────────┴──────────────┘   │
         │                      └────────┬────────────────────────┘
         ▼                               │
┌─────────────────────────┐              ▼
│   Database (SQLite)     │    ┌─────────────────────────────────┐
│  ┌──────────────────┐   │    │  External APIs                  │
│  │ matched_tracks   │   │    │  ┌─────────────────────────┐    │
│  │ failed_tracks    │   │    │  │ Spotify Web API         │    │
│  └──────────────────┘   │    │  │ YouTube Data API v3     │    │
│      (data/)             │    │  └─────────────────────────┘    │
└─────────────────────────┘    └─────────────────────────────────┘
```

Layered Architecture Details

1. Presentation Layer (`api/v1/routes/`)

Responsibility: Handle HTTP requests, validate input, format responses

Components:
- health.py: Health/readiness checks, root endpoint
- auth.py: OAuth callback handlers
- migration.py: Playlist migration endpoints
- utilities.py: Utility operations (split songs, download covers, find playlists)

Pattern: Thin controllers - delegate to services, minimal logic

Example:
```python
@router.get("/migrate")
async def migrate_playlist(
    params: MigrateParams = Depends(),
    service: MigrationService = Depends(get_migration_service),
) -> dict[str, str]:
    return await run_in_threadpool(
        service.migrate_playlist,
        params.youtube_playlist_title,
        params.spotify_playlist_id,
    )
```

2. Business Logic Layer (`services/`)

Responsibility: Implement core business rules and workflows

Components:

MigrationService
- Orchestrates full playlist migration workflow
- Handles track-by-track processing
- Implements retry logic for failures
- Manages quota exceeded scenarios

PlaylistService
- Splits large playlists (e.g., 10,000 songs → 10 playlists)
- Finds missing/duplicate tracks between platforms
- Downloads playlist cover art

TrackMatcher
- Fuzzy string matching algorithm (rapidfuzz)
- Exact substring matching
- Configurable threshold (default 70%)
- Caches matching results

Pattern: Service layer encapsulates business logic, testable without HTTP

3. Data Access Layer (`database/`)

Responsibility: Abstract database operations, manage persistence

Components:

models.py (ORM Models)
```python
class MatchedTrack:
    spotify_id (PK)
    song_name
    artist
    album
    youtube_id

class FailedTrack:
    spotify_id (PK)
    youtube_id
    reason
```

repository.py (Repository Pattern)
```python
class TrackRepository:
    def get_matched_track(spotify_id) -> Optional[MatchedTrack]
    def save_matched_track(...) -> MatchedTrack
    def get_all_matched_tracks() -> List[MatchedTrack]
    def record_failed_track(...)
    def clear_failed_track(...)
```

Pattern: Repository pattern provides clean abstraction over SQLAlchemy

4. External API Clients (`clients/`)

Responsibility: Communicate with third-party APIs

SpotifyClient
- OAuth2 authentication flow
- Fetch playlists/liked songs (handles pagination)
- Create playlists
- Add tracks to playlists
- Retry logic with exponential backoff

YouTubeClient
- OAuth2 authentication flow
- Search videos with query
- Find playlists by name
- Get playlist items (handles pagination)
- Create playlists
- Add videos to playlists
- Quota management (10,000 units/day limit)
- Caching with TTLCache (reduces API calls)

Pattern: Singleton instances managed by dependency injection

5. Infrastructure Layer (`core/`)

Responsibility: Cross-cutting concerns (config, logging)

config.py
- Type-safe configuration with frozen dataclasses
- Environment variable loading
- Validation on startup
- Grouped by service (spotify, youtube, database, etc.)

logging.py
- Centralized logging setup
- Rotating file handlers
- Per-module loggers
- DEBUG/INFO levels based on environment

Data Flow: Migration Endpoint

```
1. HTTP Request
   └─> FastAPI receives GET /v1/migrate

2. Validation & DI
   └─> Pydantic validates params
   └─> FastAPI Depends injects MigrationService

3. Service Layer
   └─> MigrationService.migrate_playlist()
       ├─> SpotifyClient.get_playlist_tracks()
       │   └─> Spotify API call
       ├─> For each track:
       │   ├─> Repository.get_matched_track() (check cache)
       │   │   └─> SQLite query
       │   ├─> If not cached:
       │   │   ├─> YouTubeClient.search_video()
       │   │   │   └─> YouTube API call
       │   │   ├─> TrackMatcher.match_track() (fuzzy match)
       │   │   └─> Repository.save_matched_track() (cache result)
       │   └─> YouTubeClient.add_video_to_playlist()
       │       └─> YouTube API call
       └─> Return result

4. Response
   └─> FastAPI serializes to JSON
   └─> HTTP 200 OK
```

Design Patterns Used

1. Layered Architecture
- Clear separation: Presentation → Business Logic → Data Access
- Dependencies point inward (inner layers don't know about outer)

2. Repository Pattern
- TrackRepository abstracts database access
- Easy to swap SQLite for PostgreSQL
- Testable with mock repository

3. Dependency Injection
- FastAPI Depends system
- Singleton clients (shared across requests)
- Service factory functions

4. Service Layer
- Business logic isolated from HTTP concerns
- Reusable, testable services
- Clear single responsibility

5. Factory Pattern
- Client initialization (SpotifyClient, YouTubeClient)
- Service creation (MigrationService, PlaylistService)

6. Singleton Pattern
- API clients (expensive to create)
- Configuration (loaded once at startup)

7. Retry Pattern
- Tenacity library for exponential backoff
- Handles transient API failures
- Configurable attempts/delays

8. Caching Pattern
- TTLCache for YouTube search results
- Database cache for matched tracks
- Reduces API quota usage

Configuration Management

Environment-Based Config

```python
@dataclass(frozen=True)  # Immutable
class Settings:
    debug: bool
    environment: str
    spotify: SpotifyConfig
    youtube: YouTubeConfig
    database: DatabaseConfig
    logging: LoggingConfig
    matching: MatchingConfig
    cover: CoverConfig
```

Loading Priority:
1. Environment variables (.env file)
2. Default values
3. Validation on startup (fail-fast)

API Versioning Strategy

Current: `/v1/migrate`, `/v1/check-missing`

Future Compatibility:
- Add `/v2/` routes without breaking v1
- Deprecation headers for old versions
- Gradual migration path

Error Handling

Layered Error Handling

1. Client Layer: Catch API errors, retry transient failures
2. Service Layer: Catch business logic errors, log context
3. Route Layer: Convert to HTTP exceptions
4. FastAPI: Serialize to JSON error response

Example:
```python
try:
    result = service.migrate_playlist(...)
except Exception as e:
    if "quota exceeded" in str(e).lower():
        raise HTTPException(status_code=429, detail=str(e)) from e
    raise HTTPException(status_code=400, detail=str(e)) from e
```

Monitoring & Observability

Health Checks
- `/health`: Basic liveness check
- `/ready`: Readiness check (DB connection, etc.)

Metrics (Prometheus)
- `/metrics`: Request counts, latencies, error rates
- Custom metrics: API quota usage, cache hit rates

Logging
- Structured logs with context
- Rotating file handlers
- Per-module loggers for granularity

Security Considerations

OAuth2 Flow
- Spotify: Authorization Code Flow
- YouTube: Installed App Flow
- Secure token storage (pickle files, should migrate to encrypted storage)

Input Validation
- Pydantic schemas validate all inputs
- Type checking prevents injection
- Rate limiting prevents abuse

Secrets Management
- Environment variables (not hardcoded)
- .env.example template (no real secrets committed)
- Should integrate with secrets manager (AWS Secrets Manager, HashiCorp Vault)

Performance Optimizations

YouTube API Quota Management

The following optimizations have been implemented to reduce YouTube API quota usage:

1. Video Category Filter (`videoCategoryId=10`)
- Implementation: Added to search requests in `YouTubeClient.search_video()`
- Impact: Filters results to Music category only, eliminating pagination
- Quota Savings: 100-400 units per song

2. Remove Redundant Category Checking
- Implementation: Removed `videos.list` calls since category filter guarantees music videos
- Impact: Simplified search logic, reduced API calls
- Quota Savings: 1 unit per song

3. Increased Search Results per Page
- Implementation: Increased `maxResults` from 1 to 5
- Impact: Fewer pagination requests if first result isn't suitable
- Quota Savings: Up to 400 units per song

4. Database Caching
- Implementation: `matched_tracks` table caches YouTube video IDs
- Impact: Same song in different playlists reuses cached video ID (no search cost)
- Quota Savings: 100 units per cached song

Expected Performance

Per-Song Quota Cost:
- New song (not cached): 150 units (100 search + 50 insert)
- Cached song: 50 units (0 search + 50 insert)

Daily Capacity (10,000 quota units):
- Worst case (0% cache): 66 songs/day
- Average (50% cache): 100 songs/day
- Best case (70% cache): 125 songs/day

Scalability Considerations

Current Limitations (Single Instance)
- SQLite (file-based, not distributed)
- In-memory caches (not shared across instances)
- Synchronous migration (blocks thread)

Future Scaling Path
1. Database: Migrate to PostgreSQL/MySQL
2. Caching: Use Redis for shared cache
3. Async Processing: Use Celery for background tasks
4. Load Balancing: Deploy multiple instances
5. Queue System: RabbitMQ/SQS for task distribution

Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Web Framework | FastAPI | HTTP server, async support, OpenAPI |
| Database | SQLAlchemy + SQLite | ORM, local persistence |
| API Clients | Spotipy, google-api-python-client | OAuth, API wrappers |
| Matching | RapidFuzz | Fuzzy string matching |
| Retry Logic | Tenacity | Exponential backoff |
| Caching | cachetools | In-memory TTL cache |
| Validation | Pydantic | Schema validation, type safety |
| Monitoring | Prometheus | Metrics collection |
| Rate Limiting | SlowAPI | Request throttling |
| Testing | Pytest | Unit/integration tests |
| Code Quality | Black, Ruff, MyPy | Formatting, linting, typing |

Development Workflow

Local Development
1. `pip install -e ".[dev]"` - Install with dev dependencies
2. `cp .env.example .env` - Configure environment
3. `uvicorn spotify_yt_transfer.main:app --reload` - Run with hot reload

Code Quality
1. `black src/ tests/` - Auto-format
2. `ruff check src/ tests/ --fix` - Lint and auto-fix
3. `mypy src/` - Type check
4. `pytest --cov` - Test with coverage

Pre-commit Hooks
- Automatically run Black, Ruff, MyPy on git commit
- Ensures code quality before push

Deployment Considerations

Production Checklist
- [ ] Set `DEBUG=False` in environment
- [ ] Use production WSGI server (Gunicorn + Uvicorn workers)
- [ ] Set up HTTPS/TLS
- [ ] Configure proper logging (centralized, structured)
- [ ] Set up monitoring (Prometheus + Grafana)
- [ ] Database backups (automated)
- [ ] Rate limiting tuned for production load
- [ ] Health checks configured in orchestrator (K8s, ECS)
- [ ] Secrets in secrets manager (not .env file)
- [ ] CI/CD pipeline for automated testing/deployment

---

This architecture provides:
✅ Maintainability - Clear separation of concerns
✅ Testability - Dependency injection, mocking support
✅ Scalability - Layered design supports growth
✅ Reliability - Retry logic, error handling, caching
✅ Observability - Logging, metrics, health checks
✅ Security - OAuth2, input validation, secrets management
