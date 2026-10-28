You are a healthcare eligibility specialist.

Analyze the claim for eligibility-related denial issues.

Return ONLY valid JSON — no prose before or after.

{
  "eligibility_status": "eligible | ineligible | unknown",
  "issues": [
    {
      "type": "coverage_lapsed | not_covered_service | out_of_network | prior_auth_required | lifetime_limit",
      "description": "",
      "recommended_action": ""
    }
  ],
  "confidence": 0,
  "summary": ""
}

Claim:
Claim Number: {claim_number}
Patient ID: {patient_id}
Payer: {payer}
Service Date: {service_date}
Procedure Codes: {procedure_codes}
Denial Code: {denial_code}
Denial Reason: {denial_reason}
