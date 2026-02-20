"""Randomized delay utilities for human-like behavior.

This module provides randomized delays to mimic human behavior and avoid
detection during browser automation.
"""
import random
import asyncio

from config import settings


async def human_delay(
    min_seconds: float = None,
    max_seconds: float = None
) -> None:
    """Randomized delay between actions.

    Args:
        min_seconds: Minimum delay (default from settings)
        max_seconds: Maximum delay (default from settings)
    """
    min_seconds = min_seconds or settings.min_action_delay
    max_seconds = max_seconds or settings.max_action_delay
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def page_scroll_delay() -> None:
    """Delay after scrolling, mimics reading."""
    await human_delay(0.5, 2.0)


async def navigation_delay() -> None:
    """Delay after page navigation."""
    min_delay = settings.min_navigation_delay
    max_delay = settings.max_navigation_delay
    await human_delay(min_delay, max_delay)


async def search_delay() -> None:
    """Delay between search operations."""
    min_delay = settings.min_search_delay
    max_delay = settings.max_search_delay
    await human_delay(min_delay, max_delay)


async def action_delay() -> None:
    """Delay for general actions like clicking."""
    await human_delay()


async def typing_delay() -> None:
    """Delay between keystrokes to mimic human typing."""
    delay = random.uniform(0.05, 0.15)
    await asyncio.sleep(delay)


async def random_pause() -> None:
    """Random pause to simulate thinking/reading."""
    delay = random.uniform(1.0, 4.0)
    await asyncio.sleep(delay)
