from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr


LinkedInStatus = Literal["connected", "expired", "invalid", "not_set", "connecting", "challenge_required"]


class LinkedInSessionCreate(BaseModel):
    """Schema for creating/updating LinkedIn session via cookie (admin/advanced use)."""
    li_at_cookie: str = Field(..., description="LinkedIn li_at session cookie value", min_length=1)


class LinkedInConnectRequest(BaseModel):
    """Schema for connecting LinkedIn via email + password.
    Password is used once and NEVER stored.
    """
    email: EmailStr = Field(..., description="LinkedIn account email")
    password: str = Field(..., description="LinkedIn account password (never stored)", min_length=1)


class LinkedInConnectResponse(BaseModel):
    """Returned immediately after POST /linkedin/connect."""
    task_id: str
    status: str = "connecting"
    message: str = "LinkedIn connection initiated. Check status with task_id."


class LinkedInAuthTaskStatus(BaseModel):
    """Status of a background LinkedIn auth task."""
    task_id: str
    status: str
    message: Optional[str] = None


class LinkedInSessionResponse(BaseModel):
    """Schema for LinkedIn session response (no cookie returned)."""
    id: str
    user_id: str
    status: LinkedInStatus
    last_validated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LinkedInSessionStatus(BaseModel):
    """Schema for LinkedIn session status check."""
    connected: bool
    status: LinkedInStatus
    last_validated: Optional[str] = None
    expires_at: Optional[str] = None
    message: Optional[str] = None
