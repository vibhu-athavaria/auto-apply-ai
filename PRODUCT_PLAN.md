# LinkedIn Autopilot – PRODUCT_PLAN.md

## Overview

LinkedIn Autopilot is a bootstrapped SaaS product that automates LinkedIn job discovery and Easy Apply using AI-powered resume tailoring.

This document defines:
- System architecture
- Engineering principles
- Phased development plan
- Cost control strategy
- Scaling approach

This project must be built incrementally and with strict cost-awareness.

---

# 1. Core Product Vision (MVP)

The user should be able to:

1. Register and log in
2. Upload their resume
3. Define job search preferences (keywords, location)
4. Connect their LinkedIn account (email + password)
5. See LinkedIn job listings
6. Generate AI-tailored resume + cover letter
7. Apply via Easy Apply
8. Track application status

We are building LinkedIn-only in Phase 1.

---

# 2. Technical Architecture

## Backend API
- Framework: FastAPI
- Language: Python 3.11+
- Responsibilities:
  - Authentication (JWT)
  - Resume storage
  - Job storage
  - User preferences
  - Application tracking
  - Cost tracking
  - Queue job creation

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register new user |
| `/auth/login` | POST | Login and get JWT token |
| `/resumes` | GET, POST | List and upload resumes |
| `/resumes/{id}` | GET, DELETE | Get or delete specific resume |
| `/profiles` | GET, POST | Job search profiles |
| `/profiles/{id}` | GET, PUT, DELETE | Manage search profile |
| `/jobs` | GET | List jobs for a search profile |
| `/jobs/search` | POST | Trigger job search |
| `/jobs/{id}/tailor` | POST | Generate tailored resume |
| `/jobs/{id}/tailored` | GET | Get tailored resume |
| `/jobs/{id}/apply` | POST | Apply via Easy Apply |
| `/linkedin/connect` | POST | Connect LinkedIn (email + password) |
| `/linkedin/connect/status/{task_id}` | GET | Poll connection status |
| `/linkedin/session` | GET | Get session status |
| `/linkedin/session/validate` | POST | Validate LinkedIn session |
| `/applications` | GET | List applications |
| `/applications/task/{task_id}` | GET | Check application task status |
| `/users/me/costs` | GET | Get LLM cost summary |

## Worker Service
- Python-based background worker
- Responsibilities:
  - LinkedIn authentication (Playwright)
  - LinkedIn job search automation
  - Easy Apply automation
  - Resume tailoring (LLM calls)
  - Status updates
  - Cost logging
  - Caching checks
- Must run independently from API

### Worker Task Queues

| Queue | Purpose |
|-------|---------|
| `li_autopilot:tasks:linkedin_auth` | LinkedIn login via email + password |
| `li_autopilot:tasks:job_search` | Job search automation |
| `li_autopilot:worker:queue:applications` | Easy Apply automation |

## Browser Automation
- Playwright
- Human-like delays
- Rate-limited actions
- Retry with backoff

## Database
Postgres

Core Tables:
- users
- resumes
- job_search_profiles
- jobs
- applications
- tailored_resumes
- linkedin_sessions
- llm_usage_logs

## Cache Layer
Redis

Used for:
- Job search result caching (24h TTL)
- LLM response caching
- Deduplication keys
- Rate limiting
- Background queue
- Task status tracking

### Redis Key Format

All keys follow: `li_autopilot:{service}:{entity}:{identifier}`

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `li_autopilot:api:auth_task:{task_id}` | 5min | Auth task status |
| `li_autopilot:worker:session:{user_id}` | 24h | LinkedIn session for worker |
| `li_autopilot:cache:llm:{hash}` | 7 days | LLM response cache |

## Frontend
- Framework: Next.js 14
- Language: TypeScript
- Styling: Tailwind CSS

### Pages

| Route | Description |
|-------|-------------|
| `/login` | Login page |
| `/register` | Registration page |
| `/dashboard` | Dashboard overview |
| `/dashboard/resumes` | Resume management |
| `/dashboard/profiles` | Job search profiles |
| `/dashboard/jobs` | Job listings and actions |
| `/dashboard/linkedin` | LinkedIn connection |

---

# 3. Engineering Principles (Mandatory)

1. No LinkedIn request without rate limiting
2. No LLM call without cache check
3. All LLM calls must log token usage
4. All background jobs must be idempotent
5. All failures must be logged with structured logs
6. DB queries must use indexed columns
7. Worker must be restart-safe
8. No blocking I/O in async endpoints
9. Strict separation of API and Worker responsibilities

Cost and stability take priority over speed of feature release.

---

# 4. Phased Implementation Plan

---

## PHASE 1 – Core Backend Foundation ✅ COMPLETE

Goal: User system + resume upload.

### Completed Tasks:

1. ✅ Initialize FastAPI project structure
2. ✅ Setup Docker:
   - Postgres
   - Redis
3. ✅ Implement User model
4. ✅ Implement JWT authentication
5. ✅ Resume upload endpoint
6. ✅ Store resume file locally (MVP)
7. ✅ Create JobSearchProfile model
8. ✅ Add health check endpoint
9. ✅ Implement structured logging
10. ✅ Prepare cost logging middleware

### Deliverable:
User can register, login, upload resume.

---

## PHASE 2 – Job Search Engine ✅ COMPLETE

Goal: Fetch and store LinkedIn job listings.

### Completed Tasks:

1. ✅ Create Worker service
2. ✅ Integrate Playwright
3. ✅ Implement LinkedIn login:
   - Session cookie method
   - Email + password method (Playwright automation)
4. ✅ Automate job search:
   - Keyword
   - Location
5. ✅ Parse job listings:
   - Title
   - Company
   - URL
   - Easy Apply flag
6. ✅ Store jobs in DB
7. ✅ Implement Redis caching:
   - Cache search results (24h TTL)
8. ✅ Deduplicate jobs by LinkedIn job ID
9. ✅ Create API endpoint:
   - GET /jobs?search_profile_id=
10. ✅ Implement per-user LinkedIn session management

### Deliverable:
User can connect LinkedIn, search and see jobs in dashboard.

---

## PHASE 3 – Resume Tailoring Engine ✅ COMPLETE

Goal: AI-generated tailored resume + cover letter.

### Completed Tasks:

1. ✅ Integrate LLM provider (OpenAI)
2. ✅ Build ResumeTailorService
3. ✅ Create deterministic input hash:
   - hash(resume + job_description)
4. ✅ Check Redis cache before LLM call
5. ✅ Store tailored output in DB
6. ✅ Log:
   - Prompt tokens
   - Completion tokens
   - Cost
   - User ID
7. ✅ Track cumulative cost per user
8. ✅ Add endpoints:
   - POST /jobs/{id}/tailor
   - GET /jobs/{id}/tailored
   - GET /users/me/costs

### Deliverable:
User can generate tailored resume and cover letter.

Caching is enforced before every LLM call.

---

## PHASE 4 – Easy Apply Automation ✅ COMPLETE

Goal: Apply to jobs via Easy Apply.

### Completed Tasks:

1. ✅ Implement Easy Apply handler in Worker
2. ✅ Detect multi-step forms
3. ✅ Fill:
   - Resume
   - Basic information
4. ✅ Add per-user rate limiting
5. ✅ Add daily application cap
6. ✅ Update application status in DB
7. ✅ Add retry mechanism with exponential backoff
8. ✅ Add randomized human-like delays
9. ✅ Log success/failure reason
10. ✅ Application queue with status tracking

### Deliverable:
System applies to Easy Apply jobs safely.

---

## PHASE 5 – Cost & Safety Controls

Goal: Ensure profitability and system protection.

### Tasks:

1. Add per-user daily limits:
   - Searches
   - LLM calls
   - Applications
2. Build admin metrics endpoints:
   - Total LLM cost
   - Cost per user
   - Applications per day
3. Add queue monitoring
4. Implement circuit breaker:
   - Stop automation if failure rate spikes
5. Add system-wide rate throttle

### Deliverable:
System becomes cost-aware and stable under load.

---

# 5. Cost Control Strategy

From Day 1:

- Cache all job searches
- Cache all LLM outputs
- Deduplicate jobs globally
- Track token usage per call
- Track cost per user
- Enforce daily limits
- Log infra-heavy operations

Goal:
Revenue per user must always exceed infrastructure + LLM costs.

---

# 6. Security Considerations

## LinkedIn Credentials
- Passwords are NEVER stored
- Passwords are used once during Playwright login, then discarded
- Only the resulting `li_at` session cookie is persisted (encrypted)

## Session Cookie Storage
- Encrypted in PostgreSQL using Fernet (AES-128)
- Plaintext in Redis for worker (24h TTL)
- Per-user session isolation

## API Security
- JWT tokens with expiration
- All endpoints require authentication
- Input validation via Pydantic
- File upload validation (type + size)

---

# 7. Error Handling Philosophy

Per AGENTS.md:

- Fail fast, fail loudly
- No silent error swallowing
- User-friendly messages for frontend
- Detailed structured logs for debugging

### Task Status Messages

User-facing progress messages:

**LinkedIn Connection:**
- "Connecting to LinkedIn..."
- "Saving your session..."
- "LinkedIn connected successfully"
- "Invalid email or password"
- "Could not connect to LinkedIn"

**Job Search (Async):**
- "Connecting to LinkedIn..."
- "Searching for '{keywords}' jobs in {location}..."
- "Found X jobs, saving to your dashboard..."
- "Found X jobs, Y new"

### Async Flow

All automation tasks are processed asynchronously:

1. **User triggers action** → API creates task in Redis queue
2. **API returns task_id immediately** → User sees progress indicator
3. **Worker picks up task** → Processes in background
4. **Frontend polls status** → Shows progress messages
5. **Task completes** → User sees result

This ensures the API never blocks and users get real-time feedback.
