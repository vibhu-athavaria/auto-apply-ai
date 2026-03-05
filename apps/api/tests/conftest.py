import asyncio
import json
import pytest
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.resume import Resume
from app.utils.security import get_password_hash, create_access_token
from app.services.queue_service import get_queue_service
from app.services.llm_service import get_llm_service

# Test database URL (using SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def mock_redis():
    """Create a mock Redis client for testing."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    mock.set = AsyncMock(return_value=True)
    mock.rpush = AsyncMock(return_value=1)
    mock.close = AsyncMock()
    mock.delete = AsyncMock(return_value=1)
    return mock


@pytest.fixture(scope="function")
async def client(
    db_session: AsyncSession,
    mock_redis: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    async def override_get_queue_service():
        # Create a mock QueueService with the mock redis
        from app.services.queue_service import QueueService
        queue_service = QueueService(mock_redis)
        yield queue_service

    async def override_get_llm_service():
        # Create a mock LLMService with the mock redis
        from app.services.llm_service import LLMService
        llm_service = LLMService(mock_redis)
        yield llm_service

    async def override_get_redis():
        yield mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_queue_service] = override_get_queue_service
    app.dependency_overrides[get_llm_service] = override_get_llm_service

    from app.routers.applications import get_redis as get_applications_redis
    from app.routers.linkedin import get_redis as get_linkedin_redis
    from app.routers.jobs import get_redis_client as get_jobs_redis
    app.dependency_overrides[get_applications_redis] = override_get_redis
    app.dependency_overrides[get_linkedin_redis] = override_get_redis
    app.dependency_overrides[get_jobs_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user for authentication tests."""
    user = User(
        email="test@example.com",
        password_hash=get_password_hash("testpassword123")
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
async def auth_headers(test_user: User) -> dict:
    """Generate authorization headers for the test user."""
    token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
async def test_resume(db_session: AsyncSession, test_user: User) -> Resume:
    """Create a test resume for resume-related tests."""
    resume = Resume(
        user_id=test_user.id,
        filename="test_resume.txt",
        file_path="/tmp/test_resume.txt",
        file_size=1024,
        content_type="text/plain"
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume
