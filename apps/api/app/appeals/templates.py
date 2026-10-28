"""
Appeal letter templates for common denial scenarios.
These are structural templates — the AI fills in the specific content.
"""

STANDARD_APPEAL = """
{organization_name}
{organization_address}

{date}

Appeals Department
{payer_name}

RE: Appeal for Claim {claim_number}
    Patient: {patient_name}
    Date of Service: {service_date}
    Billed Amount: {billed_amount}

Dear Appeals Reviewer,

{appeal_body}

We respectfully request reconsideration of this claim within the timeframe required by your provider agreement and applicable regulations.

Please contact us if additional documentation is required.

Sincerely,

{signatory_name}
Revenue Cycle Management
{organization_name}
""".strip()

CODING_APPEAL = """
RE: Appeal for Claim {claim_number} — Coding Dispute

This appeal addresses a denial based on coding. We assert that the codes submitted accurately reflect the services rendered as documented in the medical record.

{appeal_body}

Supporting documentation is attached, including the operative note and medical record.
""".strip()

MEDICAL_NECESSITY_APPEAL = """
RE: Appeal for Claim {claim_number} — Medical Necessity

This appeal challenges the denial of services on the basis of medical necessity. The treating physician has determined that the services rendered were medically necessary and appropriate.

{appeal_body}

Clinical documentation supporting medical necessity is attached.
""".strip()


def get_template(denial_type: str) -> str:
    mapping = {
        "coding": CODING_APPEAL,
        "medical_necessity": MEDICAL_NECESSITY_APPEAL,
    }
    return mapping.get(denial_type, STANDARD_APPEAL)
