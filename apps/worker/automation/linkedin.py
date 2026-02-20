"""LinkedIn client using Playwright for browser automation.

This module handles:
- Browser context creation
- Cookie-based authentication
- Page navigation
- Session management

CRITICAL: Never store LinkedIn passwords. Use session cookies only.
"""
import json
from typing import Optional, Dict, Any
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import settings
from utils.logger import get_logger
from utils.delays import navigation_delay, action_delay

logger = get_logger(__name__)

LINKEDIN_BASE_URL = "https://www.linkedin.com"
LINKEDIN_JOBS_URL = f"{LINKEDIN_BASE_URL}/jobs"


class LinkedInClient:
    """Playwright-based LinkedIn client.

    Uses session cookie (li_at) for authentication.
    Never stores or handles LinkedIn passwords.
    """

    def __init__(self, session_cookie: str = None):
        """Initialize LinkedIn client.

        Args:
            session_cookie: LinkedIn li_at session cookie value
        """
        self.session_cookie = session_cookie or settings.linkedin_session_cookie
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self):
        """Start browser and create context."""
        logger.info(
            "Starting LinkedIn client",
            extra={
                "action": "start_client",
                "status": "in_progress"
            }
        )

        self._playwright = await async_playwright().start()

        # Launch browser
        self._browser = await self._playwright.chromium.launch(
            headless=settings.headless_browser
        )

        # Create context with session cookie
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Add session cookie if provided
        if self.session_cookie:
            await self._context.add_cookies([
                {
                    "name": "li_at",
                    "value": self.session_cookie,
                    "domain": ".linkedin.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True
                }
            ])

        # Create page
        self._page = await self._context.new_page()
        self._page.set_default_timeout(settings.browser_timeout)

        logger.info(
            "LinkedIn client started",
            extra={
                "action": "start_client",
                "status": "success"
            }
        )

    async def close(self):
        """Close browser and cleanup."""
        logger.info(
            "Closing LinkedIn client",
            extra={
                "action": "close_client",
                "status": "in_progress"
            }
        )

        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

        logger.info(
            "LinkedIn client closed",
            extra={
                "action": "close_client",
                "status": "success"
            }
        )

    async def navigate_to_jobs(self) -> bool:
        """Navigate to LinkedIn jobs page.

        Returns:
            True if navigation successful, False otherwise
        """
        try:
            logger.info(
                "Navigating to jobs page",
                extra={
                    "action": "navigate_to_jobs",
                    "status": "in_progress"
                }
            )

            await self._page.goto(LINKEDIN_JOBS_URL)
            await navigation_delay()

            # Check if we're logged in
            if await self._is_logged_in():
                logger.info(
                    "Successfully navigated to jobs page",
                    extra={
                        "action": "navigate_to_jobs",
                        "status": "success"
                    }
                )
                return True
            else:
                logger.warning(
                    "Not logged in to LinkedIn",
                    extra={
                        "action": "navigate_to_jobs",
                        "status": "failed",
                        "message": "Session cookie may be expired"
                    }
                )
                return False

        except Exception as e:
            logger.error(
                f"Failed to navigate to jobs page: {e}",
                extra={
                    "action": "navigate_to_jobs",
                    "status": "error",
                    "error": str(e)
                }
            )
            return False

    async def _is_logged_in(self) -> bool:
        """Check if user is logged in to LinkedIn.

        Returns:
            True if logged in, False otherwise
        """
        try:
            # Check for presence of global-nav element or user-specific elements
            # LinkedIn shows different content when logged in
            await self._page.wait_for_selector(
                "div.global-nav, div.jobs-search, div.scaffold-layout",
                timeout=5000
            )

            # Check URL - if redirected to login page, not logged in
            current_url = self._page.url
            if "login" in current_url or "authwall" in current_url:
                return False

            return True

        except Exception:
            return False

    @property
    def page(self) -> Page:
        """Get the current page."""
        if not self._page:
            raise RuntimeError("Client not started. Call start() first.")
        return self._page

    async def search_jobs(
        self,
        keywords: str,
        location: str,
        max_results: int = 50
    ) -> list:
        """Search for jobs on LinkedIn.

        Args:
            keywords: Job search keywords
            location: Job location
            max_results: Maximum number of results to return

        Returns:
            List of job dictionaries
        """
        from automation.job_search import JobSearchScraper

        scraper = JobSearchScraper(self._page)
        return await scraper.search_jobs(keywords, location, max_results)

    async def get_page_content(self) -> str:
        """Get current page content.

        Returns:
            Page HTML content
        """
        return await self._page.content()

    async def take_screenshot(self, path: str) -> None:
        """Take a screenshot of the current page.

        Args:
            path: Path to save screenshot
        """
        await self._page.screenshot(path=path)

        logger.info(
            "Screenshot saved",
            extra={
                "action": "take_screenshot",
                "status": "success",
                "path": path
            }
        )
