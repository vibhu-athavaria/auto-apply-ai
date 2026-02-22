"""
Tailor Router - API endpoints for resume tailoring.

Endpoints:
- POST /jobs/{id}/tailor - Generate tailored resume and cover letter
- GET /jobs/{id}/tailored - Get tailored resume for a job
- GET /users/me/costs - Get user's LLM cost summary
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.tailor import (
    TailorRequest,
    TailorResponse,
    TailoredResumeResponse,
    LLMUsageResponse,
    UserCostSummary
)
from app.services.llm_service import LLMService, get_llm_service
from app.services.resume_tailor_service import ResumeTailorService, ResumeTailorServiceError
from app.utils.security import get_current_user

router = APIRouter()


@router.post("/{job_id}/tailor", response_model=TailorResponse)
async def tailor_resume_for_job(
    job_id: str,
    request: TailorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service)
):
    """
    Generate a tailored resume and cover letter for a specific job.

    This endpoint:
    1. Validates the resume and job belong to the user
    2. Generates a deterministic hash for caching
    3. Checks Redis cache before calling LLM (MANDATORY)
    4. Returns tailored resume with usage metrics

    The LLM call is cached per AGENTS.md rules:
    - Same resume + job description = same result (from cache)
    - Caching saves tokens and costs
    """
    try:
        tailor_service = ResumeTailorService(db, llm_service)
        tailored, usage = await tailor_service.tailor_resume(
            user_id=current_user.id,
            resume_id=request.resume_id,
            job_id=job_id
        )

        return TailorResponse(
            tailored_resume=TailoredResumeResponse.model_validate(tailored),
            usage=LLMUsageResponse(
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                estimated_cost=usage["estimated_cost"],
                cached=usage["cached"]
            )
        )
    except ResumeTailorServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}/tailored", response_model=TailoredResumeResponse)
async def get_tailored_resume(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service)
):
    """
    Get the tailored resume for a specific job.

    Returns the existing tailored resume if one exists.
    Returns 404 if no tailored resume exists for this job.
    """
    tailor_service = ResumeTailorService(db, llm_service)
    tailored = await tailor_service.get_tailored_resume(
        user_id=current_user.id,
        job_id=job_id
    )

    if not tailored:
        raise HTTPException(
            status_code=404,
            detail="No tailored resume found for this job. Use POST /jobs/{id}/tailor to create one."
        )

    return TailoredResumeResponse.model_validate(tailored)


@router.get("/users/me/costs", response_model=UserCostSummary)
async def get_user_costs(
    current_user: User = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service)
):
    """
    Get the current user's cumulative LLM cost summary.

    Returns:
    - Total prompt tokens used
    - Total completion tokens used
    - Total estimated cost in USD
    - Operation counts by type
    """
    summary = await llm_service.get_user_cost_summary(current_user.id)
    return UserCostSummary(**summary)