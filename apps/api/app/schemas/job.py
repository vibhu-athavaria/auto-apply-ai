from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class JobBase(BaseModel):
    """Base schema for Job."""
    linkedin_job_id: str = Field(..., max_length=100, description="LinkedIn's unique job ID")
    title: str = Field(..., max_length=500, description="Job title")
    company: Optional[str] = Field(None, max_length=255, description="Company name")
    location: Optional[str] = Field(None, max_length=255, description="Job location")
    job_url: str = Field(..., description="Full URL to LinkedIn job posting")
    easy_apply: bool = Field(default=False, description="Whether job supports Easy Apply")
    description: Optional[str] = Field(None, description="Full job description")


class JobCreate(JobBase):
    """Schema for creating a new Job."""
    search_profile_id: str = Field(..., description="ID of the search profile")
    user_id: str = Field(..., description="ID of the user")


class JobResponse(JobBase):
    """Schema for Job response."""
    id: str = Field(..., description="Job ID")
    search_profile_id: str = Field(..., description="ID of the search profile")
    user_id: str = Field(..., description="ID of the user")
    status: str = Field(default="discovered", description="Job status")
    discovered_at: datetime = Field(..., description="When job was discovered")
    updated_at: datetime = Field(..., description="Last update time")

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """Schema for list of jobs."""
    jobs: List[JobResponse]
    total: int
    limit: int
    offset: int


class JobSearchRequest(BaseModel):
    """Schema for job search request."""
    search_profile_id: str = Field(..., description="ID of the search profile to search for")


class JobSearchStatusResponse(BaseModel):
    """Schema for job search status response."""
    task_id: str = Field(..., description="Task ID for tracking")
    status: str = Field(..., description="Task status: queued, running, completed, failed")
    message: Optional[str] = Field(None, description="Status message")
    jobs_found: Optional[int] = Field(None, description="Number of jobs found")
    created_at: Optional[datetime] = Field(None, description="Task creation time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")
