"""LinkedIn authentication task for the worker.

Handles the linkedin_auth queue messages.
Runs Playwright login, extracts li_at, stores it.
The password is used once and NEVER stored.
"""
import json
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import base64
from cryptography.fernet import Fernet

from automation.linkedin_auth import (
    LinkedInAuthenticator,
    LinkedInAuthError,
    LinkedInChallengeRequired,
    LinkedInInvalidCredentials,
)
from models.linkedin_session import LinkedInSession
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

AUTH_TASK_KEY_PREFIX = "li_autopilot:api:auth_task"
WORKER_SESSION_KEY_PREFIX = "li_autopilot:worker:session"
WORKER_SESSION_TTL = 86400


class LinkedInAuthTask:
    """Handles LinkedIn credential-based login in the worker.

    Flow:
    1. Receive email + password from queue
    2. Launch Playwright, navigate to linkedin.com/login
    3. Fill credentials, submit
    4. Extract li_at cookie
    5. Store encrypted cookie via DB session service
    6. Write plaintext to Redis for automation tasks
    7. Update task status key
    8. Password is discarded — never written to any store
    """

    def __init__(self, redis_client: aioredis.Redis, db_session: AsyncSession):
        self.redis = redis_client
        self.db = db_session

    async def execute(self, task_data: dict) -> None:
        """Execute LinkedIn auth task.

        Args:
            task_data: Must contain task_id, user_id, email, password
        """
        task_id = task_data["task_id"]
        user_id = task_data["user_id"]
        email = task_data["email"]
        password = task_data["password"]

        logger.info(
            "Starting LinkedIn auth task",
            extra={
                "user_id": user_id,
                "action": "linkedin_auth_task",
                "status": "started",
                "task_id": task_id,
            }
        )

        try:
            await self._update_task(task_id, "connecting", "Connecting to LinkedIn...")
            
            authenticator = LinkedInAuthenticator()
            li_at = await authenticator.login(email=email, password=password)

            await self._update_task(task_id, "saving", "Saving your session...")
            await self._store_session(user_id, li_at)
            
            await self._update_task(task_id, "connected", "LinkedIn connected successfully")

            logger.info(
                "LinkedIn auth task completed",
                extra={
                    "user_id": user_id,
                    "action": "linkedin_auth_task",
                    "status": "success",
                    "task_id": task_id,
                }
            )

        except LinkedInChallengeRequired as e:
            logger.warning(
                "LinkedIn challenge required",
                extra={
                    "user_id": user_id,
                    "action": "linkedin_auth_task",
                    "status": "challenge_required",
                    "task_id": task_id,
                }
            )
            await self._update_task(task_id, "challenge_required", str(e))

        except LinkedInInvalidCredentials as e:
            logger.error(
                "LinkedIn invalid credentials",
                extra={
                    "user_id": user_id,
                    "action": "linkedin_auth_task",
                    "status": "failed",
                    "task_id": task_id,
                }
            )
            await self._update_task(task_id, "failed", "Invalid email or password")

        except LinkedInAuthError as e:
            logger.error(
                f"LinkedIn auth error: {e}",
                extra={
                    "user_id": user_id,
                    "action": "linkedin_auth_task",
                    "status": "failed",
                    "task_id": task_id,
                    "error": str(e),
                }
            )
            await self._update_task(task_id, "failed", "Could not connect to LinkedIn")

        except Exception as e:
            logger.error(
                f"Unexpected auth error: {e}",
                extra={
                    "user_id": user_id,
                    "action": "linkedin_auth_task",
                    "status": "error",
                    "task_id": task_id,
                    "error": str(e),
                }
            )
            await self._update_task(task_id, "failed", f"Error: {str(e)}")

    async def _store_session(self, user_id: str, li_at: str) -> None:
        """Store the session cookie in Redis (for worker) and DB (encrypted).

        Args:
            user_id: User ID
            li_at: Plaintext li_at cookie (only cookie, not password)
        """
        worker_key = f"{WORKER_SESSION_KEY_PREFIX}:{user_id}"
        await self.redis.setex(worker_key, WORKER_SESSION_TTL, li_at)

        raw_key = settings.secret_key.encode()[:32]
        padded = raw_key.ljust(32, b'0')[:32]
        cipher = Fernet(base64.urlsafe_b64encode(padded))
        encrypted = cipher.encrypt(li_at.encode()).decode()

        result = await self.db.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == user_id)
        )
        session = result.scalars().first()

        now = datetime.utcnow()
        expires = now + timedelta(days=30)

        if session:
            session.encrypted_cookie = encrypted
            session.status = "connected"
            session.last_validated_at = now
            session.expires_at = expires
        else:
            session = LinkedInSession(
                user_id=user_id,
                encrypted_cookie=encrypted,
                status="connected",
                last_validated_at=now,
                expires_at=expires,
            )
            self.db.add(session)

        await self.db.commit()

    async def _update_task(self, task_id: str, status: str, message: str) -> None:
        """Update task status in Redis."""
        key = f"{AUTH_TASK_KEY_PREFIX}:{task_id}"
        await self.redis.setex(
            key,
            300,
            json.dumps({
                "task_id": task_id,
                "status": status,
                "message": message,
            })
        )
