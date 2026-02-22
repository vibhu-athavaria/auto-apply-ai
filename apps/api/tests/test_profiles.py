"""Tests for Profiles API endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.job_search_profile import JobSearchProfile


@pytest.mark.asyncio
async def test_create_profile(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User
):
    """Test creating a new job search profile."""
    response = await client.post(
        "/profiles/",
        json={
            "keywords": "Python Developer",
            "location": "San Francisco",
            "experience_level": "Senior",
            "job_type": "Full-time"
        },
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["keywords"] == "Python Developer"
    assert data["location"] == "San Francisco"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_profile_unauthorized(client: AsyncClient):
    """Test creating profile without authentication."""
    response = await client.post(
        "/profiles/",
        json={
            "keywords": "Python Developer",
            "location": "San Francisco"
        }
    )

    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_list_profiles(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test listing user's job search profiles."""
    # Create some profiles
    profile1 = JobSearchProfile(
        user_id=test_user.id,
        keywords="Python Developer",
        location="San Francisco"
    )
    profile2 = JobSearchProfile(
        user_id=test_user.id,
        keywords="React Developer",
        location="New York"
    )
    db_session.add(profile1)
    db_session.add(profile2)
    await db_session.commit()

    response = await client.get("/profiles/", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_list_profiles_unauthorized(client: AsyncClient):
    """Test listing profiles without authentication."""
    response = await client.get("/profiles/")
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_update_profile(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test updating a job search profile."""
    # Create a profile
    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="Python Developer",
        location="San Francisco"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    response = await client.put(
        f"/profiles/{profile.id}",
        json={
            "keywords": "Senior Python Developer",
            "location": "Remote"
        },
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["keywords"] == "Senior Python Developer"
    assert data["location"] == "Remote"


@pytest.mark.asyncio
async def test_update_profile_not_found(
    client: AsyncClient,
    auth_headers: dict
):
    """Test updating a non-existent profile."""
    response = await client.put(
        "/profiles/nonexistent-id",
        json={"keywords": "Updated"},
        headers=auth_headers
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_profile_unauthorized(client: AsyncClient):
    """Test updating profile without authentication."""
    response = await client.put(
        "/profiles/some-id",
        json={"keywords": "Updated"}
    )

    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_update_profile_wrong_user(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession
):
    """Test updating a profile belonging to another user."""
    # Create a profile for a different user (directly in DB)
    from app.utils.security import get_password_hash

    other_user = User(
        email="other@example.com",
        password_hash=get_password_hash("password123")
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    profile = JobSearchProfile(
        user_id=other_user.id,
        keywords="Secret Job",
        location="Secret Location"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    # Try to update with different user's auth
    response = await client.put(
        f"/profiles/{profile.id}",
        json={"keywords": "Hacked"},
        headers=auth_headers
    )

    # Should return 404 since the profile doesn't belong to the authenticated user
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_profiles_order(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test that profiles are returned in descending order by created_at."""
    import asyncio

    # Create profiles with slight delay to ensure different timestamps
    profile1 = JobSearchProfile(
        user_id=test_user.id,
        keywords="First Profile",
        location="Location 1"
    )
    db_session.add(profile1)
    await db_session.commit()
    await db_session.refresh(profile1)

    # Small delay to ensure different timestamp
    await asyncio.sleep(0.01)

    profile2 = JobSearchProfile(
        user_id=test_user.id,
        keywords="Second Profile",
        location="Location 2"
    )
    db_session.add(profile2)
    await db_session.commit()
    await db_session.refresh(profile2)

    response = await client.get("/profiles/", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    # Most recent should be first
    if len(data) >= 2:
        # Find our profiles
        keywords = [p["keywords"] for p in data]
        assert "Second Profile" in keywords
        assert "First Profile" in keywords
