"""
Transactional email sending. Sends real emails over SMTP when SMTP_HOST is
configured (see app/core/config.py); otherwise falls back to logging what
WOULD be sent so the surrounding verification/invite/reset flows remain
fully functional and testable end to end without a mail server. Callers
never need to change regardless of which mode is active.
"""

import logging
import smtplib
from email.message import EmailMessage
from collections.abc import Sequence

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:

    def _send(
        self,
        to: str,
        subject: str,
        body: str,
        stub_label: str,
        attachments: Sequence[tuple[str, bytes, str]] | None = None,
    ) -> None:
        if not settings.SMTP_HOST:
            logger.info("[EMAIL STUB] %s to %s: %s", stub_label, to, body)
            return

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = to
        message.set_content(body)
        for filename, content, content_type in attachments or []:
            maintype, subtype = content_type.split("/", 1)
            message.add_attachment(
                content,
                maintype=maintype,
                subtype=subtype,
                filename=filename,
            )

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
                if settings.SMTP_USE_TLS:
                    smtp.starttls()
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError):
            # Never let a mail-server outage break the underlying auth flow —
            # log and move on, same as the stub would have.
            logger.exception("Failed to send email (%s) to %s", stub_label, to)

    def send_verification_email(self, to: str, token: str) -> None:
        link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        self._send(to, "Verify your Atlas account", f"Click to verify your email: {link}", "Verification email")

    def send_password_reset_email(self, to: str, token: str) -> None:
        link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        self._send(to, "Reset your Atlas password", f"Click to reset your password: {link}", "Password reset email")

    def send_invitation_email(self, to: str, token: str, organization_name: str) -> None:
        link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
        self._send(
            to,
            f"You've been invited to join {organization_name} on Atlas",
            f"Click to accept your invitation to join {organization_name}: {link}",
            "Invitation email",
        )

    def send_custom(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: Sequence[tuple[str, bytes, str]] | None = None,
    ) -> None:
        """Free-form send used by callers that build their own subject/body
        (e.g. the Workflow Engine's EMAIL step) rather than one of the
        fixed templates above."""
        self._send(to, subject, body, "Custom email", attachments)

