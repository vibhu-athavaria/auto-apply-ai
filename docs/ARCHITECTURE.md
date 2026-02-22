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

---

# PHASE 3 - Resume Tailoring Engine

Phase 3 introduces AI-powered resume tailoring with mandatory caching and cost tracking. The system generates tailored resumes and cover letters based on job descriptions using LLM providers.

## Critical Architecture Rules (Non-Negotiable)

Per AGENTS.md, the following rules are mandatory for LLM operations:

1. **LLM calls without caching are FORBIDDEN**
2. **Before ANY LLM call**:
   - Generate deterministic hash: `hash(resume + job_description)`
   - Check Redis cache
   - If cached → return cached result
   - If not cached → call LLM, log tokens, store in Redis
3. **Never log raw resumes or LLM tokens**
4. **Track cumulative cost per user**

## Folder Structure (Updated)

```
apps/
  api/
    app/
      models/
        tailored_resume.py       # NEW: TailoredResume model
        llm_usage_log.py         # NEW: LLMUsageLog model
      schemas/
        tailored_resume.py       # NEW: Tailored resume schemas
        llm_usage.py             # NEW: LLM usage tracking schemas
      routers/
        tailor.py                # NEW: Resume tailoring endpoint
      services/
        resume_tailor_service.py # NEW: Core tailoring logic with caching
        llm_client.py            # NEW: LLM provider client wrapper
        cost_tracker.py          # NEW: Cost tracking service
    ...
  worker/
    # LLM calls happen in Worker, not API
    llm/                         # NEW: LLM integration module
      __init__.py
      openai_client.py           # OpenAI API client
      anthropic_client.py        # Anthropic API client (optional)
      cache.py                   # LLM response caching
    tasks/
      tailor_task.py             # NEW: Background tailoring task
    ...
```

## Database Schema (Phase 3)

### tailored_resumes Table

```sql
CREATE TABLE tailored_resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    job_id UUID NOT NULL REFERENCES jobs(id),
    original_resume_id UUID NOT NULL REFERENCES resumes(id),

    -- Content hash for cache key
    content_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash of resume + job_description

    -- Tailored outputs
    tailored_resume_text TEXT NOT NULL,
    cover_letter_text TEXT,

    -- Metadata
    model_used VARCHAR(100) NOT NULL,        -- e.g., 'gpt-4', 'claude-3-opus'
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    estimated_cost_usd DECIMAL(10, 6) NOT NULL,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    UNIQUE(job_id, original_resume_id),      -- One tailored resume per job/resume pair
    INDEX idx_tailored_resumes_user_id (user_id),
    INDEX idx_tailored_resumes_job_id (job_id),
    INDEX idx_tailored_resumes_content_hash (content_hash)
);
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | Reference to the user who owns this tailored resume |
| job_id | UUID | Reference to the job this resume is tailored for |
| original_resume_id | UUID | Reference to the source resume |
| content_hash | VARCHAR(64) | SHA-256 hash of `resume_content + job_description`. Used as Redis cache key component. |
| tailored_resume_text | TEXT | The AI-generated tailored resume content |
| cover_letter_text | TEXT | Optional AI-generated cover letter |
| model_used | VARCHAR(100) | LLM model identifier for reproducibility and cost tracking |
| prompt_tokens | INTEGER | Number of tokens in the prompt |
| completion_tokens | INTEGER | Number of tokens in the completion |
| estimated_cost_usd | DECIMAL(10, 6) | Calculated cost based on token usage |

### llm_usage_logs Table

```sql
CREATE TABLE llm_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),

    -- Request identification
    request_type VARCHAR(50) NOT NULL,       -- 'resume_tailor', 'cover_letter', etc.
    content_hash VARCHAR(64) NOT NULL,       -- For cache hit tracking

    -- Token usage
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,

    -- Cost tracking
    model_used VARCHAR(100) NOT NULL,
    cost_per_prompt_token DECIMAL(10, 8) NOT NULL,
    cost_per_completion_token DECIMAL(10, 8) NOT NULL,
    estimated_cost_usd DECIMAL(10, 6) NOT NULL,

    -- Cache status
    cache_hit BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),

    -- Indexes
    INDEX idx_llm_usage_logs_user_id (user_id),
    INDEX idx_llm_usage_logs_created_at (created_at),
    INDEX idx_llm_usage_logs_request_type (request_type),
    INDEX idx_llm_usage_logs_cache_hit (cache_hit)
);
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | Reference to the user who initiated the LLM call |
| request_type | VARCHAR(50) | Type of LLM request: 'resume_tailor', 'cover_letter', etc. |
| content_hash | VARCHAR(64) | Hash of input content for deduplication tracking |
| prompt_tokens | INTEGER | Tokens used in the prompt |
| completion_tokens | INTEGER | Tokens generated in the completion |
| total_tokens | INTEGER | Sum of prompt and completion tokens |
| model_used | VARCHAR(100) | LLM model identifier |
| cost_per_prompt_token | DECIMAL(10, 8) | Cost per input token at time of request |
| cost_per_completion_token | DECIMAL(10, 8) | Cost per output token at time of request |
| estimated_cost_usd | DECIMAL(10, 6) | Total calculated cost for this request |
| cache_hit | BOOLEAN | Whether this was served from cache (cost = $0) |

## LLM Caching Flow

```mermaid
flowchart TD
    A[POST /jobs/id/tailor] --> B[Get resume content]
    B --> C[Get job description]
    C --> D[Generate content hash]
    D --> E{Check Redis cache}

    E -->|Cache Hit| F[Return cached result]
    F --> G[Log cache hit to llm_usage_logs]
    G --> H[Return tailored resume]

    E -->|Cache Miss| I[Call LLM Provider]
    I --> J[Log prompt tokens]
    J --> K[Log completion tokens]
    K --> L[Calculate estimated cost]
    L --> M[Store result in Redis]
    M --> N[Store in tailored_resumes table]
    N --> O[Log to llm_usage_logs]
    O --> P[Update user cost tracking]
    P --> Q[Return tailored resume]

    subgraph Cost Tracking
        L
        O
        P
    end

    subgraph Caching Layer
        E
        M
    end
```

## Redis Key Naming Conventions (Phase 3)

All keys follow the format: `li_autopilot:{service}:{entity}:{identifier}`

### LLM Caching

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `li_autopilot:api:llm_cache:{content_hash}` | 30 days | Cached LLM response for resume tailoring. Key is SHA-256 hash of normalized resume + job description. |
| `li_autopilot:api:llm_cache:meta:{user_id}` | None | Metadata about user's cached responses for quick lookup. |

### Cost Tracking

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `li_autopilot:api:cost:{user_id}:daily:{date}` | 7 days | Daily cost accumulator per user. |
| `li_autopilot:api:cost:{user_id}:total` | None | Cumulative cost per user (persistent). |
| `li_autopilot:api:cost:{user_id}:monthly:{month}` | 13 months | Monthly cost summary per user. |

### Rate Limiting (LLM)

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `li_autopilot:api:rate_limit:{user_id}:llm_calls` | 24h | Daily LLM call count per user. |

## Cost Tracking Architecture

### Cost Calculation

```python
# services/cost_tracker.py
from decimal import Decimal

# Cost per 1K tokens (example rates, should be configurable)
MODEL_COSTS = {
    "gpt-4": {
        "prompt": Decimal("0.03"),      # $0.03 per 1K prompt tokens
        "completion": Decimal("0.06"),  # $0.06 per 1K completion tokens
    },
    "gpt-3.5-turbo": {
        "prompt": Decimal("0.0015"),
        "completion": Decimal("0.002"),
    },
    "claude-3-opus": {
        "prompt": Decimal("0.015"),
        "completion": Decimal("0.075"),
    },
}

class CostTracker:
    async def calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> Decimal:
        rates = MODEL_COSTS.get(model)
        if not rates:
            raise ValueError(f"Unknown model: {model}")

        prompt_cost = (Decimal(prompt_tokens) / 1000) * rates["prompt"]
        completion_cost = (Decimal(completion_tokens) / 1000) * rates["completion"]

        return prompt_cost + completion_cost

    async def log_usage(
        self,
        user_id: str,
        request_type: str,
        content_hash: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        cache_hit: bool = False
    ) -> None:
        cost = await self.calculate_cost(model, prompt_tokens, completion_tokens)

        # Log to database
        await self.db.execute(
            """
            INSERT INTO llm_usage_logs (
                user_id, request_type, content_hash,
                prompt_tokens, completion_tokens, total_tokens,
                model_used, cost_per_prompt_token, cost_per_completion_token,
                estimated_cost_usd, cache_hit
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            user_id, request_type, content_hash,
            prompt_tokens, completion_tokens, prompt_tokens + completion_tokens,
            model, MODEL_COSTS[model]["prompt"], MODEL_COSTS[model]["completion"],
            cost, cache_hit
        )

        # Update Redis counters (only for actual costs, not cache hits)
        if not cache_hit:
            await self.redis.incrbyfloat(
                f"li_autopilot:api:cost:{user_id}:total",
                float(cost)
            )
            await self.redis.incrbyfloat(
                f"li_autopilot:api:cost:{user_id}:daily:{date.today()}",
                float(cost)
            )
```

### Content Hash Generation

```python
# services/resume_tailor_service.py
import hashlib

def generate_content_hash(resume_content: str, job_description: str) -> str:
    """
    Generate deterministic hash for cache key.

    Normalizes inputs to ensure consistent hashing:
    - Strip whitespace
    - Lowercase
    - Remove extra spaces
    """
    normalized_resume = " ".join(resume_content.lower().split())
    normalized_job = " ".join(job_description.lower().split())

    combined = f"{normalized_resume}|{normalized_job}"
    return hashlib.sha256(combined.encode()).hexdigest()
```

## API Endpoints (Phase 3)

### New Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jobs/{id}/tailor` | Generate tailored resume for a job |
| GET | `/jobs/{id}/tailored-resume` | Get existing tailored resume for a job |
| GET | `/users/me/costs` | Get cost summary for current user |

### POST /jobs/{id}/tailor Endpoint

```python
# routers/tailor.py
from fastapi import APIRouter, Depends, HTTPException
from app.services.resume_tailor_service import ResumeTailorService
from app.schemas.tailored_resume import TailorRequest, TailorResponse

router = APIRouter(prefix="/jobs", tags=["tailoring"])

@router.post("/{job_id}/tailor", response_model=TailorResponse)
async def tailor_resume(
    job_id: str,
    request: TailorRequest,
    current_user: User = Depends(get_current_user),
    tailor_service: ResumeTailorService = Depends(get_tailor_service)
):
    """
    Generate a tailored resume for a specific job.

    Flow:
    1. Validate job exists and belongs to user
    2. Validate resume exists and belongs to user
    3. Generate content hash
    4. Check Redis cache
    5. If cached: return cached result, log cache hit
    6. If not cached: call LLM, store result, log usage
    7. Return tailored resume

    Returns:
        TailorResponse with tailored_resume_text, cover_letter_text,
        and metadata (cache_hit, tokens_used, cost)
    """
    result = await tailor_service.tailor_resume(
        user_id=current_user.id,
        job_id=job_id,
        resume_id=request.resume_id,
        generate_cover_letter=request.generate_cover_letter
    )
    return result
```

### Request/Response Schemas

```python
# schemas/tailored_resume.py
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal

class TailorRequest(BaseModel):
    resume_id: str = Field(..., description="UUID of the resume to tailor")
    generate_cover_letter: bool = Field(
        default=True,
        description="Whether to also generate a cover letter"
    )

class TailorResponse(BaseModel):
    id: str = Field(..., description="UUID of the tailored resume")
    job_id: str
    original_resume_id: str
    tailored_resume_text: str
    cover_letter_text: Optional[str] = None

    # Metadata
    cache_hit: bool = Field(..., description="Whether result was from cache")
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: Decimal

class CostSummary(BaseModel):
    total_cost_usd: Decimal
    total_tokens: int
    total_requests: int
    cache_hit_rate: float
    daily_cost_usd: Decimal
    monthly_cost_usd: Decimal
```

## ResumeTailorService Implementation

```python
# services/resume_tailor_service.py
import hashlib
from typing import Optional
from decimal import Decimal

class ResumeTailorService:
    CACHE_TTL = 30 * 24 * 60 * 60  # 30 days

    def __init__(
        self,
        db: AsyncSession,
        redis: Redis,
        llm_client: LLMClient,
        cost_tracker: CostTracker
    ):
        self.db = db
        self.redis = redis
        self.llm_client = llm_client
        self.cost_tracker = cost_tracker

    async def tailor_resume(
        self,
        user_id: str,
        job_id: str,
        resume_id: str,
        generate_cover_letter: bool = True
    ) -> TailorResponse:
        """
        Tailor a resume for a specific job with mandatory caching.

        MANDATORY FLOW (per AGENTS.md):
        1. Generate deterministic hash
        2. Check Redis cache
        3. If cached → return cached result
        4. If not cached:
           - Call LLM
           - Log prompt tokens
           - Log completion tokens
           - Log estimated cost
           - Store result in Redis
           - Update per-user cost tracking
        """
        # 1. Get resume and job content
        resume = await self._get_resume(resume_id, user_id)
        job = await self._get_job(job_id, user_id)

        resume_content = await self._read_resume_file(resume.file_path)
        job_description = job.description or ""

        # 2. Generate deterministic hash
        content_hash = self._generate_content_hash(resume_content, job_description)

        # 3. Check Redis cache (MANDATORY)
        cache_key = f"li_autopilot:api:llm_cache:{content_hash}"
        cached_result = await self.redis.get(cache_key)

        if cached_result:
            # Cache hit - return without LLM call
            await self.cost_tracker.log_usage(
                user_id=user_id,
                request_type="resume_tailor",
                content_hash=content_hash,
                prompt_tokens=0,
                completion_tokens=0,
                model="cached",
                cache_hit=True
            )
            return self._parse_cached_result(cached_result, content_hash)

        # 4. Cache miss - call LLM
        llm_response = await self.llm_client.tailor_resume(
            resume_content=resume_content,
            job_description=job_description,
            job_title=job.title,
            company=job.company,
            generate_cover_letter=generate_cover_letter
        )

        # 5. Log token usage (MANDATORY)
        await self.cost_tracker.log_usage(
            user_id=user_id,
            request_type="resume_tailor",
            content_hash=content_hash,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            model=llm_response.model,
            cache_hit=False
        )

        # 6. Store result in Redis (MANDATORY)
        result_data = {
            "tailored_resume_text": llm_response.tailored_resume,
            "cover_letter_text": llm_response.cover_letter,
            "model_used": llm_response.model,
            "prompt_tokens": llm_response.prompt_tokens,
            "completion_tokens": llm_response.completion_tokens,
            "estimated_cost_usd": str(llm_response.estimated_cost)
        }
        await self.redis.setex(
            cache_key,
            self.CACHE_TTL,
            json.dumps(result_data)
        )

        # 7. Store in database
        tailored_resume = await self._store_tailored_resume(
            user_id=user_id,
            job_id=job_id,
            original_resume_id=resume_id,
            content_hash=content_hash,
            tailored_resume_text=llm_response.tailored_resume,
            cover_letter_text=llm_response.cover_letter,
            model_used=llm_response.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            estimated_cost=llm_response.estimated_cost
        )

        return TailorResponse(
            id=tailored_resume.id,
            job_id=job_id,
            original_resume_id=resume_id,
            tailored_resume_text=llm_response.tailored_resume,
            cover_letter_text=llm_response.cover_letter,
            cache_hit=False,
            model_used=llm_response.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            estimated_cost_usd=llm_response.estimated_cost
        )

    def _generate_content_hash(self, resume_content: str, job_description: str) -> str:
        """Generate deterministic SHA-256 hash for cache key."""
        normalized_resume = " ".join(resume_content.lower().split())
        normalized_job = " ".join(job_description.lower().split())
        combined = f"{normalized_resume}|{normalized_job}"
        return hashlib.sha256(combined.encode()).hexdigest()
```

## Structured Logging Requirements (Phase 3)

All LLM-related logs must include:

```json
{
    "timestamp": "2024-01-15T10:30:00Z",
    "level": "INFO",
    "service": "api",
    "user_id": "uuid-here",
    "action": "llm_call",
    "status": "success",
    "request_type": "resume_tailor",
    "model": "gpt-4",
    "prompt_tokens": 1500,
    "completion_tokens": 800,
    "estimated_cost_usd": 0.093,
    "cache_hit": false,
    "duration_ms": 3500
}
```

### Never Log

- LinkedIn credentials
- Raw resumes
- LLM tokens (actual token content)
- Session cookies (unencrypted)

## Summary

Phase 3 introduces AI-powered resume tailoring with strict cost control:

- **Mandatory Caching**: Every LLM call must check Redis cache first
- **Cost Tracking**: All token usage logged with per-user accumulation
- **Deterministic Hashing**: `hash(resume + job_description)` for cache keys
- **Database Storage**: `tailored_resumes` and `llm_usage_logs` tables
- **Redis Keys**: Follow `li_autopilot:{service}:{entity}:{identifier}` format

Key architectural decisions:
1. LLM calls happen in Worker service (not API) for long-running operations
2. Cache TTL is 30 days for tailored resumes
3. Cost is tracked both in database (persistent) and Redis (fast access)
4. Content hash ensures identical inputs never incur duplicate LLM costs