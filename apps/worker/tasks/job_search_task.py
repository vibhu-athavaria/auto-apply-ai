"""Job search task handler.

This module handles the execution of job search tasks:
1. Get search profile from database
2. Use LinkedIn client to search for jobs
3. Store jobs in database
4. Update task status in Redis
5. Handle deduplication
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import update

from config import settings
from automation.linkedin import LinkedInClient
from models import Base
from models.job import Job
from models.job_search_profile import JobSearchProfile
from utils.logger import get_logger
from utils.rate_limiter import RateLimiter
from utils.delays import search_delay
from utils.session_store import get_user_session

logger = get_logger(__name__)


class JobSearchTask:
    """Handles job search task execution.

    Redis keys used:
    - li_autopilot:api:task_status:{task_id} - Task status
    - li_autopilot:worker:job_dedup:{linkedin_job_id} - Deduplication
    """

    TASK_STATUS_PREFIX = "li_autopilot:api:task_status"
    JOB_DEDUP_PREFIX = "li_autopilot:worker:job_dedup"
    DEDUP_TTL = 604800  # 7 days

    def __init__(
        self,
        redis_client: redis.Redis,
        db_session: AsyncSession
    ):
        """Initialize task handler.

        Args:
            redis_client: Redis client for status updates
            db_session: Database session for job storage
        """
        self.redis = redis_client
        self.db = db_session
        self.rate_limiter = RateLimiter(redis_client)

    async def execute(
        self,
        task_id: str,
        user_id: str,
        search_profile_id: str
    ) -> Dict[str, Any]:
        """Execute job search task.

        Args:
            task_id: Unique task identifier
            user_id: User ID requesting search
            search_profile_id: Search profile to use

        Returns:
            Task result dictionary
        """
        start_time = datetime.utcnow()

        logger.info(
            "Starting job search task",
            extra={
                "user_id": user_id,
                "action": "job_search_task",
                "status": "started",
                "task_id": task_id,
                "search_profile_id": search_profile_id
            }
        )

        try:
            await self._update_task_status(task_id, "running", "Connecting to LinkedIn...")

            if not await self.rate_limiter.check_search_limit(user_id):
                await self._update_task_status(
                    task_id,
                    "failed",
                    "Daily search limit exceeded"
                )
                return {
                    "status": "failed",
                    "message": "Daily search limit exceeded"
                }

            profile = await self._get_search_profile(search_profile_id)
            if not profile:
                await self._update_task_status(
                    task_id,
                    "failed",
                    "Search profile not found"
                )
                return {
                    "status": "failed",
                    "message": "Search profile not found"
                }

            if profile.user_id != user_id:
                await self._update_task_status(
                    task_id,
                    "failed",
                    "Access denied"
                )
                return {
                    "status": "failed",
                    "message": "Access denied"
                }

            await self._update_task_status(task_id, "running", f"Searching for '{profile.keywords}' jobs in {profile.location}...")

            jobs = await self._search_linkedin(
                keywords=profile.keywords,
                location=profile.location,
                user_id=user_id
            )

            await self._update_task_status(task_id, "running", f"Found {len(jobs)} jobs, saving to your dashboard...")

            new_jobs_count = await self._store_jobs(
                jobs=jobs,
                user_id=user_id,
                search_profile_id=search_profile_id
            )

            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            await self._update_task_status(
                task_id,
                "completed",
                f"Found {len(jobs)} jobs, {new_jobs_count} new",
                jobs_found=len(jobs)
            )

            logger.info(
                "Job search task completed",
                extra={
                    "user_id": user_id,
                    "action": "job_search_task",
                    "status": "success",
                    "task_id": task_id,
                    "jobs_found": len(jobs),
                    "new_jobs": new_jobs_count,
                    "duration_ms": duration_ms
                }
            )

            return {
                "status": "completed",
                "jobs_found": len(jobs),
                "new_jobs": new_jobs_count,
                "duration_ms": duration_ms
            }

        except Exception as e:
            logger.error(
                f"Job search task failed: {e}",
                extra={
                    "user_id": user_id,
                    "action": "job_search_task",
                    "status": "error",
                    "task_id": task_id,
                    "error": str(e)
                }
            )

            await self._update_task_status(
                task_id,
                "failed",
                str(e)
            )

            return {
                "status": "failed",
                "message": str(e)
            }

    async def _get_search_profile(
        self,
        search_profile_id: str
    ) -> Optional[JobSearchProfile]:
        """Get search profile from database.

        Args:
            search_profile_id: Profile ID

        Returns:
            JobSearchProfile or None
        """
        result = await self.db.execute(
            select(JobSearchProfile)
            .where(JobSearchProfile.id == search_profile_id)
        )
        return result.scalars().first()

    async def _search_linkedin(
        self,
        keywords: str,
        location: str,
        user_id: str
    ) -> list:
        """Execute LinkedIn job search using user's session cookie.

        Args:
            keywords: Search keywords
            location: Job location
            user_id: User ID to fetch session cookie for

        Returns:
            List of job dictionaries
        """
        session_cookie = await get_user_session(self.redis, user_id)

        if not session_cookie:
            raise Exception(
                f"No LinkedIn session found for user {user_id}. "
                "User must connect their LinkedIn account first."
            )

        async with LinkedInClient(session_cookie=session_cookie) as client:
            if not await client.navigate_to_jobs():
                raise Exception(
                    "LinkedIn authentication failed. "
                    "Session cookie may be expired."
                )

            await search_delay()

            jobs = await client.search_jobs(
                keywords=keywords,
                location=location,
                max_results=50
            )

            return jobs

    async def _store_jobs(
        self,
        jobs: list,
        user_id: str,
        search_profile_id: str
    ) -> int:
        """Store jobs in database with deduplication.

        Args:
            jobs: List of job dictionaries
            user_id: User ID
            search_profile_id: Search profile ID

        Returns:
            Number of new jobs stored
        """
        new_jobs_count = 0

        for job_data in jobs:
            linkedin_job_id = job_data.get("linkedin_job_id")
            if not linkedin_job_id:
                continue

            # Check deduplication
            dedup_key = f"{self.JOB_DEDUP_PREFIX}:{linkedin_job_id}"
            is_duplicate = await self.redis.exists(dedup_key)

            if is_duplicate:
                logger.debug(
                    f"Skipping duplicate job: {linkedin_job_id}",
                    extra={
                        "user_id": user_id,
                        "action": "store_job",
                        "status": "duplicate",
                        "linkedin_job_id": linkedin_job_id
                    }
                )
                continue

            # Check if job already exists in database
            existing = await self.db.execute(
                select(Job).where(Job.linkedin_job_id == linkedin_job_id)
            )
            if existing.scalars().first():
                # Set dedup key and skip
                await self.redis.setex(dedup_key, self.DEDUP_TTL, "1")
                continue

            # Create new job
            job = Job(
                linkedin_job_id=linkedin_job_id,
                title=job_data.get("title"),
                company=job_data.get("company"),
                location=job_data.get("location"),
                job_url=job_data.get("job_url"),
                easy_apply=job_data.get("easy_apply", False),
                search_profile_id=search_profile_id,
                user_id=user_id,
                status="discovered"
            )

            self.db.add(job)

            # Set dedup key
            await self.redis.setex(dedup_key, self.DEDUP_TTL, "1")

            new_jobs_count += 1

        # Commit all jobs
        await self.db.commit()

        return new_jobs_count

    async def _update_task_status(
        self,
        task_id: str,
        status: str,
        message: str = None,
        jobs_found: int = None
    ):
        """Update task status in Redis.

        Args:
            task_id: Task identifier
            status: New status
            message: Status message
            jobs_found: Number of jobs found
        """
        task_key = f"{self.TASK_STATUS_PREFIX}:{task_id}"
        existing = await self.redis.get(task_key)

        if existing:
            task_data = json.loads(existing)
            task_data["status"] = status
            task_data["updated_at"] = datetime.utcnow().isoformat()

            if message:
                task_data["message"] = message
            if jobs_found is not None:
                task_data["jobs_found"] = jobs_found
            if status in ("completed", "failed"):
                task_data["completed_at"] = datetime.utcnow().isoformat()

            await self.redis.setex(
                task_key,
                3600,  # 1 hour TTL
                json.dumps(task_data)
            )
