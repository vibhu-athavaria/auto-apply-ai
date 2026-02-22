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

- Job search result caching
- LLM result caching
- Deduplication keys
- Rate limiting
- Background job queue

TTL values for each key type are defined in PRODUCT_PLAN.md.

Key format:

li_autopilot:{service}:{entity}:{identifier}

No arbitrary key names allowed.
Every new Redis key must follow this format without exception.

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

## 9. Fail Fast Philosophy (Non-Negotiable)

Over-protective, defensive programming is forbidden.
The system must fail loudly, immediately, and at the exact point of failure.

### Core Principle

If a required condition is not met — raise an exception.
Do NOT silently handle it, substitute a default, or let execution continue.

A function that requires a value must receive that value.
If it does not, it must raise immediately — not guess, not skip, not log-and-continue.

A crash with a clear error message is always preferable to corrupted or silent behaviour.

---------------------------------------------------------------------

### Hard Rules

1. Required function arguments must be enforced at the call site.
   If a DB query requires user_id or job_id, the caller must pass it.
   The function must NOT check for None and silently return early.

   FORBIDDEN — hides the real bug:

   def get_application(user_id: UUID | None):
       if not user_id:
           return None

   REQUIRED — fails at the right place:

   def get_application(user_id: UUID):
       # user_id is guaranteed non-null by type contract
       ...

2. No silent fallbacks for missing required data.
   If a required DB record does not exist, raise 404 or a domain exception.
   Do NOT return an empty object, None, or a default placeholder.

3. No swallowed exceptions.

   FORBIDDEN:

   try:
       result = some_operation()
   except Exception:
       pass

   REQUIRED — catch only what you handle, re-raise everything else:

   try:
       result = some_operation()
   except SpecificException as e:
       logger.error("specific failure", error=str(e))
       raise

4. No default substitution for invalid state.
   If the system enters an unexpected state (unknown job status,
   missing Redis dedup key, invalid automation action), raise immediately.
   Do NOT attempt to recover silently.

5. Pydantic validation must be strict.
   All required fields are non-optional in schemas.
   Do NOT use Optional for fields that are functionally required.
   Validation failure must surface as 422 immediately — not be caught and masked.

6. Type hints are contracts, not suggestions.
   If a function is typed to receive UUID, it must receive UUID.
   Functions must not internally guard against None or str
   unless the type hint explicitly declares it.

---------------------------------------------------------------------

### Where Defensive Handling IS Acceptable

The only legitimate cases for defensive handling in this system:

- LinkedIn automation (Playwright, scraping)
  — external system, unpredictable failures. Catch, log, use exponential backoff, retry.
- LLM API calls
  — external dependency. Catch, log, check cache, retry. Fail task after max retries.
- Celery task retries
  — transient failures are expected. max_retries is intentional, not defensive.
- Redis cache miss with DB fallback
  — explicitly defined in the architecture. Acceptable and documented.

Everything else: fail fast, fail loudly.

---------------------------------------------------------------------
## 10. Implementation Order

Development must follow PRODUCT_PLAN.md phases sequentially.
The phase sequence, branch names, and acceptance criteria are defined in PRODUCT_PLAN.md.

Do NOT implement future phases prematurely.
Do NOT begin a new phase until the current phase is fully closed per the Git Workflow rules below.

---------------------------------------------------------------------


## 11. Git Workflow (Non-Negotiable)

Every unit of work is developed on its own dedicated branch.
Work is never done directly on main.

---------------------------------------------------------------------

### 11.1 Branch Convention

Create branches from main before writing any code:

git checkout main
git pull origin main
git checkout -b feature/{short-description}

Branch names must be lowercase, hyphenated, and descriptive.
One branch per logical unit of work. No combined branches.

---------------------------------------------------------------------

### 11.2 Work Completion Requirements

A branch is NOT ready to close until ALL of the following are true:

1. All acceptance criteria met — as defined in PRODUCT_PLAN.md for the current phase.

2. Test coverage is 90% or above — enforced by the test runner, not self-assessed.

   pytest --cov=app --cov-report=term-missing --cov-fail-under=90

   Coverage below 90% blocks closure.
   Write missing tests before proceeding.

3. Code is clean and committed:
   - No uncommitted changes (git status must be clean)
   - No debug code or commented-out blocks in production paths
   - No undocumented environment variables
   - All migrations included in the commit

   Commit format (conventional commits):

   feat(scope):  new functionality
   fix(scope):   bug fix
   chore(scope): config, migration, tooling

4. Branch is pushed to origin and confirmed:

   git push origin feature/{short-description}

   Confirm the push is acknowledged by origin with no errors.

---------------------------------------------------------------------

### 11.3 Commit Hygiene

- One logical unit of work per commit where possible.
- Do not commit broken or untested code at any point.
- Migration files must be committed alongside the model changes they support.
- Do not bundle unrelated changes into one commit.

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
- Aim for "engineered enough."

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