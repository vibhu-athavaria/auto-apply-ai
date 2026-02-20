from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class JobSearchProfileBase(BaseModel):
    keywords: str
    location: str
    remote_preference: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None

class JobSearchProfileCreate(JobSearchProfileBase):
    pass

class JobSearchProfileUpdate(BaseModel):
    keywords: Optional[str] = None
    location: Optional[str] = None
    remote_preference: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None

class JobSearchProfile(JobSearchProfileBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)