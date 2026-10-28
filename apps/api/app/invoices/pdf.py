from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.invoice import Invoice


class InvoicePDFService:
    @staticmethod
    def render(invoice: Invoice) -> bytes:
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            rightMargin=0.6 * inch,
            leftMargin=0.6 * inch,
            topMargin=0.55 * inch,
            bottomMargin=0.55 * inch,
            title=f"Atlas Recovery Invoice {invoice.invoice_number}",
            author="Atlas",
        )
        styles = getSampleStyleSheet()
        story = [
            Paragraph("ATLAS RECOVERY INVOICE", styles["Title"]),
            Spacer(1, 0.12 * inch),
            Paragraph(f"<b>Invoice:</b> {escape(invoice.invoice_number)}", styles["BodyText"]),
            Paragraph(f"<b>Bill to:</b> {escape(invoice.billing_name)}", styles["BodyText"]),
            Paragraph(f"<b>Billing email:</b> {escape(invoice.billing_email)}", styles["BodyText"]),
            Paragraph(
                f"<b>Recovery period:</b> {invoice.period_start} to {invoice.period_end}",
                styles["BodyText"],
            ),
            Paragraph(
                f"<b>Due:</b> {invoice.due_date} ({invoice.payment_terms_days} days)",
                styles["BodyText"],
            ),
            Spacer(1, 0.2 * inch),
        ]
        rows = [["Payment", "Claim", "Paid date", "Recovered", "Fee %", "Fee"]]
        rows.extend(
            [
                [
                    str(line.payment_id),
                    str(line.claim_id),
                    str(line.payment_date),
                    f"{invoice.currency} {line.recovered_amount:,.2f}",
                    f"{line.fee_percentage:.2f}%",
                    f"{invoice.currency} {line.fee_amount:,.2f}",
                ]
                for line in invoice.lines
            ]
        )
        table = Table(
            rows,
            repeatRows=1,
            colWidths=[0.75 * inch, 0.75 * inch, 1.05 * inch, 1.35 * inch, 0.7 * inch, 1.25 * inch],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324D")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C2CC")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F4F7F9")],
                    ),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.extend(
            [
                table,
                Spacer(1, 0.22 * inch),
                Paragraph(
                    f"<b>Total recovered:</b> {invoice.currency} {invoice.total_recovered_amount:,.2f}",
                    styles["BodyText"],
                ),
                Paragraph(
                    f"<b>Recovery fee:</b> {invoice.currency} {invoice.total_fee_amount:,.2f}",
                    styles["BodyText"],
                ),
                Paragraph(
                    f"<b>VAT ({invoice.vat_percentage:.2f}%):</b> {invoice.currency} {invoice.vat_amount:,.2f}",
                    styles["BodyText"],
                ),
                Paragraph(
                    f"<b>Amount due:</b> {invoice.currency} {invoice.total_amount:,.2f}",
                    styles["Heading2"],
                ),
            ]
        )
        document.build(story)
        return buffer.getvalue()
