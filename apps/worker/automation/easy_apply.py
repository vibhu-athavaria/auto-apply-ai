"""Easy Apply automation for LinkedIn job applications.

This module handles:
- Detecting Easy Apply buttons
- Filling multi-step application forms
- Uploading resume
- Submitting applications
- Handling form errors

CRITICAL: All actions must use randomized delays to avoid detection.
"""
from typing import Optional
from pathlib import Path

from playwright.async_api import Page, ElementHandle, TimeoutError as PlaywrightTimeout

from config import settings
from utils.logger import get_logger
from utils.delays import human_delay, action_delay, typing_delay, random_pause

logger = get_logger(__name__)

EASY_APPLY_BUTTON_SELECTOR = 'button[data-control-name="jobdetails_topcard_inapply"]'
EASY_APPLY_MODAL_SELECTOR = '.jobs-easy-apply-modal, .artdeco-modal'
NEXT_BUTTON_SELECTOR = 'button[aria-label="Continue to next step"], button[aria-label="Review your application"]'
SUBMIT_BUTTON_SELECTOR = 'button[aria-label="Submit application"]'
REVIEW_BUTTON_SELECTOR = 'button[aria-label="Review your application"]'
CLOSE_BUTTON_SELECTOR = 'button[aria-label="Dismiss"]'
FILE_UPLOAD_SELECTOR = 'input[type="file"]'
TEXT_INPUT_SELECTOR = 'input[type="text"], textarea'
FORM_ERROR_SELECTOR = '.artdeco-inline-feedback--error, .jobs-easy-apply-modal-element'


class EasyApplyError(Exception):
    """Base exception for Easy Apply errors."""
    pass


class ApplicationNotFoundError(EasyApplyError):
    """Raised when job does not have Easy Apply option."""
    pass


class FormFillError(EasyApplyError):
    """Raised when form cannot be filled correctly."""
    pass


class SubmissionError(EasyApplyError):
    """Raised when application submission fails."""
    pass


class EasyApplyHandler:
    """Handles LinkedIn Easy Apply workflow.

    Usage:
        async with LinkedInClient(session_cookie) as client:
            handler = EasyApplyHandler(client.page)
            result = await handler.apply_to_job(job_url, resume_path)
    """

    def __init__(self, page: Page):
        self.page = page
        self.max_form_steps = 10

    async def apply_to_job(
        self,
        job_url: str,
        resume_path: Optional[str] = None,
        additional_info: Optional[dict] = None
    ) -> dict:
        """Apply to a job using Easy Apply.

        Args:
            job_url: LinkedIn job URL
            resume_path: Path to resume file for upload
            additional_info: Additional form data (phone, etc.)

        Returns:
            dict with 'success', 'application_id', 'message' keys

        Raises:
            ApplicationNotFoundError: If Easy Apply not available
            FormFillError: If form cannot be filled
            SubmissionError: If submission fails
        """
        logger.info(
            "Starting Easy Apply process",
            extra={
                "action": "easy_apply_start",
                "job_url": job_url,
                "status": "in_progress"
            }
        )

        try:
            await self._navigate_to_job(job_url)
            await random_pause()

            easy_apply_button = await self._find_easy_apply_button()
            if not easy_apply_button:
                raise ApplicationNotFoundError(
                    "Easy Apply button not found. Job may not support Easy Apply."
                )

            await self._click_button(easy_apply_button, "Easy Apply")
            await human_delay(1.5, 3.0)

            result = await self._fill_application_form(
                resume_path=resume_path,
                additional_info=additional_info
            )

            logger.info(
                "Easy Apply completed successfully",
                extra={
                    "action": "easy_apply_complete",
                    "job_url": job_url,
                    "status": "success"
                }
            )

            return result

        except (ApplicationNotFoundError, FormFillError, SubmissionError):
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during Easy Apply: {e}",
                extra={
                    "action": "easy_apply_error",
                    "job_url": job_url,
                    "error": str(e),
                    "status": "failed"
                }
            )
            raise SubmissionError(f"Application failed: {str(e)}") from e

    async def _navigate_to_job(self, job_url: str) -> None:
        """Navigate to job posting page."""
        try:
            await self.page.goto(job_url, wait_until="domcontentloaded")
            await human_delay(2.0, 4.0)

            await self.page.wait_for_selector(
                '.jobs-unified-top-card, .job-view-layout',
                timeout=15000
            )
        except PlaywrightTimeout:
            raise ApplicationNotFoundError(f"Could not load job page: {job_url}")

    async def _find_easy_apply_button(self) -> Optional[ElementHandle]:
        """Find the Easy Apply button on the job page."""
        try:
            await self.page.wait_for_selector(EASY_APPLY_BUTTON_SELECTOR, timeout=5000)
            buttons = await self.page.query_selector_all(EASY_APPLY_BUTTON_SELECTOR)

            for button in buttons:
                text = await button.inner_text()
                if "Easy Apply" in text:
                    return button

            return None
        except PlaywrightTimeout:
            return None

    async def _click_button(self, button: ElementHandle, button_name: str) -> None:
        """Click a button with proper delay."""
        await button.click()
        await action_delay()

        logger.info(
            f"Clicked {button_name} button",
            extra={
                "action": "click_button",
                "button": button_name,
                "status": "success"
            }
        )

    async def _fill_application_form(
        self,
        resume_path: Optional[str] = None,
        additional_info: Optional[dict] = None
    ) -> dict:
        """Fill out the Easy Apply modal form.

        Returns:
            dict with application result
        """
        steps_completed = 0

        while steps_completed < self.max_form_steps:
            try:
                await self.page.wait_for_selector(
                    EASY_APPLY_MODAL_SELECTOR,
                    timeout=5000
                )
            except PlaywrightTimeout:
                raise FormFillError("Application modal did not appear")

            await human_delay(0.5, 1.5)

            if await self._is_submission_complete():
                return {
                    "success": True,
                    "application_id": None,
                    "message": "Application submitted successfully"
                }

            current_step = await self._detect_current_step()

            if current_step == "resume_upload" and resume_path:
                await self._handle_resume_upload(resume_path)

            elif current_step == "contact_info":
                await self._fill_contact_info(additional_info)

            elif current_step == "questions":
                await self._handle_questions()

            elif current_step == "review":
                await self._handle_review()

            next_button = await self._find_next_button()
            if next_button:
                await self._click_button(next_button, "Next/Continue")
                steps_completed += 1
                await human_delay(1.0, 2.5)
            else:
                submit_button = await self._find_submit_button()
                if submit_button:
                    await self._click_button(submit_button, "Submit")
                    await human_delay(2.0, 4.0)
                    steps_completed += 1
                else:
                    raise FormFillError(
                        f"No action button found at step {steps_completed}"
                    )

        raise FormFillError(
            f"Max form steps ({self.max_form_steps}) exceeded"
        )

    async def _detect_current_step(self) -> str:
        """Detect what type of form step we're on."""
        content = await self.page.content()

        if 'Resume' in content and await self.page.query_selector(FILE_UPLOAD_SELECTOR):
            return "resume_upload"
        elif 'Phone' in content or 'Email' in content:
            return "contact_info"
        elif await self.page.query_selector(TEXT_INPUT_SELECTOR):
            return "questions"
        elif 'Review' in content or 'review' in content.lower():
            return "review"

        return "unknown"

    async def _handle_resume_upload(self, resume_path: str) -> None:
        """Handle resume file upload."""
        file_input = await self.page.query_selector(FILE_UPLOAD_SELECTOR)
        if file_input:
            path = Path(resume_path)
            if not path.exists():
                raise FormFillError(f"Resume file not found: {resume_path}")

            await file_input.set_input_files(str(path))
            await human_delay(1.0, 2.0)

            logger.info(
                "Resume uploaded",
                extra={
                    "action": "upload_resume",
                    "status": "success"
                }
            )

    async def _fill_contact_info(
        self,
        additional_info: Optional[dict] = None
    ) -> None:
        """Fill contact information fields."""
        additional_info = additional_info or {}

        text_inputs = await self.page.query_selector_all(TEXT_INPUT_SELECTOR)

        for input_elem in text_inputs:
            try:
                label_elem = await input_elem.evaluate(
                    'el => el.closest(".fb-dash-form-element")?.querySelector("label")?.textContent || ""'
                )
                label_text = label_elem.lower() if label_elem else ""

                if "phone" in label_text and "phone" in additional_info:
                    await input_elem.fill(additional_info["phone"])
                    await typing_delay()
                elif "email" in label_text and "email" in additional_info:
                    await input_elem.fill(additional_info["email"])
                    await typing_delay()

            except Exception as e:
                logger.warning(
                    f"Could not fill form field: {e}",
                    extra={
                        "action": "fill_form_field",
                        "error": str(e),
                        "status": "warning"
                    }
                )

        await human_delay(0.5, 1.5)

    async def _handle_questions(self) -> None:
        """Handle additional application questions."""
        text_inputs = await self.page.query_selector_all(
            'input[type="text"]:not([disabled]), textarea:not([disabled])'
        )

        for input_elem in text_inputs:
            try:
                input_id = await input_elem.get_attribute("id")
                current_value = await input_elem.get_attribute("value")

                if current_value:
                    continue

                await input_elem.fill("N/A")
                await typing_delay()

            except Exception as e:
                logger.warning(
                    f"Could not answer question: {e}",
                    extra={
                        "action": "answer_question",
                        "error": str(e),
                        "status": "warning"
                    }
                )

        radio_buttons = await self.page.query_selector_all(
            'input[type="radio"]:not([checked])'
        )

        for radio in radio_buttons[:3]:
            try:
                await radio.click()
                await action_delay()
            except Exception:
                pass

        await human_delay(0.5, 1.0)

    async def _handle_review(self) -> None:
        """Handle the review step before submission."""
        logger.info(
            "Reviewing application",
            extra={
                "action": "review_application",
                "status": "in_progress"
            }
        )
        await random_pause()

    async def _find_next_button(self) -> Optional[ElementHandle]:
        """Find the Next/Continue button."""
        buttons = await self.page.query_selector_all(NEXT_BUTTON_SELECTOR)
        for button in buttons:
            if await button.is_visible():
                return button

        all_buttons = await self.page.query_selector_all('button[type="button"]')
        for button in all_buttons:
            try:
                text = await button.inner_text()
                if "Continue" in text or "Next" in text:
                    return button
            except Exception:
                continue

        return None

    async def _find_submit_button(self) -> Optional[ElementHandle]:
        """Find the Submit button."""
        buttons = await self.page.query_selector_all(SUBMIT_BUTTON_SELECTOR)
        for button in buttons:
            if await button.is_visible():
                return button

        all_buttons = await self.page.query_selector_all('button[type="button"]')
        for button in all_buttons:
            try:
                text = await button.inner_text()
                if "Submit" in text and "application" in text.lower():
                    return button
            except Exception:
                continue

        return None

    async def _is_submission_complete(self) -> bool:
        """Check if application submission is complete."""
        try:
            content = await self.page.content()
            success_indicators = [
                "Application sent",
                "Your application was sent",
                "You have successfully applied",
                "Application submitted"
            ]

            for indicator in success_indicators:
                if indicator.lower() in content.lower():
                    return True

            close_button = await self.page.query_selector(CLOSE_BUTTON_SELECTOR)
            if close_button:
                await close_button.click()
                await action_delay()
                return True

            return False

        except Exception:
            return False

    async def close_modal(self) -> None:
        """Close any open modal."""
        try:
            close_button = await self.page.query_selector(CLOSE_BUTTON_SELECTOR)
            if close_button:
                await close_button.click()
                await action_delay()
        except Exception:
            pass

    async def check_easy_apply_available(self, job_url: str) -> bool:
        """Check if a job has Easy Apply option.

        Args:
            job_url: LinkedIn job URL

        Returns:
            True if Easy Apply is available
        """
        try:
            await self._navigate_to_job(job_url)
            button = await self._find_easy_apply_button()
            return button is not None
        except Exception:
            return False
