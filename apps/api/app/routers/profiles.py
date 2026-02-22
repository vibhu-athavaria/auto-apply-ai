from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.models.user import User
from app.models.job_search_profile import JobSearchProfile as JobSearchProfileModel
from app.schemas.job_search_profile import (
    JobSearchProfileCreate,
    JobSearchProfileUpdate,
    JobSearchProfile
)
from app.utils.security import get_current_user

router = APIRouter()

@router.post("/", response_model=JobSearchProfile)
async def create_profile(
    profile: JobSearchProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    db_profile = JobSearchProfileModel(
        user_id=current_user.id,
        **profile.model_dump()
    )
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)
    return db_profile

@router.get("/", response_model=List[JobSearchProfile])
async def get_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(JobSearchProfileModel)
        .where(JobSearchProfileModel.user_id == current_user.id)
        .order_by(JobSearchProfileModel.created_at.desc())
    )
    return result.scalars().all()

@router.put("/{profile_id}", response_model=JobSearchProfile)
async def update_profile(
    profile_id: str,
    profile_update: JobSearchProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(JobSearchProfileModel)
        .where(JobSearchProfileModel.id == profile_id)
        .where(JobSearchProfileModel.user_id == current_user.id)
    )
    db_profile = result.scalars().first()

    if not db_profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = profile_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_profile, key, value)

    await db.commit()
    await db.refresh(db_profile)
    return db_profile