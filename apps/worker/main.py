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
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from utils.logger import get_logger, setup_logging
from tasks.job_search_task import JobSearchTask

# Setup structured logging
setup_logging()
logger = get_logger(__name__)


class Worker:
    """Background worker for LinkedIn automation tasks.

    Listens for tasks from Redis queue and executes them.
    """

    # Redis key for job search task queue
    TASK_QUEUE_KEY = "li_autopilot:tasks:job_search"

    # Polling interval in seconds
    POLL_INTERVAL = 1

    def __init__(self):
        """Initialize worker."""
        self.redis: Optional[redis.Redis] = None
        self.db_engine = None
        self.db_session_factory = None
        self.running = False

    async def start(self):
        """Start the worker."""
        logger.info(
            "Starting worker service",
            extra={
                "action": "start_worker",
                "status": "in_progress"
            }
        )

        # Connect to Redis
        self.redis = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )

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
                # Blocking pop from queue with timeout
                result = await self.redis.brpop(
                    self.TASK_QUEUE_KEY,
                    timeout=self.POLL_INTERVAL
                )

                if result:
                    _, task_json = result
                    task_data = json.loads(task_json)

                    # Process task in background
                    asyncio.create_task(
                        self.handle_task(task_data)
                    )

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
        """Handle a single task.

        Args:
            task_data: Task data dictionary with:
                - task_id: Unique task identifier
                - user_id: User ID
                - search_profile_id: Search profile ID
        """
        task_id = task_data.get("task_id")
        user_id = task_data.get("user_id")
        search_profile_id = task_data.get("search_profile_id")

        logger.info(
            "Processing task",
            extra={
                "user_id": user_id,
                "action": "handle_task",
                "status": "started",
                "task_id": task_id,
                "search_profile_id": search_profile_id
            }
        )

        try:
            async with self.db_session_factory() as session:
                task_handler = JobSearchTask(self.redis, session)
                result = await task_handler.execute(
                    task_id=task_id,
                    user_id=user_id,
                    search_profile_id=search_profile_id
                )

                logger.info(
                    "Task completed",
                    extra={
                        "user_id": user_id,
                        "action": "handle_task",
                        "status": result.get("status"),
                        "task_id": task_id,
                        "result": result
                    }
                )

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
