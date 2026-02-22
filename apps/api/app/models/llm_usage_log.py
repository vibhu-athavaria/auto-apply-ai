import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Numeric, ForeignKey

from app.database import Base
from app.models.user import TimestampMixin


class LLMUsageLog(Base, TimestampMixin):
    """Model for tracking LLM API usage and costs."""
    __tablename__ = "llm_usage_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    estimated_cost = Column(Numeric(10, 6), nullable=False)
    model = Column(String(100), nullable=False)
    operation = Column(String(50), nullable=False)  # e.g., "tailor_resume"
