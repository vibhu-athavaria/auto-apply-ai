"""Per-user rate limiting using Redis.

This module enforces per-user rate limits to prevent abuse and detection.
"""
import redis.asyncio as redis

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Per-user rate limiting using Redis counters.

    Key format: li_autopilot:worker:rate_limit:{user_id}:{action_type}
    """

    # Redis key prefix following AGENTS.md convention
    RATE_LIMIT_PREFIX = "li_autopilot:worker:rate_limit"

    # Default limits
    DAILY_SEARCH_LIMIT = 50
    DAILY_APPLICATION_LIMIT = 20

    # TTL for rate limit keys (24 hours in seconds)
    DAILY_TTL = 86400

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    @classmethod
    async def create(cls, redis_url: str) -> "RateLimiter":
        """Factory method to create RateLimiter with Redis connection."""
        redis_client = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        return cls(redis_client)

    async def close(self):
        """Close Redis connection."""
        await self.redis.close()

    async def check_search_limit(self, user_id: str) -> bool:
        """Check if user can perform a search.

        Args:
            user_id: User ID to check

        Returns:
            True if user is within limits, False if limit exceeded
        """
        key = f"{self.RATE_LIMIT_PREFIX}:{user_id}:searches"
        count = await self.redis.incr(key)

        # Set expiry on first increment
        if count == 1:
            await self.redis.expire(key, self.DAILY_TTL)

        limit = settings.daily_search_limit or self.DAILY_SEARCH_LIMIT

        if count > limit:
            logger.warning(
                "Search rate limit exceeded",
                extra={
                    "user_id": user_id,
                    "action": "check_search_limit",
                    "status": "rate_limited",
                    "count": count,
                    "limit": limit
                }
            )
            return False

        logger.info(
            "Search rate check passed",
            extra={
                "user_id": user_id,
                "action": "check_search_limit",
                "status": "success",
                "count": count,
                "limit": limit
            }
        )
        return True

    async def check_application_limit(self, user_id: str) -> bool:
        """Check if user can submit an application.

        Args:
            user_id: User ID to check

        Returns:
            True if user is within limits, False if limit exceeded
        """
        key = f"{self.RATE_LIMIT_PREFIX}:{user_id}:applications"
        count = await self.redis.incr(key)

        # Set expiry on first increment
        if count == 1:
            await self.redis.expire(key, self.DAILY_TTL)

        limit = settings.daily_application_limit or self.DAILY_APPLICATION_LIMIT

        if count > limit:
            logger.warning(
                "Application rate limit exceeded",
                extra={
                    "user_id": user_id,
                    "action": "check_application_limit",
                    "status": "rate_limited",
                    "count": count,
                    "limit": limit
                }
            )
            return False

        logger.info(
            "Application rate check passed",
            extra={
                "user_id": user_id,
                "action": "check_application_limit",
                "status": "success",
                "count": count,
                "limit": limit
            }
        )
        return True

    async def get_search_count(self, user_id: str) -> int:
        """Get current search count for user.

        Args:
            user_id: User ID to check

        Returns:
            Current search count
        """
        key = f"{self.RATE_LIMIT_PREFIX}:{user_id}:searches"
        count = await self.redis.get(key)
        return int(count) if count else 0

    async def get_application_count(self, user_id: str) -> int:
        """Get current application count for user.

        Args:
            user_id: User ID to check

        Returns:
            Current application count
        """
        key = f"{self.RATE_LIMIT_PREFIX}:{user_id}:applications"
        count = await self.redis.get(key)
        return int(count) if count else 0

    async def reset_limits(self, user_id: str) -> None:
        """Reset rate limits for a user.

        Args:
            user_id: User ID to reset
        """
        search_key = f"{self.RATE_LIMIT_PREFIX}:{user_id}:searches"
        app_key = f"{self.RATE_LIMIT_PREFIX}:{user_id}:applications"

        await self.redis.delete(search_key, app_key)

        logger.info(
            "Rate limits reset",
            extra={
                "user_id": user_id,
                "action": "reset_limits",
                "status": "success"
            }
        )
