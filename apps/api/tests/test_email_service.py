import smtplib

import httpx
import pytest

from app.core.config import settings
from app.services import email_service
from app.services.email_service import EmailDeliveryError, EmailService


class FakeSMTP:
    sent_message = None

    def __init__(self, host: str, port: int, timeout: int):
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def starttls(self):
        return None

    def login(self, user: str, password: str):
        return None

    def send_message(self, message):
        type(self).sent_message = message


def test_log_only_mode_never_logs_token_or_full_recipient(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DELIVERY_PROVIDER", "smtp")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    messages = []
    monkeypatch.setattr(
        email_service.logger,
        "warning",
        lambda message, *args: messages.append(message % args),
    )

    EmailService().send_password_reset_email(
        "patient@example.com",
        "secret-reset-token",
    )

    log_text = "\n".join(messages)
    assert "secret-reset-token" not in log_text
    assert "patient@example.com" not in log_text
    assert "p***@example.com" in log_text


def test_strict_email_requires_smtp_configuration(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DELIVERY_PROVIDER", "smtp")
    monkeypatch.setattr(settings, "SMTP_HOST", "")

    with pytest.raises(EmailDeliveryError, match="not configured"):
        EmailService().send_custom_strict(
            "payer@example.com",
            "Appeal",
            "Approved appeal attached",
        )


def test_verification_email_requires_smtp_configuration(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DELIVERY_PROVIDER", "smtp")
    monkeypatch.setattr(settings, "SMTP_HOST", "")

    with pytest.raises(EmailDeliveryError, match="not configured"):
        EmailService().send_verification_email(
            "admin@hospital.example",
            "verification-token",
        )


def test_smtp_delivery_returns_message_id(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DELIVERY_PROVIDER", "smtp")
    monkeypatch.setattr(settings, "SMTP_HOST", "mailpit")
    monkeypatch.setattr(settings, "SMTP_PORT", 1025)
    monkeypatch.setattr(settings, "SMTP_USE_TLS", False)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "no-reply@atlas.local")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    message_id = EmailService().send_custom_strict(
        "payer@example.com",
        "Appeal",
        "Approved appeal attached",
    )

    assert message_id.startswith("<")
    assert message_id.endswith("@atlas.local>")
    assert FakeSMTP.sent_message["To"] == "payer@example.com"
    assert FakeSMTP.sent_message["Message-ID"] == message_id


def test_configured_smtp_failure_is_explicit(monkeypatch):
    messages = []

    def fail_to_connect(*args, **kwargs):
        raise ConnectionRefusedError(111, "Connection refused")

    monkeypatch.setattr(settings, "EMAIL_DELIVERY_PROVIDER", "smtp")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(smtplib, "SMTP", fail_to_connect)
    monkeypatch.setattr(
        email_service.logger,
        "exception",
        lambda message, *args: messages.append(message % args),
    )

    with pytest.raises(EmailDeliveryError, match="Invitation email delivery failed"):
        EmailService().send_invitation_email(
            "teammate@example.com",
            "invite-token",
            "Nairobi Hospital",
        )

    log_text = "\n".join(messages)
    assert "ConnectionRefusedError (errno=111)" in log_text
    assert "teammate@example.com" not in log_text
    assert "t***@example.com" in log_text


def test_postmark_delivery_uses_https_api_and_returns_message_id(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "ErrorCode": 0,
                "Message": "OK",
                "MessageID": "postmark-message-id",
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(settings, "EMAIL_DELIVERY_PROVIDER", "postmark")
    monkeypatch.setattr(settings, "POSTMARK_SERVER_TOKEN", "server-token")
    monkeypatch.setattr(settings, "POSTMARK_API_URL", "https://api.postmarkapp.com/email")
    monkeypatch.setattr(settings, "POSTMARK_MESSAGE_STREAM", "outbound")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "onboarding@atlashealth.ke")
    monkeypatch.setattr(httpx, "post", fake_post)

    message_id = EmailService().send_custom_strict(
        "payer@example.com",
        "Appeal evidence",
        "Approved evidence attached.",
        [("appeal.pdf", b"pdf-content", "application/pdf")],
    )

    assert message_id == "postmark-message-id"
    assert captured["url"] == "https://api.postmarkapp.com/email"
    assert captured["headers"]["X-Postmark-Server-Token"] == "server-token"
    assert captured["json"] == {
        "From": "onboarding@atlashealth.ke",
        "To": "payer@example.com",
        "Subject": "Appeal evidence",
        "TextBody": "Approved evidence attached.",
        "MessageStream": "outbound",
        "Tag": "custom-email",
        "TrackOpens": False,
        "TrackLinks": "None",
        "Attachments": [
            {
                "Name": "appeal.pdf",
                "Content": "cGRmLWNvbnRlbnQ=",
                "ContentType": "application/pdf",
            }
        ],
    }


def test_postmark_rejection_is_explicit_and_privacy_safe(monkeypatch):
    messages = []

    class FakeResponse:
        status_code = 422

        @staticmethod
        def json():
            return {
                "ErrorCode": 300,
                "Message": "Invalid email request for teammate@example.com",
            }

    monkeypatch.setattr(settings, "EMAIL_DELIVERY_PROVIDER", "postmark")
    monkeypatch.setattr(settings, "POSTMARK_SERVER_TOKEN", "server-token")
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(
        email_service.logger,
        "error",
        lambda message, *args: messages.append(message % args),
    )

    with pytest.raises(EmailDeliveryError, match="Invitation email delivery failed"):
        EmailService().send_invitation_email(
            "teammate@example.com",
            "invite-token",
            "Nairobi Hospital",
        )

    log_text = "\n".join(messages)
    assert "http_status=422" in log_text
    assert "api_error_code=300" in log_text
    assert "teammate@example.com" not in log_text
    assert "t***@example.com" in log_text
