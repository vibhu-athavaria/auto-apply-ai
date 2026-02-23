"""
Application Router - API endpoints for job applications.

Endpoints:
- POST /jobs/{id}/apply - Apply to a job via Easy Apply
- GET /applications - List user's applications
- GET /applications/{id} - Get specific application
- GET /applications/task/{task_id} - Check application task status
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationListResponse
)
from app.services.application_service import (
    ApplicationService,
    ApplicationServiceError,
    DuplicateApplicationError
)
from app.config import settings
from app.utils.security import get_current_user
import redis.asyncio as redis

router = APIRouter()


async def get_redis():
    """Get Redis client."""
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield redis_client
    finally:
        await redis_client.close()


@router.post("/{job_id}/apply", response_model=dict)
async def apply_to_job(
    job_id: str,
    tailored_resume_id: str = Query(None, description="Optional tailored resume ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Apply to a job using Easy Apply.

    This endpoint:
    1. Creates an application record
    2. Enqueues an application task for the worker
    3. Returns task_id for status tracking

    The actual application is processed asynchronously by the worker.
    """
    application_data = ApplicationCreate(
        job_id=job_id,
        tailored_resume_id=tailored_resume_id
    )

    service = ApplicationService(db, redis_client)

    try:
        application = await service.create_application(
            user_id=current_user.id,
            application_data=application_data
        )
    except DuplicateApplicationError:
        raise HTTPException(
            status_code=409,
            detail="Application already exists for this job"
        )
    except ApplicationServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.models.job import Job
    from sqlalchemy.future import select

    result = await db.execute(
        select(Job).where(Job.id == job_id).where(Job.user_id == current_user.id)
    )
    job = result.scalars().first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resume_path = None
    if tailored_resume_id:
        from app.models.tailored_resume import TailoredResume

        tailored_result = await db.execute(
            select(TailoredResume)
            .where(TailoredResume.id == tailored_resume_id)
            .where(TailoredResume.user_id == current_user.id)
        )
        tailored = tailored_result.scalars().first()

        if tailored:
            from app.models.resume import Resume

            resume_result = await db.execute(
                select(Resume).where(Resume.id == tailored.original_resume_id)
            )
            original_resume = resume_result.scalars().first()
            if original_resume:
                resume_path = original_resume.file_path

    task_id = await service.enqueue_application_task(
        application=application,
        job_url=job.job_url,
        resume_path=resume_path
    )

    return {
        "application_id": application.id,
        "task_id": task_id,
        "status": "queued",
        "message": "Application task queued for processing"
    }


@router.get("/applications", response_model=ApplicationListResponse)
async def list_applications(
    status: str = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    List user's job applications.

    Supports pagination and filtering by status.
    """
    service = ApplicationService(db, redis_client)
    applications, total = await service.list_applications(
        user_id=current_user.id,
        status=status,
        limit=limit,
        offset=offset
    )

    return ApplicationListResponse(
        applications=[
            ApplicationResponse.model_validate(app)
            for app in applications
        ],
        total=total
    )


@router.get("/applications/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Get a specific application by ID.
    """
    service = ApplicationService(db, redis_client)
    application = await service.get_application(
        application_id=application_id,
        user_id=current_user.id
    )

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    return ApplicationResponse.model_validate(application)


@router.get("/applications/task/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Get status of an application task.

    Returns the current status of the background application task.
    """
    service = ApplicationService(db, redis_client)
    task_status = await service.get_task_status(task_id)

    if not task_status:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_status.get("user_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return task_status
