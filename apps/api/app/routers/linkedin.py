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

from app.database import get_db
from app.models.user import User
from app.schemas.linkedin import (
    LinkedInSessionCreate,
    LinkedInSessionResponse,
    LinkedInSessionStatus
)
from app.services.linkedin_session_service import LinkedInSessionService
from app.utils.security import get_current_user

router = APIRouter(prefix="/linkedin", tags=["linkedin"])


@router.post("/session", response_model=LinkedInSessionResponse)
async def save_session(
    session_data: LinkedInSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Save user's LinkedIn session cookie (encrypted).

    The cookie is encrypted before storage and never returned in plain text.
    """
    service = LinkedInSessionService(db)
    session = await service.save_session(
        user_id=current_user.id,
        li_at_cookie=session_data.li_at_cookie
    )
    return session


@router.get("/session", response_model=LinkedInSessionStatus)
async def get_session_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's LinkedIn session status.

    Returns status only, not the actual cookie.
    """
    service = LinkedInSessionService(db)
    status = await service.get_session_status(current_user.id)
    return status


@router.delete("/session")
async def delete_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete user's LinkedIn session.
    """
    service = LinkedInSessionService(db)
    await service.delete_session(current_user.id)
    return {"message": "Session deleted"}


@router.post("/session/validate", response_model=LinkedInSessionStatus)
async def validate_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Validate user's LinkedIn session by making a test request.
    """
    service = LinkedInSessionService(db)
    status = await service.validate_session(current_user.id)
    return status
