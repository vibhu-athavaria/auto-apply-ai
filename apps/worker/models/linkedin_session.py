import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import ENUM

from models.job import Base, TimestampMixin

linkedin_status = ENUM(
    "connected",
    "expired",
    "invalid",
    "not_set",
    name="linkedin_status",
    create_type=False
)


class LinkedInSession(Base, TimestampMixin):
    """Model for storing user's LinkedIn session cookie (encrypted)."""
    __tablename__ = "linkedin_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True
    )
    encrypted_cookie = Column(Text, nullable=False)
    status = Column(linkedin_status, nullable=False, default="connected")
    last_validated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
