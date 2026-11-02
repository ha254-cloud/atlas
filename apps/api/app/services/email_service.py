"""
Transactional email sending. Sends real emails over SMTP when SMTP_HOST is
configured (see app/core/config.py); otherwise falls back to metadata-only
logging for tests and non-Docker development.
"""

import smtplib
from collections.abc import Sequence
from email.message import EmailMessage
from email.utils import make_msgid

from app.core.config import settings
from app.observability.logging import get_logger

logger = get_logger("atlas.email")


class EmailDeliveryError(RuntimeError):
    """Raised when configured or required SMTP delivery does not succeed."""


def _masked_email(address: str) -> str:
    local, separator, domain = address.partition("@")
    if not separator:
        return "***"
    return f"{local[:1]}***@{domain}"


class EmailService:
    def _send(
        self,
        to: str,
        subject: str,
        body: str,
        stub_label: str,
        attachments: Sequence[tuple[str, bytes, str]] | None = None,
        *,
        require_delivery: bool = False,
    ) -> str | None:
        if not settings.SMTP_HOST:
            if require_delivery:
                raise EmailDeliveryError("SMTP delivery is not configured")
            logger.warning(
                "[EMAIL LOG ONLY] %s for %s; SMTP_HOST is not configured",
                stub_label,
                _masked_email(to),
            )
            return

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = to
        sender_domain = settings.SMTP_FROM_EMAIL.partition("@")[2] or None
        message["Message-ID"] = make_msgid(domain=sender_domain)
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
        except (smtplib.SMTPException, OSError) as exc:
            logger.exception(
                "Failed to send email (%s) to %s",
                stub_label,
                _masked_email(to),
            )
            raise EmailDeliveryError(f"{stub_label} delivery failed") from exc

        message_id = str(message["Message-ID"])
        logger.info(
            "SMTP accepted %s for %s with message ID %s",
            stub_label,
            _masked_email(to),
            message_id,
        )
        return message_id

    def send_verification_email(self, to: str, token: str) -> str | None:
        link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        return self._send(
            to,
            "Verify your Atlas account",
            f"Click to verify your email: {link}",
            "Verification email",
            require_delivery=True,
        )

    def send_password_reset_email(self, to: str, token: str) -> str | None:
        link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        return self._send(
            to,
            "Reset your Atlas password",
            f"Click to reset your password: {link}",
            "Password reset email",
        )

    def send_invitation_email(
        self,
        to: str,
        token: str,
        organization_name: str,
    ) -> str | None:
        link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
        return self._send(
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
    ) -> str | None:
        return self._send(to, subject, body, "Custom email", attachments)

    def send_custom_strict(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: Sequence[tuple[str, bytes, str]] | None = None,
    ) -> str:
        message_id = self._send(
            to,
            subject,
            body,
            "Custom email",
            attachments,
            require_delivery=True,
        )
        if message_id is None:
            raise EmailDeliveryError("SMTP did not return a message ID")
        return message_id
