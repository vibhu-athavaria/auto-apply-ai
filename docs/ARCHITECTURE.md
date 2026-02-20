# LinkedIn Autopilot - Architecture Document

## Overview

This document outlines the complete folder structure, database schema, API endpoints, and Redis key conventions for the LinkedIn Autopilot project. It covers Phase 1 (Core Backend Foundation) and Phase 2 (Job Search Engine).

---

# PHASE 1 - Core Backend Foundation

Phase 1 focuses on user system and resume upload functionality.

## Folder Structure

### Root Level
```
.env.example                    # Environment variables template
docker-compose.yml              # Docker services (Postgres, Redis)
pyproject.toml                  # Python project configuration
docs/                           # Documentation
  ARCHITECTURE.md              # This architecture document
apps/                           # Application modules
  api/                          # FastAPI backend
    app/                        # Main application code
      __init__.py
      main.py                   # FastAPI app entry point
      config.py                 # Settings and configuration
      database.py               # Database connection and session
      models/                   # SQLAlchemy models
        __init__.py
        user.py
        resume.py
        job_search_profile.py
      schemas/                  # Pydantic schemas
        __init__.py
        user.py
        resume.py
        job_search_profile.py
        auth.py
      routers/                  # API routes
        __init__.py
        auth.py
        resumes.py
        health.py
      services/                 # Business logic
        __init__.py
        auth_service.py
        resume_service.py
      middleware/               # Custom middleware
        __init__.py
        logging_middleware.py
        cost_logging_middleware.py  # Empty for Phase 1
      utils/                    # Utilities
        __init__.py
        security.py             # JWT utilities
        logger.py
      uploads/                  # Local resume storage directory
    tests/                      # Test suite
      __init__.py
      conftest.py
      test_auth.py
      test_resumes.py
      test_health.py
    alembic/                    # Database migrations
      versions/
      env.py
      script.py.mako
    requirements.txt
    Dockerfile
  worker/                       # Placeholder for future phases
  web/                          # Placeholder for future phases
```

## File/Folder Descriptions

- **app/main.py**: Initializes the FastAPI application, includes all routers, and sets up middleware. Serves as the entry point for the API service.

- **app/config.py**: Manages application settings, loads environment variables, and configures database URLs, JWT secrets, etc.

- **app/database.py**: Establishes async database connections using SQLAlchemy, provides session management for database operations.

- **models/**: Contains SQLAlchemy ORM models defining database table structures. Each model file corresponds to a database table.

- **schemas/**: Houses Pydantic models for request/response validation, ensuring data integrity and type safety.

- **routers/**: Defines FastAPI route handlers, organizing API endpoints by functionality (auth, resumes, health).

- **services/**: Implements core business logic, separating concerns from route handlers for better maintainability.

- **middleware/**: Custom middleware components, including structured logging and placeholder for cost logging.

- **utils/**: Utility functions and helpers, such as JWT token handling and logging configuration.

- **uploads/**: Local directory for storing uploaded resume files securely.

- **tests/**: Unit and integration tests to ensure code reliability and catch regressions.

- **alembic/**: Database migration management using Alembic, ensuring schema changes are version-controlled.

## Database Schema (Phase 1)

All tables use UUID primary keys and include appropriate indexes on foreign keys and frequently queried columns.

### users
- id: UUID, primary key
- email: String(255), unique, indexed
- hashed_password: String(255)
- created_at: DateTime, default now()
- updated_at: DateTime, default now()

### resumes
- id: UUID, primary key
- user_id: UUID, foreign key to users.id, indexed
- filename: String(255)
- file_path: String(500)
- uploaded_at: DateTime, default now()

### job_search_profiles
- id: UUID, primary key
- user_id: UUID, foreign key to users.id, indexed
- keywords: String(500)
- location: String(255)
- created_at: DateTime, default now()

## API Endpoint Structure

All endpoints use JSON for request/response bodies. Authentication endpoints return JWT tokens.

- POST /auth/register - Register new user (email, password)
- POST /auth/login - User login, returns JWT token
- POST /resumes/upload - Upload resume file (authenticated, multipart/form-data)
- GET /health - Health check endpoint
- GET /users/me - Get current authenticated user info

## Redis Key Naming Conventions (Phase 1)

Redis usage in Phase 1 is minimal but follows the required format: `li_autopilot:{service}:{entity}:{identifier}`

- li_autopilot:api:user:{user_id} - User session data or temporary state (if implemented)
- li_autopilot:api:rate_limit:{user_id} - Rate limiting counters (prepared for future phases)

Primary Redis usage will expand in later phases for caching and queuing.

---

# PHASE 2 - Job Search Engine (Read-Only)

Phase 2 introduces the Worker service for LinkedIn job search automation. The Worker operates independently from the API and handles all browser automation tasks.

## Critical Architecture Rules (Non-Negotiable)

Per AGENTS.md, the following rules are mandatory:

1. **API must NEVER execute browser automation**
2. **API must NEVER call Playwright**
3. **Worker must NOT expose HTTP endpoints**
4. **API enqueues tasks; Worker executes them**
5. **No long-running tasks inside API request lifecycle**
6. **Never store LinkedIn passwords**

## Folder Structure (Updated)

```
apps/
  api/                          # FastAPI backend (unchanged from Phase 1)
    app/
      models/
        job.py                  # NEW: Job model for storing listings
      schemas/
        job.py                  # NEW: Job Pydantic schemas
      routers/
        jobs.py                 # NEW: Jobs endpoint
      services/
        job_service.py          # NEW: Job business logic
        queue_service.py        # NEW: Redis queue operations
    ...
  worker/                       # NEW: Independent background worker
    __init__.py
    main.py                     # Worker entry point
    config.py                   # Worker-specific settings
    alembic/                    # Shared migrations (or can be separate)
      versions/
    automation/                 # Browser automation modules
      __init__.py
      linkedin_client.py        # Playwright LinkedIn interaction
      job_scraper.py            # Job search and parsing logic
      session_manager.py        # Cookie-based session handling
    tasks/                      # Background task handlers
      __init__.py
      job_search_task.py        # Job search task implementation
    utils/                      # Worker utilities
      __init__.py
      delays.py                 # Randomized delay utilities
      rate_limiter.py           # Per-user rate limiting
      backoff.py                # Exponential backoff logic
      logger.py                 # Structured logging for worker
    tests/                      # Worker tests
      __init__.py
      test_job_scraper.py
      test_linkedin_client.py
    requirements.txt            # Worker dependencies
    Dockerfile                  # Worker container
```

## Worker Service File Descriptions

### Core Files

- **main.py**: Worker entry point. Connects to Redis, listens for job queue messages, and dispatches tasks. No HTTP server.

- **config.py**: Worker-specific configuration including Redis URL, Playwright settings, rate limits, and delay parameters.

- **automation/linkedin_client.py**: Core Playwright-based LinkedIn interaction. Handles browser context creation, cookie-based authentication, and page navigation.

- **automation/job_scraper.py**: Implements job search by keyword/location, parses job listings, extracts Title, Company, URL, and Easy Apply flag.

- **automation/session_manager.py**: Manages LinkedIn session cookies. Stores cookies securely (never passwords) and validates session validity.

- **tasks/job_search_task.py**: Background task handler for job search requests. Orchestrates the full job search flow.

### Utility Files

- **utils/delays.py**: Provides randomized human-like delays to avoid detection. Implements configurable min/max delay ranges.

- **utils/rate_limiter.py**: Enforces per-user rate limits using Redis counters. Checks daily caps before allowing automation.

- **utils/backoff.py**: Implements exponential backoff for retry logic on failures.

- **utils/logger.py**: Structured logging with required fields: timestamp, level, service (worker), user_id, action, status.

## Database Schema (Phase 2)

### jobs Table

```sql
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    linkedin_job_id VARCHAR(100) UNIQUE NOT NULL,  -- LinkedIn's unique job ID for deduplication
    title VARCHAR(500) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    job_url TEXT NOT NULL,
    easy_apply BOOLEAN DEFAULT FALSE,
    description TEXT,                              -- Full job description (for Phase 3)
    search_profile_id UUID NOT NULL REFERENCES job_search_profiles(id),
    user_id UUID NOT NULL REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'discovered',       -- discovered, viewed, applied, failed
    discovered_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_jobs_linkedin_job_id (linkedin_job_id),
    INDEX idx_jobs_user_id (user_id),
    INDEX idx_jobs_search_profile_id (search_profile_id),
    INDEX idx_jobs_status (status),
    INDEX idx_jobs_discovered_at (discovered_at)
);
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| linkedin_job_id | VARCHAR(100) | LinkedIn's unique job identifier. Used for deduplication. UNIQUE constraint prevents duplicate job entries. |
| title | VARCHAR(500) | Job title from listing |
| company | VARCHAR(255) | Company name |
| location | VARCHAR(255) | Job location |
| job_url | TEXT | Full URL to LinkedIn job posting |
| easy_apply | BOOLEAN | Whether job supports Easy Apply |
| description | TEXT | Full job description (populated in Phase 3 for resume tailoring) |
| search_profile_id | UUID | Reference to the search profile that discovered this job |
| user_id | UUID | Reference to the user who owns this job |
| status | VARCHAR(50) | Current job status: discovered, viewed, applied, failed |
| discovered_at | TIMESTAMP | When the job was first discovered |
| updated_at | TIMESTAMP | Last status update time |

## API-Worker Communication Flow

```mermaid
sequenceDiagram
    participant User
    participant API as API Service
    participant Redis as Redis Queue
    participant Worker as Worker Service
    participant LI as LinkedIn

    User->>API: GET /jobs?search_profile_id=xxx
    API->>Redis: Check cache for jobs
    alt Cache hit
        Redis-->>API: Return cached jobs
        API-->>User: Return jobs list
    else Cache miss
        API->>API: Return empty list or stale jobs
        API-->>User: Return current jobs
    end

    User->>API: POST /jobs/search - Trigger search
    API->>API: Validate request
    API->>Redis: Enqueue job_search task
    API-->>User: 202 Accepted with task_id

    Note over Worker: Worker polls Redis queue

    Worker->>Redis: Dequeue job_search task
    Worker->>Worker: Check rate limits
    Worker->>Worker: Apply randomized delay
    Worker->>LI: Navigate with Playwright
    LI-->>Worker: Job listings page

    Worker->>Worker: Parse job listings
    Worker->>Worker: Deduplicate by linkedin_job_id

    loop For each new job
        Worker->>Redis: Check dedup key
        alt New job
            Worker->>API: Store job in DB via internal call
            Worker->>Redis: Set dedup key
        else Duplicate
            Worker->>Worker: Skip job
        end
    end

    Worker->>Redis: Cache search results - 24h TTL
    Worker->>Redis: Update task status = completed
```

## Redis Key Naming Conventions (Phase 2)

All keys follow the format: `li_autopilot:{service}:{entity}:{identifier}`

### Job Search & Caching

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `li_autopilot:worker:job_search_cache:{search_profile_id}:{date}` | 24h | Cached job search results for a profile on a specific date |
| `li_autopilot:worker:job_dedup:{linkedin_job_id}` | 7 days | Deduplication key to prevent re-processing the same job |
| `li_autopilot:worker:task:{task_id}` | 1h | Task status and metadata for tracking |

### Rate Limiting

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `li_autopilot:worker:rate_limit:{user_id}:searches` | 24h | Daily search count per user |
| `li_autopilot:worker:rate_limit:{user_id}:applications` | 24h | Daily application count per user |

### Queue

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `li_autopilot:worker:queue:job_search` | None | List-based queue for job search tasks |
| `li_autopilot:worker:queue:priority` | None | Priority queue for urgent tasks |

### Session Management

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `li_autopilot:worker:session:{user_id}` | 24h | LinkedIn session cookies for user (encrypted) |

## LinkedIn Automation Safety Patterns

### 1. Randomized Delays

All browser actions must include randomized delays to mimic human behavior:

```python
# utils/delays.py
import random
import asyncio

async def human_delay(min_seconds: float = 1.0, max_seconds: float = 3.0):
    """Randomized delay between actions."""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)

async def page_scroll_delay():
    """Delay after scrolling, mimics reading."""
    await human_delay(0.5, 2.0)

async def navigation_delay():
    """Delay after page navigation."""
    await human_delay(2.0, 5.0)

async def search_delay():
    """Delay between search operations."""
    await human_delay(3.0, 8.0)
```

### 2. Per-User Rate Limiting

Each user has configurable daily limits:

```python
# utils/rate_limiter.py
class RateLimiter:
    DAILY_SEARCH_LIMIT = 50
    DAILY_APPLICATION_LIMIT = 20

    async def check_search_limit(self, user_id: str) -> bool:
        key = f"li_autopilot:worker:rate_limit:{user_id}:searches"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 86400)  # 24h
        return count <= self.DAILY_SEARCH_LIMIT
```

### 3. Exponential Backoff on Failure

Retry logic with increasing delays:

```python
# utils/backoff.py
import asyncio

async def with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)  # 1, 2, 4 seconds
            await asyncio.sleep(delay)
```

### 4. Idempotency

Job search tasks must be idempotent:

- Check if task already completed before starting
- Use deduplication keys for jobs
- Store task status in Redis
- Handle duplicate queue messages gracefully

### 5. Session Cookie Authentication

Never store LinkedIn passwords. Use session cookies:

```python
# automation/session_manager.py
class SessionManager:
    async def store_session(self, user_id: str, cookies: dict):
        """Encrypt and store session cookies."""
        encrypted = self._encrypt_cookies(cookies)
        key = f"li_autopilot:worker:session:{user_id}"
        await redis.set(key, encrypted, ex=86400)  # 24h TTL

    async def get_session(self, user_id: str) -> dict:
        """Retrieve and decrypt session cookies."""
        key = f"li_autopilot:worker:session:{user_id}"
        encrypted = await redis.get(key)
        return self._decrypt_cookies(encrypted)
```

## API Endpoints (Phase 2)

### New Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/jobs?search_profile_id={id}` | List jobs for a search profile |
| POST | `/jobs/search` | Trigger a new job search (enqueues task) |
| GET | `/jobs/search/status/{task_id}` | Check job search task status |

### GET /jobs Endpoint

```python
# routers/jobs.py
@router.get("/jobs")
async def list_jobs(
    search_profile_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List jobs for a search profile.

    - Validates user owns the search profile
    - Returns jobs ordered by discovered_at desc
    - Supports filtering by status
    """
    pass
```

### POST /jobs/search Endpoint

```python
@router.post("/jobs/search", status_code=202)
async def trigger_job_search(
    request: JobSearchRequest,
    current_user: User = Depends(get_current_user),
    queue: QueueService = Depends(get_queue_service)
):
    """
    Trigger a job search task.

    - Validates search profile exists and belongs to user
    - Enqueues task to Redis
    - Returns task_id for status tracking
    - Does NOT wait for completion (async)
    """
    task_id = await queue.enqueue_job_search(
        user_id=current_user.id,
        search_profile_id=request.search_profile_id
    )
    return {"task_id": task_id, "status": "queued"}
```

## Structured Logging Requirements

All Worker logs must include:

```json
{
    "timestamp": "2024-01-15T10:30:00Z",
    "level": "INFO",
    "service": "worker",
    "user_id": "uuid-here",
    "action": "job_search",
    "status": "success",
    "jobs_found": 25,
    "new_jobs": 10,
    "duration_ms": 4500
}
```

### Never Log

- LinkedIn credentials
- Raw resumes
- Session cookies (unencrypted)
- LLM tokens

## Docker Configuration (Phase 2)

### docker-compose.yml Updates

```yaml
services:
  api:
    # ... existing config

  worker:
    build:
      context: ./apps/worker
      dockerfile: Dockerfile
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/db
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
```

### Worker Dockerfile

```dockerfile
# apps/worker/Dockerfile
FROM python:3.11-slim

# Install Playwright dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

COPY . .

CMD ["python", "main.py"]
```

## Summary

Phase 2 introduces the Worker service architecture with strict separation from the API:

- **API**: Handles HTTP requests, enqueues tasks, queries job data
- **Worker**: Executes browser automation, scrapes LinkedIn, stores jobs
- **Redis**: Queue for task dispatch, caching for results, rate limiting
- **Postgres**: Persistent job storage with deduplication

All automation follows safety patterns: randomized delays, rate limiting, exponential backoff, and idempotency.