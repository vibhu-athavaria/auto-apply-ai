"""Tests for Jobs API endpoints."""
import json
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.job_search_profile import JobSearchProfile
from app.models.user import User
from app.services.queue_service import QueueService


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
async def test_list_jobs_profile_not_found(
    client: AsyncClient,
    auth_headers: dict
):
    """Test listing jobs for non-existent profile."""
    response = await client.get(
        "/jobs/?search_profile_id=nonexistent-id",
        headers=auth_headers
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_jobs_with_status_filter(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test listing jobs with status filter."""
    # Create a search profile
    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="Software Engineer",
        location="San Francisco"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    # Create jobs with different statuses
    job1 = Job(
        linkedin_job_id="test-job-status-1",
        title="Software Engineer",
        company="Company A",
        location="Remote",
        job_url="https://linkedin.com/jobs/view/test-job-status-1",
        search_profile_id=profile.id,
        user_id=test_user.id,
        status="discovered"
    )
    job2 = Job(
        linkedin_job_id="test-job-status-2",
        title="Senior Engineer",
        company="Company B",
        location="Remote",
        job_url="https://linkedin.com/jobs/view/test-job-status-2",
        search_profile_id=profile.id,
        user_id=test_user.id,
        status="applied"
    )
    db_session.add(job1)
    db_session.add(job2)
    await db_session.commit()

    # List jobs with status filter
    response = await client.get(
        f"/jobs/?search_profile_id={profile.id}&status=discovered",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert all(job["status"] == "discovered" for job in data["jobs"])


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
async def test_trigger_job_search_profile_not_found(
    client: AsyncClient,
    auth_headers: dict
):
    """Test triggering job search for non-existent profile."""
    response = await client.post(
        "/jobs/search",
        json={"search_profile_id": "nonexistent-id"},
        headers=auth_headers
    )

    assert response.status_code == 404


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


@pytest.mark.asyncio
async def test_job_search_status_success(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    mock_redis: AsyncMock
):
    """Test getting status of a task."""
    task_id = "test-task-id"
    task_data = {
        "task_id": task_id,
        "user_id": test_user.id,
        "status": "completed",
        "message": "Job search completed successfully",
        "jobs_found": 10,
        "created_at": "2024-01-01T00:00:00",
        "completed_at": "2024-01-01T00:05:00"
    }

    mock_redis.get = AsyncMock(return_value=json.dumps(task_data))

    response = await client.get(
        f"/jobs/search/status/{task_id}",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] == "completed"
    assert data["jobs_found"] == 10


@pytest.mark.asyncio
async def test_job_search_status_wrong_user(
    client: AsyncClient,
    auth_headers: dict,
    mock_redis: AsyncMock
):
    """Test getting status of task belonging to another user."""
    task_id = "test-task-id"
    task_data = {
        "task_id": task_id,
        "user_id": "different-user-id",
        "status": "completed"
    }

    mock_redis.get = AsyncMock(return_value=json.dumps(task_data))

    response = await client.get(
        f"/jobs/search/status/{task_id}",
        headers=auth_headers
    )

    assert response.status_code == 403


class TestQueueService:
    """Tests for QueueService."""

    @pytest.mark.asyncio
    async def test_enqueue_job_search(self, mock_redis: AsyncMock):
        """Test enqueueing a job search task."""
        queue_service = QueueService(mock_redis)

        task_id = await queue_service.enqueue_job_search(
            user_id="user_123",
            search_profile_id="profile_456"
        )

        assert task_id is not None
        mock_redis.setex.assert_called_once()
        mock_redis.rpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_task_status_found(self, mock_redis: AsyncMock):
        """Test getting task status when task exists."""
        task_data = {
            "task_id": "task_123",
            "user_id": "user_123",
            "status": "running"
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(task_data))

        queue_service = QueueService(mock_redis)
        result = await queue_service.get_task_status("task_123")

        assert result is not None
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, mock_redis: AsyncMock):
        """Test getting task status when task doesn't exist."""
        mock_redis.get = AsyncMock(return_value=None)

        queue_service = QueueService(mock_redis)
        result = await queue_service.get_task_status("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_task_status(self, mock_redis: AsyncMock):
        """Test updating task status."""
        existing_task = {
            "task_id": "task_123",
            "user_id": "user_123",
            "status": "queued",
            "created_at": "2024-01-01T00:00:00"
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(existing_task))

        queue_service = QueueService(mock_redis)
        await queue_service.update_task_status(
            task_id="task_123",
            status="completed",
            message="Job search completed",
            jobs_found=5
        )

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        updated_data = json.loads(call_args[0][2])
        assert updated_data["status"] == "completed"
        assert updated_data["message"] == "Job search completed"
        assert updated_data["jobs_found"] == 5
        assert "completed_at" in updated_data

    @pytest.mark.asyncio
    async def test_update_task_status_running(self, mock_redis: AsyncMock):
        """Test updating task status to running."""
        existing_task = {
            "task_id": "task_123",
            "user_id": "user_123",
            "status": "queued",
            "created_at": "2024-01-01T00:00:00"
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(existing_task))

        queue_service = QueueService(mock_redis)
        await queue_service.update_task_status(
            task_id="task_123",
            status="running",
            message="Job search in progress"
        )

        call_args = mock_redis.setex.call_args
        updated_data = json.loads(call_args[0][2])
        assert updated_data["status"] == "running"
        # completed_at should not be set for non-terminal status
        assert "completed_at" not in updated_data

    @pytest.mark.asyncio
    async def test_update_task_status_not_found(self, mock_redis: AsyncMock):
        """Test updating task status when task doesn't exist."""
        mock_redis.get = AsyncMock(return_value=None)

        queue_service = QueueService(mock_redis)
        # Should not raise, just do nothing
        await queue_service.update_task_status(
            task_id="nonexistent",
            status="completed"
        )

        # setex should not be called since task doesn't exist
        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_job_search(self, mock_redis: AsyncMock):
        """Test caching job search results."""
        queue_service = QueueService(mock_redis)

        jobs = [
            {"id": "job_1", "title": "Engineer"},
            {"id": "job_2", "title": "Developer"}
        ]

        await queue_service.cache_job_search(
            search_profile_id="profile_123",
            jobs=jobs
        )

        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_job_search_custom_ttl(self, mock_redis: AsyncMock):
        """Test caching job search results with custom TTL."""
        queue_service = QueueService(mock_redis)

        jobs = [{"id": "job_1", "title": "Engineer"}]

        await queue_service.cache_job_search(
            search_profile_id="profile_123",
            jobs=jobs,
            ttl=3600
        )

        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600

    @pytest.mark.asyncio
    async def test_get_cached_job_search_found(self, mock_redis: AsyncMock):
        """Test getting cached job search results."""
        jobs = [
            {"id": "job_1", "title": "Engineer"},
            {"id": "job_2", "title": "Developer"}
        ]

        mock_redis.get = AsyncMock(return_value=json.dumps(jobs))

        queue_service = QueueService(mock_redis)
        result = await queue_service.get_cached_job_search("profile_123")

        assert result is not None
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_cached_job_search_not_found(self, mock_redis: AsyncMock):
        """Test getting cached job search results when not cached."""
        mock_redis.get = AsyncMock(return_value=None)

        queue_service = QueueService(mock_redis)
        result = await queue_service.get_cached_job_search("profile_123")

        assert result is None

    @pytest.mark.asyncio
    async def test_close_connection(self, mock_redis: AsyncMock):
        """Test closing Redis connection."""
        queue_service = QueueService(mock_redis)
        await queue_service.close()

        mock_redis.close.assert_called_once()
