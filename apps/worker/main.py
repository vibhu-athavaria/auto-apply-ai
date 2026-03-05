"""Worker service entry point.

This is the main entry point for the LinkedIn Autopilot Worker service.
The worker:
- Connects to Redis for task queue
- Connects to PostgreSQL for data storage
- Listens for job search tasks
- Executes browser automation using Playwright

CRITICAL: Worker must NOT expose HTTP endpoints (per AGENTS.md).
"""
import asyncio
import json
import signal
import sys
from typing import Optional

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from utils.logger import get_logger, setup_logging
from tasks.job_search_task import JobSearchTask
from tasks.application_task import ApplicationTask, ApplicationTaskError
from tasks.linkedin_auth_task import LinkedInAuthTask
from utils.rate_limiter import RateLimiter

# Setup structured logging
setup_logging()
logger = get_logger(__name__)


class Worker:
    """Background worker for LinkedIn automation tasks.

    Listens for tasks from Redis queue and executes them.
    """

    JOB_SEARCH_QUEUE = "li_autopilot:tasks:job_search"
    APPLICATION_QUEUE = "li_autopilot:worker:queue:applications"
    AUTH_QUEUE = "li_autopilot:tasks:linkedin_auth"
    POLL_INTERVAL = 1
    REDIS_CONNECT_MAX_RETRIES = 10
    REDIS_CONNECT_BASE_DELAY = 1.0

    def __init__(self):
        """Initialize worker."""
        self.redis: Optional[redis.Redis] = None
        self.db_engine = None
        self.db_session_factory = None
        self.running = False

    async def _connect_redis_with_retry(self) -> redis.Redis:
        """Connect to Redis with retry logic and health check.

        Retries with exponential backoff until Redis is available.
        Performs a ping check to verify the connection is working.

        Returns:
            redis.Redis: Verified Redis connection

        Raises:
            RedisConnectionError: If max retries exceeded
        """
        logger.info(
            "Connecting to Redis",
            extra={
                "action": "connect_redis",
                "status": "in_progress",
                "redis_url": settings.redis_url.replace("@", "***@"),  # Hide creds
                "max_retries": self.REDIS_CONNECT_MAX_RETRIES
            }
        )

        last_exception = None

        for attempt in range(self.REDIS_CONNECT_MAX_RETRIES):
            try:
                # Create Redis connection with socket timeout
                client = redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30
                )

                # Verify connection with ping - this forces actual connection
                await client.ping()

                logger.info(
                    "Redis connection established",
                    extra={
                        "action": "connect_redis",
                        "status": "success",
                        "attempt": attempt + 1
                    }
                )

                return client

            except RedisConnectionError as e:
                last_exception = e
                delay = self.REDIS_CONNECT_BASE_DELAY * (2 ** attempt)

                if attempt < self.REDIS_CONNECT_MAX_RETRIES - 1:
                    logger.warning(
                        f"Redis connection attempt {attempt + 1}/{self.REDIS_CONNECT_MAX_RETRIES} failed: {e}",
                        extra={
                            "action": "connect_redis",
                            "status": "retrying",
                            "attempt": attempt + 1,
                            "max_retries": self.REDIS_CONNECT_MAX_RETRIES,
                            "delay": delay,
                            "error": str(e)
                        }
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Max Redis connection retries ({self.REDIS_CONNECT_MAX_RETRIES}) exceeded",
                        extra={
                            "action": "connect_redis",
                            "status": "failed",
                            "max_retries": self.REDIS_CONNECT_MAX_RETRIES,
                            "error": str(e)
                        }
                    )
                    raise RedisConnectionError(
                        f"Failed to connect to Redis after {self.REDIS_CONNECT_MAX_RETRIES} attempts. "
                        f"Last error: {e}"
                    ) from e

            except Exception as e:
                last_exception = e
                logger.error(
                    f"Unexpected error connecting to Redis: {e}",
                    extra={
                        "action": "connect_redis",
                        "status": "error",
                        "attempt": attempt + 1,
                        "error": str(e)
                    }
                )
                raise

    async def start(self):
        """Start the worker."""
        logger.info(
            "Starting worker service",
            extra={
                "action": "start_worker",
                "status": "in_progress"
            }
        )

        # Connect to Redis with retry logic and health check
        self.redis = await self._connect_redis_with_retry()

        # Connect to database
        self.db_engine = create_async_engine(settings.database_url, echo=False)
        self.db_session_factory = sessionmaker(
            self.db_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        self.running = True

        logger.info(
            "Worker service started",
            extra={
                "action": "start_worker",
                "status": "success"
            }
        )

        # Start processing tasks
        await self.process_tasks()

    async def stop(self):
        """Stop the worker gracefully."""
        logger.info(
            "Stopping worker service",
            extra={
                "action": "stop_worker",
                "status": "in_progress"
            }
        )

        self.running = False

        if self.redis:
            await self.redis.close()

        if self.db_engine:
            await self.db_engine.dispose()

        logger.info(
            "Worker service stopped",
            extra={
                "action": "stop_worker",
                "status": "success"
            }
        )

    async def process_tasks(self):
        """Main task processing loop."""
        logger.info(
            "Starting task processing loop",
            extra={
                "action": "process_tasks",
                "status": "started"
            }
        )

        while self.running:
            try:
                # Block on both queues with timeout
                result = await self.redis.brpop(
                    [self.JOB_SEARCH_QUEUE, self.APPLICATION_QUEUE, self.AUTH_QUEUE],
                    timeout=self.POLL_INTERVAL
                )

                if result:
                    queue_key, task_json = result
                    task_data = json.loads(task_json)
                    task_data["_queue"] = queue_key

                    asyncio.create_task(self.handle_task(task_data))

            except redis.ConnectionError as e:
                logger.error(
                    f"Redis connection error: {e}",
                    extra={
                        "action": "process_tasks",
                        "status": "error",
                        "error": str(e)
                    }
                )
                await asyncio.sleep(5)  # Wait before retrying

            except Exception as e:
                logger.error(
                    f"Error processing tasks: {e}",
                    extra={
                        "action": "process_tasks",
                        "status": "error",
                        "error": str(e)
                    }
                )
                await asyncio.sleep(1)

    async def handle_task(self, task_data: dict):
        """Dispatch task to appropriate handler based on queue."""
        queue = task_data.get("_queue", self.JOB_SEARCH_QUEUE)
        task_id = task_data.get("task_id")
        user_id = task_data.get("user_id")

        logger.info(
            "Processing task",
            extra={
                "user_id": user_id,
                "action": "handle_task",
                "status": "started",
                "task_id": task_id,
                "queue": queue
            }
        )

        try:
            async with self.db_session_factory() as session:
                if queue == self.APPLICATION_QUEUE:
                    await self._handle_application_task(task_data, session)
                elif queue == self.AUTH_QUEUE:
                    await self._handle_linkedin_auth_task(task_data, session)
                else:
                    await self._handle_job_search_task(task_data, session)

        except Exception as e:
            logger.error(
                f"Task failed: {e}",
                extra={
                    "user_id": user_id,
                    "action": "handle_task",
                    "status": "error",
                    "task_id": task_id,
                    "error": str(e)
                }
            )

    async def _handle_job_search_task(self, task_data: dict, session):
        task_id = task_data.get("task_id")
        user_id = task_data.get("user_id")
        search_profile_id = task_data.get("search_profile_id")

        task_handler = JobSearchTask(self.redis, session)
        result = await task_handler.execute(
            task_id=task_id,
            user_id=user_id,
            search_profile_id=search_profile_id
        )

        logger.info(
            "Job search task completed",
            extra={
                "user_id": user_id,
                "action": "handle_job_search_task",
                "status": result.get("status"),
                "task_id": task_id,
            }
        )

    async def _handle_linkedin_auth_task(self, task_data: dict, session):
        auth_task = LinkedInAuthTask(self.redis, session)
        await auth_task.execute(task_data)

    async def _handle_application_task(self, task_data: dict, session):
        user_id = task_data.get("user_id")
        job_id = task_data.get("job_id")
        job_url = task_data.get("job_url")
        resume_path = task_data.get("resume_path")
        task_id = task_data.get("task_id")

        rate_limiter = RateLimiter(self.redis)
        app_task = ApplicationTask(session, self.redis, rate_limiter)

        try:
            result = await app_task.process_application(
                user_id=user_id,
                job_id=job_id,
                job_url=job_url,
                resume_path=resume_path
            )

            logger.info(
                "Application task completed",
                extra={
                    "user_id": user_id,
                    "action": "handle_application_task",
                    "status": "success",
                    "task_id": task_id,
                    "job_id": job_id,
                }
            )

        except ApplicationTaskError as e:
            logger.error(
                f"Application task failed: {e}",
                extra={
                    "user_id": user_id,
                    "action": "handle_application_task",
                    "status": "failed",
                    "task_id": task_id,
                    "job_id": job_id,
                    "error": str(e)
                }
            )
            await app_task.update_task_status(task_id, "failed", error=str(e))


async def main():
    """Main entry point."""
    worker = Worker()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(worker.stop())

    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await worker.start()
    except KeyboardInterrupt:
        pass
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
