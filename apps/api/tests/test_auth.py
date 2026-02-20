import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    response = await client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "testpassword123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    # Register first user
    await client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "testpassword123"}
    )

    # Try to register with same email
    response = await client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "testpassword123"}
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login_user(client: AsyncClient):
    # Register user first
    await client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "testpassword123"}
    )

    # Login
    response = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "testpassword123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    # Register user first
    await client.post(
        "/auth/register",
        json={"email": "wrongpass@example.com", "password": "testpassword123"}
    )

    # Login with wrong password
    response = await client.post(
        "/auth/login",
        json={"email": "wrongpass@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401