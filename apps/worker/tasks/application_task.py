"""Application task for Easy Apply automation.

This task:
1. Checks rate limits before applying
2. Uses EasyApplyHandler for browser automation
3. Updates application status in database
4. Implements retry with exponential backoff
"""
import json
from datetime import datetime
from typing import Optional

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import settings
from automation.linkedin import LinkedInClient
from automation.easy_apply import (
    EasyApplyHandler,
    EasyApplyError,
    ApplicationNotFoundError,
    FormFillError,
    SubmissionError
)
from utils.logger import get_logger
from utils.rate_limiter import RateLimiter
from utils.backoff import retry_with_backoff, MaxRetriesExceededError
from utils.delays import search_delay

logger = get_logger(__name__)

QUEUE_KEY = "li_autopilot:worker:queue:applications"
TASK_KEY_PREFIX = "li_autopilot:worker:application_task"
DEDUP_KEY_PREFIX = "li_autopilot:worker:application_dedup"


class ApplicationTaskError(Exception):
    """Base exception for application task errors."""
    pass


class ApplicationTask:
    """Handles Easy Apply application workflow.

    This task is idempotent - it can be safely retried without
    creating duplicate applications.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        rate_limiter: RateLimiter
    ):
        self.db = db_session
        self.redis = redis_client
        self.rate_limiter = rate_limiter

    async def create_application(
        self,
        user_id: str,
        job_id: str,
        tailored_resume_id: Optional[str] = None
    ) -> dict:
        """Create a pending application and enqueue the task.

        Args:
            user_id: User ID
            job_id: Job ID to apply to
            tailored_resume_id: Optional tailored resume ID

        Returns:
            dict with task_id and status
        """
        dedup_key = f"{DEDUP_KEY_PREFIX}:{user_id}:{job_id}"
        existing = await self.redis.get(dedup_key)
        if existing:
            logger.info(
                "Application already queued/processed",
                extra={
                    "user_id": user_id,
                    "job_id": job_id,
                    "action": "create_application",
                    "status": "duplicate"
                }
            )
            return json.loads(existing)

        task_id = f"app_{user_id}_{job_id}_{datetime.utcnow().timestamp()}"
        task_data = {
            "task_id": task_id,
            "user_id": user_id,
            "job_id": job_id,
            "tailored_resume_id": tailored_resume_id,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "error": None
        }

        await self.redis.setex(
            dedup_key,
            86400,
            json.dumps({"task_id": task_id, "status": "pending"})
        )

        task_key = f"{TASK_KEY_PREFIX}:{task_id}"
        await self.redis.setex(
            task_key,
            86400,
            json.dumps(task_data)
        )

        await self.redis.rpush(QUEUE_KEY, json.dumps(task_data))

        logger.info(
            "Application task queued",
            extra={
                "user_id": user_id,
                "job_id": job_id,
                "task_id": task_id,
                "action": "create_application",
                "status": "queued"
            }
        )

        return task_data

    async def process_application(
        self,
        user_id: str,
        job_id: str,
        job_url: str,
        resume_path: Optional[str] = None,
        session_cookie: Optional[str] = None
    ) -> dict:
        """Process an application with rate limiting and retry.

        Args:
            user_id: User ID
            job_id: Job ID
            job_url: LinkedIn job URL
            resume_path: Path to resume file
            session_cookie: LinkedIn session cookie

        Returns:
            dict with application result
        """
        if not await self.rate_limiter.check_application_limit(user_id):
            raise ApplicationTaskError(
                f"Daily application limit exceeded for user {user_id}"
            )

        try:
            result = await self._apply_with_retry(
                user_id=user_id,
                job_id=job_id,
                job_url=job_url,
                resume_path=resume_path,
                session_cookie=session_cookie
            )

            await search_delay()

            return result

        except MaxRetriesExceededError as e:
            logger.error(
                f"Application failed after retries: {e}",
                extra={
                    "user_id": user_id,
                    "job_id": job_id,
                    "action": "process_application",
                    "error": str(e),
                    "status": "failed"
                }
            )
            raise ApplicationTaskError(str(e)) from e

    @retry_with_backoff(exceptions=(EasyApplyError,), max_retries=3)
    async def _apply_with_retry(
        self,
        user_id: str,
        job_id: str,
        job_url: str,
        resume_path: Optional[str],
        session_cookie: Optional[str]
    ) -> dict:
        """Apply to job with retry logic.

        This method is decorated with retry_with_backoff for
        transient failures.
        """
        async with LinkedInClient(session_cookie) as client:
            handler = EasyApplyHandler(client.page)

            result = await handler.apply_to_job(
                job_url=job_url,
                resume_path=resume_path
            )

            result["user_id"] = user_id
            result["job_id"] = job_id
            result["applied_at"] = datetime.utcnow().isoformat()

            return result

    async def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get status of an application task.

        Args:
            task_id: Task ID to check

        Returns:
            Task status dict or None if not found
        """
        task_key = f"{TASK_KEY_PREFIX}:{task_id}"
        task_data = await self.redis.get(task_key)

        if task_data:
            return json.loads(task_data)

        return None

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        error: Optional[str] = None
    ) -> None:
        """Update task status.

        Args:
            task_id: Task ID to update
            status: New status
            error: Optional error message
        """
        task_key = f"{TASK_KEY_PREFIX}:{task_id}"
        task_data = await self.redis.get(task_key)

        if task_data:
            data = json.loads(task_data)
            data["status"] = status
            data["updated_at"] = datetime.utcnow().isoformat()
            if error:
                data["error"] = error

            await self.redis.setex(task_key, 86400, json.dumps(data))

            logger.info(
                "Task status updated",
                extra={
                    "task_id": task_id,
                    "status": status,
                    "action": "update_task_status"
                }
            )

    async def skip_application(
        self,
        user_id: str,
        job_id: str,
        reason: str
    ) -> dict:
        """Mark an application as skipped.

        Args:
            user_id: User ID
            job_id: Job ID
            reason: Reason for skipping

        Returns:
            dict with skip result
        """
        dedup_key = f"{DEDUP_KEY_PREFIX}:{user_id}:{job_id}"

        await self.redis.setex(
            dedup_key,
            86400,
            json.dumps({"status": "skipped", "reason": reason})
        )

        logger.info(
            "Application skipped",
            extra={
                "user_id": user_id,
                "job_id": job_id,
                "reason": reason,
                "action": "skip_application",
                "status": "skipped"
            }
        )

        return {
            "user_id": user_id,
            "job_id": job_id,
            "status": "skipped",
            "reason": reason
        }
