"""
LLM Service for OpenAI integration with Redis caching.

MANDATORY CACHING RULE (AGENTS.md):
Before ANY LLM call:
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
"""

import hashlib
import json
import logging
from decimal import Decimal
from typing import Optional, Any

import redis.asyncio as redis
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Base exception for LLM service errors."""
    pass


class LLMService:
    """
    Service for LLM operations with mandatory caching.

    Redis key format: li_autopilot:{service}:{entity}:{identifier}
    - LLM cache: li_autopilot:llm:tailor:{input_hash}
    - User cost tracking: li_autopilot:llm:user_cost:{user_id}
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    @staticmethod
    def generate_input_hash(resume_text: str, job_description: str) -> str:
        """
        Generate deterministic hash from resume and job description.

        Uses SHA-256 for consistent hashing.
        """
        combined = f"{resume_text}|{job_description}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def _get_cache_key(self, input_hash: str) -> str:
        """Get Redis cache key for LLM result."""
        return f"li_autopilot:llm:tailor:{input_hash}"

    def _get_user_cost_key(self, user_id: str) -> str:
        """Get Redis key for user cost tracking."""
        return f"li_autopilot:llm:user_cost:{user_id}"

    async def get_cached_result(self, input_hash: str) -> Optional[dict]:
        """
        Check Redis cache for existing LLM result.

        Returns cached result or None if not found.
        """
        cache_key = self._get_cache_key(input_hash)
        cached = await self.redis.get(cache_key)

        if cached:
            logger.info(
                "llm_cache_hit",
                extra={
                    "action": "llm_cache_hit",
                    "input_hash": input_hash,
                    "status": "success"
                }
            )
            return json.loads(cached)

        logger.info(
            "llm_cache_miss",
            extra={
                "action": "llm_cache_miss",
                "input_hash": input_hash,
                "status": "success"
            }
        )
        return None

    async def cache_result(self, input_hash: str, result: dict) -> None:
        """Store LLM result in Redis cache with TTL."""
        cache_key = self._get_cache_key(input_hash)
        await self.redis.setex(
            cache_key,
            settings.llm_cache_ttl,
            json.dumps(result)
        )

        logger.info(
            "llm_result_cached",
            extra={
                "action": "llm_result_cached",
                "input_hash": input_hash,
                "ttl_seconds": settings.llm_cache_ttl,
                "status": "success"
            }
        )

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> Decimal:
        """Calculate estimated cost based on token usage."""
        prompt_cost = Decimal(str(prompt_tokens)) / 1000 * Decimal(str(settings.llm_prompt_cost_per_1k))
        completion_cost = Decimal(str(completion_tokens)) / 1000 * Decimal(str(settings.llm_completion_cost_per_1k))
        return prompt_cost + completion_cost

    async def update_user_cost(
        self,
        user_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: Decimal,
        operation: str
    ) -> None:
        """
        Update cumulative cost tracking for user in Redis.

        Stores:
        - total_prompt_tokens
        - total_completion_tokens
        - total_cost
        - operation_counts
        """
        cost_key = self._get_user_cost_key(user_id)

        # Get current values
        current = await self.redis.get(cost_key)
        if current:
            data = json.loads(current)
        else:
            data = {
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_cost": "0.000000",
                "operation_counts": {}
            }

        # Update values
        data["total_prompt_tokens"] += prompt_tokens
        data["total_completion_tokens"] += completion_tokens
        data["total_cost"] = str(Decimal(data["total_cost"]) + cost)

        if operation not in data["operation_counts"]:
            data["operation_counts"][operation] = 0
        data["operation_counts"][operation] += 1

        # Store updated values (no expiry - persistent tracking)
        await self.redis.set(cost_key, json.dumps(data))

        logger.info(
            "user_cost_updated",
            extra={
                "action": "user_cost_updated",
                "user_id": user_id,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "estimated_cost": str(cost),
                "operation": operation,
                "status": "success"
            }
        )

    async def get_user_cost_summary(self, user_id: str) -> dict:
        """Get cumulative cost summary for a user."""
        cost_key = self._get_user_cost_key(user_id)
        current = await self.redis.get(cost_key)

        if current:
            data = json.loads(current)
            data["user_id"] = user_id
            return data

        return {
            "user_id": user_id,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost": "0.000000",
            "operation_counts": {}
        }

    async def call_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        user_id: str,
        operation: str,
        input_hash: str
    ) -> dict:
        """
        Call OpenAI API with mandatory caching.

        MANDATORY FLOW:
        1. Check cache first
        2. If cached, return cached result
        3. If not cached, call LLM
        4. Log tokens and cost
        5. Cache result
        6. Update user cost tracking

        Returns dict with:
        - content: The LLM response
        - prompt_tokens: int
        - completion_tokens: int
        - estimated_cost: Decimal
        - cached: bool
        """
        # Step 1: Check cache (MANDATORY)
        cached_result = await self.get_cached_result(input_hash)
        if cached_result:
            cached_result["cached"] = True
            return cached_result

        # Step 2: Validate API key
        if not self.client:
            raise LLMServiceError("OpenAI API key not configured")

        # Step 3: Call LLM
        try:
            response = await self.client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature
            )
        except Exception as e:
            logger.error(
                "llm_api_error",
                extra={
                    "action": "llm_api_call",
                    "user_id": user_id,
                    "operation": operation,
                    "error": str(e),
                    "status": "failed"
                }
            )
            raise LLMServiceError(f"OpenAI API error: {str(e)}") from e

        # Step 4: Extract response data
        content = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        estimated_cost = self.calculate_cost(prompt_tokens, completion_tokens)

        # Step 5: Log token usage (MANDATORY)
        logger.info(
            "llm_tokens_logged",
            extra={
                "action": "llm_tokens_logged",
                "user_id": user_id,
                "operation": operation,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "estimated_cost": str(estimated_cost),
                "model": settings.llm_model,
                "status": "success"
            }
        )

        # Build result
        result = {
            "content": content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost": str(estimated_cost),
            "model": settings.llm_model,
            "cached": False
        }

        # Step 6: Cache result (MANDATORY)
        await self.cache_result(input_hash, result)

        # Step 7: Update user cost tracking (MANDATORY)
        await self.update_user_cost(
            user_id=user_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=estimated_cost,
            operation=operation
        )

        return result


# Dependency injection
async def get_llm_service() -> LLMService:
    """Get LLM service instance with Redis connection."""
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return LLMService(redis_client)