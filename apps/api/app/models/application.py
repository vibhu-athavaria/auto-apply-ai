import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import ENUM

from app.database import Base
from app.models.user import TimestampMixin

application_status = ENUM(
    "pending",
    "submitted",
    "completed",
    "failed",
    "skipped",
    name="application_status",
    create_type=True
)


class Application(Base, TimestampMixin):
    """Model for tracking job applications."""
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    job_id = Column(
        String(36),
        ForeignKey("jobs.id"),
        nullable=False,
        index=True
    )
    tailored_resume_id = Column(
        String(36),
        ForeignKey("tailored_resumes.id"),
        nullable=True
    )
    status = Column(application_status, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    linkedin_application_id = Column(String(100), nullable=True)
    submitted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_applications_user_job", "user_id", "job_id", unique=True),
    )
