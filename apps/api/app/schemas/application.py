from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


ApplicationStatus = Literal["pending", "submitted", "completed", "failed", "skipped"]


class ApplicationCreate(BaseModel):
    """Schema for creating a new application."""
    job_id: str = Field(..., description="ID of the job to apply to")
    tailored_resume_id: Optional[str] = Field(None, description="ID of the tailored resume to use")


class ApplicationResponse(BaseModel):
    """Schema for application response."""
    id: str = Field(..., description="Application ID")
    user_id: str = Field(..., description="User ID")
    job_id: str = Field(..., description="Job ID")
    tailored_resume_id: Optional[str] = Field(None, description="Tailored resume ID")
    status: ApplicationStatus = Field(..., description="Application status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    linkedin_application_id: Optional[str] = Field(None, description="LinkedIn application ID")
    submitted_at: Optional[datetime] = Field(None, description="When application was submitted")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class ApplicationListResponse(BaseModel):
    """Schema for list of applications."""
    applications: list[ApplicationResponse]
    total: int = Field(..., description="Total number of applications")


class ApplicationStatusUpdate(BaseModel):
    """Schema for updating application status."""
    status: ApplicationStatus = Field(..., description="New status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    linkedin_application_id: Optional[str] = Field(None, description="LinkedIn application ID if successful")
