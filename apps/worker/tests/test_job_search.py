"""Tests for JobSearchScraper.

Uses mocked Playwright page to test job parsing logic.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import re

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.job_search import JobSearchScraper


class MockElement:
    """Mock Playwright element handle."""

    def __init__(self, attributes=None, inner_text_value="", href=None):
        self._attributes = attributes or {}
        self._inner_text = inner_text_value
        self._href = href

    async def get_attribute(self, name: str):
        return self._attributes.get(name)

    async def inner_text(self):
        return self._inner_text

    async def query_selector(self, selector: str):
        return None

    async def query_selector_all(self, selector: str):
        return []


class MockJobCard:
    """Mock job card element for testing."""

    def __init__(
        self,
        job_id: str = "1234567890",
        title: str = "Software Engineer",
        company: str = "Tech Corp",
        location: str = "San Francisco, CA",
        job_url: str = "/jobs/view/1234567890/",
        easy_apply: bool = True
    ):
        self.job_id = job_id
        self.title = title
        self.company = company
        self.location = location
        self.job_url = job_url
        self.easy_apply = easy_apply
        self._attributes = {"data-job-id": job_id} if job_id else {}

    async def get_attribute(self, name: str):
        return self._attributes.get(name)

    async def inner_text(self):
        text = f"{self.title} {self.company} {self.location}"
        if self.easy_apply:
            text += " Easy Apply"
        return text

    async def query_selector(self, selector: str):
        if "a[href*='/jobs/view/']" in selector:
            return MockElement(
                attributes={"href": self.job_url},
                inner_text_value=self.title
            )
        elif "job-card-container__link" in selector or "sr-only" in selector:
            return MockElement(inner_text_value=self.title)
        elif "artdeco-entity-lockup__subtitle" in selector or "primary-description" in selector:
            return MockElement(inner_text_value=self.company)
        elif "artdeco-entity-lockup__caption" in selector or "metadata-item" in selector:
            return MockElement(inner_text_value=self.location)
        elif "apply-method" in selector:
            if self.easy_apply:
                return MockElement(inner_text_value="Easy Apply")
            return None
        return None


class MockPage:
    """Mock Playwright page for testing."""

    def __init__(self, job_cards=None):
        self._job_cards = job_cards or []
        self.url = "https://www.linkedin.com/jobs/search/"
        self._goto_count = 0

    async def goto(self, url: str, **kwargs):
        self._goto_count += 1
        return None

    async def wait_for_selector(self, selector: str, timeout: int = 10000):
        if not self._job_cards:
            raise Exception("No job cards found")
        return True

    async def query_selector(self, selector: str):
        if "jobs-search-results" in selector or "scaffold-layout" in selector:
            return MockScrollContainer(self)
        return None

    async def query_selector_all(self, selector: str):
        if "job-card-container" in selector or "jobs-search-results__list-item" in selector:
            return self._job_cards
        return []

    async def evaluate(self, script: str):
        return None


class MockScrollContainer:
    """Mock scrollable container."""

    def __init__(self, page):
        self.page = page

    async def evaluate(self, script: str):
        return None


class TestJobSearchScraper:
    """Test cases for JobSearchScraper."""

    @pytest.mark.asyncio
    async def test_parse_single_job_card(self):
        """Test parsing a single job card with all fields."""
        job_card = MockJobCard(
            job_id="999888777",
            title="Senior Python Developer",
            company="Awesome Inc",
            location="Remote",
            job_url="/jobs/view/999888777/",
            easy_apply=True
        )

        page = MockPage(job_cards=[job_card])
        scraper = JobSearchScraper(page)

        result = await scraper._parse_job_card(job_card)

        assert result is not None
        assert result["linkedin_job_id"] == "999888777"
        assert result["title"] == "Senior Python Developer"
        assert result["company"] == "Awesome Inc"
        assert result["location"] == "Remote"
        assert result["job_url"] == "https://www.linkedin.com/jobs/view/999888777/"
        assert result["easy_apply"] is True

    @pytest.mark.asyncio
    async def test_parse_job_card_without_easy_apply(self):
        """Test parsing a job card without Easy Apply."""
        job_card = MockJobCard(
            job_id="111222333",
            title="Product Manager",
            company="Big Tech",
            location="New York, NY",
            easy_apply=False
        )

        page = MockPage(job_cards=[job_card])
        scraper = JobSearchScraper(page)

        result = await scraper._parse_job_card(job_card)

        assert result is not None
        assert result["easy_apply"] is False

    @pytest.mark.asyncio
    async def test_parse_job_card_missing_job_id(self):
        """Test that job cards without ID return None."""
        job_card = MockJobCard(job_id=None)
        job_card._attributes = {}

        page = MockPage(job_cards=[job_card])
        scraper = JobSearchScraper(page)

        result = await scraper._parse_job_card(job_card)

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_job_id_from_data_attribute(self):
        """Test extracting job ID from data-job-id attribute."""
        job_card = MockJobCard(job_id="555666777")

        page = MockPage(job_cards=[job_card])
        scraper = JobSearchScraper(page)

        job_id = await scraper._extract_job_id(job_card)

        assert job_id == "555666777"

    @pytest.mark.asyncio
    async def test_extract_job_id_from_url(self):
        """Test extracting job ID from job URL."""
        job_card = MockJobCard(job_id=None, job_url="/jobs/view/444555666/")
        job_card._attributes = {}

        page = MockPage(job_cards=[job_card])
        scraper = JobSearchScraper(page)

        job_id = await scraper._extract_job_id(job_card)

        assert job_id == "444555666"

    @pytest.mark.asyncio
    async def test_parse_multiple_job_cards(self):
        """Test parsing multiple job cards."""
        job_cards = [
            MockJobCard(job_id="111", title="Job 1"),
            MockJobCard(job_id="222", title="Job 2"),
            MockJobCard(job_id="333", title="Job 3"),
        ]

        page = MockPage(job_cards=job_cards)
        scraper = JobSearchScraper(page)

        jobs = await scraper._parse_job_listings(max_results=50)

        assert len(jobs) == 3
        assert jobs[0]["linkedin_job_id"] == "111"
        assert jobs[1]["linkedin_job_id"] == "222"
        assert jobs[2]["linkedin_job_id"] == "333"

    @pytest.mark.asyncio
    async def test_parse_job_cards_respects_max_results(self):
        """Test that max_results limits the number of parsed jobs."""
        job_cards = [
            MockJobCard(job_id=str(i), title=f"Job {i}")
            for i in range(10)
        ]

        page = MockPage(job_cards=job_cards)
        scraper = JobSearchScraper(page)

        jobs = await scraper._parse_job_listings(max_results=5)

        assert len(jobs) == 5

    @pytest.mark.asyncio
    async def test_build_search_url(self):
        """Test search URL construction."""
        page = MockPage()
        scraper = JobSearchScraper(page)

        url = scraper._build_search_url("Python Developer", "San Francisco")

        assert "keywords=Python+Developer" in url
        assert "location=San+Francisco" in url
        assert "f_TPR=r86400" in url
        assert url.startswith("https://www.linkedin.com/jobs/search/")

    @pytest.mark.asyncio
    async def test_clean_text_removes_extra_whitespace(self):
        """Test text cleaning removes extra whitespace."""
        page = MockPage()
        scraper = JobSearchScraper(page)

        result = scraper._clean_text("  Hello   World   ")

        assert result == "Hello World"

    @pytest.mark.asyncio
    async def test_clean_text_returns_none_for_empty(self):
        """Test text cleaning returns None for empty strings."""
        page = MockPage()
        scraper = JobSearchScraper(page)

        assert scraper._clean_text("") is None
        assert scraper._clean_text("   ") is None
        assert scraper._clean_text(None) is None

    @pytest.mark.asyncio
    async def test_search_jobs_integration(self):
        """Test full search flow with mocked page."""
        job_cards = [
            MockJobCard(
                job_id="123",
                title="Software Engineer",
                company="Tech Corp",
                location="Remote",
                easy_apply=True
            ),
            MockJobCard(
                job_id="456",
                title="Data Scientist",
                company="Data Inc",
                location="New York, NY",
                easy_apply=False
            ),
        ]

        page = MockPage(job_cards=job_cards)
        scraper = JobSearchScraper(page)

        jobs = await scraper.search_jobs(
            keywords="Software Engineer",
            location="Remote",
            max_results=50
        )

        assert len(jobs) == 2
        assert page._goto_count == 1
