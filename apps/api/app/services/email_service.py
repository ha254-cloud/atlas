"""
Transactional email sending through configured HTTPS or SMTP transport.
"""

import smtplib
from base64 import b64encode
from collections.abc import Sequence
from email.message import EmailMessage
from email.utils import make_msgid

import httpx

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


def _smtp_failure_detail(exc: smtplib.SMTPException | OSError) -> str:
    if isinstance(exc, smtplib.SMTPResponseException):
        return f"smtp_code={exc.smtp_code}"
    if isinstance(exc, OSError) and exc.errno is not None:
        return f"errno={exc.errno}"
    return "no_transport_code"


class EmailService:
    def _send_postmark(
        self,
        to: str,
        subject: str,
        body: str,
        stub_label: str,
        attachments: Sequence[tuple[str, bytes, str]] | None,
    ) -> str:
        payload = {
            "From": settings.SMTP_FROM_EMAIL,
            "To": to,
            "Subject": subject,
            "TextBody": body,
            "MessageStream": settings.POSTMARK_MESSAGE_STREAM,
            "Tag": stub_label.lower().replace(" ", "-"),
            "TrackOpens": False,
            "TrackLinks": "None",
            "Attachments": [
                {
                    "Name": filename,
                    "Content": b64encode(content).decode("ascii"),
                    "ContentType": content_type,
                }
                for filename, content, content_type in attachments or []
            ],
        }
        try:
            response = httpx.post(
                settings.POSTMARK_API_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Postmark-Server-Token": settings.POSTMARK_SERVER_TOKEN,
                },
                json=payload,
                timeout=settings.EMAIL_DELIVERY_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            logger.exception(
                "Postmark request failed for %s to %s: %s",
                stub_label,
                _masked_email(to),
                type(exc).__name__,
            )
            raise EmailDeliveryError(f"{stub_label} delivery failed") from exc

        try:
            result = response.json()
        except ValueError:
            result = {}
        error_code = result.get("ErrorCode")
        if response.status_code != 200 or error_code != 0:
            logger.error(
                "Postmark rejected %s to %s: http_status=%s api_error_code=%s",
                stub_label,
                _masked_email(to),
                response.status_code,
                error_code,
            )
            raise EmailDeliveryError(f"{stub_label} delivery failed")

        message_id = result.get("MessageID")
        if not isinstance(message_id, str) or not message_id:
            logger.error(
                "Postmark accepted %s to %s without a message ID",
                stub_label,
                _masked_email(to),
            )
            raise EmailDeliveryError(f"{stub_label} delivery failed")

        logger.info(
            "Postmark accepted %s for %s with message ID %s",
            stub_label,
            _masked_email(to),
            message_id,
        )
        return message_id

    def _send_smtp(
        self,
        to: str,
        subject: str,
        body: str,
        stub_label: str,
        attachments: Sequence[tuple[str, bytes, str]] | None,
        *,
        require_delivery: bool,
    ) -> str | None:
        if not settings.SMTP_HOST:
            if require_delivery:
                raise EmailDeliveryError("SMTP delivery is not configured")
            logger.warning(
                "[EMAIL LOG ONLY] %s for %s; SMTP_HOST is not configured",
                stub_label,
                _masked_email(to),
            )
            return None

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
                "Failed to send email (%s) to %s: %s (%s)",
                stub_label,
                _masked_email(to),
                type(exc).__name__,
                _smtp_failure_detail(exc),
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
        if settings.EMAIL_DELIVERY_PROVIDER == "postmark":
            return self._send_postmark(
                to,
                subject,
                body,
                stub_label,
                attachments,
            )
        return self._send_smtp(
            to,
            subject,
            body,
            stub_label,
            attachments,
            require_delivery=require_delivery,
        )

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
