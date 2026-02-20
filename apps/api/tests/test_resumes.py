import pytest
import io
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_upload_resume_unauthorized(client: AsyncClient):
    # Try to upload without authentication
    response = await client.post(
        "/resumes/upload",
        files={"file": ("test.pdf", b"test content", "application/pdf")}
    )
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_upload_resume_authorized(client: AsyncClient):
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