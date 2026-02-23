"""
Application Service for managing job applications.

This service handles:
- Creating and tracking applications
- Enqueuing application tasks
- Retrieving application status
"""
from datetime import datetime
from typing import Optional
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.models.application import Application
from app.models.job import Job
from app.models.tailored_resume import TailoredResume
from app.schemas.application import ApplicationCreate, ApplicationStatusUpdate
import redis.asyncio as redis


class ApplicationServiceError(Exception):
    """Base exception for application service errors."""
    pass


class DuplicateApplicationError(ApplicationServiceError):
    """Raised when attempting to create a duplicate application."""
    pass


class ApplicationService:
    """Service for managing job applications."""

    QUEUE_KEY = "li_autopilot:worker:queue:applications"
    TASK_KEY_PREFIX = "li_autopilot:worker:application_task"

    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client

    async def create_application(
        self,
        user_id: str,
        application_data: ApplicationCreate
    ) -> Application:
        """Create a new application record.

        Args:
            user_id: User ID
            application_data: Application creation data

        Returns:
            Created Application instance

        Raises:
            DuplicateApplicationError: If application already exists
            ApplicationServiceError: If job not found or doesn't belong to user
        """
        job = await self._get_job(application_data.job_id, user_id)
        if not job:
            raise ApplicationServiceError(
                f"Job {application_data.job_id} not found or doesn't belong to user"
            )

        existing = await self.get_application_by_job(user_id, application_data.job_id)
        if existing:
            raise DuplicateApplicationError(
                f"Application already exists for job {application_data.job_id}"
            )

        if application_data.tailored_resume_id:
            resume = await self._get_tailored_resume(
                application_data.tailored_resume_id,
                user_id
            )
            if not resume:
                raise ApplicationServiceError(
                    f"Tailored resume {application_data.tailored_resume_id} not found"
                )

        application = Application(
            user_id=user_id,
            job_id=application_data.job_id,
            tailored_resume_id=application_data.tailored_resume_id,
            status="pending"
        )

        self.db.add(application)
        await self.db.commit()
        await self.db.refresh(application)

        return application

    async def enqueue_application_task(
        self,
        application: Application,
        job_url: str,
        resume_path: Optional[str] = None
    ) -> str:
        """Enqueue an application task for the worker.

        Args:
            application: Application instance
            job_url: LinkedIn job URL
            resume_path: Path to resume file

        Returns:
            Task ID for tracking
        """
        task_id = f"app_{application.user_id}_{application.job_id}_{datetime.utcnow().timestamp()}"

        task_data = {
            "task_id": task_id,
            "user_id": application.user_id,
            "job_id": application.job_id,
            "job_url": job_url,
            "tailored_resume_id": application.tailored_resume_id,
            "resume_path": resume_path,
            "application_id": application.id,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "error": None
        }

        task_key = f"{self.TASK_KEY_PREFIX}:{task_id}"
        await self.redis.setex(
            task_key,
            86400,
            json.dumps(task_data)
        )

        await self.redis.rpush(self.QUEUE_KEY, json.dumps(task_data))

        return task_id

    async def get_application(self, application_id: str, user_id: str) -> Optional[Application]:
        """Get an application by ID.

        Args:
            application_id: Application ID
            user_id: User ID (for access control)

        Returns:
            Application instance or None
        """
        result = await self.db.execute(
            select(Application)
            .where(Application.id == application_id)
            .where(Application.user_id == user_id)
        )
        return result.scalars().first()

    async def get_application_by_job(self, user_id: str, job_id: str) -> Optional[Application]:
        """Get application for a specific job.

        Args:
            user_id: User ID
            job_id: Job ID

        Returns:
            Application instance or None
        """
        result = await self.db.execute(
            select(Application)
            .where(Application.user_id == user_id)
            .where(Application.job_id == job_id)
        )
        return result.scalars().first()

    async def list_applications(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[list[Application], int]:
        """List applications for a user.

        Args:
            user_id: User ID
            status: Optional status filter
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Tuple of (applications list, total count)
        """
        query = select(Application).where(Application.user_id == user_id)

        if status:
            query = query.where(Application.status == status)

        query = query.order_by(Application.created_at.desc())

        count_result = await self.db.execute(
            select(Application).where(Application.user_id == user_id)
        )
        total = len(count_result.scalars().all())

        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        applications = result.scalars().all()

        return list(applications), total

    async def update_application_status(
        self,
        application_id: str,
        update_data: ApplicationStatusUpdate
    ) -> Application:
        """Update application status.

        Args:
            application_id: Application ID
            update_data: Status update data

        Returns:
            Updated Application instance

        Raises:
            ApplicationServiceError: If application not found
        """
        result = await self.db.execute(
            select(Application).where(Application.id == application_id)
        )
        application = result.scalars().first()

        if not application:
            raise ApplicationServiceError(f"Application {application_id} not found")

        application.status = update_data.status
        application.error_message = update_data.error_message
        application.linkedin_application_id = update_data.linkedin_application_id

        if update_data.status == "completed":
            application.submitted_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(application)

        return application

    async def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get status of an application task.

        Args:
            task_id: Task ID

        Returns:
            Task status dict or None
        """
        task_key = f"{self.TASK_KEY_PREFIX}:{task_id}"
        task_data = await self.redis.get(task_key)

        if task_data:
            return json.loads(task_data)

        return None

    async def _get_job(self, job_id: str, user_id: str) -> Optional[Job]:
        """Get job by ID, ensuring it belongs to user."""
        result = await self.db.execute(
            select(Job)
            .where(Job.id == job_id)
            .where(Job.user_id == user_id)
        )
        return result.scalars().first()

    async def _get_tailored_resume(
        self,
        resume_id: str,
        user_id: str
    ) -> Optional[TailoredResume]:
        """Get tailored resume by ID, ensuring it belongs to user."""
        result = await self.db.execute(
            select(TailoredResume)
            .where(TailoredResume.id == resume_id)
            .where(TailoredResume.user_id == user_id)
        )
        return result.scalars().first()
