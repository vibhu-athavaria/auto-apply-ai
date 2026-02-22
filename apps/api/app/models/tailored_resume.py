import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index

from app.database import Base
from app.models.user import TimestampMixin


class TailoredResume(Base, TimestampMixin):
    """Model for storing LLM-tailored resumes."""
    __tablename__ = "tailored_resumes"

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
    original_resume_id = Column(
        String(36),
        ForeignKey("resumes.id"),
        nullable=False
    )
    tailored_resume_text = Column(Text, nullable=False)
    cover_letter = Column(Text, nullable=True)
    input_hash = Column(String(64), nullable=False, index=True)

    # Add unique constraint on (user_id, job_id) to prevent duplicates
    __table_args__ = (
        Index("idx_tailored_resumes_user_job", "user_id", "job_id", unique=True),
    )
