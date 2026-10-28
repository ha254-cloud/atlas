"""
Appeal Generator — uses the AI Gateway + prompt library to produce
a structured draft appeal for a denied or underpaid claim.

The human always reviews before submission. Atlas accelerates the workflow;
it does not replace clinical judgment.
"""

from app.ai.gateway import gateway
from app.ai.prompt_loader import load_prompt
from app.appeals.validator import parse_ai_response, validate_appeal


class AppealGenerator:
    async def generate(
        self, claim, denial=None, analysis=None, organization=None, extra_context=None
    ) -> dict:
        """
        Generate a structured appeal draft.
        Returns a validated dict with appeal_letter, summary, citations, etc.
        `analysis`, if provided, is a ClaimAnalysis row — its root_cause/
        recommended_action/ai_summary are folded into the prompt so the
        appeal reasons about the AI's actual findings, not just raw claim data.
        `organization`, if provided, is the Organization (hospital/practice)
        the letter is being sent on behalf of.
        `extra_context`, if provided, is a dict that may contain
        `documents_summary` (str) and `suggested_citations` (list[str]) —
        richer evidence/citation grounding built by AppealService.
        """
        prompt = self._build_prompt(claim, denial, analysis, organization, extra_context)
        system = load_prompt("appeal")

        raw = await gateway.generate(task="appeal", prompt=prompt, system=system)

        data = parse_ai_response(raw)
        validate_appeal(
            data,
            claim.claim_number,
            denial_code=denial.denial_code if denial else None,
            patient_last_name=claim.patient.last_name if claim.patient else None,
        )

        return data

    def _build_prompt(
        self, claim, denial, analysis=None, organization=None, extra_context=None
    ) -> str:
        denial_code = denial.denial_code if denial else "N/A"
        denial_reason = denial.description if denial else "Not specified"
        diagnosis_codes = ", ".join(d.icd_code for d in claim.diagnoses) or "None on file"
        procedure_codes = ", ".join(line.cpt_code for line in claim.claim_lines) or "None on file"
        patient_name = (
            f"{claim.patient.first_name} {claim.patient.last_name}" if claim.patient else "Unknown"
        )
        payer_name = claim.payer.name if claim.payer else f"(payer_id={claim.payer_id})"
        hospital_name = organization.name if organization else "the provider organization"

        prompt = (
            f"Hospital/Provider: {hospital_name}\n"
            f"Patient Name: {patient_name}\n"
            f"Claim Number: {claim.claim_number}\n"
            f"Payer: {payer_name}\n"
            f"Service Date: {claim.service_date}\n"
            f"Billed Amount (KES): {claim.billed_amount}\n"
            f"Paid Amount (KES): {claim.paid_amount}\n"
            f"Balance (KES): {float(claim.billed_amount) - float(claim.paid_amount):.2f}\n"
            f"Denial Code: {denial_code}\n"
            f"Denial Reason: {denial_reason}\n"
            f"Diagnosis Codes: {diagnosis_codes}\n"
            f"Procedure Codes: {procedure_codes}\n"
        )

        if analysis is not None:
            prompt += (
                f"AI Root Cause Analysis: {analysis.root_cause}\n"
                f"AI Recommended Action: {analysis.recommended_action or 'N/A'}\n"
                f"AI Summary: {analysis.ai_summary or 'N/A'}\n"
            )

        if extra_context:
            if extra_context.get("documents_summary"):
                prompt += f"\nSupporting Documents on File:\n{extra_context['documents_summary']}\n"
            if extra_context.get("suggested_citations"):
                prompt += (
                    "\nVerified Applicable References (cite only if relevant):\n"
                    + "\n".join(f"- {c}" for c in extra_context["suggested_citations"])
                    + "\n"
                )

        prompt += (
            "\nCitation guard: Use only references explicitly listed under Verified Applicable "
            "References. If none are listed, return an empty citations list and do not claim "
            "that any payer policy, portal rule, CMS, LCD, NCD, CPT, or HCPCS source applies.\n"
        )

        return prompt
