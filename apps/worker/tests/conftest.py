"""Pytest configuration and fixtures for worker tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.rpush = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_playwright_page():
    """Create a mock Playwright page."""
    page = AsyncMock()
    page.url = "https://www.linkedin.com/jobs/"
    page.goto = AsyncMock(return_value=None)
    page.wait_for_selector = AsyncMock(return_value=True)
    page.query_selector = AsyncMock(return_value=None)
    page.query_selector_all = AsyncMock(return_value=[])
    page.content = AsyncMock(return_value="<html></html>")
    page.screenshot = AsyncMock(return_value=None)
    page.set_default_timeout = MagicMock(return_value=None)
    return page


@pytest.fixture
def mock_playwright_context():
    """Create a mock Playwright browser context."""
    context = AsyncMock()
    context.new_page = AsyncMock()
    context.add_cookies = AsyncMock(return_value=None)
    context.cookies = AsyncMock(return_value=[])
    context.close = AsyncMock(return_value=None)
    context.storage_state = AsyncMock(return_value={"cookies": [], "origins": []})
    return context


@pytest.fixture
def mock_playwright_browser():
    """Create a mock Playwright browser."""
    browser = AsyncMock()
    browser.new_context = AsyncMock()
    browser.close = AsyncMock(return_value=None)
    return browser


@pytest.fixture
def mock_playwright():
    """Create a mock Playwright instance."""
    pw = AsyncMock()
    pw.chromium.launch = AsyncMock()
    pw.stop = AsyncMock(return_value=None)
    return pw


@pytest.fixture
def sample_browser_state():
    """Sample browser state for testing."""
    return {
        "cookies": [
            {
                "name": "li_at",
                "value": "test_session_cookie",
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True
            }
        ],
        "origins": []
    }
