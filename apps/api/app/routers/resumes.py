from typing import List
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.resume import Resume
from app.services.resume_service import ResumeService
from app.utils.security import get_current_user

router = APIRouter()

@router.post("/upload", response_model=Resume)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    resume = await ResumeService.create_resume(db, current_user, file)
    return resume

@router.get("/", response_model=List[Resume])
async def get_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    resumes = await ResumeService.get_user_resumes(db, current_user.id)
    return resumes