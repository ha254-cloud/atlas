"""Generate a structured, editable appeal in one grounded model call."""

from app.ai.gateway import gateway
from app.ai.prompt_loader import load_prompt
from app.appeals.grounding import render_policy_reference_section
from app.appeals.validator import AppealValidationError, validate_appeal, validate_sections

SECTIONS = [
    "introduction",
    "medical_necessity",
    "coding_justification",
    "policy_references",
    "supporting_documents",
    "requested_action",
    "signature",
]

class SectionedAppealGenerator:
    async def generate(
        self, claim, denial=None, analysis=None, organization=None, extra_context=None
    ) -> dict:
        """Generate all editable sections in one validated JSON response."""
        context = self._build_context(claim, denial, analysis, organization, extra_context)
        data = await gateway.generate_json(
            task="appeal_sectioned",
            prompt=self._build_prompt(context),
            system=load_prompt("appeal_sectioned"),
        )
        sections = data.get("sections")
        if not isinstance(sections, dict):
            raise AppealValidationError("Sectioned appeal response contains no sections object.")

        validate_sections(sections, required=SECTIONS)
        sections["policy_references"] = render_policy_reference_section(
            context["verified_policy_sources"]
        )
        full_text = self._assemble(sections, context)
        result = {
            "title": data.get("title") or f"Appeal Letter — Claim {claim.claim_number}",
            "appeal_letter": full_text,
            "sections": sections,
            "summary": data.get("summary")
            or (
                f"Appeal for claim {claim.claim_number} — "
                f"{denial.denial_code if denial else 'underpayment'}"
            ),
            "citations": data.get("citations"),
            "key_arguments": data.get("key_arguments"),
            "requested_action": sections.get("requested_action", ""),
            "attachments": data.get("attachments"),
            "missing_information": data.get("missing_information"),
            "confidence": data.get("confidence", 0),
        }
        validate_appeal(
            result,
            claim.claim_number,
            denial_code=denial.denial_code if denial else None,
            patient_last_name=claim.patient.last_name if claim.patient else None,
        )
        return result

    def _build_prompt(self, context: dict) -> str:
        return (
            f"Hospital/Provider: {context['hospital_name']}\n"
            f"Patient Name: {context['patient_name']}\n"
            f"Claim Number: {context['claim_number']}\n"
            f"Payer: {context['payer_name']}\n"
            f"Service Date: {context['service_date']}\n"
            f"Billed Amount (KES): {context['billed_amount']:.2f}\n"
            f"Paid Amount (KES): {context['paid_amount']:.2f}\n"
            f"Balance (KES): {context['balance']:.2f}\n"
            f"Denial Code: {context['denial_code']}\n"
            f"Denial Reason: {context['denial_reason']}\n"
            f"Diagnosis Codes: {context['diagnosis_codes']}\n"
            f"Procedure Codes: {context['procedure_codes']}\n"
            f"Modifiers: {context['modifiers']}\n"
            f"Root Cause Analysis: {context['root_cause']}\n"
            f"Recommended Action: {context['recommended_action']}\n\n"
            f"Supporting Documents on File:\n{context['documents_summary']}\n\n"
            f"Verified Applicable References:\n{context['suggested_citations']}\n\n"
            f"Approved Source Excerpts:\n{context['policy_source_context']}\n"
        )

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
            "balance": float(claim.billed_amount) - float(claim.paid_amount),
            "service_date": claim.service_date,
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
            "verified_policy_sources": extra_context.get("verified_policy_sources") or [],
            "policy_source_context": "\n".join(
                (
                    f"{source['title']} ({source['reference']}), "
                    f"version {source['version']}:\n{source['excerpt']}"
                )
                for source in extra_context.get("verified_policy_sources") or []
            )
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
