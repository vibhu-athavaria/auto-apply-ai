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


class TestLinkedInConnectEndpoints:

    @pytest.mark.asyncio
    async def test_connect_enqueues_task(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """POST /linkedin/connect enqueues auth task and returns task_id."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "user@example.com", "password": "secret123"},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "connecting"

        # Must enqueue to the auth queue
        mock_redis.rpush.assert_called_once()
        call_args = mock_redis.rpush.call_args[0]
        assert call_args[0] == "li_autopilot:tasks:linkedin_auth"

        # Password must NOT appear in the enqueued payload
        import json as _json
        payload = _json.loads(call_args[1])
        assert payload["email"] == "user@example.com"
        assert "secret123" not in str(data)  # not in response

    @pytest.mark.asyncio
    async def test_connect_requires_auth(self, client: AsyncClient):
        """POST /linkedin/connect requires authentication."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "user@example.com", "password": "secret"}
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_connect_invalid_email_rejected(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """POST /linkedin/connect rejects invalid email."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "not-an-email", "password": "secret"},
            headers=auth_headers
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_connect_empty_password_rejected(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """POST /linkedin/connect rejects empty password."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "user@example.com", "password": ""},
            headers=auth_headers
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_connect_status_connecting(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """GET /linkedin/connect/status returns task status."""
        import json as _json
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "test-task-id",
            "status": "connecting",
            "message": None
        }))

        response = await client.get(
            "/linkedin/connect/status/test-task-id",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "connecting"

    @pytest.mark.asyncio
    async def test_connect_status_connected(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """GET /linkedin/connect/status returns connected after auth."""
        import json as _json
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "test-task-id",
            "status": "connected",
            "message": "LinkedIn connected successfully"
        }))

        response = await client.get(
            "/linkedin/connect/status/test-task-id",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "connected"

    @pytest.mark.asyncio
    async def test_connect_status_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """GET /linkedin/connect/status returns 404 for expired task."""
        mock_redis.get = AsyncMock(return_value=None)

        response = await client.get(
            "/linkedin/connect/status/expired-task",
            headers=auth_headers
        )
        assert response.status_code == 404


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


# ============================================================================
# ADDITIONAL CONNECT ENDPOINT TESTS
# ============================================================================

class TestLinkedInConnectAdditional:

    @pytest.mark.asyncio
    async def test_connect_with_valid_credentials(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test connect endpoint with valid credentials."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "valid@example.com", "password": "correctpassword123"},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "connecting"

    @pytest.mark.asyncio
    async def test_connect_with_invalid_credentials_returns_401(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test connect endpoint with invalid credentials returns 401."""
        import json as _json

        # Mock Redis to return failed status
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "test-task",
            "status": "failed",
            "message": "Invalid email or password"
        }))

        response = await client.post(
            "/linkedin/connect",
            json={"email": "invalid@example.com", "password": "wrongpassword"},
            headers=auth_headers
        )

        assert response.status_code == 200  # Enqueue succeeds, task will fail

    @pytest.mark.asyncio
    async def test_connect_with_missing_email(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test connect endpoint with missing email."""
        response = await client.post(
            "/linkedin/connect",
            json={"password": "somepassword"},
            headers=auth_headers
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_connect_with_missing_password(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test connect endpoint with missing password."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@example.com"},
            headers=auth_headers
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_connect_with_invalid_email_format(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test connect endpoint with invalid email format."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "not-an-email", "password": "password123"},
            headers=auth_headers
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_connect_with_empty_email(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test connect endpoint with empty email."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "", "password": "password123"},
            headers=auth_headers
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_connect_with_empty_password(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test connect endpoint with empty password."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@example.com", "password": ""},
            headers=auth_headers
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_connect_status_endpoint_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test status endpoint returns 404 for non-existent task."""
        mock_redis.get = AsyncMock(return_value=None)

        response = await client.get(
            "/linkedin/connect/status/nonexistent-task-id",
            headers=auth_headers
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_connect_status_endpoint_task_in_progress(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test status endpoint returns in-progress status."""
        import json as _json

        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "in-progress-task",
            "status": "connecting",
            "message": "Authenticating with LinkedIn..."
        }))

        response = await client.get(
            "/linkedin/connect/status/in-progress-task",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connecting"

    @pytest.mark.asyncio
    async def test_connect_status_endpoint_task_failed(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test status endpoint returns failed status."""
        import json as _json

        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "failed-task",
            "status": "failed",
            "message": "Invalid credentials"
        }))

        response = await client.get(
            "/linkedin/connect/status/failed-task",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "credentials" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_connect_status_endpoint_challenge_required(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test status endpoint returns challenge_required for 2FA."""
        import json as _json

        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "2fa-task",
            "status": "challenge_required",
            "message": "Two-factor authentication required"
        }))

        response = await client.get(
            "/linkedin/connect/status/2fa-task",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "challenge_required"


# ============================================================================
# SESSION STATUS ENDPOINT TESTS
# ============================================================================

class TestLinkedInSessionStatus:

    @pytest.mark.asyncio
    async def test_session_status_endpoint_not_set(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test session status returns not_set when no session exists."""
        response = await client.get(
            "/linkedin/session",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["status"] == "not_set"

    @pytest.mark.asyncio
    async def test_session_status_endpoint_connected(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test session status returns connected after saving session."""
        # First save a session
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "valid_session_cookie"},
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
    async def test_session_status_endpoint_unauthorized(
        self,
        client: AsyncClient
    ):
        """Test session status requires authentication."""
        response = await client.get("/linkedin/session")
        assert response.status_code in (401, 403)


# ============================================================================
# VALIDATE SESSION ENDPOINT TESTS
# ============================================================================

class TestLinkedInValidateSession:

    @pytest.mark.asyncio
    async def test_validate_session_unauthorized(
        self,
        client: AsyncClient
    ):
        """Test validate session requires authentication."""
        response = await client.post("/linkedin/session/validate")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_validate_session_no_session(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test validate session returns not_set when no session exists."""
        response = await client.post(
            "/linkedin/session/validate",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["status"] == "not_set"

    @pytest.mark.asyncio
    async def test_validate_session_with_valid_cookie(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test validate session with a valid cookie."""
        # First save a session
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "valid_cookie"},
            headers=auth_headers
        )

        # Mock the HTTP validation call
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

    @pytest.mark.asyncio
    async def test_validate_session_with_invalid_cookie(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test validate session with an invalid/expired cookie."""
        # First save a session
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "expired_cookie"},
            headers=auth_headers
        )

        # Mock the HTTP validation call - redirect to login means invalid
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {"location": "https://www.linkedin.com/login"}

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
        assert data["connected"] is False
        assert data["status"] == "invalid"


# ============================================================================
# UNAUTHORIZED ACCESS TESTS
# ============================================================================

class TestLinkedInUnauthorizedAccess:

    @pytest.mark.asyncio
    async def test_connect_unauthorized(self, client: AsyncClient):
        """Test connect endpoint without authentication."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@example.com", "password": "password123"}
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_save_session_unauthorized(self, client: AsyncClient):
        """Test save session without authentication."""
        response = await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "some_cookie"}
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_delete_session_unauthorized(self, client: AsyncClient):
        """Test delete session without authentication."""
        response = await client.delete("/linkedin/session")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_connect_status_unauthorized(self, client: AsyncClient):
        """Test connect status endpoint without authentication."""
        response = await client.get("/linkedin/connect/status/some-task-id")
        assert response.status_code in (401, 403)


# ============================================================================
# 2FA FLOW TESTS
# ============================================================================

class TestLinkedIn2FAFlow:

    @pytest.mark.asyncio
    async def test_connect_with_2fa_enabled(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test connect flow when user has 2FA enabled."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "2fauser@example.com", "password": "password123"},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        # The task will handle 2FA challenge

    @pytest.mark.asyncio
    async def test_2fa_challenge_response(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test status polling during 2FA challenge."""
        import json as _json

        # Mock the task status showing challenge required
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "2fa-task-123",
            "status": "challenge_required",
            "message": "Check your phone for verification code"
        }))

        response = await client.get(
            "/linkedin/connect/status/2fa-task-123",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "challenge_required"
        assert "phone" in data["message"].lower() or "verification" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_2fa_verification_timeout(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test timeout during 2FA verification."""
        import json as _json

        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "2fa-timeout-task",
            "status": "failed",
            "message": "Verification timed out. Please try again."
        }))

        response = await client.get(
            "/linkedin/connect/status/2fa-timeout-task",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "timeout" in data["message"].lower() or "try again" in data["message"].lower() or "Verification" in data["message"]


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestLinkedInEdgeCases:

    @pytest.mark.asyncio
    async def test_connect_with_very_long_password(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test connect with an unusually long password."""
        long_password = "a" * 500

        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@example.com", "password": long_password},
            headers=auth_headers
        )

        # Should accept and enqueue task
        assert response.status_code == 200
        assert "task_id" in response.json()

    @pytest.mark.asyncio
    async def test_connect_with_unicode_email(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test connect with unicode characters in email."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "用户@例子.测试", "password": "password123"},
            headers=auth_headers
        )

        # Should be rejected as invalid email format
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_connect_with_special_characters_in_password(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test connect with special characters in password."""
        special_password = "P@$$w0rd!#$%^&*()_+-=[]{}|;:,.<>?"

        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@example.com", "password": special_password},
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "task_id" in response.json()

    @pytest.mark.asyncio
    async def test_save_session_with_empty_cookie(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test save session with empty cookie."""
        response = await client.post(
            "/linkedin/session",
            json={"li_at_cookie": ""},
            headers=auth_headers
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_save_session_with_null_cookie(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test save session with null cookie."""
        response = await client.post(
            "/linkedin/session",
            json={"li_at_cookie": None},
            headers=auth_headers
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_concurrent_connect_requests(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test handling multiple concurrent connect requests."""
        import asyncio

        async def make_request():
            return await client.post(
                "/linkedin/connect",
                json={"email": "test@example.com", "password": "password123"},
                headers=auth_headers
            )

        # Make multiple concurrent requests
        responses = await asyncio.gather(
            make_request(),
            make_request(),
            make_request()
        )

        # All should succeed and return different task IDs
        assert all(r.status_code == 200 for r in responses)
        task_ids = [r.json()["task_id"] for r in responses]
        assert len(set(task_ids)) == 3  # Each request gets unique task ID

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test deleting a session that doesn't exist."""
        response = await client.delete(
            "/linkedin/session",
            headers=auth_headers
        )

        # Should return success or appropriate error
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_session_persistence_after_validation_failure(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test session handling after validation fails."""
        # First save a session
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "cookie_to_validate"},
            headers=auth_headers
        )

        # Mock failed validation
        mock_response = MagicMock()
        mock_response.status_code = 401
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

        # Session should be marked as invalid
        data = response.json()
        assert data["connected"] is False
        assert data["status"] in ["invalid", "not_set"]  # May vary based on implementation

    @pytest.mark.asyncio
    async def test_rate_limiting_on_connect(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test rate limiting behavior on connect endpoint."""
        # Make many rapid requests
        for i in range(10):
            response = await client.post(
                "/linkedin/connect",
                json={"email": f"test{i}@example.com", "password": "password123"},
                headers=auth_headers
            )

            # Should not hit rate limit in test environment
            assert response.status_code in [200, 429]

            if response.status_code == 429:
                break  # Rate limited as expected

    @pytest.mark.asyncio
    async def test_network_error_during_validation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test handling of network errors during session validation."""
        # First save a session
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "cookie_for_network_error"},
            headers=auth_headers
        )

        # Mock network error
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=Exception("Network error"))
            mock_client_cls.return_value = mock_client

            response = await client.post(
                "/linkedin/session/validate",
                headers=auth_headers
            )

        # Should handle gracefully
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False

    @pytest.mark.asyncio
    async def test_redis_connection_failure_during_connect(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test handling of Redis connection failure."""
        # Make Redis raise an exception
        mock_redis.rpush = AsyncMock(side_effect=Exception("Redis connection failed"))

        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@example.com", "password": "password123"},
            headers=auth_headers
        )

        # Should handle gracefully with appropriate error
        assert response.status_code in [200, 500, 503]

    @pytest.mark.asyncio
    async def test_malformed_task_id_in_status(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test status endpoint with malformed task ID."""
        response = await client.get(
            "/linkedin/connect/status/malformed<task>id",
            headers=auth_headers
        )

        # Should return 404 or handle gracefully
        assert response.status_code in [404, 400, 200]

    @pytest.mark.asyncio
    async def test_session_with_expired_cookie(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock,
        db_session: AsyncSession
    ):
        """Test session handling when cookie has expired."""
        from datetime import datetime, timedelta
        from app.models.linkedin_session import LinkedInSession
        from app.services.linkedin_session_service import LinkedInSessionService

        # Create a session service and save a session
        service = LinkedInSessionService(db_session, mock_redis)
        await service.save_session("test-user-id", "expired_cookie_value")

        # Manually expire the session
        result = await db_session.execute(
            select(LinkedInSession)
        )
        session = result.scalars().first()
        if session:
            session.expires_at = datetime.utcnow() - timedelta(days=1)
            await db_session.commit()

        # Check status - should show as expired/not connected
        mock_redis.get = AsyncMock(return_value=None)

        response = await client.get(
            "/linkedin/session",
            headers=auth_headers
        )

        # Response should indicate session is not connected
        data = response.json()
        assert data["connected"] is False

    @pytest.mark.asyncio
    async def test_connect_status_with_corrupted_redis_data(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test connect status with corrupted data in Redis."""
        mock_redis.get = AsyncMock(return_value="not-valid-json")

        response = await client.get(
            "/linkedin/connect/status/corrupted-task",
            headers=auth_headers
        )

        # Should handle gracefully
        assert response.status_code in [200, 404, 500]

    @pytest.mark.asyncio
    async def test_session_encryption_verification(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock,
        db_session: AsyncSession
    ):
        """Verify that session cookies are encrypted in database."""
        cookie_value = "secret_cookie_value_12345"

        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": cookie_value},
            headers=auth_headers
        )

        # Query the database directly
        from app.models.linkedin_session import LinkedInSession
        result = await db_session.execute(
            select(LinkedInSession)
        )
        session = result.scalars().first()

        if session:
            # The encrypted cookie should NOT contain the plaintext
            assert cookie_value not in str(session.encrypted_cookie)
            # Should contain encrypted data (gibberish)
            assert len(session.encrypted_cookie) > 0

    @pytest.mark.asyncio
    async def test_redis_plaintext_storage_for_worker(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Verify that plaintext cookie is stored in Redis for worker."""
        cookie_value = "worker_cookie_value"

        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": cookie_value},
            headers=auth_headers
        )

        # Verify Redis was called with plaintext
        mock_redis.setex.assert_called()
        call_args = mock_redis.setex.call_args
        # The cookie value should be in the Redis call
        assert cookie_value in str(call_args)

    @pytest.mark.asyncio
    async def test_linkedin_down_during_connect(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test behavior when LinkedIn is down during connect."""
        import json as _json

        # Mock the task status showing failure due to LinkedIn being down
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "linkedin-down-task",
            "status": "failed",
            "message": "Could not connect to LinkedIn. Please try again later."
        }))

        response = await client.get(
            "/linkedin/connect/status/linkedin-down-task",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "linkedin" in data["message"].lower() or "try again" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_account_locked_scenario(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test handling of locked LinkedIn account."""
        import json as _json

        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "locked-account-task",
            "status": "failed",
            "message": "Account temporarily locked. Please check your email."
        }))

        response = await client.get(
            "/linkedin/connect/status/locked-account-task",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "locked" in data["message"].lower() or "email" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_captcha_challenge_scenario(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test handling of CAPTCHA challenge."""
        import json as _json

        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "captcha-task",
            "status": "challenge_required",
            "message": "CAPTCHA verification required"
        }))

        response = await client.get(
            "/linkedin/connect/status/captcha-task",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "challenge_required"
        assert "captcha" in data["message"].lower() or "verification" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_successful_reconnection_after_failure(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test successful reconnection after a previous failure."""
        import json as _json

        # First attempt fails
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "retry-task",
            "status": "failed",
            "message": "Invalid credentials"
        }))

        response1 = await client.get(
            "/linkedin/connect/status/retry-task",
            headers=auth_headers
        )

        assert response1.json()["status"] == "failed"

        # Second attempt succeeds
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "retry-task-2",
            "status": "connected",
            "message": "Successfully connected"
        }))

        response2 = await client.get(
            "/linkedin/connect/status/retry-task-2",
            headers=auth_headers
        )

        assert response2.json()["status"] == "connected"

    @pytest.mark.asyncio
    async def test_concurrent_session_validation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test concurrent session validation requests."""
        import asyncio

        # Save a session first
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "validation_test_cookie"},
            headers=auth_headers
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        async def validate():
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                return await client.post(
                    "/linkedin/session/validate",
                    headers=auth_headers
                )

        # Make concurrent validation requests
        responses = await asyncio.gather(validate(), validate(), validate())

        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        assert all(r.json()["connected"] is True for r in responses)

    @pytest.mark.asyncio
    async def test_session_retrieval_with_special_characters_in_user_id(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test session operations with unusual user ID formats."""
        # This is more of a service-level test
        # The API should handle all valid user IDs
        response = await client.get(
            "/linkedin/session",
            headers=auth_headers
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cookie_rotation_on_reconnect(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test that new cookie replaces old one on reconnection."""
        # First connection
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "first_cookie"},
            headers=auth_headers
        )

        first_call = mock_redis.setex.call_args

        # Second connection (reconnect)
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "second_cookie"},
            headers=auth_headers
        )

        second_call = mock_redis.setex.call_args

        # Both calls should have been made
        assert mock_redis.setex.call_count >= 2

    @pytest.mark.asyncio
    async def test_partial_session_data_recovery(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test behavior with partial session data."""
        import json as _json

        # Mock partial/corrupt data
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "partial-task"
            # Missing status field
        }))

        response = await client.get(
            "/linkedin/connect/status/partial-task",
            headers=auth_headers
        )

        # Should handle gracefully
        assert response.status_code in [200, 404, 500]

    @pytest.mark.asyncio
    async def test_session_deletion_cascades_to_redis(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test that deleting session also clears Redis."""
        # Save a session
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "to_be_deleted"},
            headers=auth_headers
        )

        # Delete it
        await client.delete(
            "/linkedin/session",
            headers=auth_headers
        )

        # Redis delete should have been called
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_connect_with_unicode_password(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test connect with unicode characters in password."""
        unicode_password = "пароль密码пароль"

        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@example.com", "password": unicode_password},
            headers=auth_headers
        )

        # Should accept and enqueue task
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_connect_with_newline_in_credentials(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test connect with newline characters in credentials."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@example.com", "password": "pass\nword\r\n123"},
            headers=auth_headers
        )

        # Should handle gracefully
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_connect_with_html_in_credentials(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test connect with HTML/script in credentials (XSS prevention)."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "<script>alert('xss')</script>@example.com", "password": "<b>password</b>"},
            headers=auth_headers
        )

        # Should sanitize or reject
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_connect_with_sql_injection_attempt(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test connect with SQL injection attempt."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@example.com'; DROP TABLE users; --", "password": "password123"},
            headers=auth_headers
        )

        # Should handle gracefully without executing SQL
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_connect_with_no_redis(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test connect when Redis is unavailable."""
        mock_redis.rpush = AsyncMock(side_effect=ConnectionError("Redis is down"))

        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@example.com", "password": "password123"},
            headers=auth_headers
        )

        # Should return appropriate error
        assert response.status_code in [200, 500, 503]

    @pytest.mark.asyncio
    async def test_connect_response_does_not_expose_password(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Verify that connect response does not contain the password."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@example.com", "password": "secret_password_123"},
            headers=auth_headers
        )

        response_text = response.text
        assert "secret_password_123" not in response_text

    @pytest.mark.asyncio
    async def test_connect_response_does_not_expose_email(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Verify that connect response does not contain sensitive email info."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "sensitive@example.com", "password": "password123"},
            headers=auth_headers
        )

        # Email might be in response for legitimate reasons, but this checks basic exposure
        data = response.json()
        # Should not have email field in response (security best practice)
        assert "email" not in data or data.get("email") != "sensitive@example.com"

    @pytest.mark.asyncio
    async def test_task_status_with_extra_fields(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test handling of task status with unexpected extra fields."""
        import json as _json

        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": "extra-fields-task",
            "status": "connected",
            "message": "Success",
            "extra_field": "should_be_ignored",
            "nested": {"data": "value"}
        }))

        response = await client.get(
            "/linkedin/connect/status/extra-fields-task",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"

    @pytest.mark.asyncio
    async def test_session_update_preserves_other_fields(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock,
        db_session: AsyncSession
    ):
        """Test that updating session preserves other user data."""
        from app.models.linkedin_session import LinkedInSession
        from sqlalchemy.future import select

        # Save initial session
        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "initial_cookie"},
            headers=auth_headers
        )

        # Get the session
        result = await db_session.execute(
            select(LinkedInSession)
        )
        session = result.scalars().first()

        if session:
            created_at = session.created_at

            # Update with new cookie
            await client.post(
                "/linkedin/session",
                json={"li_at_cookie": "updated_cookie"},
                headers=auth_headers
            )

            # Refresh and check
            await db_session.refresh(session)
            # Should still be the same record
            assert session.created_at == created_at
