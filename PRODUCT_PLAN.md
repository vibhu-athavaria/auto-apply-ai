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
4. See LinkedIn job listings
5. Generate AI-tailored resume + cover letter
6. Apply via Easy Apply
7. Track application status

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

## Worker Service
- Python-based background worker
- Responsibilities:
  - LinkedIn job search automation
  - Easy Apply automation
  - Resume tailoring (LLM calls)
  - Status updates
  - Cost logging
  - Caching checks
- Must run independently from API

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
- llm_usage_logs
- cost_tracking

## Cache Layer
Redis

Used for:
- Job search result caching (24h TTL)
- LLM response caching
- Deduplication keys
- Rate limiting
- Background queue

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

## PHASE 1 – Core Backend Foundation

Goal: User system + resume upload.

Tasks:

1. Initialize FastAPI project structure
2. Setup Docker:
   - Postgres
   - Redis
3. Implement User model
4. Implement JWT authentication
5. Resume upload endpoint
6. Store resume file locally (MVP)
7. Create JobSearchProfile model
8. Add health check endpoint
9. Implement structured logging
10. Prepare cost logging middleware (empty for now)

Deliverable:
User can register, login, upload resume.

No LinkedIn integration yet.

---

## PHASE 2 – Job Search Engine (Read-Only)

Goal: Fetch and store LinkedIn job listings.

Tasks:

1. Create Worker service
2. Integrate Playwright
3. Implement LinkedIn login using session cookie
4. Automate job search:
   - Keyword
   - Location
5. Parse job listings:
   - Title
   - Company
   - URL
   - Easy Apply flag
6. Store jobs in DB
7. Implement Redis caching:
   - Cache search results (24h TTL)
8. Deduplicate jobs by LinkedIn job ID
9. Create API endpoint:
   GET /jobs?search_profile_id=

Deliverable:
User can search and see LinkedIn jobs in dashboard.

No applying yet.

---

## PHASE 3 – Resume Tailoring Engine

Goal: AI-generated tailored resume + cover letter.

Tasks:

1. Integrate LLM provider
2. Build ResumeTailorService
3. Create deterministic input hash:
   hash(resume + job_description)
4. Check Redis cache before LLM call
5. Store tailored output in DB
6. Log:
   - Prompt tokens
   - Completion tokens
   - Cost
   - User ID
7. Track cumulative cost per user
8. Add endpoint:
   POST /jobs/{id}/tailor

Deliverable:
User can generate tailored resume and cover letter.

Caching must be enforced before every LLM call.

---

## PHASE 4 – Easy Apply Automation

Goal: Apply to jobs via Easy Apply.

Tasks:

1. Implement Easy Apply handler in Worker
2. Detect multi-step forms
3. Fill:
   - Resume
   - Basic information
4. Add per-user rate limiting
5. Add daily application cap
6. Update application status in DB
7. Add retry mechanism with exponential backoff
8. Add randomized human-like delays
9. Log success/failure reason

Deliverable:
System applies to Easy Apply jobs safely.

---

## PHASE 5 – Cost & Safety Controls

Goal: Ensure profitability and system protection.

Tasks:

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

Deliverable:
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
Revenue per user must always exceed
