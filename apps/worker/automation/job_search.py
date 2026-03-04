"""Job search scraper for LinkedIn.

This module handles:
- Job search by keywords and location
- Parsing job listings
- Extracting job details (Title, Company, URL, Easy Apply flag)
"""
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode, quote

from playwright.async_api import Page

from utils.logger import get_logger
from utils.delays import search_delay, navigation_delay, page_scroll_delay, action_delay

logger = get_logger(__name__)


class JobSearchScraper:
    """Scrapes job listings from LinkedIn.

    Extracts:
    - Job title
    - Company name
    - Location
    - Job URL
    - Easy Apply flag
    - LinkedIn job ID
    """

    # LinkedIn job search URL
    JOBS_SEARCH_URL = "https://www.linkedin.com/jobs/search/"

    # Selectors for job listings (these may need updates if LinkedIn changes their UI)
    JOB_CARD_SELECTOR = "div.job-card-container, li.jobs-search-results__list-item, div.scaffold-layout__list-item"
    JOB_TITLE_SELECTOR = "span.job-card-container__link, a.job-card-container__link strong, span.sr-only"
    COMPANY_SELECTOR = "div.artdeco-entity-lockup__subtitle span, span.job-card-container__primary-description"
    LOCATION_SELECTOR = "div.artdeco-entity-lockup__caption span, li.job-card-container__metadata-item"
    EASY_APPLY_SELECTOR = "li.job-card-container__apply-method, span.job-card-container__apply-method"
    JOB_LINK_SELECTOR = "a.job-card-container__link, a[data-control-name='job_card_title']"

    def __init__(self, page: Page):
        """Initialize scraper with a Playwright page.

        Args:
            page: Playwright page object
        """
        self.page = page

    async def search_jobs(
        self,
        keywords: str,
        location: str,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Search for jobs on LinkedIn.

        Args:
            keywords: Job search keywords
            location: Job location
            max_results: Maximum number of results to return

        Returns:
            List of job dictionaries with:
            - linkedin_job_id
            - title
            - company
            - location
            - job_url
            - easy_apply
        """
        logger.info(
            "Starting job search",
            extra={
                "action": "search_jobs",
                "status": "in_progress",
                "keywords": keywords,
                "location": location,
                "max_results": max_results
            }
        )

        # Build search URL
        search_url = self._build_search_url(keywords, location)

        try:
            # Navigate to search page
            logger.info(
                f"Navigating to search URL: {search_url}",
                extra={
                    "action": "search_jobs",
                    "status": "navigating",
                    "url": search_url
                }
            )
            await self.page.goto(search_url)
            await navigation_delay()

            current_url = self.page.url
            logger.info(
                f"Current page URL: {current_url}",
                extra={
                    "action": "search_jobs",
                    "status": "page_loaded",
                    "current_url": current_url
                }
            )

            # Check if we got redirected to login
            if "login" in current_url or "authwall" in current_url:
                # Take a screenshot for debugging
                try:
                    await self.page.screenshot(path="/tmp/linkedin_auth_failed.png")
                    logger.info(
                        "Screenshot saved to /tmp/linkedin_auth_failed.png",
                        extra={"action": "search_jobs", "status": "screenshot_saved"}
                    )
                except Exception as screenshot_error:
                    logger.warning(
                        f"Failed to take screenshot: {screenshot_error}",
                        extra={"action": "search_jobs", "status": "screenshot_failed"}
                    )

                logger.error(
                    "Redirected to login page - session expired",
                    extra={
                        "action": "search_jobs",
                        "status": "auth_failed",
                        "current_url": current_url
                    }
                )
                raise Exception("LinkedIn session expired. Please reconnect your account.")

            # Wait for job listings to load
            logger.info(
                "Waiting for job listings to load...",
                extra={"action": "search_jobs", "status": "waiting_for_listings"}
            )
            await self._wait_for_job_listings()

            logger.info(
                "Job listings loaded, scrolling for more results...",
                extra={"action": "search_jobs", "status": "scrolling"}
            )

            # Scroll to load more results
            await self._scroll_to_load_more(max_results)

            logger.info(
                "Scrolling complete, parsing job listings...",
                extra={"action": "search_jobs", "status": "parsing"}
            )

            # Parse job listings
            jobs = await self._parse_job_listings(max_results)

            logger.info(
                "Job search completed",
                extra={
                    "action": "search_jobs",
                    "status": "success",
                    "jobs_found": len(jobs),
                    "keywords": keywords,
                    "location": location
                }
            )

            return jobs

        except Exception as e:
            logger.error(
                f"Job search failed: {e}",
                extra={
                    "action": "search_jobs",
                    "status": "error",
                    "error": str(e),
                    "keywords": keywords,
                    "location": location
                }
            )
            raise

    def _build_search_url(self, keywords: str, location: str) -> str:
        """Build LinkedIn job search URL.

        Args:
            keywords: Search keywords
            location: Job location

        Returns:
            Full search URL
        """
        params = {
            "keywords": keywords,
            "location": location,
            "f_TPR": "r86400",  # Past 24 hours - can be made configurable
            "position": 1,
            "pageNum": 0
        }

        return f"{self.JOBS_SEARCH_URL}?{urlencode(params)}"

    async def _wait_for_job_listings(self, timeout: int = 10000):
        """Wait for job listings to load on the page.

        Args:
            timeout: Maximum wait time in milliseconds
        """
        try:
            await self.page.wait_for_selector(
                self.JOB_CARD_SELECTOR,
                timeout=timeout
            )
        except Exception:
            # Try alternative selectors
            await self.page.wait_for_selector(
                "div.jobs-search-results, div.scaffold-layout__list",
                timeout=timeout
            )

    async def _scroll_to_load_more(self, max_results: int):
        """Scroll down to load more job listings.

        LinkedIn uses infinite scroll, so we need to scroll
        to load additional results.

        Args:
            max_results: Target number of results
        """
        # Find the scrollable container
        scroll_container = await self.page.query_selector(
            "div.jobs-search-results, div.scaffold-layout__list"
        )

        if not scroll_container:
            # Fallback to window scroll
            scroll_container = self.page

        loaded = 0
        max_scrolls = 20  # Prevent infinite scrolling
        scroll_count = 0

        while scroll_count < max_scrolls:
            # Count current job cards
            job_cards = await self.page.query_selector_all(self.JOB_CARD_SELECTOR)
            current_count = len(job_cards)

            if current_count >= max_results:
                break

            if current_count == loaded:
                # No new jobs loaded, stop scrolling
                break

            loaded = current_count

            # Scroll down
            await scroll_container.evaluate(
                "element => element.scrollTop = element.scrollHeight"
            )

            await page_scroll_delay()
            scroll_count += 1

    async def _parse_job_listings(self, max_results: int) -> List[Dict[str, Any]]:
        """Parse job listings from the page.

        Args:
            max_results: Maximum number of results to parse

        Returns:
            List of job dictionaries
        """
        jobs = []

        # Get all job cards
        job_cards = await self.page.query_selector_all(self.JOB_CARD_SELECTOR)

        # Also check for alternative selectors if none found
        if not job_cards:
            logger.warning(
                f"No job cards found with selector: {self.JOB_CARD_SELECTOR}",
                extra={
                    "action": "parse_job_listings",
                    "status": "no_cards_found",
                    "selector": self.JOB_CARD_SELECTOR
                }
            )
            # Try alternative selectors
            alternative_selectors = [
                "div.job-card-container",
                "li.jobs-search-results__list-item",
                "div.scaffold-layout__list-item",
                "[data-job-id]"
            ]
            for selector in alternative_selectors:
                job_cards = await self.page.query_selector_all(selector)
                if job_cards:
                    logger.info(
                        f"Found {len(job_cards)} job cards with alternative selector: {selector}",
                        extra={
                            "action": "parse_job_listings",
                            "status": "found_with_alt_selector",
                            "selector": selector,
                            "cards_found": len(job_cards)
                        }
                    )
                    break

        logger.info(
            f"Found {len(job_cards)} job cards total",
            extra={
                "action": "parse_job_listings",
                "status": "in_progress",
                "cards_found": len(job_cards)
            }
        )

        for i, card in enumerate(job_cards[:max_results]):
            try:
                job = await self._parse_job_card(card)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.warning(
                    f"Failed to parse job card {i}: {e}",
                    extra={
                        "action": "parse_job_card",
                        "status": "error",
                        "card_index": i,
                        "error": str(e)
                    }
                )
                continue

        return jobs

    async def _parse_job_card(self, card) -> Optional[Dict[str, Any]]:
        """Parse a single job card.

        Args:
            card: Playwright element handle for job card

        Returns:
            Job dictionary or None if parsing failed
        """
        # Extract job ID from card attributes or URL
        job_id = await self._extract_job_id(card)
        if not job_id:
            return None

        # Extract title
        title = await self._extract_text(card, self.JOB_TITLE_SELECTOR)
        if not title:
            # Try alternative approach
            title_element = await card.query_selector("a[href*='/jobs/view/']")
            if title_element:
                title = await title_element.inner_text()

        # Extract company
        company = await self._extract_text(card, self.COMPANY_SELECTOR)

        # Extract location
        location = await self._extract_text(card, self.LOCATION_SELECTOR)

        # Extract job URL
        job_url = await self._extract_job_url(card)

        # Check for Easy Apply
        easy_apply = await self._check_easy_apply(card)

        # Clean up extracted text
        title = self._clean_text(title)
        company = self._clean_text(company)
        location = self._clean_text(location)

        if not title or not job_url:
            return None

        return {
            "linkedin_job_id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "job_url": job_url,
            "easy_apply": easy_apply
        }

    async def _extract_job_id(self, card) -> Optional[str]:
        """Extract LinkedIn job ID from card.

        Args:
            card: Job card element

        Returns:
            Job ID string or None
        """
        # Try to get from data attribute
        job_id = await card.get_attribute("data-job-id")
        if job_id:
            return job_id

        # Try to extract from link
        link = await card.query_selector("a[href*='/jobs/view/']")
        if link:
            href = await link.get_attribute("href")
            if href:
                # Extract job ID from URL like /jobs/view/1234567890/
                match = re.search(r'/jobs/view/(\d+)', href)
                if match:
                    return match.group(1)

        # Try to get from job card container ID
        card_id = await card.get_attribute("id")
        if card_id:
            # ID format might be job-card-container-1234567890
            match = re.search(r'(\d{10,})', card_id)
            if match:
                return match.group(1)

        return None

    async def _extract_text(self, element, selector: str) -> Optional[str]:
        """Extract text from element using selector.

        Args:
            element: Parent element
            selector: CSS selector

        Returns:
            Extracted text or None
        """
        try:
            child = await element.query_selector(selector)
            if child:
                return await child.inner_text()
        except Exception:
            pass
        return None

    async def _extract_job_url(self, card) -> Optional[str]:
        """Extract job URL from card.

        Args:
            card: Job card element

        Returns:
            Full job URL or None
        """
        try:
            link = await card.query_selector("a[href*='/jobs/view/']")
            if link:
                href = await link.get_attribute("href")
                if href:
                    # Ensure full URL
                    if href.startswith("/"):
                        return f"https://www.linkedin.com{href}"
                    return href
        except Exception:
            pass
        return None

    async def _check_easy_apply(self, card) -> bool:
        """Check if job has Easy Apply option.

        Args:
            card: Job card element

        Returns:
            True if Easy Apply is available
        """
        try:
            # Look for Easy Apply badge
            easy_apply_element = await card.query_selector(self.EASY_APPLY_SELECTOR)
            if easy_apply_element:
                text = await easy_apply_element.inner_text()
                return "easy apply" in text.lower()

            # Alternative: look for Easy Apply button text
            card_text = await card.inner_text()
            return "easy apply" in card_text.lower()
        except Exception:
            return False

    def _clean_text(self, text: Optional[str]) -> Optional[str]:
        """Clean extracted text.

        Args:
            text: Raw text

        Returns:
            Cleaned text or None
        """
        if not text:
            return None

        # Remove extra whitespace
        text = " ".join(text.split())

        # Remove empty text
        if not text.strip():
            return None

        return text.strip()
