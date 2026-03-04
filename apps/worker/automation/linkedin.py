"""LinkedIn client using Playwright for browser automation.

This module handles:
- Browser context creation
- Cookie-based authentication
- Page navigation
- Session management

CRITICAL: Never store LinkedIn passwords. Use session cookies only.

Browser state (cookies, localStorage) is persisted per user to maintain
device identity and prevent "new device" security alerts from LinkedIn.
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

    Browser state is persisted to maintain device identity across sessions,
    preventing LinkedIn from sending "new device" security alerts.
    """

    def __init__(self, session_cookie: str = None, browser_state: Dict[str, Any] = None):
        """Initialize LinkedIn client.

        Args:
            session_cookie: LinkedIn li_at session cookie value
            browser_state: Previously saved browser state for device persistence
        """
        self.session_cookie = session_cookie or settings.linkedin_session_cookie
        self.browser_state = browser_state
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

        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ]

        self._browser = await self._playwright.chromium.launch(
            headless=settings.headless_browser,
            args=browser_args
        )

        context_options = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "locale": "en-US",
            "timezone_id": "America/New_York",
        }

        if self.browser_state:
            context_options["storage_state"] = self.browser_state
            logger.info(
                "Loaded existing browser state for device persistence",
                extra={
                    "action": "start_client",
                    "status": "state_loaded"
                }
            )

        self._context = await self._browser.new_context(**context_options)

        if self.session_cookie:
            logger.info(
                f"Setting LinkedIn session cookie (li_at), length: {len(self.session_cookie)}",
                extra={
                    "action": "start_client",
                    "status": "setting_cookie",
                    "cookie_length": len(self.session_cookie),
                    "cookie_prefix": self.session_cookie[:20] + "..." if len(self.session_cookie) > 20 else self.session_cookie
                }
            )
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

            # Verify cookie was set
            cookies = await self._context.cookies()
            li_at_cookie = next((c for c in cookies if c.get("name") == "li_at"), None)
            if li_at_cookie:
                logger.info(
                    "Session cookie verified in browser context",
                    extra={
                        "action": "start_client",
                        "status": "cookie_verified",
                        "cookie_domain": li_at_cookie.get("domain")
                    }
                )
            else:
                logger.warning(
                    "Session cookie not found in browser context after setting",
                    extra={"action": "start_client", "status": "cookie_not_found"}
                )

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

    async def get_browser_state(self) -> Optional[Dict[str, Any]]:
        """Get current browser state for device persistence.

        Returns:
            Browser state dict or None if context not available
        """
        if self._context:
            state = await self._context.storage_state()
            logger.info(
                "Retrieved browser state for device persistence",
                extra={
                    "action": "get_browser_state",
                    "status": "success"
                }
            )
            return state
        return None

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
                    "Not logged in to LinkedIn - Session cookie may be expired",
                    extra={
                        "action": "navigate_to_jobs",
                        "status": "failed",
                        "reason": "Session cookie may be expired"
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
            current_url = self._page.url
            logger.info(
                f"Checking login status, current URL: {current_url}",
                extra={
                    "action": "check_login",
                    "status": "checking",
                    "current_url": current_url
                }
            )

            # Check URL first - if redirected to login page, not logged in
            if "login" in current_url or "authwall" in current_url:
                logger.warning(
                    "Not logged in - redirected to login/authwall",
                    extra={"action": "check_login", "status": "not_logged_in", "url": current_url}
                )
                return False

            # Check for presence of global-nav element or user-specific elements
            # LinkedIn shows different content when logged in
            # Try multiple selectors as LinkedIn changes their UI frequently
            logged_in_selectors = [
                "div.global-nav",
                "div.jobs-search",
                "div.scaffold-layout",
                "[data-test-id='global-nav']",
                "nav.global-nav",
                ".jobs-search-results",
                "[data-test-job-search-results]",
                "div.feed-shared-update-v2",
                "button[aria-label*='Me' i]",
                "img[alt*='photo' i]",
            ]

            for selector in logged_in_selectors:
                try:
                    await self._page.wait_for_selector(selector, timeout=1000)
                    logger.info(
                        f"Login check passed - found selector: {selector}",
                        extra={"action": "check_login", "status": "logged_in", "selector": selector}
                    )
                    return True
                except:
                    continue

            # If we're on /jobs and not redirected to login, we're probably logged in
            # even if selectors don't match
            if "/jobs" in current_url and "login" not in current_url:
                logger.info(
                    "Login check passed - on jobs page without redirect",
                    extra={"action": "check_login", "status": "logged_in", "method": "url_check"}
                )
                return True

            logger.warning(
                "Login check failed - no logged-in indicators found",
                extra={"action": "check_login", "status": "no_indicators", "url": current_url}
            )
            return False

        except Exception as e:
            logger.error(
                f"Error checking login status: {e}",
                extra={"action": "check_login", "status": "error", "error": str(e)}
            )
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
