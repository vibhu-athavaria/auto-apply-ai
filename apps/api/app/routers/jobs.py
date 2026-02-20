from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.database import get_db
from app.models.user import User
from app.models.job import Job
from app.models.job_search_profile import JobSearchProfile
from app.schemas.job import (
    JobResponse,
    JobListResponse,
    JobSearchRequest,
    JobSearchStatusResponse
)
from app.services.queue_service import QueueService, get_queue_service
from app.utils.security import get_current_user

router = APIRouter()


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    search_profile_id: str = Query(..., description="Search profile ID"),
    status: Optional[str] = Query(None, description="Filter by job status"),
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List jobs for a search profile.

    - Validates user owns the search profile
    - Returns jobs ordered by discovered_at desc
    - Supports filtering by status
    """
    # Verify user owns the search profile
    profile_result = await db.execute(
        select(JobSearchProfile)
        .where(JobSearchProfile.id == search_profile_id)
        .where(JobSearchProfile.user_id == current_user.id)
    )
    profile = profile_result.scalars().first()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Search profile not found or access denied"
        )

    # Build query
    query = select(Job).where(Job.search_profile_id == search_profile_id)
    count_query = select(func.count(Job.id)).where(
        Job.search_profile_id == search_profile_id
    )

    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get jobs with pagination
    query = query.order_by(Job.discovered_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(
        jobs=[JobResponse.model_validate(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset
    )


@router.post("/search", status_code=202, response_model=JobSearchStatusResponse)
async def trigger_job_search(
    request: JobSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    queue: QueueService = Depends(get_queue_service)
):
    """
    Trigger a job search task.

    - Validates search profile exists and belongs to user
    - Enqueues task to Redis
    - Returns task_id for status tracking
    - Does NOT wait for completion (async)
    """
    # Verify user owns the search profile
    profile_result = await db.execute(
        select(JobSearchProfile)
        .where(JobSearchProfile.id == request.search_profile_id)
        .where(JobSearchProfile.user_id == current_user.id)
    )
    profile = profile_result.scalars().first()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Search profile not found or access denied"
        )

    # Enqueue job search task
    task_id = await queue.enqueue_job_search(
        user_id=current_user.id,
        search_profile_id=request.search_profile_id
    )

    return JobSearchStatusResponse(
        task_id=task_id,
        status="queued",
        message="Job search task has been queued for processing"
    )


@router.get("/search/status/{task_id}", response_model=JobSearchStatusResponse)
async def get_job_search_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    queue: QueueService = Depends(get_queue_service)
):
    """
    Check job search task status.

    Returns current status of the job search task:
    - queued: Task is waiting to be processed
    - running: Worker is executing the search
    - completed: Search finished successfully
    - failed: Search encountered an error
    """
    task_status = await queue.get_task_status(task_id)

    if not task_status:
        raise HTTPException(
            status_code=404,
            detail="Task not found or expired"
        )

    # Verify user owns this task
    if task_status.get("user_id") != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    return JobSearchStatusResponse(
        task_id=task_status.get("task_id"),
        status=task_status.get("status"),
        message=task_status.get("message"),
        jobs_found=task_status.get("jobs_found"),
        created_at=task_status.get("created_at"),
        completed_at=task_status.get("completed_at")
    )
