# Wizard Page Refactoring Implementation Plan

## Executive Summary

This plan addresses three issues identified in the wizard page component:

1. **Large monolithic component** (~850 lines) - Split into smaller components
2. **Incomplete payload** - `remoteOnly`, `experienceLevel`, `jobType` not properly sent to API
3. **SPA navigation issue** - Plain `<a href>` causes full page reload

---

## Issue 1: Split Wizard Page into Smaller Components

### Current State
The wizard page (`apps/web/app/dashboard/wizard/page.tsx`) mixes:
- Resume upload logic (lines 305-377)
- LinkedIn connection logic (lines 379-557)
- Profile form logic (lines 560-731)
- UI layout and step indicator (lines 734-880)

### Proposed File Structure

```
apps/web/
├── components/
│   └── wizard/
│       ├── ResumeStep.tsx       # NEW - Upload dropzone, file validation
│       ├── LinkedInStep.tsx    # NEW - Connection form, skip flow
│       └── ProfileStep.tsx     # NEW - Profile form, summary
├── hooks/
│   └── useLinkedInConnection.ts # NEW - Polling, status management
└── app/
    └── dashboard/
        └── wizard/
            └── page.tsx         # REFACTORED - Uses child components
```

### Component Breakdown

#### ResumeStep.tsx
- Props: `isUploaded`, `filename`, `onUploadComplete`, `onChange`
- Logic: Dropzone, file validation, upload state, error handling

#### LinkedInStep.tsx
- Props: `isConnected`, `isSkipped`, `onConnect`, `onSkip`, `onRetry`
- Logic: Connection form, credentials input, skip warning modal

#### ProfileStep.tsx
- Props: `data`, `onChange`, `resumeStatus`, `linkedinStatus`
- Logic: All form fields, summary card, validation

#### useLinkedInConnection.ts
- Hook that manages polling interval for connection status
- Returns: `status`, `message`, `taskId`, `connect()`, `skip()`

---

## Issue 2: Fix handleCreateProfile Payload

### Current Problem
In `handleCreateProfile` (wizard page lines 237-256):

| Field | Current Behavior |
|-------|------------------|
| `remoteOnly` | **IGNORED** - not sent at all |
| `experienceLevel` | Appended to keywords: `"Python (Senior)"` |
| `jobType` | Appended to keywords: `"Python - Full-time"` |

### API Schema Mismatch
- `test_profiles.py` sends `experience_level` and `job_type`
- But `job_search_profile.py` schema doesn't accept these fields

### Fix Required

#### Step 1: Update API Schema
File: `apps/api/app/schemas/job_search_profile.py`

```python
class JobSearchProfileBase(BaseModel):
    keywords: str
    location: str
    remote_preference: Optional[str] = None  # Already exists, use it!
    experience_level: Optional[str] = None    # ADD
    job_type: Optional[str] = None           # ADD
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
```

#### Step 2: Update API Model
File: `apps/api/app/models/job_search_profile.py`

```python
class JobSearchProfile(Base, TimestampMixin):
    # ... existing fields
    experience_level = Column(String(50), nullable=True)   # ADD
    job_type = Column(String(50), nullable=True)          # ADD
```

#### Step 3: Update TypeScript API
File: `apps/web/lib/api.ts`

```typescript
export const profileApi = {
  create: async (data: {
    keywords: string;
    location: string;
    remote_preference?: string;
    experience_level?: string;  // ADD
    job_type?: string;          // ADD
  }) => {
    const response = await api.post('/profiles/', data);
    return response.data;
  },
};
```

#### Step 4: Update Wizard Page
File: `apps/web/app/dashboard/wizard/page.tsx`

```typescript
// In handleCreateProfile:
await profileApi.create({
  keywords: wizardData.keywords,
  location: wizardData.location,
  remote_preference: wizardData.remoteOnly ? 'remote' : 'onsite',
  experience_level: wizardData.experienceLevel || undefined,
  job_type: wizardData.jobType || undefined,
});
```

---

## Issue 3: Fix SPA Navigation

### Current Problem
File: `apps/web/app/dashboard/page.tsx` (lines 48-54)

```tsx
<a href="/dashboard/wizard" className="...">
```

This causes full page reload, losing client state.

### Fix Required

```tsx
import Link from 'next/link';

// Replace:
<a href="/dashboard/wizard" className="...">

// With:
<Link href="/dashboard/wizard" className="...">
```

This is consistent with:
- `DashboardLayout.tsx` - uses `next/link`
- `login/page.tsx` - uses `next/link`
- `register/page.tsx` - uses `next/link`

---

## Test Updates Required

### 1. Wizard Page Tests
File: `apps/web/__tests__/app/dashboard/wizard/page.test.tsx`

**Current:** Tests monolithic component
**After:** Mock child components

```typescript
// Add mocks for new components
jest.mock('@/components/wizard/ResumeStep', () => ({
  __esModule: true,
  default: ({ isUploaded, onUploadComplete }) => (
    <div data-testid="resume-step">Resume Step</div>
  ),
}));

jest.mock('@/components/wizard/LinkedInStep', () => ({
  __esModule: true,
  default: ({ isConnected, onConnect }) => (
    <div data-testid="linkedin-step">LinkedIn Step</div>
  ),
}));

jest.mock('@/components/wizard/ProfileStep', () => ({
  __esModule: true,
  default: ({ data, onChange }) => (
    <div data-testid="profile-step">Profile Step</div>
  ),
}));

jest.mock('@/hooks/useLinkedInConnection', () => ({
  __esModule: true,
  default: () => ({
    status: 'idle',
    connect: jest.fn(),
    skip: jest.fn(),
  }),
}));
```

### 2. API Profile Tests
File: `apps/api/tests/test_profiles.py`

**Current:** Test sends fields that schema doesn't accept
**After:** Verify fields are properly stored and returned

```python
def test_create_profile_with_filters():
    response = client.post(
        "/profiles/",
        json={
            "keywords": "Python Developer",
            "location": "San Francisco",
            "experience_level": "senior",
            "job_type": "full-time",
            "remote_preference": "remote"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["experience_level"] == "senior"  # Verify it's stored
    assert data["job_type"] == "full-time"        # Verify it's stored
```

---

## Implementation Order

1. **Issue 3 (Quick Win)** - Fix SPA navigation in dashboard
2. **Issue 2 (API)** - Update schema, model, and TypeScript
3. **Issue 1 (Components)** - Create new components and refactor wizard

---

## Files to Modify

| File | Changes |
|------|---------|
| `apps/web/app/dashboard/page.tsx` | Replace `<a>` with `<Link>` |
| `apps/api/app/schemas/job_search_profile.py` | Add experience_level, job_type |
| `apps/api/app/models/job_search_profile.py` | Add experience_level, job_type columns |
| `apps/web/lib/api.ts` | Update profileApi.create interface |
| `apps/web/app/dashboard/wizard/page.tsx` | Refactor to use child components |
| `apps/web/components/wizard/ResumeStep.tsx` | NEW |
| `apps/web/components/wizard/LinkedInStep.tsx` | NEW |
| `apps/web/components/wizard/ProfileStep.tsx` | NEW |
| `apps/web/hooks/useLinkedInConnection.ts` | NEW |
| `apps/web/__tests__/app/dashboard/wizard/page.test.tsx` | Update mocks |
| `apps/api/tests/test_profiles.py` | Fix test expectations |
