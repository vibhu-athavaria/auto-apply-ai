"""
Tests for LinkedIn session management.

Covers:
- Save session (encrypts to DB, writes plaintext to Redis)
- Get session status
- Delete session (clears DB + Redis)
- Validate session (mocked HTTP call)
- API endpoints: POST/GET/DELETE/POST-validate
"""
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.linkedin_session import LinkedInSession
from app.services.linkedin_session_service import LinkedInSessionService


class TestLinkedInSessionService:

    @pytest.mark.asyncio
    async def test_save_session_creates_new(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_redis: AsyncMock
    ):
        """Save session creates DB record and writes to Redis."""
        service = LinkedInSessionService(db_session, mock_redis)
        session = await service.save_session(
            user_id=str(test_user.id),
            li_at_cookie="test_li_at_cookie_value"
        )

        assert session.id is not None
        assert session.user_id == str(test_user.id)
        assert session.status == "connected"
        assert session.last_validated_at is not None
        assert session.expires_at is not None

        # Must NOT store plaintext cookie
        assert "test_li_at_cookie_value" not in str(session.encrypted_cookie)

        # Must write plaintext to Redis for worker
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert f"li_autopilot:worker:session:{test_user.id}" in call_args[0][0]
        assert call_args[0][2] == "test_li_at_cookie_value"

    @pytest.mark.asyncio
    async def test_save_session_updates_existing(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_redis: AsyncMock
    ):
        """Save session updates existing record."""
        service = LinkedInSessionService(db_session, mock_redis)
        await service.save_session(str(test_user.id), "cookie_v1")
        await service.save_session(str(test_user.id), "cookie_v2")

        # Should still be one record
        from sqlalchemy.future import select
        result = await db_session.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == str(test_user.id))
        )
        sessions = result.scalars().all()
        assert len(sessions) == 1

        # Cookie must decrypt to v2
        decrypted = service._decrypt(sessions[0].encrypted_cookie)
        assert decrypted == "cookie_v2"

    @pytest.mark.asyncio
    async def test_get_session_returns_decrypted(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_redis: AsyncMock
    ):
        """Get session returns decrypted cookie."""
        service = LinkedInSessionService(db_session, mock_redis)
        await service.save_session(str(test_user.id), "my_li_at_cookie")

        cookie = await service.get_session(str(test_user.id))
        assert cookie == "my_li_at_cookie"

    @pytest.mark.asyncio
    async def test_get_session_returns_none_if_not_found(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Get session returns None for unknown user."""
        service = LinkedInSessionService(db_session, mock_redis)
        cookie = await service.get_session("nonexistent-user-id")
        assert cookie is None

    @pytest.mark.asyncio
    async def test_get_session_returns_none_if_expired(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_redis: AsyncMock
    ):
        """Get session returns None and marks as expired."""
        service = LinkedInSessionService(db_session, mock_redis)
        await service.save_session(str(test_user.id), "cookie_val")

        # Force expiry
        from sqlalchemy.future import select
        result = await db_session.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == str(test_user.id))
        )
        session = result.scalars().first()
        session.expires_at = datetime.utcnow() - timedelta(days=1)
        await db_session.commit()

        cookie = await service.get_session(str(test_user.id))
        assert cookie is None

    @pytest.mark.asyncio
    async def test_get_session_status_not_set(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Status is not_set for user with no session."""
        service = LinkedInSessionService(db_session, mock_redis)
        status = await service.get_session_status("no-session-user")

        assert status["connected"] is False
        assert status["status"] == "not_set"

    @pytest.mark.asyncio
    async def test_get_session_status_connected(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_redis: AsyncMock
    ):
        """Status is connected after saving a session."""
        service = LinkedInSessionService(db_session, mock_redis)
        await service.save_session(str(test_user.id), "valid_cookie")

        status = await service.get_session_status(str(test_user.id))

        assert status["connected"] is True
        assert status["status"] == "connected"

    @pytest.mark.asyncio
    async def test_delete_session_removes_db_and_redis(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_redis: AsyncMock
    ):
        """Delete clears both DB record and Redis key."""
        service = LinkedInSessionService(db_session, mock_redis)
        await service.save_session(str(test_user.id), "cookie_to_delete")

        result = await service.delete_session(str(test_user.id))
        assert result is True

        # DB should be gone
        cookie = await service.get_session(str(test_user.id))
        assert cookie is None

        # Redis delete must have been called
        mock_redis.delete.assert_called_once_with(
            f"li_autopilot:worker:session:{test_user.id}"
        )

    @pytest.mark.asyncio
    async def test_delete_session_not_found(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Delete returns False for unknown user."""
        service = LinkedInSessionService(db_session, mock_redis)
        result = await service.delete_session("unknown-user")
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_session_valid(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_redis: AsyncMock
    ):
        """Validate returns connected when LinkedIn responds with 200."""
        service = LinkedInSessionService(db_session, mock_redis)
        await service.save_session(str(test_user.id), "valid_cookie")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            status = await service.validate_session(str(test_user.id))

        assert status["connected"] is True
        assert status["status"] == "connected"

    @pytest.mark.asyncio
    async def test_validate_session_invalid_redirect(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_redis: AsyncMock
    ):
        """Validate returns invalid when LinkedIn redirects to login."""
        service = LinkedInSessionService(db_session, mock_redis)
        await service.save_session(str(test_user.id), "stale_cookie")

        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {"location": "https://www.linkedin.com/login"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            status = await service.validate_session(str(test_user.id))

        assert status["connected"] is False
        assert status["status"] == "invalid"

    @pytest.mark.asyncio
    async def test_mark_invalid(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_redis: AsyncMock
    ):
        """mark_invalid sets status to invalid."""
        service = LinkedInSessionService(db_session, mock_redis)
        await service.save_session(str(test_user.id), "cookie")

        await service.mark_invalid(str(test_user.id))

        status = await service.get_session_status(str(test_user.id))
        assert status["status"] == "invalid"
        assert status["connected"] is False


class TestLinkedInEndpoints:

    @pytest.mark.asyncio
    async def test_save_session_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """POST /linkedin/session saves the session."""
        response = await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "test_cookie_value"},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert "test_cookie_value" not in str(data)  # never expose cookie

    @pytest.mark.asyncio
    async def test_save_session_requires_auth(self, client: AsyncClient):
        """POST /linkedin/session requires authentication."""
        response = await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "cookie"}
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_save_session_empty_cookie_rejected(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """POST /linkedin/session rejects empty cookie."""
        response = await client.post(
            "/linkedin/session",
            json={"li_at_cookie": ""},
            headers=auth_headers
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_session_status_endpoint_not_set(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """GET /linkedin/session returns not_set for new user."""
        response = await client.get(
            "/linkedin/session",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["status"] == "not_set"

    @pytest.mark.asyncio
    async def test_get_session_status_endpoint_connected(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """GET /linkedin/session returns connected after saving."""
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "my_cookie"},
            headers=auth_headers
        )

        response = await client.get(
            "/linkedin/session",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["status"] == "connected"

    @pytest.mark.asyncio
    async def test_delete_session_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """DELETE /linkedin/session removes session."""
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "cookie_to_delete"},
            headers=auth_headers
        )

        response = await client.delete(
            "/linkedin/session",
            headers=auth_headers
        )
        assert response.status_code == 200

        # Status should now be not_set
        status_response = await client.get(
            "/linkedin/session",
            headers=auth_headers
        )
        assert status_response.json()["status"] == "not_set"

    @pytest.mark.asyncio
    async def test_validate_session_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """POST /linkedin/session/validate validates the session."""
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "test_cookie"},
            headers=auth_headers
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await client.post(
                "/linkedin/session/validate",
                headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
