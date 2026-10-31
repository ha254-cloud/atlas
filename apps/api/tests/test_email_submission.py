import pytest

from app.integrations.base import SubmissionAttachment, SubmissionPayload
from app.integrations.email_submission import EmailSubmissionConnector
from app.models.submission import SubmissionStatus
from app.services.email_service import EmailService


def payload(*, with_pdf: bool = True) -> SubmissionPayload:
    attachments = (
        [
            SubmissionAttachment(
                filename="appeal-CLM-001-v1.pdf",
                content=b"%PDF-1.4 approved appeal",
                content_type="application/pdf",
            )
        ]
        if with_pdf
        else []
    )
    return SubmissionPayload(
        appeal_id=11,
        claim_id=22,
        claim_number="CLM-001",
        payer_code="SHA",
        appeal_text="Please reconsider this claim.",
        attachment_files=attachments,
    )


@pytest.mark.asyncio
async def test_email_submission_sends_approved_pdf(monkeypatch):
    captured = {}

    def send_custom_strict(self, **kwargs):
        captured.update(kwargs)
        return "<submission@atlas.local>"

    monkeypatch.setattr(EmailService, "send_custom_strict", send_custom_strict)
    connector = EmailSubmissionConnector(
        recipient_email="appeals@payer.test",
        payer_name="Social Health Authority",
    )

    result = await connector.submit(payload())

    assert result.status == SubmissionStatus.SUBMITTED
    assert result.external_reference == "<submission@atlas.local>"
    assert result.payload["attachment_count"] == 1
    assert captured["attachments"] == [
        ("appeal-CLM-001-v1.pdf", b"%PDF-1.4 approved appeal", "application/pdf")
    ]


@pytest.mark.asyncio
async def test_email_submission_rejects_missing_approved_pdf():
    connector = EmailSubmissionConnector(recipient_email="appeals@payer.test")

    with pytest.raises(ValueError, match="approved appeal PDF"):
        await connector.submit(payload(with_pdf=False))
