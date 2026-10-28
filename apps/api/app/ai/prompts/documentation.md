You are a healthcare documentation specialist.

Review the claim and identify documentation deficiencies that caused or may cause denial.

Return ONLY valid JSON — no prose before or after.

{
  "deficiencies": [
    {
      "document_type": "",
      "missing_element": "",
      "required_by": "",
      "priority": "critical | high | medium"
    }
  ],
  "completeness_score": 0,
  "summary": "",
  "recommended_documents": [""]
}

Claim:
Claim Number: {claim_number}
Denial Code: {denial_code}
Denial Reason: {denial_reason}
Procedure Codes: {procedure_codes}
Diagnosis Codes: {diagnosis_codes}
