"""
LinkedIn Session Router - API endpoints for LinkedIn session management.

Endpoints:
- POST /linkedin/session - Save LinkedIn session cookie
- GET /linkedin/session - Get session status
- DELETE /linkedin/session - Delete session
- POST /linkedin/session/validate - Validate session
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.schemas.linkedin import (
    LinkedInSessionCreate,
    LinkedInSessionResponse,
    LinkedInSessionStatus,
    LinkedInConnectRequest,
    LinkedInConnectResponse,
    LinkedInAuthTaskStatus
)
from app.services.linkedin_session_service import LinkedInSessionService
from app.utils.security import get_current_user

router = APIRouter(tags=["linkedin"])


async def get_redis():
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@router.post("/session", response_model=LinkedInSessionResponse)
async def save_session(
    session_data: LinkedInSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis)
):
    """Save user's LinkedIn session cookie (encrypted in DB, plaintext in Redis for worker)."""
    service = LinkedInSessionService(db, redis_client)
    session = await service.save_session(
        user_id=str(current_user.id),
        li_at_cookie=session_data.li_at_cookie
    )
    return session


@router.get("/session", response_model=LinkedInSessionStatus)
async def get_session_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's LinkedIn session status (no cookie returned)."""
    service = LinkedInSessionService(db)
    status = await service.get_session_status(str(current_user.id))
    return status


@router.delete("/session")
async def delete_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis)
):
    """Delete user's LinkedIn session from DB and Redis."""
    service = LinkedInSessionService(db, redis_client)
    await service.delete_session(str(current_user.id))
    return {"message": "Session deleted"}


@router.post("/session/validate", response_model=LinkedInSessionStatus)
async def validate_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis)
):
    """Validate LinkedIn session by making a live request to LinkedIn."""
    service = LinkedInSessionService(db, redis_client)
    status = await service.validate_session(str(current_user.id))
    return status


@router.post("/connect", response_model=LinkedInConnectResponse)
async def connect_linkedin(
    request: LinkedInConnectRequest,
    current_user: User = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis)
):
    """
    Connect LinkedIn using email + password.

    The password is used once to log in via Playwright and is NEVER stored.
    Only the resulting session cookie (li_at) is encrypted and persisted.

    Returns a task_id to poll for connection status.
    """
    import json
    import uuid

    task_id = str(uuid.uuid4())

    task_data = {
        "task_id": task_id,
        "user_id": str(current_user.id),
        "email": request.email,
        "password": request.password,
        "type": "linkedin_auth"
    }

    await redis_client.setex(
        f"li_autopilot:api:auth_task:{task_id}",
        300,
        json.dumps({"task_id": task_id, "status": "connecting", "message": None})
    )

    await redis_client.rpush(
        "li_autopilot:tasks:linkedin_auth",
        json.dumps(task_data)
    )

    return LinkedInConnectResponse(task_id=task_id)


@router.get("/connect/status/{task_id}", response_model=LinkedInAuthTaskStatus)
async def get_connect_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis)
):
    """
    Poll the status of a LinkedIn connection task.

    Statuses: connecting | connected | failed | challenge_required
    """
    import json

    raw = await redis_client.get(f"li_autopilot:api:auth_task:{task_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="Task not found or expired")

    return json.loads(raw)
