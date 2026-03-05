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
    JobSearchStatusResponse,
    JobMatchScoreResponse
)
from app.services.queue_service import QueueService, get_queue_service
from app.services.job_matcher_service import JobMatcherService
from app.utils.security import get_current_user
from app.config import settings
import redis.asyncio as redis

router = APIRouter()


def get_redis_client():
    """Get Redis client for caching."""
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    search_profile_id: str = Query(..., description="Search profile ID"),
    status: Optional[str] = Query(None, description="Filter by job status"),
    limit: int = Query(10, ge=1, le=100, description="Number of results per page (default: 10)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List jobs for a search profile.

    - Validates user owns the search profile
    - Returns jobs ordered by discovered_at desc
    - Supports filtering by status
    - Default 10 jobs per page (configurable via limit parameter)
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


@router.get("/{job_id}/match-score", response_model=JobMatchScoreResponse)
async def get_job_match_score(
    job_id: str,
    resume_id: Optional[str] = Query(None, description="Optional resume ID to use for matching (defaults to latest resume)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    Get match score for a specific job against user's resume.

    Calculates a score (0-100) indicating how well the user's resume
    matches the job requirements based on:
    - Skills match (50% weight)
    - Experience level match (30% weight)
    - Job title/role match (20% weight)

    Results are cached for 24 hours per AGENTS.md rules.
    """
    # Verify job belongs to user
    job_result = await db.execute(
        select(Job).where(Job.id == job_id).where(Job.user_id == current_user.id)
    )
    job = job_result.scalars().first()

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or access denied"
        )

    # Calculate match score
    matcher = JobMatcherService(db, redis_client)
    score = await matcher.get_match_score(
        user_id=current_user.id,
        job_id=job_id,
        resume_id=resume_id
    )

    if score is None:
        raise HTTPException(
            status_code=400,
            detail="Could not calculate match score. Please upload a resume first."
        )

    return JobMatchScoreResponse(
        job_id=job_id,
        score=score,
        max_score=100,
        percentage=f"{score}%"
    )


@router.post("/{job_id}/calculate-match", response_model=JobMatchScoreResponse)
async def calculate_and_store_match_score(
    job_id: str,
    resume_id: Optional[str] = Query(None, description="Optional resume ID to use for matching"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    Calculate and store match score for a job.

    Recalculates the match score and stores it on the job record.
    Use this when you want to force a recalculation.
    """
    # Verify job belongs to user
    job_result = await db.execute(
        select(Job).where(Job.id == job_id).where(Job.user_id == current_user.id)
    )
    job = job_result.scalars().first()

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or access denied"
        )

    # Calculate match score (forces recalculation)
    matcher = JobMatcherService(db, redis_client)

    # Clear cache to force recalculation
    if redis_client:
        cache_key = matcher._generate_cache_key(current_user.id, job_id, resume_id or "")
        await redis_client.delete(cache_key)

    score = await matcher.get_match_score(
        user_id=current_user.id,
        job_id=job_id,
        resume_id=resume_id
    )

    if score is None:
        raise HTTPException(
            status_code=400,
            detail="Could not calculate match score. Please upload a resume first."
        )

    return JobMatchScoreResponse(
        job_id=job_id,
        score=score,
        max_score=100,
        percentage=f"{score}%"
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
