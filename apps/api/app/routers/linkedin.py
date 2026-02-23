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
    LinkedInSessionStatus
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
