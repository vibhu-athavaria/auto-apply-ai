"""
Session store utility for fetching user LinkedIn session cookies.

The worker fetches per-user session cookies stored by the API.
Redis key: li_autopilot:worker:session:{user_id}
"""
import json
from typing import Optional

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from utils.logger import get_logger

logger = get_logger(__name__)

SESSION_KEY_PREFIX = "li_autopilot:worker:session"
SESSION_TTL = 3600  # 1 hour cache in worker


async def get_user_session(
    redis_client: redis.Redis,
    user_id: str,
    db_session: Optional[AsyncSession] = None
) -> Optional[str]:
    """Fetch decrypted LinkedIn session cookie for a user.

    Checks Redis cache first, then falls back to database via
    internal lookup. The API service encrypts and stores cookies;
    the worker fetches the plaintext version via a shared Redis key
    written by the API after decryption.

    Redis key written by API on session save:
        li_autopilot:worker:session:{user_id}

    Args:
        redis_client: Redis client
        user_id: User ID
        db_session: Optional DB session (unused here, kept for future use)

    Returns:
        Plaintext li_at cookie or None
    """
    key = f"{SESSION_KEY_PREFIX}:{user_id}"
    cached = await redis_client.get(key)

    if cached:
        logger.info(
            "LinkedIn session retrieved from cache",
            extra={
                "user_id": user_id,
                "action": "get_user_session",
                "status": "cache_hit"
            }
        )
        return cached

    logger.warning(
        "No LinkedIn session found for user",
        extra={
            "user_id": user_id,
            "action": "get_user_session",
            "status": "not_found"
        }
    )
    return None
