"""Job Matcher Service - Calculates match score between resume and job.

This service implements a cost-effective keyword-based matching algorithm
to calculate how well a user's resume matches job requirements.

The algorithm extracts keywords from both resume and job description,
then calculates a weighted score based on:
- Skills match (50%)
- Experience level match (30%)
- Job title/role match (20%)

Results are cached in Redis per AGENTS.md rules.
"""
import hashlib
import re
from typing import Optional, List, Set, Dict, Any, Tuple
from datetime import datetime

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.job import Job
from app.models.resume import Resume
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Common tech skills and keywords for matching
TECH_SKILLS = {
    # Programming Languages
    'python', 'javascript', 'typescript', 'java', 'c++', 'c#', 'go', 'rust', 'ruby', 'php',
    'swift', 'kotlin', 'scala', 'r', 'matlab', 'perl', 'shell', 'bash', 'powershell',
    # Web Technologies
    'html', 'css', 'react', 'vue', 'angular', 'svelte', 'nextjs', 'nuxt', 'nodejs',
    'express', 'django', 'flask', 'fastapi', 'spring', 'laravel', 'rails', 'aspnet',
    # Databases
    'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'dynamodb',
    'cassandra', 'neo4j', 'sqlite', 'oracle', 'mssql', 'firebase', 'supabase',
    # Cloud & DevOps
    'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'ansible', 'jenkins',
    'github actions', 'gitlab ci', 'circleci', 'travis', 'prometheus', 'grafana',
    'nginx', 'apache', 'lambda', 'ec2', 's3', 'cloudfront', 'route53', 'vpc',
    # Data & AI
    'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'scikit-learn',
    'pandas', 'numpy', 'spark', 'hadoop', 'kafka', 'airflow', 'dbt', 'tableau',
    'powerbi', 'looker', 'data engineering', 'data science', 'nlp', 'computer vision',
    # Mobile
    'ios', 'android', 'react native', 'flutter', 'xamarin', 'cordova', 'ionic',
    # Other
    'git', 'github', 'gitlab', 'bitbucket', 'jira', 'confluence', 'slack', 'notion',
    'agile', 'scrum', 'kanban', 'tdd', 'ci/cd', 'microservices', 'rest api', 'graphql',
    'websocket', 'oauth', 'jwt', 'sso', 'ldap', 'oauth2',
    # Soft Skills (weighted lower)
    'leadership', 'communication', 'teamwork', 'problem solving', 'analytical',
    'project management', 'stakeholder management', 'mentoring',
}

EXPERIENCE_KEYWORDS = [
    r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',
    r'(\d+)\+?\s*yrs?\s*(?:of\s*)?exp',
    r'minimum\s*(?:of\s*)?(\d+)\s*years?',
    r'at\s*least\s*(\d+)\s*years?',
]

SENIORITY_LEVELS = {
    'entry': ['entry level', 'junior', 'associate', '0-2 years', '0-1 years', 'fresh graduate', 'new grad'],
    'mid': ['mid level', 'intermediate', '2-5 years', '3-5 years', '2+ years', '3+ years'],
    'senior': ['senior', 'sr.', 'lead', '5+ years', '7+ years', 'staff', 'principal'],
    'executive': ['director', 'vp', 'head of', 'chief', 'cto', 'ceo', 'vp of'],
}


class JobMatcherService:
    """Service for calculating job-resume match scores."""

    CACHE_PREFIX = "li_autopilot:api:job_match"
    CACHE_TTL = 86400  # 24 hours

    def __init__(self, db: AsyncSession, redis_client: Optional[redis.Redis] = None):
        """Initialize service.

        Args:
            db: Database session
            redis_client: Optional Redis client for caching
        """
        self.db = db
        self.redis = redis_client

    def _generate_cache_key(self, user_id: str, job_id: str, resume_id: str) -> str:
        """Generate deterministic cache key for match score."""
        content = f"{user_id}:{job_id}:{resume_id}"
        hash_value = hashlib.md5(content.encode()).hexdigest()[:16]
        return f"{self.CACHE_PREFIX}:{hash_value}"

    async def _get_cached_score(
        self,
        user_id: str,
        job_id: str,
        resume_id: str
    ) -> Optional[int]:
        """Get cached match score from Redis.

        Args:
            user_id: User ID
            job_id: Job ID
            resume_id: Resume ID

        Returns:
            Cached score or None if not found
        """
        if not self.redis:
            return None

        try:
            cache_key = self._generate_cache_key(user_id, job_id, resume_id)
            cached = await self.redis.get(cache_key)
            if cached:
                logger.info(
                    "Match score cache hit",
                    extra={
                        "user_id": user_id,
                        "job_id": job_id,
                        "action": "match_score_cache_hit"
                    }
                )
                return int(cached)
        except Exception as e:
            logger.error(
                f"Redis cache error: {e}",
                extra={
                    "user_id": user_id,
                    "job_id": job_id,
                    "action": "match_score_cache_error"
                }
            )
        return None

    async def _cache_score(
        self,
        user_id: str,
        job_id: str,
        resume_id: str,
        score: int
    ) -> None:
        """Cache match score in Redis.

        Args:
            user_id: User ID
            job_id: Job ID
            resume_id: Resume ID
            score: Match score to cache
        """
        if not self.redis:
            return

        try:
            cache_key = self._generate_cache_key(user_id, job_id, resume_id)
            await self.redis.setex(cache_key, self.CACHE_TTL, str(score))
            logger.info(
                "Match score cached",
                extra={
                    "user_id": user_id,
                    "job_id": job_id,
                    "score": score,
                    "action": "match_score_cached"
                }
            )
        except Exception as e:
            logger.error(
                f"Failed to cache match score: {e}",
                extra={
                    "user_id": user_id,
                    "job_id": job_id,
                    "action": "match_score_cache_error"
                }
            )

    def _extract_skills(self, text: str) -> Set[str]:
        """Extract tech skills from text.

        Args:
            text: Text to extract skills from

        Returns:
            Set of found skills
        """
        text_lower = text.lower()
        found_skills = set()

        for skill in TECH_SKILLS:
            # Use word boundaries for matching
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                found_skills.add(skill)

        return found_skills

    def _extract_experience_years(self, text: str) -> Optional[int]:
        """Extract required years of experience from text.

        Args:
            text: Job description text

        Returns:
            Minimum years required or None
        """
        text_lower = text.lower()
        years_found = []

        for pattern in EXPERIENCE_KEYWORDS:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                try:
                    years = int(match)
                    if 0 <= years <= 30:  # Sanity check
                        years_found.append(years)
                except (ValueError, IndexError):
                    continue

        return min(years_found) if years_found else None

    def _detect_seniority(self, text: str) -> Optional[str]:
        """Detect seniority level from text.

        Args:
            text: Job title or description

        Returns:
            Seniority level or None
        """
        text_lower = text.lower()

        for level, keywords in SENIORITY_LEVELS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return level

        return None

    def _calculate_skills_score(
        self,
        job_skills: Set[str],
        resume_skills: Set[str]
    ) -> float:
        """Calculate skills match score.

        Args:
            job_skills: Skills required by job
            resume_skills: Skills in resume

        Returns:
            Score between 0 and 1
        """
        if not job_skills:
            return 0.5  # Neutral if no skills specified

        if not resume_skills:
            return 0.0

        # Calculate overlap
        matching_skills = job_skills & resume_skills
        missing_skills = job_skills - resume_skills

        # Weight: matching skills are positive, missing skills reduce score
        match_ratio = len(matching_skills) / len(job_skills) if job_skills else 0

        # Bonus for having more skills than required
        extra_skills_ratio = len(resume_skills - job_skills) / 20  # Normalize to ~20 skills
        bonus = min(extra_skills_ratio * 0.1, 0.1)  # Max 10% bonus

        score = match_ratio + bonus
        return min(score, 1.0)

    def _calculate_experience_score(
        self,
        job_years: Optional[int],
        resume_years: Optional[int]
    ) -> float:
        """Calculate experience match score.

        Args:
            job_years: Years required by job
            resume_years: Years in resume

        Returns:
            Score between 0 and 1
        """
        # If job doesn't specify, give neutral score
        if job_years is None:
            return 0.7

        # If resume doesn't specify, assume some experience
        if resume_years is None:
            resume_years = 3  # Assume mid-level

        if resume_years >= job_years:
            # Meets or exceeds requirement
            excess = resume_years - job_years
            bonus = min(excess * 0.05, 0.2)  # Max 20% bonus
            return 0.8 + bonus

        # Below requirement
        deficit = job_years - resume_years
        penalty = deficit * 0.15
        return max(0.3, 1.0 - penalty)

    def _calculate_title_score(
        self,
        job_title: str,
        resume_text: str
    ) -> float:
        """Calculate job title/role match score.

        Args:
            job_title: Job title
            resume_text: Resume text

        Returns:
            Score between 0 and 1
        """
        job_title_lower = job_title.lower()
        resume_lower = resume_text.lower()

        # Extract key terms from job title
        title_terms = set(job_title_lower.split())
        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'in', 'at', 'to', 'for', 'of', 'with'}
        title_terms = title_terms - stop_words

        if not title_terms:
            return 0.5

        # Count how many title terms appear in resume
        matches = sum(1 for term in title_terms if term in resume_lower)
        match_ratio = matches / len(title_terms)

        # Seniority match bonus
        job_seniority = self._detect_seniority(job_title)
        resume_seniority = self._detect_seniority(resume_text)

        if job_seniority and resume_seniority:
            seniority_match = job_seniority == resume_seniority
            if seniority_match:
                return min(match_ratio + 0.15, 1.0)

        return match_ratio

    def calculate_match_score(
        self,
        job_description: str,
        job_title: str,
        resume_text: str
    ) -> int:
        """Calculate overall match score.

        Algorithm:
        - Skills match: 50% weight
        - Experience match: 30% weight
        - Title/role match: 20% weight

        Args:
            job_description: Full job description
            job_title: Job title
            resume_text: Full resume text

        Returns:
            Match score 0-100
        """
        # Extract components
        job_skills = self._extract_skills(job_description + " " + job_title)
        resume_skills = self._extract_skills(resume_text)

        job_years = self._extract_experience_years(job_description)
        resume_years = self._extract_experience_years(resume_text)

        # Calculate component scores
        skills_score = self._calculate_skills_score(job_skills, resume_skills)
        exp_score = self._calculate_experience_score(job_years, resume_years)
        title_score = self._calculate_title_score(job_title, resume_text)

        # Weighted total
        total_score = (
            skills_score * 0.50 +
            exp_score * 0.30 +
            title_score * 0.20
        )

        # Convert to 0-100 integer
        final_score = int(total_score * 100)

        logger.info(
            f"Match score calculated: {final_score}",
            extra={
                "action": "match_score_calculated",
                "skills_score": skills_score,
                "exp_score": exp_score,
                "title_score": title_score,
                "final_score": final_score,
                "job_skills_count": len(job_skills),
                "resume_skills_count": len(resume_skills)
            }
        )

        return final_score

    async def get_match_score(
        self,
        user_id: str,
        job_id: str,
        resume_id: Optional[str] = None
    ) -> Optional[int]:
        """Get match score for a job against user's resume.

        Checks cache first, then calculates if needed.

        Args:
            user_id: User ID
            job_id: Job ID
            resume_id: Optional specific resume ID to use

        Returns:
            Match score (0-100) or None if calculation not possible
        """
        # Get user's default resume if not specified
        if not resume_id:
            resume_result = await self.db.execute(
                select(Resume).where(Resume.user_id == user_id).order_by(Resume.uploaded_at.desc())
            )
            resume = resume_result.scalars().first()
            if not resume:
                logger.warning(
                    "No resume found for match calculation",
                    extra={"user_id": user_id, "action": "match_score_no_resume"}
                )
                return None
            resume_id = resume.id

        # Check cache first
        cached_score = await self._get_cached_score(user_id, job_id, resume_id)
        if cached_score is not None:
            return cached_score

        # Get job details
        job_result = await self.db.execute(
            select(Job).where(Job.id == job_id).where(Job.user_id == user_id)
        )
        job = job_result.scalars().first()
        if not job:
            logger.error(
                f"Job not found: {job_id}",
                extra={"user_id": user_id, "action": "match_score_job_not_found"}
            )
            raise ValueError(f"Job not found: {job_id}")

        # Get resume
        resume_result = await self.db.execute(
            select(Resume).where(Resume.id == resume_id).where(Resume.user_id == user_id)
        )
        resume = resume_result.scalars().first()
        if not resume:
            logger.error(
                f"Resume not found: {resume_id}",
                extra={"user_id": user_id, "action": "match_score_resume_not_found"}
            )
            raise ValueError(f"Resume not found: {resume_id}")

        # Read resume content
        try:
            with open(resume.file_path, 'r', encoding='utf-8') as f:
                resume_text = f.read()
        except Exception as e:
            logger.error(
                f"Failed to read resume: {e}",
                extra={
                    "user_id": user_id,
                    "resume_id": resume_id,
                    "action": "match_score_read_error"
                }
            )
            return None

        # Calculate score
        job_description = job.description or job.title
        score = self.calculate_match_score(
            job_description=job_description,
            job_title=job.title,
            resume_text=resume_text
        )

        # Cache result
        await self._cache_score(user_id, job_id, resume_id, score)

        # Update job with match score
        job.match_score = score
        await self.db.commit()

        return score

    async def calculate_scores_for_jobs(
        self,
        user_id: str,
        job_ids: List[str],
        resume_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Calculate match scores for multiple jobs.

        Args:
            user_id: User ID
            job_ids: List of job IDs
            resume_id: Optional specific resume ID

        Returns:
            Dictionary mapping job_id to score
        """
        scores = {}
        for job_id in job_ids:
            try:
                score = await self.get_match_score(user_id, job_id, resume_id)
                if score is not None:
                    scores[job_id] = score
            except Exception as e:
                logger.error(
                    f"Failed to calculate score for job {job_id}: {e}",
                    extra={
                        "user_id": user_id,
                        "job_id": job_id,
                        "action": "match_score_calculation_error"
                    }
                )
                continue
        return scores
