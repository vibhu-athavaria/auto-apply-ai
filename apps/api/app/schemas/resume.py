from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ResumeBase(BaseModel):
    filename: str
    file_path: str
    file_size: int
    content_type: str
    uploaded_at: datetime

class ResumeCreate(ResumeBase):
    pass

class Resume(ResumeBase):
    id: str
    user_id: str

    model_config = ConfigDict(from_attributes=True)