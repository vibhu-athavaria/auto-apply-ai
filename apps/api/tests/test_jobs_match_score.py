"""Tests for job match score functionality."""
import json
import pytest
from unittest.mock import AsyncMock, patch, mock_open
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.job_search_profile import JobSearchProfile
from app.models.user import User
from app.services.job_matcher_service import JobMatcherService


@pytest.mark.asyncio
async def test_get_match_score_unauthorized(
    client: AsyncClient
):
    """Test getting match score without authentication."""
    response = await client.get("/jobs/test-job-id/match-score")
    assert response.status_code in [401, 403]  # Either unauthorized or forbidden


@pytest.mark.asyncio
async def test_get_match_score_job_not_found(
    client: AsyncClient,
    auth_headers: dict
):
    """Test getting match score for non-existent job."""
    response = await client.get(
        "/jobs/nonexistent-id/match-score",
        headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_match_score_no_resume(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test getting match score when user has no resume."""
    # Create a search profile and job
    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="Software Engineer",
        location="San Francisco"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    job = Job(
        linkedin_job_id="test-job-match-1",
        title="Software Engineer",
        company="Test Company",
        location="Remote",
        job_url="https://linkedin.com/jobs/view/test-job-match-1",
        search_profile_id=profile.id,
        user_id=test_user.id,
        status="discovered"
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # Try to get match score without resume
    response = await client.get(
        f"/jobs/{job.id}/match-score",
        headers=auth_headers
    )

    # Should return 400 since no resume exists
    assert response.status_code == 400
    assert "resume" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_job_list_includes_match_score(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test that job list includes match_score field."""
    # Create a search profile
    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="Software Engineer",
        location="San Francisco"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    # Create a job with match score
    job = Job(
        linkedin_job_id="test-job-match-3",
        title="Software Engineer",
        company="Test Company",
        location="Remote",
        job_url="https://linkedin.com/jobs/view/test-job-match-3",
        search_profile_id=profile.id,
        user_id=test_user.id,
        status="discovered",
        match_score=75
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
    assert len(data["jobs"]) == 1
    assert "match_score" in data["jobs"][0]
    assert data["jobs"][0]["match_score"] == 75


@pytest.mark.asyncio
async def test_job_list_pagination_default_10(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test job list pagination with default 10 per page."""
    # Create a search profile
    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="Software Engineer",
        location="San Francisco"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    # Create 15 jobs
    for i in range(15):
        job = Job(
            linkedin_job_id=f"test-job-paginate-{i}",
            title=f"Software Engineer {i}",
            company="Test Company",
            location="Remote",
            job_url=f"https://linkedin.com/jobs/view/test-job-paginate-{i}",
            search_profile_id=profile.id,
            user_id=test_user.id,
            status="discovered"
        )
        db_session.add(job)
    await db_session.commit()

    # Get first page (default limit is 10)
    response = await client.get(
        f"/jobs/?search_profile_id={profile.id}",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10  # Default is now 10
    assert data["total"] == 15
    assert len(data["jobs"]) == 10

    # Get second page
    response = await client.get(
        f"/jobs/?search_profile_id={profile.id}&offset=10",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["jobs"]) == 5  # Remaining jobs


class TestJobMatcherService:
    """Tests for JobMatcherService."""

    @pytest.mark.asyncio
    async def test_calculate_match_score(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test match score calculation."""
        matcher = JobMatcherService(db_session, mock_redis)

        job_description = "Looking for Python developer with 5 years experience in Django and AWS"
        job_title = "Senior Python Developer"
        resume_text = "Python developer with 6 years experience. Expert in Django, Flask, AWS, Docker."

        score = matcher.calculate_match_score(job_description, job_title, resume_text)

        assert isinstance(score, int)
        assert 0 <= score <= 100
        # Should be a good match
        assert score > 50

    @pytest.mark.asyncio
    async def test_extract_skills(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test skill extraction."""
        matcher = JobMatcherService(db_session, mock_redis)

        text = "Python developer with experience in Django, React, AWS, and Docker"
        skills = matcher._extract_skills(text)

        assert "python" in skills
        assert "django" in skills
        assert "react" in skills
        assert "aws" in skills
        assert "docker" in skills

    @pytest.mark.asyncio
    async def test_extract_experience_years(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test experience years extraction."""
        matcher = JobMatcherService(db_session, mock_redis)

        # Test various formats
        assert matcher._extract_experience_years("5 years of experience") == 5
        assert matcher._extract_experience_years("3+ years experience") == 3
        assert matcher._extract_experience_years("minimum 7 years") == 7
        assert matcher._extract_experience_years("at least 2 years") == 2
        assert matcher._extract_experience_years("no requirement") is None

    @pytest.mark.asyncio
    async def test_cache_key_generation(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test cache key generation is deterministic."""
        matcher = JobMatcherService(db_session, mock_redis)

        key1 = matcher._generate_cache_key("user1", "job1", "resume1")
        key2 = matcher._generate_cache_key("user1", "job1", "resume1")

        assert key1 == key2
        assert key1.startswith("li_autopilot:api:job_match:")

    @pytest.mark.asyncio
    async def test_calculate_skills_score(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test skills score calculation."""
        matcher = JobMatcherService(db_session, mock_redis)

        # Perfect match
        job_skills = {"python", "django"}
        resume_skills = {"python", "django", "flask"}
        score = matcher._calculate_skills_score(job_skills, resume_skills)
        assert score == 1.0

        # Partial match
        job_skills = {"python", "django", "react"}
        resume_skills = {"python", "flask"}
        score = matcher._calculate_skills_score(job_skills, resume_skills)
        assert 0 < score < 1

        # No match - should be very low but not exactly 0 due to bonus calculation
        job_skills = {"java", "spring"}
        resume_skills = {"python", "django"}
        score = matcher._calculate_skills_score(job_skills, resume_skills)
        assert score >= 0.0
        assert score < 0.5

        # Empty job skills - should be neutral
        score = matcher._calculate_skills_score(set(), resume_skills)
        assert score == 0.5

    @pytest.mark.asyncio
    async def test_calculate_experience_score(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test experience score calculation."""
        matcher = JobMatcherService(db_session, mock_redis)

        # Meets requirement
        score = matcher._calculate_experience_score(5, 5)
        assert score >= 0.8

        # Exceeds requirement
        score = matcher._calculate_experience_score(3, 6)
        assert score > 0.8

        # Below requirement
        score = matcher._calculate_experience_score(5, 2)
        assert score < 1.0

        # No job requirement specified
        score = matcher._calculate_experience_score(None, 3)
        assert score == 0.7

    @pytest.mark.asyncio
    async def test_calculate_title_score(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test title score calculation."""
        matcher = JobMatcherService(db_session, mock_redis)

        # Good match
        score = matcher._calculate_title_score(
            "Senior Python Developer",
            "Senior Python Developer with 5 years experience"
        )
        assert score > 0.5

        # No match - should be low
        score = matcher._calculate_title_score(
            "Java Developer",
            "Python Developer with Django experience"
        )
        assert score <= 0.5

    @pytest.mark.asyncio
    async def test_detect_seniority(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test seniority level detection."""
        matcher = JobMatcherService(db_session, mock_redis)

        assert matcher._detect_seniority("Junior Developer") == "entry"
        assert matcher._detect_seniority("Senior Engineer") == "senior"
        # "Mid-level" is not in our keywords, but "intermediate" is
        assert matcher._detect_seniority("Intermediate Developer") == "mid"
        assert matcher._detect_seniority("Director of Engineering") == "executive"
        assert matcher._detect_seniority("Developer") is None

    @pytest.mark.asyncio
    async def test_cache_operations(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test cache get and set operations."""
        matcher = JobMatcherService(db_session, mock_redis)

        # Mock cache miss
        mock_redis.get = AsyncMock(return_value=None)
        score = await matcher._get_cached_score("user1", "job1", "resume1")
        assert score is None

        # Mock cache hit
        mock_redis.get = AsyncMock(return_value="85")
        score = await matcher._get_cached_score("user1", "job1", "resume1")
        assert score == 85

        # Test cache set
        mock_redis.setex = AsyncMock(return_value=True)
        await matcher._cache_score("user1", "job1", "resume1", 90)
        mock_redis.setex.assert_called_once()
