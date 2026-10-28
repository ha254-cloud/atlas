import hashlib
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy.orm import Session

from app.documents.storage import save_bytes
from app.models.appeal import Appeal
from app.models.document import Document, DocumentType


class AppealPDFService:
    """Render and persist an approved appeal as a claim document."""

    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def create_document(self, appeal: Appeal, uploaded_by_id: int) -> Document:
        if appeal.organization_id != self.organization_id:
            raise ValueError("Appeal does not belong to this organization")

        content = self.render(appeal)
        filename = f"appeal-{appeal.claim.claim_number}-v{appeal.current_version}.pdf"
        storage_path, file_size = save_bytes(content, self.organization_id, ".pdf")
        document = Document(
            organization_id=self.organization_id,
            claim_id=appeal.claim_id,
            uploaded_by_id=uploaded_by_id,
            document_type=DocumentType.OTHER,
            filename=filename,
            storage_path=storage_path,
            content_type="application/pdf",
            file_size=file_size,
            checksum=hashlib.sha256(content).hexdigest(),
            tags=["appeal", f"appeal:{appeal.id}", f"version:{appeal.current_version}"],
            extracted_text=appeal.appeal_text,
            extraction_status="succeeded",
            extraction_method="generated_text",
            extraction_engine="reportlab",
            extraction_engine_version="4",
        )
        self.db.add(document)
        self.db.flush()
        appeal.pdf_document_id = document.id
        return document

    @staticmethod
    def render(appeal: Appeal) -> bytes:
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.65 * inch,
            bottomMargin=0.65 * inch,
            title=appeal.title or "Healthcare Claim Appeal",
            author=appeal.organization.name,
        )
        styles = getSampleStyleSheet()
        letterhead = ParagraphStyle(
            "Letterhead",
            parent=styles["Title"],
            alignment=TA_CENTER,
            spaceAfter=4,
        )
        centered = ParagraphStyle(
            "Centered",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            spaceAfter=3,
        )
        body = ParagraphStyle(
            "AppealBody",
            parent=styles["BodyText"],
            leading=15,
            spaceAfter=10,
        )

        organization = appeal.organization
        claim = appeal.claim
        patient = claim.patient
        story = [
            Paragraph(escape(organization.name), letterhead),
            Paragraph(
                escape(
                    " | ".join(
                        value
                        for value in (
                            getattr(organization, "address", None),
                            organization.phone,
                            organization.email,
                        )
                        if value
                    )
                ),
                centered,
            ),
            Spacer(1, 0.25 * inch),
            Paragraph(escape(appeal.title or "Healthcare Claim Appeal"), styles["Heading1"]),
            Paragraph(
                f"<b>Patient:</b> {escape(patient.first_name)} {escape(patient.last_name)}", body
            ),
            Paragraph(f"<b>Claim:</b> {escape(claim.claim_number)}", body),
            Paragraph(f"<b>Payer:</b> {escape(claim.payer.name)}", body),
            Paragraph(
                f"<b>Service date:</b> {escape(str(claim.service_date or 'Not provided'))}", body
            ),
            Spacer(1, 0.1 * inch),
        ]

        for paragraph in appeal.appeal_text.splitlines():
            if paragraph.strip():
                story.append(Paragraph(escape(paragraph.strip()), body))

        if appeal.references:
            story.extend([Paragraph("Evidence and references", styles["Heading2"])])
            story.extend(
                Paragraph(f"- {escape(reference)}", body) for reference in appeal.references
            )

        story.extend(
            [
                Spacer(1, 0.25 * inch),
                Paragraph("Sincerely,", body),
                Paragraph(escape(organization.name), body),
                Paragraph("Revenue Cycle Appeals Team", body),
            ]
        )
        document.build(story)
        return buffer.getvalue()
