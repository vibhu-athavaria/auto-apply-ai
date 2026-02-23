"""
LinkedIn Session Service for managing user's LinkedIn session cookies.

IMPORTANT: Never store LinkedIn passwords. Only session cookies (li_at).
"""
import base64
from datetime import datetime, timedelta
from typing import Optional
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import redis.asyncio as aioredis

from app.models.linkedin_session import LinkedInSession
from app.config import settings


class LinkedInSessionError(Exception):
    pass


class LinkedInSessionService:
    SESSION_EXPIRY_DAYS = 30
    WORKER_SESSION_KEY_PREFIX = "li_autopilot:worker:session"
    WORKER_SESSION_TTL = 86400  # 24h

    def __init__(self, db: AsyncSession, redis_client: Optional[aioredis.Redis] = None):
        self.db = db
        self.redis = redis_client
        raw_key = settings.secret_key.encode()[:32]
        padded = raw_key.ljust(32, b'0')[:32]
        self.cipher = Fernet(base64.urlsafe_b64encode(padded))

    def _encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()

    def _decrypt(self, encrypted_value: str) -> str:
        return self.cipher.decrypt(encrypted_value.encode()).decode()

    async def save_session(self, user_id: str, li_at_cookie: str) -> LinkedInSession:
        """Save or update user's LinkedIn session cookie (encrypted in DB, plaintext in Redis for worker)."""
        encrypted = self._encrypt(li_at_cookie)
        now = datetime.utcnow()
        expires = now + timedelta(days=self.SESSION_EXPIRY_DAYS)

        result = await self.db.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == user_id)
        )
        session = result.scalars().first()

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
                expires_at=expires
            )
            self.db.add(session)

        await self.db.commit()
        await self.db.refresh(session)

        # Write plaintext cookie to Redis so worker can access it
        if self.redis:
            worker_key = f"{self.WORKER_SESSION_KEY_PREFIX}:{user_id}"
            await self.redis.setex(worker_key, self.WORKER_SESSION_TTL, li_at_cookie)

        return session

    async def get_session(self, user_id: str) -> Optional[str]:
        """Get user's decrypted LinkedIn session cookie."""
        result = await self.db.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == user_id)
        )
        session = result.scalars().first()

        if not session:
            return None

        expires_at = session.expires_at
        if expires_at and expires_at < datetime.utcnow():
            session.status = "expired"
            await self.db.commit()
            return None

        return self._decrypt(str(session.encrypted_cookie))

    async def get_session_status(self, user_id: str) -> dict:
        """Get user's LinkedIn session status."""
        result = await self.db.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == user_id)
        )
        session = result.scalars().first()

        if not session:
            return {
                "connected": False,
                "status": "not_set",
                "message": "LinkedIn session not configured"
            }

        expires_at = session.expires_at
        last_validated = session.last_validated_at
        is_expired = bool(expires_at and expires_at < datetime.utcnow())

        return {
            "connected": session.status == "connected" and not is_expired,
            "status": "expired" if is_expired else str(session.status),
            "last_validated": last_validated.isoformat() if last_validated else None,
            "expires_at": expires_at.isoformat() if expires_at else None
        }

    async def validate_session(self, user_id: str) -> dict:
        """Validate by making a lightweight LinkedIn HEAD request."""
        import httpx

        cookie = await self.get_session(user_id)

        if not cookie:
            await self.mark_invalid(user_id)
            return {
                "connected": False,
                "status": "not_set",
                "message": "No session cookie found"
            }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://www.linkedin.com/feed/",
                    headers={"cookie": f"li_at={cookie}"},
                    follow_redirects=False
                )
            # LinkedIn redirects to login if session is invalid
            is_valid = response.status_code in (200, 302) and "login" not in str(response.headers.get("location", ""))
        except Exception:
            is_valid = False

        result = await self.db.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == user_id)
        )
        session = result.scalars().first()

        if session:
            session.status = "connected" if is_valid else "invalid"
            session.last_validated_at = datetime.utcnow()
            await self.db.commit()

        # Refresh Redis cache if valid
        if is_valid and self.redis:
            worker_key = f"{self.WORKER_SESSION_KEY_PREFIX}:{user_id}"
            await self.redis.setex(worker_key, self.WORKER_SESSION_TTL, cookie)

        return {
            "connected": is_valid,
            "status": "connected" if is_valid else "invalid",
            "last_validated": datetime.utcnow().isoformat(),
            "message": None if is_valid else "Session is invalid or expired"
        }

    async def delete_session(self, user_id: str) -> bool:
        """Delete user's LinkedIn session from DB and Redis."""
        result = await self.db.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == user_id)
        )
        session = result.scalars().first()

        if not session:
            return False

        await self.db.delete(session)
        await self.db.commit()

        if self.redis:
            worker_key = f"{self.WORKER_SESSION_KEY_PREFIX}:{user_id}"
            await self.redis.delete(worker_key)

        return True

    async def mark_invalid(self, user_id: str) -> None:
        """Mark user's session as invalid."""
        result = await self.db.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == user_id)
        )
        session = result.scalars().first()

        if session:
            session.status = "invalid"
            await self.db.commit()
