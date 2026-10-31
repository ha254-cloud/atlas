from typing import Any

from app.integrations.base import (
    SubmissionConnector,
    SubmissionPayload,
    SubmissionResponse,
)
from app.integrations.registry import submission_registry
from app.models.submission import SubmissionStatus
from app.services.email_service import EmailService


class EmailSubmissionConnector(SubmissionConnector):
    provider = "email"

    def __init__(self, **config: Any) -> None:
        self.recipient_email = str(config.get("recipient_email", "")).strip()
        self.payer_name = str(config.get("payer_name", "payer")).strip()
        if not self.recipient_email:
            raise ValueError("Payer submission email is not configured")

    async def submit(self, payload: SubmissionPayload) -> SubmissionResponse:
        if not payload.attachment_files:
            raise ValueError("Email submission requires the approved appeal PDF")
        attachments = [
            (item.filename, item.content, item.content_type) for item in payload.attachment_files
        ]
        message_id = EmailService().send_custom_strict(
            to=self.recipient_email,
            subject=f"Claim appeal {payload.claim_number} - {payload.payer_code}",
            body=(
                f"Please find the approved appeal for claim {payload.claim_number} "
                "attached. Please acknowledge receipt using this email's Message-ID."
            ),
            attachments=attachments,
        )
        return SubmissionResponse(
            external_reference=message_id,
            status=SubmissionStatus.SUBMITTED,
            message="SMTP server accepted the appeal email; payer acknowledgement pending",
            payload={
                "channel": "email",
                "recipient": self.recipient_email,
                "payer_name": self.payer_name,
                "attachment_count": len(attachments),
                "smtp_accepted": True,
                "payer_acknowledged": False,
            },
        )

    async def status(self, external_reference: str) -> SubmissionResponse:
        return SubmissionResponse(
            external_reference=external_reference,
            status=SubmissionStatus.SUBMITTED,
            message="SMTP accepted; payer acknowledgement must be recorded separately",
            payload={
                "channel": "email",
                "smtp_accepted": True,
                "payer_acknowledged": False,
            },
        )

    async def cancel(self, external_reference: str) -> SubmissionResponse:
        raise ValueError("An accepted email cannot be recalled through Atlas")


submission_registry.register("email", EmailSubmissionConnector)
