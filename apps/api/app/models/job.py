import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer

from app.database import Base
from app.models.user import TimestampMixin


class Job(Base, TimestampMixin):
    """Job model for storing LinkedIn job listings."""
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    linkedin_job_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    company = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    job_url = Column(Text, nullable=False)
    easy_apply = Column(Boolean, default=False, nullable=False)
    description = Column(Text, nullable=True)
    search_profile_id = Column(
        String(36),
        ForeignKey("job_search_profiles.id"),
        nullable=False,
        index=True
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    status = Column(String(50), default="discovered", nullable=False, index=True)
    discovered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    match_score = Column(Integer, nullable=True, index=True, doc="Job match score 0-100 calculated based on resume vs job requirements")
