import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.auth_service import AuthService
from app.schemas.auth import UserCreate


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


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login with non-existent user."""
    response = await client.post(
        "/auth/login",
        json={"email": "nonexistent@example.com", "password": "testpassword123"}
    )
    assert response.status_code == 401


class TestAuthService:
    """Tests for AuthService."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, db_session: AsyncSession):
        """Test successful user creation."""
        user_create = UserCreate(
            email="newuser@example.com",
            password="securepassword123"
        )

        user = await AuthService.create_user(db_session, user_create)

        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.password_hash != "securepassword123"  # Should be hashed

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, db_session: AsyncSession):
        """Test creating user with duplicate email raises error."""
        user_create1 = UserCreate(
            email="duplicate@example.com",
            password="password123"
        )
        user_create2 = UserCreate(
            email="duplicate@example.com",
            password="password456"
        )

        # First user should succeed
        await AuthService.create_user(db_session, user_create1)

        # Second user with same email should fail
        with pytest.raises(ValueError) as exc_info:
            await AuthService.create_user(db_session, user_create2)

        assert "already registered" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authenticate_user_success(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test successful user authentication."""
        # test_user is created with password "testpassword123"
        authenticated = await AuthService.authenticate_user(
            db_session,
            "test@example.com",
            "testpassword123"
        )

        assert authenticated is not None
        assert authenticated.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test authentication with wrong password."""
        authenticated = await AuthService.authenticate_user(
            db_session,
            "test@example.com",
            "wrongpassword"
        )

        assert authenticated is None

    @pytest.mark.asyncio
    async def test_authenticate_user_nonexistent_email(
        self,
        db_session: AsyncSession
    ):
        """Test authentication with non-existent email."""
        authenticated = await AuthService.authenticate_user(
            db_session,
            "nonexistent@example.com",
            "anypassword"
        )

        assert authenticated is None