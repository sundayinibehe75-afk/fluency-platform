"""Notification service — sends transactional emails via Resend.

Functions:
- send_email — render an HTML template and send via Resend with retry logic

Template names: welcome, booking_confirmation, lesson_reminder,
               cancellation, post_lesson, password_reset
"""
import asyncio
import logging
from pathlib import Path
from string import Template

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure Resend API key
resend.api_key = settings.resend_api_key

# Directory containing HTML email templates
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Sender address for all outgoing emails
FROM_EMAIL = "Fluency Tutoring <noreply@fluencytutoring.com>"

# Retry configuration
MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s

# Valid template names
VALID_TEMPLATES = {
    "welcome",
    "booking_confirmation",
    "lesson_reminder",
    "cancellation",
    "post_lesson",
    "password_reset",
}


def _render_template(template_name: str, context: dict) -> str:
    """Load and render an HTML template with the given context.

    Uses Python's string.Template for simple $variable substitution.
    """
    template_path = TEMPLATES_DIR / f"{template_name}.html"
    if not template_path.exists():
        raise FileNotFoundError(f"Email template not found: {template_path}")

    raw_html = template_path.read_text(encoding="utf-8")
    template = Template(raw_html)
    return template.safe_substitute(context)


async def send_email(to: str, template_name: str, context: dict) -> None:
    """Send an email using the Resend API with retry logic.

    Renders the specified HTML template with the provided context and sends
    it to the recipient. Retries up to 3 times with exponential backoff
    (1s, 2s, 4s) on failure. Logs failure without blocking the caller.

    Args:
        to: Recipient email address.
        template_name: Name of the template (without .html extension).
        context: Dictionary of variables to substitute into the template.
    """
    if template_name not in VALID_TEMPLATES:
        logger.error(
            "Invalid email template name",
            extra={"template_name": template_name, "to": to},
        )
        return

    try:
        html_content = _render_template(template_name, context)
    except FileNotFoundError:
        logger.error(
            "Email template file not found",
            extra={"template_name": template_name, "to": to},
        )
        return

    subject = _get_subject(template_name, context)

    for attempt in range(MAX_RETRIES):
        try:
            resend.Emails.send(
                {
                    "from": FROM_EMAIL,
                    "to": [to],
                    "subject": subject,
                    "html": html_content,
                }
            )
            logger.info(
                "Email sent successfully",
                extra={
                    "template_name": template_name,
                    "to": to,
                    "attempt": attempt + 1,
                },
            )
            return
        except Exception as exc:
            logger.warning(
                "Email send attempt failed",
                extra={
                    "template_name": template_name,
                    "to": to,
                    "attempt": attempt + 1,
                    "error": str(exc),
                },
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(BACKOFF_SECONDS[attempt])

    # All retries exhausted — log and continue without blocking
    logger.error(
        "Email delivery failed after all retries",
        extra={
            "template_name": template_name,
            "to": to,
            "max_retries": MAX_RETRIES,
        },
    )


def _get_subject(template_name: str, context: dict) -> str:
    """Return the email subject line based on the template name."""
    subjects = {
        "welcome": "Welcome to Fluency Tutoring!",
        "booking_confirmation": "Your Lesson is Confirmed",
        "lesson_reminder": "Reminder: Your Lesson is Tomorrow",
        "cancellation": "Booking Cancellation Confirmation",
        "post_lesson": "How Was Your Lesson?",
        "password_reset": "Reset Your Password",
    }
    return subjects.get(template_name, "Fluency Tutoring")
