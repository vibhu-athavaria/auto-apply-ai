"""Periodic task scheduler for LinkedIn Autopilot.

This module implements a lightweight scheduler that runs alongside
the worker to trigger periodic tasks like daily job searches.

It uses Redis to store schedule state and coordinates with the
existing worker task queue.
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from config import settings
from models.job_search_profile import JobSearchProfile
from models.linkedin_session import LinkedInSession
from utils.logger import get_logger

logger = get_logger(__name__)

# Redis keys for scheduler state
SCHEDULER_LAST_RUN_KEY = "li_autopilot:scheduler:last_run"
SCHEDULER_LOCK_KEY = "li_autopilot:scheduler:lock"
SCHEDULER_LOCK_TTL = 3600  # 1 hour lock


class JobSearchScheduler:
    """Scheduler for periodic job search tasks.

    Runs daily and enqueues job search tasks for all active search profiles
    that have a valid LinkedIn session.
    """

    def __init__(self, redis_client: redis.Redis):
        """Initialize scheduler.

        Args:
            redis_client: Redis client for coordination and queue
        """
        self.redis = redis_client
        self.db_engine = create_async_engine(settings.database_url, echo=False)
        self.db_session_factory = sessionmaker(
            self.db_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        self.running = False

    async def start(self):
        """Start the scheduler loop."""
        logger.info(
            "Starting job search scheduler",
            extra={"action": "scheduler_start", "status": "in_progress"}
        )

        self.running = True

        logger.info(
            "Job search scheduler started",
            extra={"action": "scheduler_start", "status": "success"}
        )

        # Main scheduler loop
        while self.running:
            try:
                await self._run_scheduler_cycle()
            except Exception as e:
                logger.error(
                    f"Scheduler cycle error: {e}",
                    extra={"action": "scheduler_cycle", "status": "error", "error": str(e)}
                )

            # Check every minute
            await asyncio.sleep(60)

    async def stop(self):
        """Stop the scheduler gracefully."""
        logger.info(
            "Stopping job search scheduler",
            extra={"action": "scheduler_stop", "status": "in_progress"}
        )

        self.running = False

        logger.info(
            "Job search scheduler stopped",
            extra={"action": "scheduler_stop", "status": "success"}
        )

    async def _run_scheduler_cycle(self):
        """Run one scheduler cycle - check if it's time to run daily searches."""
        now = datetime.utcnow()

        # Check if we should run today (run at 9 AM UTC daily)
        last_run_str = await self.redis.get(SCHEDULER_LAST_RUN_KEY)

        if last_run_str:
            last_run = datetime.fromisoformat(last_run_str)
            # Only run once per day
            if last_run.date() == now.date():
                return

        # Try to acquire lock to prevent multiple schedulers from running
        lock_acquired = await self.redis.set(
            SCHEDULER_LOCK_KEY,
            "1",
            nx=True,  # Only set if not exists
            ex=SCHEDULER_LOCK_TTL
        )

        if not lock_acquired:
            logger.debug(
                "Scheduler lock not acquired, another instance is running",
                extra={"action": "scheduler_lock", "status": "busy"}
            )
            return

        try:
            await self._enqueue_daily_searches()

            # Update last run time
            await self.redis.set(SCHEDULER_LAST_RUN_KEY, now.isoformat())

        finally:
            # Release lock
            await self.redis.delete(SCHEDULER_LOCK_KEY)

    async def _enqueue_daily_searches(self):
        """Enqueue job search tasks for all active profiles."""
        logger.info(
            "Starting daily job search enqueue",
            extra={"action": "daily_search", "status": "started"}
        )

        async with self.db_session_factory() as db:
            # Get all search profiles
            result = await db.execute(select(JobSearchProfile))
            profiles = result.scalars().all()

            enqueued_count = 0
            skipped_count = 0

            for profile in profiles:
                # Check if user has valid LinkedIn session
                has_session = await self._check_linkedin_session(db, profile.user_id)

                if not has_session:
                    logger.warning(
                        f"Skipping profile {profile.id}: No valid LinkedIn session",
                        extra={
                            "user_id": profile.user_id,
                            "profile_id": profile.id,
                            "action": "daily_search_skip",
                            "reason": "no_session"
                        }
                    )
                    skipped_count += 1
                    continue

                # Check if we already ran today for this profile
                profile_last_run_key = f"li_autopilot:scheduler:profile:{profile.id}:last_run"
                profile_last_run = await self.redis.get(profile_last_run_key)

                if profile_last_run:
                    last_run = datetime.fromisoformat(profile_last_run)
                    if last_run.date() == datetime.utcnow().date():
                        logger.debug(
                            f"Skipping profile {profile.id}: Already ran today",
                            extra={
                                "user_id": profile.user_id,
                                "profile_id": profile.id,
                                "action": "daily_search_skip",
                                "reason": "already_ran"
                            }
                        )
                        skipped_count += 1
                        continue

                # Enqueue job search task
                await self._enqueue_job_search(profile)
                enqueued_count += 1

                # Update profile last run time
                await self.redis.set(
                    profile_last_run_key,
                    datetime.utcnow().isoformat(),
                    ex=86400 * 2  # Keep for 2 days
                )

            logger.info(
                f"Daily job search enqueue complete: {enqueued_count} enqueued, {skipped_count} skipped",
                extra={
                    "action": "daily_search",
                    "status": "completed",
                    "enqueued": enqueued_count,
                    "skipped": skipped_count
                }
            )

    async def _check_linkedin_session(
        self,
        db: AsyncSession,
        user_id: str
    ) -> bool:
        """Check if user has a valid LinkedIn session.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            True if valid session exists
        """
        from models.linkedin_session import LinkedInSession

        result = await db.execute(
            select(LinkedInSession)
            .where(LinkedInSession.user_id == user_id)
            .where(LinkedInSession.is_valid == True)
        )
        session = result.scalars().first()

        if not session:
            return False

        # Check if session is expired
        if session.expires_at and session.expires_at < datetime.utcnow():
            return False

        return True

    async def _enqueue_job_search(self, profile: JobSearchProfile):
        """Enqueue a job search task for a profile.

        Args:
            profile: Job search profile
        """
        task_id = f"scheduled_{datetime.utcnow().strftime('%Y%m%d')}_{profile.id}"

        task_data = {
            "task_id": task_id,
            "user_id": profile.user_id,
            "search_profile_id": profile.id,
            "type": "job_search",
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
            "scheduled": True,
            "message": f"Daily scheduled search for '{profile.keywords}' in {profile.location}"
        }

        # Store task status
        task_key = f"li_autopilot:api:task_status:{task_id}"
        await self.redis.setex(
            task_key,
            86400,  # 24 hour TTL
            json.dumps(task_data)
        )

        # Add to job search queue
        queue_key = "li_autopilot:tasks:job_search"
        await self.redis.rpush(queue_key, json.dumps({
            "task_id": task_id,
            "user_id": profile.user_id,
            "search_profile_id": profile.id
        }))

        logger.info(
            f"Enqueued daily job search for profile {profile.id}",
            extra={
                "user_id": profile.user_id,
                "profile_id": profile.id,
                "task_id": task_id,
                "action": "enqueue_daily_search",
                "status": "success"
            }
        )


async def run_scheduler():
    """Entry point for running the scheduler."""
    redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True
    )

    scheduler = JobSearchScheduler(redis_client)

    try:
        await scheduler.start()
    except asyncio.CancelledError:
        await scheduler.stop()
    except Exception as e:
        logger.error(
            f"Scheduler fatal error: {e}",
            extra={"action": "scheduler_fatal", "error": str(e)}
        )
        raise


if __name__ == "__main__":
    asyncio.run(run_scheduler())
