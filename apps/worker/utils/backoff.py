"""Exponential backoff utility for retry logic.

This module provides retry functionality with exponential backoff for
handling transient failures in external systems (LinkedIn, LLM APIs).
"""
import asyncio
from functools import wraps
from typing import Callable, TypeVar, ParamSpec, Type, Tuple

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class MaxRetriesExceededError(Exception):
    """Raised when max retries are exceeded."""
    pass


async def with_backoff(
    func: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs
) -> T:
    """Execute function with exponential backoff on failure.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result of func if successful

    Raises:
        MaxRetriesExceededError: If all retries fail
        Exception: The last exception if all retries fail
    """
    max_retries = settings.max_retries
    base_delay = settings.base_backoff_delay

    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"Retry attempt {attempt + 1}/{max_retries} after {delay}s",
                    extra={
                        "action": "retry_with_backoff",
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "delay": delay,
                        "error": str(e),
                        "status": "retrying"
                    }
                )
                await asyncio.sleep(delay)

    logger.error(
        f"Max retries ({max_retries}) exceeded",
        extra={
            "action": "retry_with_backoff",
            "max_retries": max_retries,
            "error": str(last_exception),
            "status": "failed"
        }
    )
    raise MaxRetriesExceededError(
        f"Max retries ({max_retries}) exceeded. Last error: {last_exception}"
    ) from last_exception


def retry_with_backoff(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    max_retries: int = None,
    base_delay: float = None
) -> Callable:
    """Decorator for retrying async functions with exponential backoff.

    Args:
        exceptions: Tuple of exception types to catch
        max_retries: Maximum number of retries (default from settings)
        base_delay: Base delay in seconds (default from settings)

    Returns:
        Decorated function
    """
    max_retries = max_retries or settings.max_retries
    base_delay = base_delay or settings.base_backoff_delay

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"Retry attempt {attempt + 1}/{max_retries} for {func.__name__}",
                            extra={
                                "action": "retry_with_backoff",
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "delay": delay,
                                "error": str(e),
                                "status": "retrying"
                            }
                        )
                        await asyncio.sleep(delay)

            logger.error(
                f"Max retries ({max_retries}) exceeded for {func.__name__}",
                extra={
                    "action": "retry_with_backoff",
                    "function": func.__name__,
                    "max_retries": max_retries,
                    "error": str(last_exception),
                    "status": "failed"
                }
            )
            raise MaxRetriesExceededError(
                f"Max retries ({max_retries}) exceeded for {func.__name__}. "
                f"Last error: {last_exception}"
            ) from last_exception

        return wrapper

    return decorator
