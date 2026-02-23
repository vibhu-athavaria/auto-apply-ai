"""LinkedIn authenticator using Playwright.

Logs in with email + password, extracts the li_at session cookie.
The password is NEVER stored — it is used once and discarded.
Only the resulting li_at cookie is persisted (encrypted).
"""
import asyncio
from typing import Optional

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

from utils.logger import get_logger
from utils.delays import human_delay, typing_delay, action_delay, navigation_delay

logger = get_logger(__name__)

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed"

EMAIL_SELECTOR = 'input[id="username"]'
PASSWORD_SELECTOR = 'input[id="password"]'
SUBMIT_SELECTOR = 'button[type="submit"]'
CHALLENGE_SELECTOR = 'input[id="input__email_verification_pin"]'
ERROR_SELECTOR = '.form__label--error, #error-for-username, #error-for-password'


class LinkedInAuthError(Exception):
    """Raised when LinkedIn authentication fails."""
    pass


class LinkedInChallengeRequired(LinkedInAuthError):
    """Raised when LinkedIn requires email/SMS verification."""
    pass


class LinkedInInvalidCredentials(LinkedInAuthError):
    """Raised when credentials are wrong."""
    pass


class LinkedInAuthenticator:
    """Logs into LinkedIn and extracts the li_at session cookie.

    The password is never stored — it is passed in, used once, then
    discarded. Only the li_at cookie from the resulting session is returned.
    """

    async def login(self, email: str, password: str) -> str:
        """Log into LinkedIn and return the li_at session cookie.

        Args:
            email: LinkedIn account email
            password: LinkedIn account password (never stored)

        Returns:
            li_at session cookie value

        Raises:
            LinkedInInvalidCredentials: If email/password are wrong
            LinkedInChallengeRequired: If LinkedIn requires 2FA/verification
            LinkedInAuthError: For other authentication failures
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )

            try:
                page = await context.new_page()
                await self._do_login(page, email, password)
                li_at = await self._extract_li_at(context)
                return li_at
            finally:
                await context.close()
                await browser.close()

    async def _do_login(self, page: Page, email: str, password: str) -> None:
        """Navigate to login page and submit credentials."""
        logger.info(
            "Navigating to LinkedIn login",
            extra={"action": "linkedin_login", "status": "in_progress"}
        )

        await page.goto(LINKEDIN_LOGIN_URL, wait_until="domcontentloaded")
        await navigation_delay()

        try:
            await page.wait_for_selector(EMAIL_SELECTOR, timeout=10000)
        except PlaywrightTimeout:
            # May already be logged in
            if "feed" in page.url or "home" in page.url:
                return
            raise LinkedInAuthError("LinkedIn login page did not load")

        # Type email with human-like delay
        await page.fill(EMAIL_SELECTOR, "")
        for char in email:
            await page.type(EMAIL_SELECTOR, char, delay=50)
        await typing_delay()

        # Type password with human-like delay
        await page.fill(PASSWORD_SELECTOR, "")
        for char in password:
            await page.type(PASSWORD_SELECTOR, char, delay=50)
        await typing_delay()

        # Click submit
        await page.click(SUBMIT_SELECTOR)
        await human_delay(3.0, 5.0)

        await self._check_login_result(page)

    async def _check_login_result(self, page: Page) -> None:
        """Check if login succeeded, failed, or requires challenge."""
        current_url = page.url

        # Success: redirected to feed
        if "feed" in current_url or "home" in current_url:
            logger.info(
                "LinkedIn login successful",
                extra={"action": "linkedin_login", "status": "success"}
            )
            return

        # Challenge: LinkedIn requires verification code
        try:
            await page.wait_for_selector(CHALLENGE_SELECTOR, timeout=3000)
            raise LinkedInChallengeRequired(
                "LinkedIn requires email/SMS verification. "
                "Please log in manually at linkedin.com first to clear the challenge, "
                "then try connecting again."
            )
        except PlaywrightTimeout:
            pass

        # Check for error messages
        try:
            error_elem = await page.query_selector(ERROR_SELECTOR)
            if error_elem:
                error_text = await error_elem.inner_text()
                if error_text.strip():
                    raise LinkedInInvalidCredentials(
                        f"LinkedIn rejected credentials: {error_text.strip()}"
                    )
        except LinkedInInvalidCredentials:
            raise
        except Exception:
            pass

        # Still on login page = wrong credentials
        if "login" in current_url or "checkpoint" in current_url:
            raise LinkedInInvalidCredentials(
                "Invalid LinkedIn email or password."
            )

        raise LinkedInAuthError(
            f"Login failed: unexpected page {current_url}"
        )

    async def _extract_li_at(self, context) -> str:
        """Extract the li_at session cookie from the browser context."""
        cookies = await context.cookies("https://www.linkedin.com")
        for cookie in cookies:
            if cookie["name"] == "li_at":
                logger.info(
                    "li_at cookie extracted",
                    extra={"action": "extract_li_at", "status": "success"}
                )
                return cookie["value"]

        raise LinkedInAuthError(
            "Login appeared to succeed but li_at cookie was not found. "
            "Please try again."
        )
