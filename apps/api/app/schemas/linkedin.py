from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


LinkedInStatus = Literal["connected", "expired", "invalid", "not_set"]


class LinkedInSessionCreate(BaseModel):
    """Schema for creating/updating LinkedIn session."""
    li_at_cookie: str = Field(
        ...,
        description="LinkedIn li_at session cookie value",
        min_length=1
    )


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
