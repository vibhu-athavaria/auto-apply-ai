"""
Tests for Application functionality.

Tests cover:
- Application Service
- Application API endpoints
- Easy Apply automation (mocked)
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.resume import Resume
from app.models.job import Job
from app.models.job_search_profile import JobSearchProfile
from app.models.tailored_resume import TailoredResume
from app.models.application import Application
from app.services.application_service import (
    ApplicationService,
    ApplicationServiceError,
    DuplicateApplicationError
)


@pytest.fixture
async def test_job_with_easy_apply(
    db_session: AsyncSession,
    test_user: User
) -> Job:
    """Create a test job with Easy Apply enabled."""
    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="python, fastapi",
        location="Remote"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    job = Job(
        linkedin_job_id="li_easy_apply_123",
        title="Senior Python Developer",
        company="Test Corp",
        location="San Francisco, CA",
        job_url="https://linkedin.com/jobs/view/li_easy_apply_123",
        easy_apply=True,
        description="Looking for a Python developer with FastAPI experience",
        search_profile_id=profile.id,
        user_id=test_user.id
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    return job


@pytest.fixture
async def test_tailored_resume(
    db_session: AsyncSession,
    test_user: User,
    test_resume: Resume,
    test_job_with_easy_apply: Job
) -> TailoredResume:
    """Create a test tailored resume."""
    tailored = TailoredResume(
        user_id=test_user.id,
        job_id=test_job_with_easy_apply.id,
        original_resume_id=test_resume.id,
        tailored_resume_text="Tailored resume content",
        cover_letter="Cover letter content",
        input_hash="test_hash_123"
    )
    db_session.add(tailored)
    await db_session.commit()
    await db_session.refresh(tailored)

    return tailored


class TestApplicationService:
    """Tests for Application Service."""

    @pytest.mark.asyncio
    async def test_create_application(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test creating a new application."""
        service = ApplicationService(db_session, mock_redis)

        from app.schemas.application import ApplicationCreate
        application = await service.create_application(
            user_id=test_user.id,
            application_data=ApplicationCreate(job_id=test_job_with_easy_apply.id)
        )

        assert application.id is not None
        assert application.user_id == test_user.id
        assert application.job_id == test_job_with_easy_apply.id
        assert application.status == "pending"

    @pytest.mark.asyncio
    async def test_create_duplicate_application(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test that duplicate applications are rejected."""
        service = ApplicationService(db_session, mock_redis)

        from app.schemas.application import ApplicationCreate
        await service.create_application(
            user_id=test_user.id,
            application_data=ApplicationCreate(job_id=test_job_with_easy_apply.id)
        )

        with pytest.raises(DuplicateApplicationError):
            await service.create_application(
                user_id=test_user.id,
                application_data=ApplicationCreate(job_id=test_job_with_easy_apply.id)
            )

    @pytest.mark.asyncio
    async def test_create_application_wrong_user(
        self,
        db_session: AsyncSession,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test that application fails for wrong user."""
        service = ApplicationService(db_session, mock_redis)

        from app.schemas.application import ApplicationCreate
        with pytest.raises(ApplicationServiceError):
            await service.create_application(
                user_id="wrong-user-id",
                application_data=ApplicationCreate(job_id=test_job_with_easy_apply.id)
            )

    @pytest.mark.asyncio
    async def test_create_application_with_tailored_resume(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        test_tailored_resume: TailoredResume,
        mock_redis: AsyncMock
    ):
        """Test creating application with tailored resume."""
        service = ApplicationService(db_session, mock_redis)

        from app.schemas.application import ApplicationCreate
        application = await service.create_application(
            user_id=test_user.id,
            application_data=ApplicationCreate(
                job_id=test_job_with_easy_apply.id,
                tailored_resume_id=test_tailored_resume.id
            )
        )

        assert application.tailored_resume_id == test_tailored_resume.id

    @pytest.mark.asyncio
    async def test_get_application(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test retrieving an application."""
        service = ApplicationService(db_session, mock_redis)

        from app.schemas.application import ApplicationCreate
        created = await service.create_application(
            user_id=test_user.id,
            application_data=ApplicationCreate(job_id=test_job_with_easy_apply.id)
        )

        retrieved = await service.get_application(created.id, test_user.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_get_application_not_found(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_redis: AsyncMock
    ):
        """Test retrieving non-existent application."""
        service = ApplicationService(db_session, mock_redis)

        retrieved = await service.get_application("nonexistent-id", test_user.id)

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_applications(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test listing applications."""
        service = ApplicationService(db_session, mock_redis)

        from app.schemas.application import ApplicationCreate
        await service.create_application(
            user_id=test_user.id,
            application_data=ApplicationCreate(job_id=test_job_with_easy_apply.id)
        )

        applications, total = await service.list_applications(test_user.id)

        assert total >= 1
        assert len(applications) >= 1

    @pytest.mark.asyncio
    async def test_list_applications_filter_status(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test filtering applications by status."""
        service = ApplicationService(db_session, mock_redis)

        from app.schemas.application import ApplicationCreate
        await service.create_application(
            user_id=test_user.id,
            application_data=ApplicationCreate(job_id=test_job_with_easy_apply.id)
        )

        applications, total = await service.list_applications(
            test_user.id,
            status="pending"
        )

        assert all(app.status == "pending" for app in applications)

    @pytest.mark.asyncio
    async def test_update_application_status(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test updating application status."""
        service = ApplicationService(db_session, mock_redis)

        from app.schemas.application import ApplicationCreate, ApplicationStatusUpdate
        created = await service.create_application(
            user_id=test_user.id,
            application_data=ApplicationCreate(job_id=test_job_with_easy_apply.id)
        )

        updated = await service.update_application_status(
            created.id,
            ApplicationStatusUpdate(
                status="completed",
                linkedin_application_id="li_app_123"
            )
        )

        assert updated.status == "completed"
        assert updated.linkedin_application_id == "li_app_123"
        assert updated.submitted_at is not None

    @pytest.mark.asyncio
    async def test_enqueue_application_task(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test enqueueing an application task."""
        service = ApplicationService(db_session, mock_redis)

        from app.schemas.application import ApplicationCreate
        application = await service.create_application(
            user_id=test_user.id,
            application_data=ApplicationCreate(job_id=test_job_with_easy_apply.id)
        )

        task_id = await service.enqueue_application_task(
            application=application,
            job_url=test_job_with_easy_apply.job_url
        )

        assert task_id is not None
        assert task_id.startswith("app_")

        mock_redis.rpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_task_status(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test getting task status."""
        task_data = {
            "task_id": "test_task_123",
            "status": "pending",
            "user_id": "user_123"
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(task_data))

        service = ApplicationService(db_session, mock_redis)
        status = await service.get_task_status("test_task_123")

        assert status["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test getting non-existent task status."""
        mock_redis.get = AsyncMock(return_value=None)

        service = ApplicationService(db_session, mock_redis)
        status = await service.get_task_status("nonexistent")

        assert status is None


class TestApplicationEndpoints:
    """Tests for Application API endpoints."""

    @pytest.mark.asyncio
    async def test_apply_to_job(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test POST /jobs/{id}/apply endpoint."""
        mock_redis.rpush = AsyncMock(return_value=True)
        mock_redis.setex = AsyncMock(return_value=True)

        response = await client.post(
            f"/jobs/{test_job_with_easy_apply.id}/apply",
            headers=auth_headers
        )

        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_apply_to_job_with_tailored_resume(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        test_tailored_resume: TailoredResume,
        mock_redis: AsyncMock
    ):
        """Test applying with tailored resume."""
        mock_redis.rpush = AsyncMock(return_value=True)
        mock_redis.setex = AsyncMock(return_value=True)

        response = await client.post(
            f"/jobs/{test_job_with_easy_apply.id}/apply",
            params={"tailored_resume_id": test_tailored_resume.id},
            headers=auth_headers
        )

        assert response.status_code in [200, 201, 202]

    @pytest.mark.asyncio
    async def test_apply_to_job_duplicate(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test duplicate application returns 409."""
        mock_redis.rpush = AsyncMock(return_value=True)
        mock_redis.setex = AsyncMock(return_value=True)

        await client.post(
            f"/jobs/{test_job_with_easy_apply.id}/apply",
            headers=auth_headers
        )

        response = await client.post(
            f"/jobs/{test_job_with_easy_apply.id}/apply",
            headers=auth_headers
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_apply_to_nonexistent_job(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test applying to non-existent job."""
        response = await client.post(
            "/jobs/nonexistent-id/apply",
            headers=auth_headers
        )

        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_list_applications_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test GET /jobs/applications endpoint."""
        mock_redis.rpush = AsyncMock(return_value=True)
        mock_redis.setex = AsyncMock(return_value=True)

        await client.post(
            f"/jobs/{test_job_with_easy_apply.id}/apply",
            headers=auth_headers
        )

        response = await client.get(
            "/jobs/applications",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "applications" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_get_application_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_job_with_easy_apply: Job,
        mock_redis: AsyncMock
    ):
        """Test GET /jobs/applications/{id} endpoint."""
        mock_redis.rpush = AsyncMock(return_value=True)
        mock_redis.setex = AsyncMock(return_value=True)

        create_response = await client.post(
            f"/jobs/{test_job_with_easy_apply.id}/apply",
            headers=auth_headers
        )
        application_id = create_response.json()["application_id"]

        response = await client.get(
            f"/jobs/applications/{application_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == application_id

    @pytest.mark.asyncio
    async def test_get_task_status_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        mock_redis: AsyncMock
    ):
        """Test GET /jobs/applications/task/{task_id} endpoint."""
        task_data = {
            "task_id": "test_task_123",
            "user_id": test_user.id,
            "status": "completed"
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(task_data))

        from app.services.application_service import ApplicationService
        service = ApplicationService(db_session, mock_redis)
        await service.get_task_status("test_task_123")

        response = await client.get(
            "/jobs/applications/task/test_task_123",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, client: AsyncClient):
        """Test that endpoints require authentication."""
        response = await client.post("/jobs/some-id/apply")
        assert response.status_code in [401, 403]

        response = await client.get("/jobs/applications")
        assert response.status_code in [401, 403]


class TestRateLimiter:
    """Tests for rate limiting in applications - worker module tests."""

    pass


class TestBackoff:
    """Tests for exponential backoff - worker module tests."""

    pass
