import os
import uuid
from pathlib import Path
import aiofiles
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.resume import Resume
from app.models.user import User

class ResumeService:
    UPLOAD_DIR = Path(__file__).parent.parent / "uploads"

    @staticmethod
    def validate_file(file: UploadFile) -> None:
        # Check file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in settings.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {settings.allowed_extensions}"
            )

        # Check file size (will be checked during read)
        if file.size and file.size > settings.max_upload_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {settings.max_upload_size} bytes"
            )

    @staticmethod
    async def save_file(file: UploadFile, user_id: uuid.UUID) -> tuple[str, int]:
        # Create user-specific directory
        user_dir = ResumeService.UPLOAD_DIR / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1].lower()
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = user_dir / unique_filename

        # Read and save file
        content = await file.read()
        if len(content) > settings.max_upload_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {settings.max_upload_size} bytes"
            )

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        return str(file_path), len(content)

    @staticmethod
    async def create_resume(
        db: AsyncSession,
        user: User,
        file: UploadFile
    ) -> Resume:
        ResumeService.validate_file(file)

        file_path, file_size = await ResumeService.save_file(file, user.id)

        db_resume = Resume(
            user_id=user.id,
            filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            content_type=file.content_type
        )
        db.add(db_resume)
        await db.commit()
        await db.refresh(db_resume)
        return db_resume

    @staticmethod
    async def get_user_resumes(db: AsyncSession, user_id: uuid.UUID) -> list[Resume]:
        result = await db.execute(
            select(Resume).where(Resume.user_id == user_id).order_by(Resume.uploaded_at.desc())
        )
        return result.scalars().all()