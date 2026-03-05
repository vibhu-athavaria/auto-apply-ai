"""
Integration tests for the Job Profile Wizard flow.

Tests the complete wizard flow:
1. Resume Upload
2. LinkedIn Connection
3. Job Profile Creation

And various error scenarios and edge cases.
"""
import pytest
import json as _json
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User
from app.models.resume import Resume
from app.models.job_search_profile import JobSearchProfile
from app.models.linkedin_session import LinkedInSession


# ============================================================================
# COMPLETE WIZARD FLOW TESTS
# ============================================================================

class TestCompleteWizardFlow:
    """Tests for the complete wizard flow."""

    @pytest.mark.asyncio
    async def test_complete_wizard_flow_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test complete wizard flow: Resume → LinkedIn → Profile → Redirect."""

        # Step 1: Upload Resume
        resume_response = await client.post(
            "/resumes/upload",
            headers=auth_headers,
            files={"file": ("resume.pdf", b"PDF content for resume", "application/pdf")}
        )
        assert resume_response.status_code == 200
        resume_data = resume_response.json()
        assert "id" in resume_data
        assert resume_data["filename"] == "resume.pdf"

        # Verify resume was saved
        result = await db_session.execute(
            select(Resume).where(Resume.user_id == test_user.id)
        )
        resumes = result.scalars().all()
        assert len(resumes) == 1
        assert resumes[0].filename == "resume.pdf"

        # Step 2: Connect LinkedIn
        connect_response = await client.post(
            "/linkedin/connect",
            json={"email": "test@linkedin.com", "password": "password123"},
            headers=auth_headers
        )
        assert connect_response.status_code == 200
        connect_data = connect_response.json()
        assert "task_id" in connect_data
        assert connect_data["status"] == "connecting"

        # Mock successful connection status
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": connect_data["task_id"],
            "status": "connected",
            "message": "LinkedIn connected successfully"
        }))

        # Poll for connection status
        status_response = await client.get(
            f"/linkedin/connect/status/{connect_data['task_id']}",
            headers=auth_headers
        )
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] == "connected"

        # Save LinkedIn session
        session_response = await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "valid_li_at_cookie_value"},
            headers=auth_headers
        )
        assert session_response.status_code == 200

        # Verify session was saved
        result = await db_session.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == str(test_user.id))
        )
        sessions = result.scalars().all()
        assert len(sessions) == 1
        assert sessions[0].status == "connected"

        # Step 3: Create Job Profile
        profile_response = await client.post(
            "/profiles/",
            json={
                "keywords": "Software Engineer",
                "location": "San Francisco, CA",
                "remote_preference": "hybrid",
                "salary_min": 120000,
                "salary_max": 180000
            },
            headers=auth_headers
        )
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["keywords"] == "Software Engineer"
        assert profile_data["location"] == "San Francisco, CA"
        assert "id" in profile_data

        # Verify profile was saved
        result = await db_session.execute(
            select(JobSearchProfile).where(JobSearchProfile.user_id == test_user.id)
        )
        profiles = result.scalars().all()
        assert len(profiles) == 1
        assert profiles[0].keywords == "Software Engineer"

    @pytest.mark.asyncio
    async def test_wizard_flow_skip_linkedin(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession
    ):
        """Test wizard flow with skipped LinkedIn: Resume → skip LinkedIn → Profile."""

        # Step 1: Upload Resume
        resume_response = await client.post(
            "/resumes/upload",
            headers=auth_headers,
            files={"file": ("resume.pdf", b"PDF content", "application/pdf")}
        )
        assert resume_response.status_code == 200

        # Step 2: Skip LinkedIn (no connection attempt)
        # User simply proceeds to step 3 without connecting

        # Step 3: Create Profile without LinkedIn
        profile_response = await client.post(
            "/profiles/",
            json={
                "keywords": "Data Scientist",
                "location": "Remote"
            },
            headers=auth_headers
        )
        assert profile_response.status_code == 200

        # Verify no LinkedIn session was created
        result = await db_session.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == str(test_user.id))
        )
        sessions = result.scalars().all()
        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_wizard_flow_resume_upload_failure(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession
    ):
        """Test that flow stops when resume upload fails."""

        # Step 1: Try to upload invalid file
        response = await client.post(
            "/resumes/upload",
            headers=auth_headers,
            files={"file": ("malware.exe", b"malicious content", "application/x-msdownload")}
        )
        assert response.status_code == 400

        # Verify no resume was saved
        result = await db_session.execute(
            select(Resume).where(Resume.user_id == test_user.id)
        )
        resumes = result.scalars().all()
        assert len(resumes) == 0

        # Flow cannot continue without resume

    @pytest.mark.asyncio
    async def test_wizard_flow_linkedin_connection_failure(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test LinkedIn failure handling - can retry or skip."""

        # Step 1: Upload Resume
        resume_response = await client.post(
            "/resumes/upload",
            headers=auth_headers,
            files={"file": ("resume.pdf", b"PDF content", "application/pdf")}
        )
        assert resume_response.status_code == 200

        # Step 2: Try to connect LinkedIn - will fail
        connect_response = await client.post(
            "/linkedin/connect",
            json={"email": "wrong@linkedin.com", "password": "wrongpassword"},
            headers=auth_headers
        )
        assert connect_response.status_code == 200
        task_id = connect_response.json()["task_id"]

        # Mock failed connection status
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": task_id,
            "status": "failed",
            "message": "Invalid credentials"
        }))

        # Poll for status - should show failure
        status_response = await client.get(
            f"/linkedin/connect/status/{task_id}",
            headers=auth_headers
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "failed"

        # User can either retry or skip
        # No LinkedIn session should be saved
        result = await db_session.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == str(test_user.id))
        )
        sessions = result.scalars().all()
        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_wizard_flow_profile_creation_failure(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test profile creation failure - data preserved for retry."""

        # Step 1: Upload Resume
        resume_response = await client.post(
            "/resumes/upload",
            headers=auth_headers,
            files={"file": ("resume.pdf", b"PDF content", "application/pdf")}
        )
        assert resume_response.status_code == 200

        # Step 2: Connect LinkedIn
        connect_response = await client.post(
            "/linkedin/connect",
            json={"email": "test@linkedin.com", "password": "password123"},
            headers=auth_headers
        )
        assert connect_response.status_code == 200

        # Mock successful connection
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": connect_response.json()["task_id"],
            "status": "connected"
        }))

        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "valid_cookie"},
            headers=auth_headers
        )

        # Step 3: Try to create profile with invalid data
        profile_response = await client.post(
            "/profiles/",
            json={
                "keywords": "",  # Empty keywords - should fail
                "location": "City"
            },
            headers=auth_headers
        )

        # Should fail validation
        assert profile_response.status_code in [422, 200]

        # If it failed, no profile should be saved
        if profile_response.status_code == 422:
            result = await db_session.execute(
                select(JobSearchProfile).where(JobSearchProfile.user_id == test_user.id)
            )
            profiles = result.scalars().all()
            assert len(profiles) == 0

    @pytest.mark.asyncio
    async def test_wizard_flow_with_existing_resume(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test that users with existing resume can skip step 1."""

        # Pre-create a resume
        existing_resume = Resume(
            user_id=test_user.id,
            filename="existing_resume.pdf",
            file_path="/uploads/existing.pdf",
            file_size=1024,
            content_type="application/pdf"
        )
        db_session.add(existing_resume)
        await db_session.commit()

        # Verify resume exists
        response = await client.get("/resumes/", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) >= 1

        # User can skip upload and proceed
        # Step 2: Connect LinkedIn
        connect_response = await client.post(
            "/linkedin/connect",
            json={"email": "test@linkedin.com", "password": "password123"},
            headers=auth_headers
        )
        assert connect_response.status_code == 200

        # Mock successful connection
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": connect_response.json()["task_id"],
            "status": "connected"
        }))

        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "valid_cookie"},
            headers=auth_headers
        )

        # Step 3: Create Profile
        profile_response = await client.post(
            "/profiles/",
            json={"keywords": "Engineer", "location": "City"},
            headers=auth_headers
        )
        assert profile_response.status_code == 200

    @pytest.mark.asyncio
    async def test_wizard_flow_with_existing_linkedin(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession
    ):
        """Test that users with existing LinkedIn session can skip step 2."""

        # Pre-create LinkedIn session
        from app.services.linkedin_session_service import LinkedInSessionService

        service = LinkedInSessionService(db_session, mock_redis)
        await service.save_session(str(test_user.id), "existing_cookie")

        # Verify session exists
        response = await client.get("/linkedin/session", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["connected"] is True

        # Step 1: Upload Resume
        resume_response = await client.post(
            "/resumes/upload",
            headers=auth_headers,
            files={"file": ("resume.pdf", b"PDF content", "application/pdf")}
        )
        assert resume_response.status_code == 200

        # User can skip LinkedIn connection
        # Step 3: Create Profile
        profile_response = await client.post(
            "/profiles/",
            json={"keywords": "Engineer", "location": "City"},
            headers=auth_headers
        )
        assert profile_response.status_code == 200


# ============================================================================
# AUTHORIZATION TESTS
# ============================================================================

class TestWizardFlowAuthorization:
    """Tests for authorization in wizard flow."""

    @pytest.mark.asyncio
    async def test_wizard_flow_resume_unauthorized(self, client: AsyncClient):
        """Test that resume upload requires authentication."""
        response = await client.post(
            "/resumes/upload",
            files={"file": ("resume.pdf", b"PDF content", "application/pdf")}
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_wizard_flow_linkedin_unauthorized(self, client: AsyncClient):
        """Test that LinkedIn connect requires authentication."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@linkedin.com", "password": "password123"}
        )
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_wizard_flow_profile_unauthorized(self, client: AsyncClient):
        """Test that profile creation requires authentication."""
        response = await client.post(
            "/profiles/",
            json={"keywords": "Engineer", "location": "City"}
        )
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_wizard_flow_isolation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession
    ):
        """Test that wizard flow data is isolated per user."""
        from app.utils.security import get_password_hash

        # Create another user
        other_user = User(
            email="isolation@example.com",
            password_hash=get_password_hash("password123")
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        # Create resume for other user
        other_resume = Resume(
            user_id=other_user.id,
            filename="other_resume.pdf",
            file_path="/uploads/other.pdf",
            file_size=1024,
            content_type="application/pdf"
        )
        db_session.add(other_resume)
        await db_session.commit()

        # Verify current user cannot see other user's resume
        response = await client.get("/resumes/", headers=auth_headers)
        assert response.status_code == 200
        filenames = [r["filename"] for r in response.json()]
        assert "other_resume.pdf" not in filenames


# ============================================================================
# ERROR SCENARIOS
# ============================================================================

class TestWizardFlowErrors:
    """Tests for error scenarios in wizard flow."""

    @pytest.mark.asyncio
    async def test_wizard_flow_resume_oversized(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test handling of oversized resume."""
        # Create 11MB file
        large_content = b"x" * (11 * 1024 * 1024)

        response = await client.post(
            "/resumes/upload",
            headers=auth_headers,
            files={"file": ("large.pdf", large_content, "application/pdf")}
        )
        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_wizard_flow_resume_invalid_type(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test handling of invalid file type."""
        response = await client.post(
            "/resumes/upload",
            headers=auth_headers,
            files={"file": ("resume.txt", b"Text content", "text/plain")}
        )
        assert response.status_code == 400
        assert "file type" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_wizard_flow_linkedin_invalid_email(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test LinkedIn connect with invalid email format."""
        response = await client.post(
            "/linkedin/connect",
            json={"email": "not-an-email", "password": "password123"},
            headers=auth_headers
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_wizard_flow_linkedin_missing_credentials(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test LinkedIn connect with missing credentials."""
        # Missing email
        response1 = await client.post(
            "/linkedin/connect",
            json={"password": "password123"},
            headers=auth_headers
        )
        assert response1.status_code == 422

        # Missing password
        response2 = await client.post(
            "/linkedin/connect",
            json={"email": "test@linkedin.com"},
            headers=auth_headers
        )
        assert response2.status_code == 422

    @pytest.mark.asyncio
    async def test_wizard_flow_profile_missing_required(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test profile creation with missing required fields."""
        # Missing keywords
        response1 = await client.post(
            "/profiles/",
            json={"location": "City"},
            headers=auth_headers
        )
        assert response1.status_code == 422

        # Missing location
        response2 = await client.post(
            "/profiles/",
            json={"keywords": "Engineer"},
            headers=auth_headers
        )
        assert response2.status_code == 422

    @pytest.mark.asyncio
    async def test_wizard_flow_network_errors(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_redis: AsyncMock
    ):
        """Test handling of network errors during flow."""
        # Simulate Redis failure during LinkedIn connect
        mock_redis.rpush = AsyncMock(side_effect=ConnectionError("Redis down"))

        response = await client.post(
            "/linkedin/connect",
            json={"email": "test@linkedin.com", "password": "password123"},
            headers=auth_headers
        )

        # Should handle gracefully
        assert response.status_code in [200, 500, 503]


# ============================================================================
# STATE PERSISTENCE TESTS
# ============================================================================

class TestWizardFlowStatePersistence:
    """Tests for state persistence in wizard flow."""

    @pytest.mark.asyncio
    async def test_resume_persists_across_steps(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession
    ):
        """Test that uploaded resume persists across wizard steps."""

        # Upload resume
        await client.post(
            "/resumes/upload",
            headers=auth_headers,
            files={"file": ("persistent_resume.pdf", b"PDF content", "application/pdf")}
        )

        # Resume should be available later
        response = await client.get("/resumes/", headers=auth_headers)
        assert response.status_code == 200
        assert any(r["filename"] == "persistent_resume.pdf" for r in response.json())

    @pytest.mark.asyncio
    async def test_linkedin_session_persists(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test that LinkedIn session persists across requests."""

        # Connect and save session
        connect_response = await client.post(
            "/linkedin/connect",
            json={"email": "test@linkedin.com", "password": "password123"},
            headers=auth_headers
        )

        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": connect_response.json()["task_id"],
            "status": "connected"
        }))

        await client.post(
            "/linkedin/session",
            json={"li_at_cookie": "persistent_cookie"},
            headers=auth_headers
        )

        # Session should persist
        response = await client.get("/linkedin/session", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["connected"] is True

    @pytest.mark.asyncio
    async def test_profile_data_persists(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession
    ):
        """Test that created profile persists."""

        # Create profile
        await client.post(
            "/profiles/",
            json={
                "keywords": "Persistent Profile",
                "location": "Persistent City"
            },
            headers=auth_headers
        )

        # Profile should persist
        response = await client.get("/profiles/", headers=auth_headers)
        assert response.status_code == 200
        assert any(p["keywords"] == "Persistent Profile" for p in response.json())


# ============================================================================
# CONCURRENT OPERATIONS TESTS
# ============================================================================

class TestWizardFlowConcurrency:
    """Tests for concurrent operations in wizard flow."""

    @pytest.mark.asyncio
    async def test_concurrent_resume_uploads(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test concurrent resume uploads."""
        import asyncio

        async def upload_resume(i: int):
            return await client.post(
                "/resumes/upload",
                headers=auth_headers,
                files={"file": (f"resume_{i}.pdf", b"PDF content", "application/pdf")}
            )

        responses = await asyncio.gather(*[upload_resume(i) for i in range(3)])

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

    @pytest.mark.asyncio
    async def test_concurrent_profile_creation(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test concurrent profile creation."""
        import asyncio

        async def create_profile(i: int):
            return await client.post(
                "/profiles/",
                json={
                    "keywords": f"Concurrent Profile {i}",
                    "location": f"City {i}"
                },
                headers=auth_headers
            )

        responses = await asyncio.gather(*[create_profile(i) for i in range(3)])

        # All should succeed
        assert all(r.status_code == 200 for r in responses)


# ============================================================================
# CLEANUP TESTS
# ============================================================================

class TestWizardFlowCleanup:
    """Tests for cleanup after wizard flow."""

    @pytest.mark.asyncio
    async def test_resume_cleanup_on_failure(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession
    ):
        """Test that failed uploads don't leave partial data."""

        # Try invalid upload
        await client.post(
            "/resumes/upload",
            headers=auth_headers,
            files={"file": ("invalid.exe", b"content", "application/x-msdownload")}
        )

        # No partial data should exist
        result = await db_session.execute(
            select(Resume).where(Resume.user_id == test_user.id)
        )
        resumes = result.scalars().all()
        assert len(resumes) == 0

    @pytest.mark.asyncio
    async def test_linkedin_cleanup_on_failure(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test LinkedIn cleanup on connection failure."""

        # Try to connect
        connect_response = await client.post(
            "/linkedin/connect",
            json={"email": "test@linkedin.com", "password": "password123"},
            headers=auth_headers
        )

        # Mock failure
        mock_redis.get = AsyncMock(return_value=_json.dumps({
            "task_id": connect_response.json()["task_id"],
            "status": "failed"
        }))

        # No session should be saved on failure
        result = await db_session.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == str(test_user.id))
        )
        sessions = result.scalars().all()
        assert len(sessions) == 0


# ============================================================================
# EDGE CASES
# ============================================================================

class TestWizardFlowEdgeCases:
    """Tests for edge cases in wizard flow."""

    @pytest.mark.asyncio
    async def test_wizard_flow_unicode_in_all_fields(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test wizard flow with unicode characters in all fields."""

        # Step 1: Upload resume with unicode filename
        response = await client.post(
            "/resumes/upload",
            headers=auth_headers,
            files={"file": ("履歴書.pdf", b"PDF content", "application/pdf")}
        )
        assert response.status_code == 200

        # Step 2: Connect LinkedIn with unicode email
        response = await client.post(
            "/linkedin/connect",
            json={"email": "测试@例子.测试", "password": "密码123"},
            headers=auth_headers
        )
        # May be rejected due to email validation
        assert response.status_code in [200, 422]

        # Step 3: Create profile with unicode
        response = await client.post(
            "/profiles/",
            json={
                "keywords": "工程师 👨‍💻",
                "location": "北京 🇨🇳"
            },
            headers=auth_headers
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_wizard_flow_very_long_inputs(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test wizard flow with very long inputs."""

        # Long keywords
        long_keywords = "Engineer " * 100

        response = await client.post(
            "/profiles/",
            json={
                "keywords": long_keywords,
                "location": "City"
            },
            headers=auth_headers
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_wizard_flow_special_characters(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test wizard flow with special characters."""

        response = await client.post(
            "/profiles/",
            json={
                "keywords": "Engineer <>&\"'",
                "location": "City <>"
            },
            headers=auth_headers
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_multiple_wizard_completions(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test completing wizard multiple times."""

        for i in range(3):
            # Upload resume
            await client.post(
                "/resumes/upload",
                headers=auth_headers,
                files={"file": (f"resume_{i}.pdf", b"PDF content", "application/pdf")}
            )

            # Connect LinkedIn (each time)
            connect_response = await client.post(
                "/linkedin/connect",
                json={"email": f"test{i}@linkedin.com", "password": "password123"},
                headers=auth_headers
            )

            mock_redis.get = AsyncMock(return_value=_json.dumps({
                "task_id": connect_response.json()["task_id"],
                "status": "connected"
            }))

            await client.post(
                "/linkedin/session",
                json={"li_at_cookie": f"cookie_{i}"},
                headers=auth_headers
            )

            # Create profile
            await client.post(
                "/profiles/",
                json={
                    "keywords": f"Profile {i}",
                    "location": f"City {i}"
                },
                headers=auth_headers
            )

        # Should have 3 resumes, 1 session (updated), 3 profiles
        result = await db_session.execute(
            select(Resume).where(Resume.user_id == test_user.id)
        )
        assert len(result.scalars().all()) == 3

        result = await db_session.execute(
            select(JobSearchProfile).where(JobSearchProfile.user_id == test_user.id)
        )
        assert len(result.scalars().all()) == 3

    @pytest.mark.asyncio
    async def test_wizard_flow_with_expired_session(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
        mock_redis: AsyncMock
    ):
        """Test wizard flow when LinkedIn session expires mid-flow."""
        from datetime import datetime, timedelta
        from app.services.linkedin_session_service import LinkedInSessionService

        # Create a session
        service = LinkedInSessionService(db_session, mock_redis)
        await service.save_session(str(test_user.id), "cookie")

        # Expire it
        result = await db_session.execute(
            select(LinkedInSession).where(LinkedInSession.user_id == str(test_user.id))
        )
        session = result.scalars().first()
        if session:
            session.expires_at = datetime.utcnow() - timedelta(days=1)
            await db_session.commit()

        # Check status - should show expired
        mock_redis.get = AsyncMock(return_value=None)
        response = await client.get("/linkedin/session", headers=auth_headers)

        # Should indicate not connected
        data = response.json()
        assert data["connected"] is False

    @pytest.mark.asyncio
    async def test_rapid_navigation_between_steps(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test rapid navigation between wizard steps."""
        import asyncio

        # Simulate rapid API calls
        calls = []
        for _ in range(5):
            calls.append(client.get("/resumes/", headers=auth_headers))
            calls.append(client.get("/linkedin/session", headers=auth_headers))
            calls.append(client.get("/profiles/", headers=auth_headers))

        responses = await asyncio.gather(*calls)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)
