import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
import redis.asyncio as redis

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueueService:
    """Redis-based queue service for task management.

    Key format: li_autopilot:{service}:{entity}:{identifier}
    """

    # Redis key prefixes following AGENTS.md convention
    TASK_QUEUE_KEY = "li_autopilot:tasks:job_search"
    TASK_STATUS_PREFIX = "li_autopilot:api:task_status"
    JOB_SEARCH_CACHE_PREFIX = "li_autopilot:api:job_search"

    # TTL values
    TASK_STATUS_TTL = 3600  # 1 hour
    CACHE_TTL = 86400  # 24 hours

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    @classmethod
    async def create(cls) -> "QueueService":
        """Factory method to create QueueService with Redis connection."""
        redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        return cls(redis_client)

    async def close(self):
        """Close Redis connection."""
        await self.redis.close()

    async def enqueue_job_search(
        self,
        user_id: str,
        search_profile_id: str
    ) -> str:
        """Enqueue a job search task.

        Args:
            user_id: User ID requesting the search
            search_profile_id: Search profile ID to search for

        Returns:
            task_id: Unique task identifier for tracking
        """
        task_id = str(uuid.uuid4())

        # Create task payload
        task_payload = {
            "task_id": task_id,
            "user_id": user_id,
            "search_profile_id": search_profile_id,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Store initial task status
        task_status_key = f"{self.TASK_STATUS_PREFIX}:{task_id}"
        await self.redis.setex(
            task_status_key,
            self.TASK_STATUS_TTL,
            json.dumps(task_payload)
        )

        # Enqueue task
        await self.redis.rpush(
            self.TASK_QUEUE_KEY,
            json.dumps({
                "task_id": task_id,
                "user_id": user_id,
                "search_profile_id": search_profile_id
            })
        )

        logger.info(
            "Job search task enqueued",
            extra={
                "user_id": user_id,
                "action": "enqueue_job_search",
                "status": "success",
                "task_id": task_id,
                "search_profile_id": search_profile_id
            }
        )

        return task_id

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status by task ID.

        Args:
            task_id: Task identifier

        Returns:
            Task status dict or None if not found
        """
        task_status_key = f"{self.TASK_STATUS_PREFIX}:{task_id}"
        status_json = await self.redis.get(task_status_key)

        if status_json:
            return json.loads(status_json)
        return None

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        message: Optional[str] = None,
        jobs_found: Optional[int] = None
    ):
        """Update task status.

        Args:
            task_id: Task identifier
            status: New status (queued, running, completed, failed)
            message: Optional status message
            jobs_found: Number of jobs found (if completed)
        """
        task_status_key = f"{self.TASK_STATUS_PREFIX}:{task_id}"
        existing = await self.get_task_status(task_id)

        if existing:
            existing["status"] = status
            existing["updated_at"] = datetime.utcnow().isoformat()

            if message:
                existing["message"] = message
            if jobs_found is not None:
                existing["jobs_found"] = jobs_found
            if status in ("completed", "failed"):
                existing["completed_at"] = datetime.utcnow().isoformat()

            await self.redis.setex(
                task_status_key,
                self.TASK_STATUS_TTL,
                json.dumps(existing)
            )

    async def cache_job_search(
        self,
        search_profile_id: str,
        jobs: list,
        ttl: int = None
    ):
        """Cache job search results.

        Args:
            search_profile_id: Search profile ID
            jobs: List of job dictionaries
            ttl: Cache TTL in seconds (default 24h)
        """
        cache_key = f"{self.JOB_SEARCH_CACHE_PREFIX}:{search_profile_id}"
        ttl = ttl or self.CACHE_TTL

        await self.redis.setex(
            cache_key,
            ttl,
            json.dumps(jobs)
        )

        logger.info(
            "Job search results cached",
            extra={
                "action": "cache_job_search",
                "status": "success",
                "search_profile_id": search_profile_id,
                "jobs_count": len(jobs),
                "ttl": ttl
            }
        )

    async def get_cached_job_search(
        self,
        search_profile_id: str
    ) -> Optional[list]:
        """Get cached job search results.

        Args:
            search_profile_id: Search profile ID

        Returns:
            List of cached jobs or None if not cached
        """
        cache_key = f"{self.JOB_SEARCH_CACHE_PREFIX}:{search_profile_id}"
        cached = await self.redis.get(cache_key)

        if cached:
            return json.loads(cached)
        return None


# Dependency for FastAPI
async def get_queue_service() -> QueueService:
    """FastAPI dependency for QueueService."""
    service = await QueueService.create()
    try:
        yield service
    finally:
        await service.close()
