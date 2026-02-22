"""
Resume Tailor Service for generating tailored resumes and cover letters.

This service orchestrates:
1. Reading resume content from file
2. Fetching job description from database
3. Generating input hash for caching
4. Calling LLM service (with mandatory caching)
5. Storing results in database
6. Logging usage metrics
"""

import logging
from decimal import Decimal
from typing import Optional

import aiofiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.job import Job
from app.models.resume import Resume
from app.models.tailored_resume import TailoredResume
from app.models.llm_usage_log import LLMUsageLog
from app.services.llm_service import LLMService, LLMServiceError

logger = logging.getLogger(__name__)


class ResumeTailorServiceError(Exception):
    """Base exception for resume tailor service errors."""
    pass


class ResumeTailorService:
    """
    Service for tailoring resumes to specific job postings.

    Uses LLMService with mandatory caching per AGENTS.md rules.
    """

    # System prompt for resume tailoring
    SYSTEM_PROMPT = """You are an expert resume writer and career coach. Your task is to tailor a resume to match a specific job posting while maintaining truthfulness.

Guidelines:
1. Highlight relevant skills and experiences that match the job requirements
2. Use keywords from the job description naturally
3. Maintain all factual information - never invent or exaggerate
4. Keep the same structure but reorganize for relevance
5. Adjust the professional summary to align with the role
6. Quantify achievements where possible

You must respond in the following JSON format:
{
    "tailored_resume": "The full tailored resume text",
    "cover_letter": "A brief cover letter tailored to this position"
}

Both fields are required. The cover letter should be professional and concise (3-4 paragraphs)."""

    def __init__(self, db: AsyncSession, llm_service: LLMService):
        self.db = db
        self.llm_service = llm_service

    async def _read_resume_content(self, resume: Resume) -> str:
        """Read resume file content from disk."""
        try:
            async with aiofiles.open(resume.file_path, "r") as f:
                # For PDF files, we'd need pdf parsing
                # For now, assume text-based files
                content = await f.read()
                return content
        except Exception as e:
            logger.error(
                "resume_read_error",
                extra={
                    "action": "read_resume_file",
                    "resume_id": resume.id,
                    "error": str(e),
                    "status": "failed"
                }
            )
            raise ResumeTailorServiceError(f"Failed to read resume file: {str(e)}") from e

    async def _get_resume_text(self, resume: Resume) -> str:
        """
        Extract text content from resume.

        For PDF files, this would need proper PDF parsing.
        For now, we'll read text files directly.
        """
        file_ext = resume.file_path.lower().split(".")[-1]

        if file_ext in ["txt", "md"]:
            return await self._read_resume_content(resume)
        elif file_ext == "pdf":
            # TODO: Implement PDF text extraction
            # For now, raise an error
            raise ResumeTailorServiceError(
                "PDF text extraction not yet implemented. "
                "Please upload a text-based resume."
            )
        elif file_ext in ["doc", "docx"]:
            # TODO: Implement DOCX text extraction
            raise ResumeTailorServiceError(
                "DOCX text extraction not yet implemented. "
                "Please upload a text-based resume."
            )
        else:
            # Try to read as text
            return await self._read_resume_content(resume)

    def _build_user_prompt(self, resume_text: str, job: Job) -> str:
        """Build the user prompt for LLM."""
        job_info = f"""
Job Title: {job.title}
Company: {job.company or 'Not specified'}
Location: {job.location or 'Not specified'}

Job Description:
{job.description or 'No description available'}
"""
        return f"""Here is my current resume:

---
{resume_text}
---

Here is the job posting I'm applying for:

---
{job_info}
---

Please tailor my resume for this position and write a cover letter. Remember to respond in JSON format with "tailored_resume" and "cover_letter" fields."""

    async def get_existing_tailored_resume(
        self,
        user_id: str,
        job_id: str
    ) -> Optional[TailoredResume]:
        """Check if a tailored resume already exists for this user/job combination."""
        result = await self.db.execute(
            select(TailoredResume)
            .where(TailoredResume.user_id == user_id)
            .where(TailoredResume.job_id == job_id)
        )
        return result.scalars().first()

    async def tailor_resume(
        self,
        user_id: str,
        resume_id: str,
        job_id: str
    ) -> tuple[TailoredResume, dict]:
        """
        Tailor a resume for a specific job.

        MANDATORY FLOW (per AGENTS.md):
        1. Generate deterministic hash: hash(resume + job_description)
        2. Check Redis cache
        3. If cached → return cached result
        4. If not cached:
           - Call LLM
           - Log prompt tokens
           - Log completion tokens
           - Log estimated cost
           - Store result in Redis
           - Update per-user cost tracking

        Returns:
            tuple: (TailoredResume instance, usage dict)
        """
        # Step 1: Fetch resume from database
        resume_result = await self.db.execute(
            select(Resume).where(Resume.id == resume_id)
        )
        resume = resume_result.scalars().first()

        if not resume:
            raise ResumeTailorServiceError(f"Resume not found: {resume_id}")

        if resume.user_id != user_id:
            raise ResumeTailorServiceError("Access denied: Resume belongs to another user")

        # Step 2: Fetch job from database
        job_result = await self.db.execute(
            select(Job).where(Job.id == job_id)
        )
        job = job_result.scalars().first()

        if not job:
            raise ResumeTailorServiceError(f"Job not found: {job_id}")

        if job.user_id != user_id:
            raise ResumeTailorServiceError("Access denied: Job belongs to another user")

        # Step 3: Check for existing tailored resume
        existing = await self.get_existing_tailored_resume(user_id, job_id)
        if existing:
            logger.info(
                "existing_tailored_resume",
                extra={
                    "action": "tailor_resume",
                    "user_id": user_id,
                    "job_id": job_id,
                    "resume_id": resume_id,
                    "status": "existing"
                }
            )
            # Return existing with cached usage info
            return existing, {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "estimated_cost": Decimal("0"),
                "cached": True
            }

        # Step 4: Get resume text
        resume_text = await self._get_resume_text(resume)

        # Step 5: Get job description
        job_description = job.description or ""

        # Step 6: Generate input hash (MANDATORY per AGENTS.md)
        input_hash = LLMService.generate_input_hash(resume_text, job_description)

        # Step 7: Build prompts
        user_prompt = self._build_user_prompt(resume_text, job)

        # Step 8: Call LLM service (with mandatory caching)
        llm_result = await self.llm_service.call_openai(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            user_id=user_id,
            operation="tailor_resume",
            input_hash=input_hash
        )

        # Step 9: Parse LLM response
        try:
            import json
            # Try to extract JSON from the response
            content = llm_result["content"]
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            parsed = json.loads(content.strip())
            tailored_resume_text = parsed["tailored_resume"]
            cover_letter = parsed.get("cover_letter", "")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(
                "llm_response_parse_error",
                extra={
                    "action": "parse_llm_response",
                    "user_id": user_id,
                    "error": str(e),
                    "status": "failed"
                }
            )
            # Fallback: use the entire content as the resume
            tailored_resume_text = llm_result["content"]
            cover_letter = ""

        # Step 10: Create TailoredResume record
        tailored = TailoredResume(
            user_id=user_id,
            job_id=job_id,
            original_resume_id=resume_id,
            tailored_resume_text=tailored_resume_text,
            cover_letter=cover_letter,
            input_hash=input_hash
        )
        self.db.add(tailored)

        # Step 11: Create LLMUsageLog record
        usage_log = LLMUsageLog(
            user_id=user_id,
            prompt_tokens=llm_result["prompt_tokens"],
            completion_tokens=llm_result["completion_tokens"],
            estimated_cost=Decimal(llm_result["estimated_cost"]),
            model=llm_result["model"],
            operation="tailor_resume"
        )
        self.db.add(usage_log)

        await self.db.commit()
        await self.db.refresh(tailored)

        logger.info(
            "tailored_resume_created",
            extra={
                "action": "tailor_resume",
                "user_id": user_id,
                "job_id": job_id,
                "resume_id": resume_id,
                "tailored_id": tailored.id,
                "cached": llm_result["cached"],
                "status": "success"
            }
        )

        return tailored, {
            "prompt_tokens": llm_result["prompt_tokens"],
            "completion_tokens": llm_result["completion_tokens"],
            "estimated_cost": Decimal(llm_result["estimated_cost"]),
            "cached": llm_result["cached"]
        }

    async def get_tailored_resume(
        self,
        user_id: str,
        job_id: str
    ) -> Optional[TailoredResume]:
        """Get existing tailored resume for a job."""
        return await self.get_existing_tailored_resume(user_id, job_id)