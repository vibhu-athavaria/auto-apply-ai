from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Phase 1: Empty stub for cost logging middleware
# Will be implemented in future phases for LLM cost tracking

class CostLoggingMiddleware(BaseHTTPMiddleware):
    """
    Placeholder middleware for cost logging.

    Future implementation will:
    - Track LLM token usage per user
    - Log estimated costs
    - Update per-user cost tracking in Redis
    """

    async def dispatch(self, request: Request, call_next):
        # Pass through without any cost tracking in Phase 1
        response = await call_next(request)
        return response