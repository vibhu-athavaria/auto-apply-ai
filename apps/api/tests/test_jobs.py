"""Tests for Jobs API endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.job_search_profile import JobSearchProfile
from app.models.user import User


@pytest.mark.asyncio
async def test_list_jobs_unauthorized(client: AsyncClient):
    """Test listing jobs without authentication."""
    response = await client.get("/jobs/?search_profile_id=test-id")
    # HTTPBearer returns 403 Forbidden when no credentials are provided
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_jobs_authorized(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test listing jobs with authentication."""
    # Create a search profile first
    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="Software Engineer",
        location="San Francisco"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    # Create a job
    job = Job(
        linkedin_job_id="test-job-123",
        title="Senior Software Engineer",
        company="Test Company",
        location="San Francisco, CA",
        job_url="https://linkedin.com/jobs/view/test-job-123",
        easy_apply=True,
        search_profile_id=profile.id,
        user_id=test_user.id,
        status="discovered"
    )
    db_session.add(job)
    await db_session.commit()

    # List jobs
    response = await client.get(
        f"/jobs/?search_profile_id={profile.id}",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_trigger_job_search(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test triggering a job search."""
    # Create a search profile first
    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="Python Developer",
        location="New York"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    # Trigger job search
    response = await client.post(
        "/jobs/search",
        json={"search_profile_id": profile.id},
        headers=auth_headers
    )

    # Should return 202 Accepted
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_job_search_status_not_found(
    client: AsyncClient,
    auth_headers: dict
):
    """Test getting status of non-existent task."""
    response = await client.get(
        "/jobs/search/status/non-existent-task-id",
        headers=auth_headers
    )

    assert response.status_code == 404
