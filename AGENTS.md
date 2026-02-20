# AGENTS.md
# LinkedIn Autopilot – Engineering & Review Contract

This document defines:

1. System engineering constraints (ALWAYS ACTIVE)
2. AI review contract behavior (ONLY when explicitly invoked)

These rules are mandatory.

---------------------------------------------------------------------

# PART 1 — SYSTEM ENGINEERING CONSTRAINTS (Always Active)

These rules apply to ALL development work, even outside review mode.

---------------------------------------------------------------------

## 1. System Architecture (Non-Negotiable)

The system consists of:

- FastAPI Backend (API only)
- Worker Service (automation + LLM)
- Postgres (persistent storage)
- Redis (cache + queue)

### Hard Rules

1. API must NEVER execute browser automation.
2. API must NEVER call Playwright.
3. Worker must NOT expose HTTP endpoints.
4. API enqueues tasks; Worker executes them.
5. No long-running tasks inside API request lifecycle.

Strict separation is mandatory.

---------------------------------------------------------------------

## 2. Cost Control (Bootstrapped Discipline)

This is a bootstrapped SaaS.
Cost leaks are unacceptable.

### 2.1 LLM Rules (Mandatory)

Before ANY LLM call:

1. Generate deterministic hash:
   hash(resume + job_description)
2. Check Redis cache.
3. If cached → return cached result.
4. If not cached:
   - Call LLM
   - Log prompt tokens
   - Log completion tokens
   - Log estimated cost
   - Store result in Redis
   - Update per-user cost tracking

LLM calls without caching are forbidden.

---------------------------------------------------------------------

## 3. LinkedIn Automation Safety

Automation must:

- Use randomized delays
- Respect per-user rate limits
- Enforce daily caps
- Use exponential backoff on failure
- Be idempotent
- Avoid duplicate applications

Applications must be unique:
(user_id, job_id)

No parallel browser flooding.
No aggressive scraping patterns.

Detection risk minimization is mandatory.

---------------------------------------------------------------------

## 4. Redis Usage (Required)

Redis must be used for:

- Job search caching (24h TTL)
- LLM result caching
- Deduplication keys
- Rate limiting
- Background job queue

Key format:

li_autopilot:{service}:{entity}:{identifier}

No arbitrary key names allowed.

---------------------------------------------------------------------

## 5. Database Rules

- All filter columns must be indexed.
- No SELECT * in production.
- All schema changes must use migrations.
- Jobs deduplicated by LinkedIn job ID.
- Applications must enforce unique constraint.

---------------------------------------------------------------------

## 6. Async & Performance

- No blocking I/O in async endpoints.
- All DB access must use async drivers.
- Browser automation runs ONLY in Worker.
- Heavy computation must not block API.

---------------------------------------------------------------------

## 7. Logging & Observability

All logs must be structured.

Each log must include:
- timestamp
- level
- service (api/worker)
- user_id (if applicable)
- action
- status

Never log:
- LinkedIn credentials
- Raw resumes
- Tokens

System must track:
- LLM token usage per user
- Cost per user
- Application count
- Worker failure rate
- Queue size

---------------------------------------------------------------------

## 8. Security

- Never store LinkedIn passwords.
- JWT must expire.
- Validate all input using Pydantic.
- Validate file uploads (type + size).
- No sensitive data in logs.

---------------------------------------------------------------------

## 9. Implementation Order

Development must follow PRODUCT_PLAN.md phases sequentially.

Do NOT implement future phases prematurely.

---------------------------------------------------------------------

# PART 2 — AI ENGINEERING REVIEW CONTRACT
(Activated ONLY when explicitly invoked)

This contract applies ONLY when the user says:

- "Full Engineering Review"
- "Review Mode"
- Or similar explicit instruction

For normal development, default behavior applies.

---------------------------------------------------------------------

# 1. Engineering Philosophy (Non-Negotiable)

## 1.1 DRY
- Identify duplication aggressively.
- Consolidate unless it increases coupling.

## 1.2 Testing
- Prefer strong, explicit assertions.
- Identify missing edge cases and failure modes.

## 1.3 Engineering Balance
- Avoid under-engineering.
- Avoid premature abstraction.
- Aim for “engineered enough.”

## 1.4 Explicit > Clever
- Prefer clarity over terseness.
- Avoid magic and hidden behavior.

## 1.5 Edge Cases
- Identify missing validation.
- Identify boundary conditions.
- Identify unhandled failure paths.

---------------------------------------------------------------------

# 2. Review Structure (Strict Order)

The review must be conducted in this order:

1. Architectural Review
2. Code Quality Review
3. Test Review
4. Performance Review

The agent MUST NOT skip sections.

---------------------------------------------------------------------

# 3. Review Modes (User Must Choose)

Before beginning review, the agent MUST ask:

Option 1 — BIG CHANGE
- Work section by section
- Max 4 issues per section
- Pause after each section

Option 2 — SMALL CHANGE
- One issue at a time
- Fully interactive
- Pause after each issue

The agent MUST wait for the user's selection.

---------------------------------------------------------------------

# 4. Issue Reporting Format (Strict)

For EVERY issue:

## Issue X: <Concise Title>

### Problem
- Concrete description
- Reference file names and line numbers when available

### Options

A. Recommended Option
- Implementation effort
- Risk level
- Impact
- Maintenance burden

B. Alternative Option
- Same breakdown

C. Do Nothing
- Analyze consequences explicitly

### Recommendation
- Clear opinion
- Justified using Engineering Philosophy

### AskUserQuestion
End with:

"Regarding Issue X, do you want Option A (recommended) or Option B?"

---------------------------------------------------------------------

# 5. Section Evaluation Criteria

## 5.1 Architectural Review
Evaluate:
- Boundaries (API vs Worker)
- Coupling
- Data flow
- Scaling characteristics
- Single points of failure
- Cost amplification risks
- Caching violations
- Security boundaries

## 5.2 Code Quality Review
Evaluate:
- DRY violations
- Error handling gaps
- Edge case handling
- Over/under-engineering
- Hidden cost multipliers

## 5.3 Test Review
Evaluate:
- Coverage gaps
- Assertion strength
- Untested failure modes
- Missing LLM caching tests
- Missing idempotency tests

## 5.4 Performance Review
Evaluate:
- N+1 queries
- Blocking async calls
- Missing Redis usage
- Missing indexes
- High-cost code paths

---------------------------------------------------------------------

# 6. Interaction Constraints

- Do NOT assume scope priorities.
- Do NOT batch decisions.
- Always pause after each section.
- Never skip structured output.

---------------------------------------------------------------------

# 7. Tone

- Direct
- Structured
- Opinionated but justified
- No vague generalities
- No speculative abstraction
