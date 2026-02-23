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

from app.models.linkedin_session import LinkedInSession
from app.config import settings


class LinkedInSessionError(Exception):
    """Base exception for LinkedIn session errors."""
    pass


class LinkedInSessionService:
    """Service for managing user's LinkedIn session cookies."""

    SESSION_EXPIRY_DAYS = 30

    def __init__(self, db: AsyncSession):
        self.db = db
        key = settings.secret_key.encode()[:32]
        key = base64.urlsafe_b64encode(key.ljust(32, b'0')[:32])
        self.cipher = Fernet(key)

    def _encrypt(self, value: str) -> str:
        """Encrypt a value."""
        return self.cipher.encrypt(value.encode()).decode()

    def _decrypt(self, encrypted_value: str) -> str:
        """Decrypt a value."""
        return self.cipher.decrypt(encrypted_value.encode()).decode()

    async def save_session(self, user_id: str, li_at_cookie: str) -> LinkedInSession:
        """Save or update user's LinkedIn session cookie.

        Args:
            user_id: User ID
            li_at_cookie: LinkedIn li_at session cookie value

        Returns:
            LinkedInSession instance
        """
        encrypted = self._encrypt(li_at_cookie)

        result = await self.db.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == user_id)
        )
        session = result.scalars().first()

        if session:
            session.encrypted_cookie = encrypted
            session.status = "connected"
            session.last_validated_at = datetime.utcnow()
            session.expires_at = datetime.utcnow() + timedelta(days=self.SESSION_EXPIRY_DAYS)
        else:
            session = LinkedInSession(
                user_id=user_id,
                encrypted_cookie=encrypted,
                status="connected",
                last_validated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=self.SESSION_EXPIRY_DAYS)
            )
            self.db.add(session)

        await self.db.commit()
        await self.db.refresh(session)

        return session

    async def get_session(self, user_id: str) -> Optional[str]:
        """Get user's decrypted LinkedIn session cookie.

        Args:
            user_id: User ID

        Returns:
            Decrypted li_at cookie or None if not found/expired
        """
        result = await self.db.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == user_id)
        )
        session = result.scalars().first()

        if not session:
            return None

        if session.expires_at and session.expires_at < datetime.utcnow():
            session.status = "expired"
            await self.db.commit()
            return None

        return self._decrypt(session.encrypted_cookie)

    async def get_session_status(self, user_id: str) -> dict:
        """Get user's LinkedIn session status.

        Args:
            user_id: User ID

        Returns:
            dict with status info
        """
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

        is_expired = session.expires_at and session.expires_at < datetime.utcnow()

        return {
            "connected": session.status == "connected" and not is_expired,
            "status": "expired" if is_expired else session.status,
            "last_validated": session.last_validated_at.isoformat() if session.last_validated_at else None,
            "expires_at": session.expires_at.isoformat() if session.expires_at else None
        }

    async def delete_session(self, user_id: str) -> bool:
        """Delete user's LinkedIn session.

        Args:
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == user_id)
        )
        session = result.scalars().first()

        if not session:
            return False

        await self.db.delete(session)
        await self.db.commit()

        return True

    async def mark_invalid(self, user_id: str) -> None:
        """Mark user's session as invalid.

        Args:
            user_id: User ID
        """
        result = await self.db.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == user_id)
        )
        session = result.scalars().first()

        if session:
            session.status = "invalid"
            await self.db.commit()
