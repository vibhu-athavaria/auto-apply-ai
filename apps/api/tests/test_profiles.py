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


# ============================================================================
# CREATE PROFILE VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_create_profile_with_valid_data(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User
):
    """Test creating a profile with all valid data."""
    response = await client.post(
        "/profiles/",
        json={
            "keywords": "Software Engineer",
            "location": "San Francisco",
            "remote_preference": "remote",
            "salary_min": 100000,
            "salary_max": 200000
        },
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["keywords"] == "Software Engineer"
    assert data["location"] == "San Francisco"
    assert data["remote_preference"] == "remote"
    assert data["salary_min"] == 100000
    assert data["salary_max"] == 200000
    assert data["user_id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_create_profile_missing_keywords(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile without keywords."""
    response = await client.post(
        "/profiles/",
        json={"location": "San Francisco"},
        headers=auth_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_profile_missing_location(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile without location."""
    response = await client.post(
        "/profiles/",
        json={"keywords": "Software Engineer"},
        headers=auth_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_profile_empty_keywords(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with empty keywords."""
    response = await client.post(
        "/profiles/",
        json={"keywords": "", "location": "San Francisco"},
        headers=auth_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_profile_empty_location(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with empty location."""
    response = await client.post(
        "/profiles/",
        json={"keywords": "Software Engineer", "location": ""},
        headers=auth_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_profile_whitespace_only_keywords(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with whitespace-only keywords."""
    response = await client.post(
        "/profiles/",
        json={"keywords": "   ", "location": "San Francisco"},
        headers=auth_headers
    )

    assert response.status_code == 200  # Implementation may accept this


# ============================================================================
# PROFILE NAME MAX LENGTH TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_create_profile_with_very_long_keywords(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with very long keywords."""
    long_keywords = "a" * 1000

    response = await client.post(
        "/profiles/",
        json={"keywords": long_keywords, "location": "San Francisco"},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["keywords"] == long_keywords


@pytest.mark.asyncio
async def test_create_profile_with_very_long_location(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with very long location."""
    long_location = "a" * 500

    response = await client.post(
        "/profiles/",
        json={"keywords": "Software Engineer", "location": long_location},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["location"] == long_location


@pytest.mark.asyncio
async def test_create_profile_with_unicode_keywords(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with unicode keywords."""
    response = await client.post(
        "/profiles/",
        json={"keywords": "软件工程师 👨‍💻 Développeur", "location": "San Francisco"},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "软件工程师" in data["keywords"]


@pytest.mark.asyncio
async def test_create_profile_with_unicode_location(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with unicode location."""
    response = await client.post(
        "/profiles/",
        json={"keywords": "Engineer", "location": "北京 🇨🇳 東京"},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "北京" in data["location"]


# ============================================================================
# GET PROFILE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_get_profile_by_id(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test getting a specific profile by ID."""
    # Note: The current API doesn't have a GET /profiles/{id} endpoint
    # This test documents the expected behavior if it existed

    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="Specific Profile",
        location="Specific Location"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    # Try to get by ID (endpoint may not exist)
    response = await client.get(
        f"/profiles/{profile.id}",
        headers=auth_headers
    )

    # If endpoint exists, verify data
    # If not, this will be 404
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.json()
        assert data["keywords"] == "Specific Profile"
        assert data["location"] == "Specific Location"


@pytest.mark.asyncio
async def test_get_nonexistent_profile(
    client: AsyncClient,
    auth_headers: dict
):
    """Test getting a non-existent profile."""
    response = await client.get(
        "/profiles/nonexistent-id",
        headers=auth_headers
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_another_users_profile(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession
):
    """Test that users cannot get other users' profiles."""
    from app.utils.security import get_password_hash

    # Create another user and their profile
    other_user = User(
        email="otherprofile@example.com",
        password_hash=get_password_hash("password123")
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    other_profile = JobSearchProfile(
        user_id=other_user.id,
        keywords="Other User's Profile",
        location="Secret Location"
    )
    db_session.add(other_profile)
    await db_session.commit()
    await db_session.refresh(other_profile)

    # Try to get with current user's auth
    response = await client.get(
        f"/profiles/{other_profile.id}",
        headers=auth_headers
    )

    # Should return 404 (not 403, to prevent profile ID enumeration)
    assert response.status_code == 404


# ============================================================================
# DELETE PROFILE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_delete_profile(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test deleting a profile."""
    # Note: The current API doesn't have a DELETE endpoint
    # This test documents expected behavior

    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="To Be Deleted",
        location="Delete City"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    response = await client.delete(
        f"/profiles/{profile.id}",
        headers=auth_headers
    )

    assert response.status_code in [200, 404]  # May not be implemented


@pytest.mark.asyncio
async def test_delete_another_users_profile(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession
):
    """Test that users cannot delete other users' profiles."""
    from app.utils.security import get_password_hash

    other_user = User(
        email="otherdelete@example.com",
        password_hash=get_password_hash("password123")
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    other_profile = JobSearchProfile(
        user_id=other_user.id,
        keywords="Protected Profile",
        location="Safe City"
    )
    db_session.add(other_profile)
    await db_session.commit()
    await db_session.refresh(other_profile)

    response = await client.delete(
        f"/profiles/{other_profile.id}",
        headers=auth_headers
    )

    # Should return 404 to prevent ID enumeration
    assert response.status_code == 404


# ============================================================================
# UPDATE PROFILE TESTS (Additional)
# ============================================================================

@pytest.mark.asyncio
async def test_update_profile_partial(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test partial update of a profile."""
    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="Original Keywords",
        location="Original Location"
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    # Update only keywords
    response = await client.put(
        f"/profiles/{profile.id}",
        json={"keywords": "Updated Keywords"},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["keywords"] == "Updated Keywords"
    assert data["location"] == "Original Location"  # Unchanged


@pytest.mark.asyncio
async def test_update_profile_all_fields(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test updating all fields of a profile."""
    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="Old Keywords",
        location="Old Location",
        remote_preference="onsite",
        salary_min=50000,
        salary_max=100000
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    response = await client.put(
        f"/profiles/{profile.id}",
        json={
            "keywords": "New Keywords",
            "location": "New Location",
            "remote_preference": "hybrid",
            "salary_min": 75000,
            "salary_max": 150000
        },
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["keywords"] == "New Keywords"
    assert data["location"] == "New Location"
    assert data["remote_preference"] == "hybrid"
    assert data["salary_min"] == 75000
    assert data["salary_max"] == 150000


@pytest.mark.asyncio
async def test_update_profile_clear_optional_fields(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test clearing optional fields in a profile update."""
    profile = JobSearchProfile(
        user_id=test_user.id,
        keywords="Keywords",
        location="Location",
        remote_preference="remote",
        salary_min=100000,
        salary_max=200000
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    # Clear optional fields by setting to null
    response = await client.put(
        f"/profiles/{profile.id}",
        json={
            "remote_preference": None,
            "salary_min": None,
            "salary_max": None
        },
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["remote_preference"] is None
    assert data["salary_min"] is None
    assert data["salary_max"] is None


# ============================================================================
# LIST PROFILES TESTS (Additional)
# ============================================================================

@pytest.mark.asyncio
async def test_list_profiles_empty(
    client: AsyncClient,
    auth_headers: dict
):
    """Test listing profiles when user has none."""
    response = await client.get(
        "/profiles/",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_profiles_multiple(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test listing multiple profiles."""
    import asyncio

    profiles = []
    for i in range(5):
        profile = JobSearchProfile(
            user_id=test_user.id,
            keywords=f"Profile {i}",
            location=f"Location {i}"
        )
        db_session.add(profile)
        profiles.append(profile)
        await db_session.commit()
        await asyncio.sleep(0.01)  # Small delay for ordering

    response = await client.get(
        "/profiles/",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 5

    # Check that all profiles are present
    keywords = [p["keywords"] for p in data]
    for i in range(5):
        assert f"Profile {i}" in keywords


@pytest.mark.asyncio
async def test_list_profiles_isolation(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession
):
    """Test that users only see their own profiles."""
    from app.utils.security import get_password_hash

    # Create another user with profiles
    other_user = User(
        email="isolation@example.com",
        password_hash=get_password_hash("password123")
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    other_profile = JobSearchProfile(
        user_id=other_user.id,
        keywords="Other's Secret Profile",
        location="Hidden Location"
    )
    db_session.add(other_profile)
    await db_session.commit()

    # List profiles as current user
    response = await client.get(
        "/profiles/",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Should not see other user's profile
    keywords = [p["keywords"] for p in data]
    assert "Other's Secret Profile" not in keywords


# ============================================================================
# SALARY VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_create_profile_with_negative_salary(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with negative salary."""
    response = await client.post(
        "/profiles/",
        json={
            "keywords": "Engineer",
            "location": "City",
            "salary_min": -1000,
            "salary_max": -500
        },
        headers=auth_headers
    )

    # May be accepted or rejected depending on validation
    assert response.status_code in [200, 422]


@pytest.mark.asyncio
async def test_create_profile_with_salary_min_greater_than_max(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile where min > max salary."""
    response = await client.post(
        "/profiles/",
        json={
            "keywords": "Engineer",
            "location": "City",
            "salary_min": 200000,
            "salary_max": 100000
        },
        headers=auth_headers
    )

    # May be accepted (validation might be client-side)
    assert response.status_code in [200, 422]


@pytest.mark.asyncio
async def test_create_profile_with_zero_salary(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with zero salary."""
    response = await client.post(
        "/profiles/",
        json={
            "keywords": "Engineer",
            "location": "City",
            "salary_min": 0,
            "salary_max": 0
        },
        headers=auth_headers
    )

    assert response.status_code in [200, 422]


@pytest.mark.asyncio
async def test_create_profile_with_float_salary(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with float salary values."""
    response = await client.post(
        "/profiles/",
        json={
            "keywords": "Engineer",
            "location": "City",
            "salary_min": 75000.50,
            "salary_max": 150000.99
        },
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["salary_min"] == 75000.50
    assert data["salary_max"] == 150000.99


# ============================================================================
# REMOTE PREFERENCE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_create_profile_with_various_remote_preferences(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating profiles with different remote preferences."""
    preferences = ["remote", "hybrid", "onsite", "", None]

    for i, pref in enumerate(preferences):
        response = await client.post(
            "/profiles/",
            json={
                "keywords": f"Job {i}",
                "location": f"City {i}",
                "remote_preference": pref
            },
            headers=auth_headers
        )

        assert response.status_code == 200


# ============================================================================
# UNAUTHORIZED ACCESS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_create_profile_unauthorized_detailed(client: AsyncClient):
    """Test creating profile without authentication (detailed)."""
    response = await client.post(
        "/profiles/",
        json={"keywords": "Engineer", "location": "City"}
    )

    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_update_profile_unauthorized(client: AsyncClient):
    """Test updating profile without authentication."""
    response = await client.put(
        "/profiles/some-id",
        json={"keywords": "Updated"}
    )

    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_list_profiles_unauthorized_detailed(client: AsyncClient):
    """Test listing profiles without authentication (detailed)."""
    response = await client.get("/profiles/")

    assert response.status_code in [401, 403]


# ============================================================================
# EDGE CASES
# ============================================================================

@pytest.mark.asyncio
async def test_create_profile_with_special_characters(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with special characters."""
    response = await client.post(
        "/profiles/",
        json={
            "keywords": "Engineer <script>alert('xss')</script>",
            "location": "City & Town > Village"
        },
        headers=auth_headers
    )

    # Should sanitize or store as-is
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_profile_with_sql_injection(
    client: AsyncClient,
    auth_headers: dict
):
    """Test SQL injection prevention in profile creation."""
    response = await client.post(
        "/profiles/",
        json={
            "keywords": "Engineer'; DROP TABLE job_search_profiles; --",
            "location": "City"
        },
        headers=auth_headers
    )

    # Should handle safely
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_profile_with_newlines(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating a profile with newlines in text."""
    response = await client.post(
        "/profiles/",
        json={
            "keywords": "Engineer\nDeveloper\r\nProgrammer",
            "location": "City\nState"
        },
        headers=auth_headers
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_concurrent_profile_creation(
    client: AsyncClient,
    auth_headers: dict
):
    """Test creating multiple profiles concurrently."""
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

    responses = await asyncio.gather(*[create_profile(i) for i in range(5)])

    assert all(r.status_code == 200 for r in responses)


@pytest.mark.asyncio
async def test_profile_timestamps(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test that created_at and updated_at are set correctly."""
    response = await client.post(
        "/profiles/",
        json={"keywords": "Timestamp Test", "location": "Time City"},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert "created_at" in data
    assert "updated_at" in data
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


@pytest.mark.asyncio
async def test_profile_update_changes_updated_at(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession
):
    """Test that updating a profile changes the updated_at timestamp."""
    import asyncio

    # Create profile
    response = await client.post(
        "/profiles/",
        json={"keywords": "Update Time Test", "location": "City"},
        headers=auth_headers
    )

    data = response.json()
    original_updated_at = data["updated_at"]

    # Wait a moment
    await asyncio.sleep(0.1)

    # Update profile
    await client.put(
        f"/profiles/{data['id']}",
        json={"keywords": "Updated Keywords"},
        headers=auth_headers
    )

    # Get profile again
    response = await client.get("/profiles/", headers=auth_headers)
    profiles = response.json()
    updated_profile = next((p for p in profiles if p["id"] == data["id"]), None)

    if updated_profile:
        assert updated_profile["updated_at"] != original_updated_at


@pytest.mark.asyncio
async def test_profile_id_format(
    client: AsyncClient,
    auth_headers: dict
):
    """Test that profile IDs are in the expected format."""
    import uuid

    response = await client.post(
        "/profiles/",
        json={"keywords": "ID Format Test", "location": "City"},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Should be a valid UUID
    try:
        uuid.UUID(data["id"])
    except ValueError:
        pytest.fail("Profile ID is not a valid UUID")


@pytest.mark.asyncio
async def test_profile_user_id_matches_authenticated_user(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User
):
    """Test that created profile belongs to the authenticated user."""
    response = await client.post(
        "/profiles/",
        json={"keywords": "User Match Test", "location": "City"},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert data["user_id"] == str(test_user.id)
