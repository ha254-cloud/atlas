"""
Sectioned appeal generator.

Builds an appeal letter by generating each section independently:
  1. Introduction
  2. Medical Necessity / Clinical Justification
  3. Coding Justification
  4. Policy References
  5. Supporting Documents checklist
  6. Requested Action
  7. Signature block

Generating section by section produces cleaner, more editable output
than asking the LLM to write the whole letter at once.
"""

from app.ai.gateway import gateway
from app.appeals.validator import validate_sections

SECTIONS = [
    "introduction",
    "medical_necessity",
    "coding_justification",
    "policy_references",
    "supporting_documents",
    "requested_action",
    "signature",
]

_SECTION_PROMPTS = {
    "introduction": (
        "Write the introduction paragraph of a healthcare appeal letter on behalf of "
        "{hospital_name}. State the purpose of the appeal, reference the patient "
        "{patient_name}, the claim number {claim_number}, the denial date, and the "
        "denial code {denial_code}. Be formal and professional. Return only the paragraph text."
    ),
    "medical_necessity": (
        "Write the medical necessity section of a healthcare appeal letter for claim {claim_number}. "
        "Explain why the services were medically necessary based on diagnosis codes {diagnosis_codes} "
        "and the clinical condition. The AI analysis found the root cause of denial to be: "
        "{root_cause}. Recommended action: {recommended_action}. Reference applicable clinical guidelines. "
        "Return only the section text."
    ),
    "coding_justification": (
        "Write the coding justification section of a healthcare appeal letter. "
        "Defend the procedure codes {procedure_codes} and modifiers {modifiers} used. "
        "Use only verified coding guidance applicable to the payer and jurisdiction. "
        "Do not cite a source that is not supplied in the context. Denial code: {denial_code}. "
        "Return only the section text."
    ),
    "policy_references": (
        "Write the policy references section of a healthcare appeal letter. "
        "Use only supplied, verified payer contract, SHA benefit, or operating guidance. "
        "If no verified reference is supplied, state that payer policy verification is required. "
        "Claim denial code: {denial_code}. Procedures: {procedure_codes}. "
        "Applicable references to cite if relevant: {suggested_citations}. "
        "Return only the section text."
    ),
    "supporting_documents": (
        "Write a supporting documents paragraph for a healthcare appeal letter. "
        "List what documents are attached to support the appeal for claim {claim_number}. "
        "Documents on file: {documents_summary}. "
        "Include medical records, operative notes, referral letters as appropriate. "
        "Return only the section text."
    ),
    "requested_action": (
        "Write the requested action section of a healthcare appeal letter. "
        "Clearly state what action is requested from the payer: full payment, "
        "reconsideration, or reprocessing. Claim: {claim_number}. Amount: KES {billed_amount}. "
        "Return only the section text."
    ),
    "signature": (
        "Write a professional closing and signature block for a healthcare appeal letter "
        "sent on behalf of {hospital_name}. Include a professional closing, space for "
        "signature, and provider name placeholder. Return only the closing text."
    ),
}


class SectionedAppealGenerator:
    async def generate(
        self, claim, denial=None, analysis=None, organization=None, extra_context=None
    ) -> dict:
        """Generate each section independently and combine into a full letter.
        `analysis`, if provided, is a ClaimAnalysis row whose root_cause/
        recommended_action feed the medical necessity section. `organization`,
        if provided, is the Organization (hospital/practice) sending the letter.
        `extra_context`, if provided, may contain `documents_summary` and
        `suggested_citations` — richer evidence/citation grounding built by
        AppealService."""
        context = self._build_context(claim, denial, analysis, organization, extra_context)
        sections: dict[str, str] = {}

        for section in SECTIONS:
            prompt = _SECTION_PROMPTS[section].format(**context)
            text = await gateway.generate(task="appeal", prompt=prompt)
            # Strip any accidental JSON wrapping
            sections[section] = text.strip().strip('"')

        validate_sections(sections, required=SECTIONS)

        full_text = self._assemble(sections, context)

        return {
            "appeal_letter": full_text,
            "sections": sections,
            "summary": f"Appeal for claim {claim.claim_number} — {denial.denial_code if denial else 'underpayment'}",
            "citations": [],
            "key_arguments": [sections.get("requested_action", "")[:200]],
            "requested_action": sections.get("requested_action", ""),
            "confidence": 85,
        }

    def _build_context(
        self, claim, denial, analysis=None, organization=None, extra_context=None
    ) -> dict:
        modifiers = (
            ", ".join(line.modifier for line in claim.claim_lines if line.modifier) or "None"
        )
        extra_context = extra_context or {}
        return {
            "claim_number": claim.claim_number,
            "patient_name": f"{claim.patient.first_name} {claim.patient.last_name}"
            if claim.patient
            else "Unknown",
            "payer_name": claim.payer.name if claim.payer else f"(payer_id={claim.payer_id})",
            "hospital_name": organization.name if organization else "the provider organization",
            "denial_code": denial.denial_code if denial else "N/A",
            "denial_reason": denial.description if denial else "Underpayment",
            "billed_amount": float(claim.billed_amount),
            "paid_amount": float(claim.paid_amount),
            "diagnosis_codes": ", ".join(d.icd_code for d in claim.diagnoses) or "None on file",
            "procedure_codes": ", ".join(line.cpt_code for line in claim.claim_lines)
            or "None on file",
            "modifiers": modifiers,
            "root_cause": analysis.root_cause if analysis else "Not yet analyzed",
            "recommended_action": (analysis.recommended_action if analysis else None)
            or "None available",
            "documents_summary": extra_context.get("documents_summary") or "None on file",
            "suggested_citations": ", ".join(extra_context.get("suggested_citations") or [])
            or "None",
        }

    def _assemble(self, sections: dict[str, str], context: dict) -> str:
        parts = [
            f"RE: Appeal for Claim {context['claim_number']}",
            "",
            sections.get("introduction", ""),
            "",
            sections.get("medical_necessity", ""),
            "",
            sections.get("coding_justification", ""),
            "",
            sections.get("policy_references", ""),
            "",
            sections.get("supporting_documents", ""),
            "",
            sections.get("requested_action", ""),
            "",
            sections.get("signature", ""),
        ]
        return "\n".join(parts)
