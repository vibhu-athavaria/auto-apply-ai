"""Tests for LinkedInClient.

Uses mocked Playwright to test browser automation logic.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.linkedin import LinkedInClient, LINKEDIN_JOBS_URL


class TestLinkedInClient:
    """Test cases for LinkedInClient."""

    @pytest.mark.asyncio
    async def test_init_with_session_cookie(self):
        """Test client initialization with session cookie."""
        client = LinkedInClient(session_cookie="test_li_at_cookie")
        
        assert client.session_cookie == "test_li_at_cookie"
        assert client.browser_state is None

    @pytest.mark.asyncio
    async def test_init_with_browser_state(self):
        """Test client initialization with browser state."""
        state = {"cookies": [], "origins": []}
        client = LinkedInClient(session_cookie="test_cookie", browser_state=state)
        
        assert client.session_cookie == "test_cookie"
        assert client.browser_state == state

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager entry/exit."""
        client = LinkedInClient(session_cookie="test_cookie")
        
        with patch.object(client, 'start', new_callable=AsyncMock) as mock_start:
            with patch.object(client, 'close', new_callable=AsyncMock) as mock_close:
                async with client as c:
                    assert c is client
                    mock_start.assert_called_once()
                
                mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_creates_context_with_browser_state(self):
        """Test that start() loads browser state when provided."""
        browser_state = {
            "cookies": [{"name": "test", "value": "value", "domain": ".linkedin.com"}],
            "origins": []
        }
        
        client = LinkedInClient(
            session_cookie="test_cookie",
            browser_state=browser_state
        )
        
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.add_cookies = AsyncMock(return_value=None)
        
        with patch('automation.linkedin.async_playwright') as mock_pw_factory:
            mock_pw_factory.return_value.start = AsyncMock(return_value=mock_playwright)
            
            await client.start()
            
            call_kwargs = mock_browser.new_context.call_args[1]
            assert "storage_state" in call_kwargs
            assert call_kwargs["storage_state"] == browser_state

    @pytest.mark.asyncio
    async def test_start_adds_session_cookie(self):
        """Test that start() adds li_at cookie to context."""
        client = LinkedInClient(session_cookie="my_session_cookie")
        
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.add_cookies = AsyncMock(return_value=None)
        
        with patch('automation.linkedin.async_playwright') as mock_pw_factory:
            mock_pw_factory.return_value.start = AsyncMock(return_value=mock_playwright)
            
            await client.start()
            
            mock_context.add_cookies.assert_called_once()
            cookies = mock_context.add_cookies.call_args[0][0]
            assert len(cookies) == 1
            assert cookies[0]["name"] == "li_at"
            assert cookies[0]["value"] == "my_session_cookie"
            assert cookies[0]["domain"] == ".linkedin.com"

    @pytest.mark.asyncio
    async def test_close_cleanup(self):
        """Test that close() cleans up all resources."""
        client = LinkedInClient(session_cookie="test_cookie")
        
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        client._playwright = mock_playwright
        client._browser = mock_browser
        client._context = mock_context
        client._page = mock_page
        
        await client.close()
        
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        
        assert client._page is None
        assert client._context is None
        assert client._browser is None
        assert client._playwright is None

    @pytest.mark.asyncio
    async def test_navigate_to_jobs_success(self):
        """Test successful navigation to jobs page."""
        client = LinkedInClient(session_cookie="test_cookie")
        
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=None)
        mock_page.url = "https://www.linkedin.com/jobs/"
        mock_page.wait_for_selector = AsyncMock(return_value=True)
        
        client._page = mock_page
        
        with patch.object(client, '_is_logged_in', new_callable=AsyncMock) as mock_logged_in:
            mock_logged_in.return_value = True
            
            result = await client.navigate_to_jobs()
            
            assert result is True
            mock_page.goto.assert_called_once_with(LINKEDIN_JOBS_URL)

    @pytest.mark.asyncio
    async def test_navigate_to_jobs_not_logged_in(self):
        """Test navigation fails when not logged in."""
        client = LinkedInClient(session_cookie="test_cookie")
        
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=None)
        mock_page.url = "https://www.linkedin.com/login"
        
        client._page = mock_page
        
        with patch.object(client, '_is_logged_in', new_callable=AsyncMock) as mock_logged_in:
            mock_logged_in.return_value = False
            
            result = await client.navigate_to_jobs()
            
            assert result is False

    @pytest.mark.asyncio
    async def test_is_logged_in_success(self):
        """Test _is_logged_in returns True when logged in."""
        client = LinkedInClient(session_cookie="test_cookie")
        
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(return_value=True)
        mock_page.url = "https://www.linkedin.com/jobs/"
        
        client._page = mock_page
        
        result = await client._is_logged_in()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_is_logged_in_redirect_to_login(self):
        """Test _is_logged_in returns False when redirected to login."""
        client = LinkedInClient(session_cookie="test_cookie")
        
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(return_value=True)
        mock_page.url = "https://www.linkedin.com/login"
        
        client._page = mock_page
        
        result = await client._is_logged_in()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_is_logged_in_authwall(self):
        """Test _is_logged_in returns False on authwall."""
        client = LinkedInClient(session_cookie="test_cookie")
        
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(return_value=True)
        mock_page.url = "https://www.linkedin.com/authwall"
        
        client._page = mock_page
        
        result = await client._is_logged_in()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_get_browser_state(self):
        """Test get_browser_state returns storage state."""
        client = LinkedInClient(session_cookie="test_cookie")
        
        mock_state = {"cookies": [{"name": "li_at", "value": "test"}], "origins": []}
        mock_context = AsyncMock()
        mock_context.storage_state = AsyncMock(return_value=mock_state)
        
        client._context = mock_context
        
        result = await client.get_browser_state()
        
        assert result == mock_state
        mock_context.storage_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_browser_state_no_context(self):
        """Test get_browser_state returns None when context not available."""
        client = LinkedInClient(session_cookie="test_cookie")
        client._context = None
        
        result = await client.get_browser_state()
        
        assert result is None

    @pytest.mark.asyncio
    async def test_page_property_raises_when_not_started(self):
        """Test page property raises error when client not started."""
        client = LinkedInClient(session_cookie="test_cookie")
        
        with pytest.raises(RuntimeError, match="Client not started"):
            _ = client.page

    @pytest.mark.asyncio
    async def test_page_property_returns_page_when_started(self):
        """Test page property returns page when client is started."""
        client = LinkedInClient(session_cookie="test_cookie")
        
        mock_page = AsyncMock()
        client._page = mock_page
        
        assert client.page is mock_page

    @pytest.mark.asyncio
    async def test_search_jobs_delegates_to_scraper(self):
        """Test search_jobs creates scraper and delegates."""
        client = LinkedInClient(session_cookie="test_cookie")
        
        mock_page = AsyncMock()
        client._page = mock_page
        
        mock_jobs = [
            {"linkedin_job_id": "123", "title": "Job 1"},
            {"linkedin_job_id": "456", "title": "Job 2"},
        ]
        
        with patch('automation.linkedin.JobSearchScraper') as MockScraper:
            mock_scraper_instance = AsyncMock()
            mock_scraper_instance.search_jobs = AsyncMock(return_value=mock_jobs)
            MockScraper.return_value = mock_scraper_instance
            
            result = await client.search_jobs(
                keywords="Python",
                location="Remote",
                max_results=50
            )
            
            MockScraper.assert_called_once_with(mock_page)
            mock_scraper_instance.search_jobs.assert_called_once_with(
                "Python", "Remote", 50
            )
            assert result == mock_jobs
