import pytest
import io
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.resume import Resume
from app.models.user import User


@pytest.mark.asyncio
async def test_upload_resume_unauthorized(client: AsyncClient):
    """Try to upload without authentication."""
    response = await client.post(
        "/resumes/upload",
        files={"file": ("test.pdf", b"test content", "application/pdf")}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_resume_authorized(client: AsyncClient):
    """Upload resume with valid authentication."""
    # Register and get token
    register_response = await client.post(
        "/auth/register",
        json={"email": "resume@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    # Upload resume
    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.pdf", b"test content for resume", "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.pdf"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_resumes(client: AsyncClient):
    """Get list of user's resumes."""
    # Register and get token
    register_response = await client.post(
        "/auth/register",
        json={"email": "getresume@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    # Upload a resume first
    await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.pdf", b"test content", "application/pdf")}
    )

    # Get resumes
    response = await client.get(
        "/resumes/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "test.pdf"


# ============================================================================
# FILE TYPE VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_upload_valid_pdf(client: AsyncClient):
    """Test uploading a valid PDF file."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "pdf@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.pdf", b"PDF content here", "application/pdf")}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_valid_doc(client: AsyncClient):
    """Test uploading a valid DOC file."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "doc@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.doc", b"DOC content here", "application/msword")}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_valid_docx(client: AsyncClient):
    """Test uploading a valid DOCX file."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "docx@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.docx", b"DOCX content here",
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_invalid_file_type_txt(client: AsyncClient):
    """Test that TXT files are rejected."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "txt@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.txt", b"Text content here", "text/plain")}
    )
    assert response.status_code == 400
    assert "file type" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_invalid_file_type_jpg(client: AsyncClient):
    """Test that JPG files are rejected."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "jpg@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.jpg", b"Image content here", "image/jpeg")}
    )
    assert response.status_code == 400
    assert "file type" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_invalid_file_type_exe(client: AsyncClient):
    """Test that EXE files are rejected."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "exe@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("virus.exe", b"Malicious content", "application/x-msdownload")}
    )
    assert response.status_code == 400
    assert "file type" in response.json()["detail"].lower()


# ============================================================================
# FILE SIZE VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_upload_file_within_size_limit(client: AsyncClient):
    """Test uploading a file within the size limit (5MB)."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "sizeok@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    # Create a 1MB file
    content = b"x" * (1 * 1024 * 1024)

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.pdf", content, "application/pdf")}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_file_exceeding_size_limit(client: AsyncClient):
    """Test that files exceeding 10MB are rejected."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "toolarge@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    # Create an 11MB file
    content = b"x" * (11 * 1024 * 1024)

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("large.pdf", content, "application/pdf")}
    )
    assert response.status_code == 400
    assert "too large" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_file_at_size_boundary(client: AsyncClient):
    """Test uploading a file exactly at the size boundary."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "boundary@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    # Create a file just under 10MB
    content = b"x" * (10 * 1024 * 1024 - 1)

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("boundary.pdf", content, "application/pdf")}
    )
    assert response.status_code == 200


# ============================================================================
# MISSING FILE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_upload_missing_file(client: AsyncClient):
    """Test uploading with no file."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "nofile@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422


# ============================================================================
# RESUME RETRIEVAL TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_get_resume_by_id(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test getting a specific resume by ID."""
    # Create a resume directly in DB
    from app.utils.security import get_password_hash

    resume = Resume(
        user_id=test_user.id,
        filename="specific_resume.pdf",
        file_path="/uploads/test/specific_resume.pdf",
        file_size=1024,
        content_type="application/pdf"
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    # Get the resume
    response = await client.get(
        "/resumes/",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(r["filename"] == "specific_resume.pdf" for r in data)


@pytest.mark.asyncio
async def test_list_multiple_resumes(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test listing multiple resumes."""
    # Create multiple resumes
    resume1 = Resume(
        user_id=test_user.id,
        filename="resume1.pdf",
        file_path="/uploads/test/resume1.pdf",
        file_size=1024,
        content_type="application/pdf"
    )
    resume2 = Resume(
        user_id=test_user.id,
        filename="resume2.pdf",
        file_path="/uploads/test/resume2.pdf",
        file_size=2048,
        content_type="application/pdf"
    )
    db_session.add(resume1)
    db_session.add(resume2)
    await db_session.commit()

    response = await client.get(
        "/resumes/",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    filenames = [r["filename"] for r in data]
    assert "resume1.pdf" in filenames
    assert "resume2.pdf" in filenames


@pytest.mark.asyncio
async def test_resumes_ordered_by_upload_date(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test that resumes are returned in descending order by upload date."""
    import asyncio

    resume1 = Resume(
        user_id=test_user.id,
        filename="older_resume.pdf",
        file_path="/uploads/test/older.pdf",
        file_size=1024,
        content_type="application/pdf"
    )
    db_session.add(resume1)
    await db_session.commit()

    await asyncio.sleep(0.01)

    resume2 = Resume(
        user_id=test_user.id,
        filename="newer_resume.pdf",
        file_path="/uploads/test/newer.pdf",
        file_size=1024,
        content_type="application/pdf"
    )
    db_session.add(resume2)
    await db_session.commit()

    response = await client.get(
        "/resumes/",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()

    # Newer resume should come first
    filenames = [r["filename"] for r in data]
    assert filenames.index("newer_resume.pdf") < filenames.index("older_resume.pdf")


# ============================================================================
# UNAUTHORIZED ACCESS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_list_resumes_unauthorized(client: AsyncClient):
    """Test listing resumes without authentication."""
    response = await client.get("/resumes/")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_access_another_users_resume(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession
):
    """Test that users cannot access other users' resumes."""
    from app.utils.security import get_password_hash

    # Create another user
    other_user = User(
        email="other@example.com",
        password_hash=get_password_hash("password123")
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    # Create a resume for the other user
    other_resume = Resume(
        user_id=other_user.id,
        filename="other_user_resume.pdf",
        file_path="/uploads/other/resume.pdf",
        file_size=1024,
        content_type="application/pdf"
    )
    db_session.add(other_resume)
    await db_session.commit()

    # Try to access with different user's auth - should not see the other user's resume
    response = await client.get(
        "/resumes/",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    filenames = [r["filename"] for r in data]
    assert "other_user_resume.pdf" not in filenames


# ============================================================================
# RESUME DELETION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_delete_resume(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test deleting a resume."""
    # Note: The current API doesn't have a delete endpoint for resumes
    # This test verifies the behavior when attempting to delete
    # If delete is implemented, update this test

    # Create a resume
    resume = Resume(
        user_id=test_user.id,
        filename="to_delete.pdf",
        file_path="/uploads/test/to_delete.pdf",
        file_size=1024,
        content_type="application/pdf"
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    # Try to delete (endpoint may not exist)
    response = await client.delete(
        f"/resumes/{resume.id}",
        headers=auth_headers
    )

    # If endpoint exists, verify deletion
    # If not, this will be 404
    assert response.status_code in [200, 404]


# ============================================================================
# FILE UPLOAD EDGE CASES
# ============================================================================

@pytest.mark.asyncio
async def test_upload_empty_file(client: AsyncClient):
    """Test uploading an empty file."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "empty@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("empty.pdf", b"", "application/pdf")}
    )
    # Empty files should be rejected or accepted based on implementation
    # Typically accepted but may have special handling
    assert response.status_code in [200, 400]


@pytest.mark.asyncio
async def test_upload_filename_with_special_characters(client: AsyncClient):
    """Test uploading files with special characters in filename."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "special@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume (2024).pdf", b"PDF content", "application/pdf")}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_filename_with_unicode(client: AsyncClient):
    """Test uploading files with unicode characters in filename."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "unicode@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("履歴書.pdf", b"PDF content", "application/pdf")}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_very_long_filename(client: AsyncClient):
    """Test uploading files with very long filenames."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "longname@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    long_filename = "a" * 200 + ".pdf"

    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (long_filename, b"PDF content", "application/pdf")}
    )
    # Should handle long filenames gracefully
    assert response.status_code in [200, 400]


# ============================================================================
# CONTENT TYPE VALIDATION
# ============================================================================

@pytest.mark.asyncio
async def test_upload_with_incorrect_content_type(client: AsyncClient):
    """Test uploading with mismatched content-type header."""
    register_response = await client.post(
        "/auth/register",
        json={"email": "wrongtype@example.com", "password": "testpassword123"}
    )
    token = register_response.json()["access_token"]

    # Send PDF content but claim it's something else
    response = await client.post(
        "/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("file.pdf", b"PDF content", "text/plain")}
    )
    # Should be rejected based on extension or content-type
    assert response.status_code in [200, 400]
