import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey

from app.database import Base
from app.models.user import TimestampMixin

class JobSearchProfile(Base, TimestampMixin):
    __tablename__ = "job_search_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    keywords = Column(String(500), nullable=False)
    location = Column(String(255), nullable=False)
    remote_preference = Column(String(50), nullable=True)
    experience_level = Column(String(50), nullable=True)
    job_type = Column(String(50), nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)