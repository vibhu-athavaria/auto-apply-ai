import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logger import get_logger

logger = get_logger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip logging for health check
        if request.url.path == "/health/":
            return await call_next(request)

        start_time = time.time()

        # Extract user_id from request state if available
        user_id = getattr(request.state, "user_id", None)

        # Log request
        logger.info(
            "request_started",
            service="api",
            user_id=user_id,
            action=f"{request.method} {request.url.path}",
            status="started"
        )

        response: Response = await call_next(request)

        process_time = time.time() - start_time

        # Log response
        logger.info(
            "request_completed",
            service="api",
            user_id=user_id,
            action=f"{request.method} {request.url.path}",
            status="completed",
            status_code=response.status_code,
            process_time_ms=round(process_time * 1000, 2)
        )

        return response