"""
Session store utility for fetching user LinkedIn session cookies.

The worker fetches per-user session cookies stored by the API.
Primary: Redis cache (li_autopilot:worker:session:{user_id})
Fallback: Database (encrypted, decrypted on-the-fly)
"""
import base64
from typing import Optional

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from cryptography.fernet import Fernet

from models.linkedin_session import LinkedInSession
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

SESSION_KEY_PREFIX = "li_autopilot:worker:session"
SESSION_TTL = 86400  # 24 hours cache in worker


def _get_cipher() -> Fernet:
    """Get Fernet cipher for decryption."""
    raw_key = settings.secret_key.encode()[:32]
    padded = raw_key.ljust(32, b'0')[:32]
    return Fernet(base64.urlsafe_b64encode(padded))


async def get_user_session(
    redis_client: redis.Redis,
    user_id: str,
    db_session: Optional[AsyncSession] = None
) -> Optional[str]:
    """Fetch decrypted LinkedIn session cookie for a user.

    Checks Redis cache first, then falls back to database if not found.
    If found in DB, re-caches to Redis for future use.

    Args:
        redis_client: Redis client
        user_id: User ID
        db_session: Database session for fallback lookup

    Returns:
        Plaintext li_at cookie or None
    """
    key = f"{SESSION_KEY_PREFIX}:{user_id}"
    cached = await redis_client.get(key)

    if cached:
        logger.info(
            "LinkedIn session retrieved from Redis cache",
            extra={
                "user_id": user_id,
                "action": "get_user_session",
                "status": "cache_hit"
            }
        )
        return cached

    if not db_session:
        logger.warning(
            "No LinkedIn session in Redis and no DB session provided",
            extra={
                "user_id": user_id,
                "action": "get_user_session",
                "status": "no_db_fallback"
            }
        )
        return None

    logger.info(
        "LinkedIn session not in Redis, checking database",
        extra={
            "user_id": user_id,
            "action": "get_user_session",
            "status": "db_lookup"
        }
    )

    result = await db_session.execute(
        select(LinkedInSession).where(LinkedInSession.user_id == user_id)
    )
    session = result.scalars().first()

    if not session:
        logger.warning(
            "No LinkedIn session found in database",
            extra={
                "user_id": user_id,
                "action": "get_user_session",
                "status": "not_found"
            }
        )
        return None

    if session.status != "connected":
        logger.warning(
            f"LinkedIn session status is '{session.status}'",
            extra={
                "user_id": user_id,
                "action": "get_user_session",
                "status": "invalid_status",
                "session_status": session.status
            }
        )
        return None

    try:
        cipher = _get_cipher()
        decrypted = cipher.decrypt(session.encrypted_cookie.encode()).decode()

        await redis_client.setex(key, SESSION_TTL, decrypted)

        logger.info(
            "LinkedIn session retrieved from DB and cached to Redis",
            extra={
                "user_id": user_id,
                "action": "get_user_session",
                "status": "db_fallback_success"
            }
        )

        return decrypted

    except Exception as e:
        logger.error(
            f"Failed to decrypt LinkedIn session: {e}",
            extra={
                "user_id": user_id,
                "action": "get_user_session",
                "status": "decrypt_error",
                "error": str(e)
            }
        )
        return None
