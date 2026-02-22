from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from decimal import Decimal


class TailorRequest(BaseModel):
    """Schema for tailor resume request."""
    resume_id: str = Field(..., description="ID of the original resume to tailor")
    job_id: str = Field(..., description="ID of the job to tailor for")


class TailoredResumeResponse(BaseModel):
    """Schema for tailored resume response."""
    id: str = Field(..., description="Tailored resume ID")
    user_id: str = Field(..., description="User ID")
    job_id: str = Field(..., description="Job ID")
    original_resume_id: str = Field(..., description="Original resume ID")
    tailored_resume_text: str = Field(..., description="Tailored resume content")
    cover_letter: Optional[str] = Field(None, description="Generated cover letter")
    input_hash: str = Field(..., description="Hash of input for caching")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class LLMUsageResponse(BaseModel):
    """Schema for LLM usage information in response."""
    prompt_tokens: int = Field(..., description="Number of prompt tokens used")
    completion_tokens: int = Field(..., description="Number of completion tokens used")
    estimated_cost: Decimal = Field(..., description="Estimated cost in USD")
    cached: bool = Field(default=False, description="Whether result was from cache")


class TailorResponse(BaseModel):
    """Schema for complete tailor response."""
    tailored_resume: TailoredResumeResponse
    usage: LLMUsageResponse


class UserCostSummary(BaseModel):
    """Schema for user's cumulative LLM cost."""
    user_id: str = Field(..., description="User ID")
    total_prompt_tokens: int = Field(..., description="Total prompt tokens used")
    total_completion_tokens: int = Field(..., description="Total completion tokens used")
    total_cost: Decimal = Field(..., description="Total estimated cost in USD")
    operation_counts: dict = Field(..., description="Count of operations by type")
