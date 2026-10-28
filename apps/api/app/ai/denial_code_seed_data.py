"""
Canonical seed data for Atlas' denial knowledge base (the `DenialCode`
table).

Kept as a plain, dependency-free list of dicts — `category` is the
`DenialType` enum *name* (a string), not an import of the enum class itself
— so this module can be safely imported both by the Alembic migration that
creates and seeds the `denial_codes` table and by `seed.py`'s demo data
script, without either of them depending on the live `app.models` package
at migration time.

This is intentionally a starter set covering the most common payer denial
reason codes (CARC codes) rather than an exhaustive list — it's designed to
be easy to extend as payer rules evolve, which is the whole point of
grounding AI reasoning in structured data instead of asking the model to
"remember" what each code means.

Each entry also carries the richer "mature knowledge base" fields
(severity/recoverability/typical_recovery_rate/required_documents/
typical_resolution_days/common_payers/references) — same rationale as
`ai_guidance`: plain, migration- and script-safe values, no enum/model
imports. `severity`/`recoverability` are the lowercase `.value` strings of
`DenialCodeSeverity`/`DenialCodeRecoverability` (`app.models.denial_code`),
not the enum names, since they're consumed directly as column values by
both the Alembic migration and the reseed script.
"""

DENIAL_CODE_SEED_DATA: list[dict] = [
    {
        "code": "CO16",
        "category": "DOCUMENTATION",
        "description": (
            "Claim/service lacks information or has a submission/billing "
            "error needed for adjudication (missing or incomplete "
            "documentation)."
        ),
        "recovery_strategy": (
            "Identify the specific missing item from the remark code, "
            "obtain and attach the required documentation, then resubmit "
            "or appeal."
        ),
        "ai_guidance": (
            "Treat this as highly recoverable when the missing item is a "
            "document (not a hard eligibility or filing-deadline issue) — "
            "weight recovery_probability higher if the claim age suggests "
            "there's still time to gather and resubmit documentation."
        ),
        "severity": "medium",
        "recoverability": "high",
        "typical_recovery_rate": 85.0,
        "required_documents": [
            "Medical records",
            "Physician notes",
            "Item identified as missing in the remark code",
        ],
        "typical_resolution_days": 15,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO18",
        "category": "DUPLICATE",
        "description": (
            "Exact duplicate claim or service — this claim/service was already adjudicated."
        ),
        "recovery_strategy": (
            "Verify the original claim's status. If this is not a true "
            "duplicate, appeal with the differentiating claim/service "
            "details (e.g. different date of service or modifier)."
        ),
        "ai_guidance": (
            "Recovery odds hinge entirely on whether this is a genuine "
            "duplicate or a misclassified distinct service — recommend "
            "verifying against the original claim number before assuming "
            "either outcome."
        ),
        "severity": "low",
        "recoverability": "medium",
        "typical_recovery_rate": 55.0,
        "required_documents": [
            "Original claim number",
            "Proof of distinct date of service or modifier",
        ],
        "typical_resolution_days": 20,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO29",
        "category": "TIMELY_FILING",
        "description": "The time limit for filing this claim has expired.",
        "recovery_strategy": (
            "Appeal immediately with proof of timely submission (e.g. "
            "clearinghouse acceptance report or original submission date)."
        ),
        "ai_guidance": (
            "This is one of the hardest denial types to overturn without "
            "documentary proof of timely submission — keep "
            "recovery_probability conservative unless the claim shows "
            "evidence of an earlier accepted submission attempt."
        ),
        "severity": "high",
        "recoverability": "low",
        "typical_recovery_rate": 25.0,
        "required_documents": [
            "Clearinghouse acceptance report",
            "Proof of original timely submission",
        ],
        "typical_resolution_days": 30,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO50",
        "category": "MEDICAL_NECESSITY",
        "description": (
            "These are non-covered services because this is not deemed a "
            "medical necessity by the payer."
        ),
        "recovery_strategy": (
            "Submit additional medical records, physician notes, and "
            "clinical justification supporting medical necessity."
        ),
        "ai_guidance": (
            "Recovery strongly depends on the strength of clinical "
            "documentation available — recommend attaching physician "
            "notes and diagnosis-to-procedure justification in the "
            "recommended_corrections."
        ),
        "severity": "high",
        "recoverability": "medium",
        "typical_recovery_rate": 45.0,
        "required_documents": [
            "Physician notes",
            "Clinical justification",
            "Diagnosis-to-procedure documentation",
        ],
        "typical_resolution_days": 30,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO97",
        "category": "CODING",
        "description": (
            "The benefit for this service is included in the "
            "payment/allowance for another service/procedure that has "
            "already been adjudicated (bundling)."
        ),
        "recovery_strategy": (
            "Review NCCI edits and modifier usage; correct coding or "
            "append the appropriate modifier (e.g. 59/XU) and resubmit."
        ),
        "ai_guidance": (
            "Usually a coding fix rather than a clinical appeal — favor "
            "recommending a modifier/coding correction over a lengthy "
            "appeal narrative."
        ),
        "severity": "low",
        "recoverability": "high",
        "typical_recovery_rate": 80.0,
        "required_documents": ["NCCI edit review", "Modifier documentation"],
        "typical_resolution_days": 10,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO4",
        "category": "MODIFIER_ERROR",
        "description": (
            "The procedure code is inconsistent with the modifier used, "
            "or a required modifier is missing."
        ),
        "recovery_strategy": (
            "Verify the correct modifier for the procedure and resubmit with corrected coding."
        ),
        "ai_guidance": (
            "High recovery probability — this is typically a simple "
            "coding correction, not a clinical dispute."
        ),
        "severity": "low",
        "recoverability": "high",
        "typical_recovery_rate": 90.0,
        "required_documents": ["Corrected modifier documentation"],
        "typical_resolution_days": 7,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO11",
        "category": "CODING",
        "description": "The diagnosis is inconsistent with the procedure billed.",
        "recovery_strategy": (
            "Confirm the diagnosis supports medical necessity for the "
            "procedure billed; correct and resubmit."
        ),
        "ai_guidance": (
            "Check whether the fix is a coding correction (higher "
            "recovery odds) or a genuine mismatch requiring new clinical "
            "documentation (lower recovery odds)."
        ),
        "severity": "medium",
        "recoverability": "medium",
        "typical_recovery_rate": 60.0,
        "required_documents": [
            "Corrected diagnosis coding",
            "Clinical documentation supporting medical necessity",
        ],
        "typical_resolution_days": 14,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO22",
        "category": "COORDINATION_OF_BENEFITS",
        "description": ("This care may be covered by another payer per coordination of benefits."),
        "recovery_strategy": (
            "Verify primary/secondary payer order, obtain the EOB from "
            "the primary payer, and resubmit to the correct payer."
        ),
        "ai_guidance": (
            "Recovery depends on administrative correction (payer order) "
            "rather than clinical appeal — recommend verifying COB status "
            "before anything else."
        ),
        "severity": "low",
        "recoverability": "high",
        "typical_recovery_rate": 75.0,
        "required_documents": [
            "Primary payer EOB",
            "Coordination of benefits verification",
        ],
        "typical_resolution_days": 14,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO27",
        "category": "ELIGIBILITY",
        "description": ("Expenses were incurred after the patient's coverage was terminated."),
        "recovery_strategy": (
            "Verify patient eligibility on the date of service; bill the "
            "patient or correct the payer if eligibility was actually "
            "active."
        ),
        "ai_guidance": (
            "Low recovery probability if eligibility truly lapsed — only "
            "raise it if there's a plausible eligibility-verification "
            "error to investigate."
        ),
        "severity": "high",
        "recoverability": "low",
        "typical_recovery_rate": 15.0,
        "required_documents": ["Eligibility verification records"],
        "typical_resolution_days": 20,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO31",
        "category": "ELIGIBILITY",
        "description": "Patient cannot be identified as our insured.",
        "recovery_strategy": (
            "Verify patient demographics and insurance ID; correct and resubmit."
        ),
        "ai_guidance": (
            "Usually a data-entry/matching issue with a good chance of "
            "recovery once demographics are corrected."
        ),
        "severity": "medium",
        "recoverability": "high",
        "typical_recovery_rate": 70.0,
        "required_documents": [
            "Corrected patient demographics",
            "Insurance ID verification",
        ],
        "typical_resolution_days": 10,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO45",
        "category": "CODING",
        "description": ("Charge exceeds the fee schedule/maximum allowable or contracted amount."),
        "recovery_strategy": (
            "Confirm the contracted rate; write off per contract, or "
            "appeal if the contracted rate was applied incorrectly."
        ),
        "ai_guidance": (
            "Low recovery probability in most cases — this is a "
            "contractual adjustment, not a clinical denial. Only flag as "
            "recoverable if the contracted rate itself appears misapplied."
        ),
        "severity": "low",
        "recoverability": "low",
        "typical_recovery_rate": 10.0,
        "required_documents": ["Contracted rate documentation"],
        "typical_resolution_days": 14,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO96",
        "category": "NON_COVERED_SERVICE",
        "description": "Non-covered charge(s) under the patient's plan.",
        "recovery_strategy": (
            "Confirm plan benefits; bill the patient if genuinely "
            "non-covered, or appeal with medical necessity documentation "
            "if coverage should apply."
        ),
        "ai_guidance": (
            "Recovery odds are moderate and depend entirely on whether "
            "the service is truly excluded by the plan or was "
            "miscategorized — recommend a benefits verification step."
        ),
        "severity": "medium",
        "recoverability": "medium",
        "typical_recovery_rate": 40.0,
        "required_documents": [
            "Plan benefits verification",
            "Medical necessity documentation",
        ],
        "typical_resolution_days": 21,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO109",
        "category": "ELIGIBILITY",
        "description": (
            "Claim/service not covered by this payer/contractor — "
            "patient not enrolled with this payer."
        ),
        "recovery_strategy": (
            "Verify the correct payer for the date of service and "
            "resubmit to the appropriate carrier."
        ),
        "ai_guidance": (
            "High recovery probability once resubmitted to the correct "
            "payer — this is a routing error, not a coverage dispute."
        ),
        "severity": "low",
        "recoverability": "high",
        "typical_recovery_rate": 85.0,
        "required_documents": ["Correct payer verification"],
        "typical_resolution_days": 10,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO151",
        "category": "PRIOR_AUTH",
        "description": (
            "Payment adjusted because the payer deems the information "
            "submitted does not support this many/frequency of services "
            "— commonly used interchangeably with a missing-authorization "
            "denial by many payers."
        ),
        "recovery_strategy": (
            "Attach the prior authorization number/documentation and "
            "clinical notes justifying the frequency of services, then "
            "resubmit or appeal."
        ),
        "ai_guidance": (
            "Recovery odds are good when a valid authorization already "
            "exists and simply wasn't attached/matched — much lower if "
            "authorization was genuinely never obtained."
        ),
        "severity": "high",
        "recoverability": "medium",
        "typical_recovery_rate": 50.0,
        "required_documents": [
            "Prior authorization number",
            "Clinical notes justifying frequency",
        ],
        "typical_resolution_days": 21,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "CO197",
        "category": "PRIOR_AUTH",
        "description": "Precertification, authorization, or notification is absent.",
        "recovery_strategy": (
            "Obtain retroactive authorization if the payer allows it, or "
            "appeal with proof authorization was obtained or not "
            "required."
        ),
        "ai_guidance": (
            "Recovery odds are good when a valid authorization already "
            "exists and simply wasn't attached/matched — much lower if "
            "authorization was genuinely never obtained."
        ),
        "severity": "high",
        "recoverability": "medium",
        "typical_recovery_rate": 50.0,
        "required_documents": [
            "Prior authorization documentation",
            "Proof authorization was obtained or not required",
        ],
        "typical_resolution_days": 21,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "PR1",
        "category": "OTHER",
        "description": "Patient responsibility — deductible amount.",
        "recovery_strategy": (
            "Bill the patient for the deductible amount per plan terms; "
            "verify the deductible accumulator with the payer if "
            "disputed."
        ),
        "ai_guidance": (
            "Not payer-recoverable in the normal sense — this is patient "
            "responsibility. recovery_probability should reflect "
            "likelihood of patient payment, not payer appeal success."
        ),
        "severity": "low",
        "recoverability": "low",
        "typical_recovery_rate": 60.0,
        "required_documents": ["Deductible accumulator statement"],
        "typical_resolution_days": 30,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
    {
        "code": "PR2",
        "category": "OTHER",
        "description": "Patient responsibility — coinsurance amount.",
        "recovery_strategy": "Bill the patient for the coinsurance amount per plan terms.",
        "ai_guidance": (
            "Not payer-recoverable in the normal sense — this is patient "
            "responsibility. recovery_probability should reflect "
            "likelihood of patient payment, not payer appeal success."
        ),
        "severity": "low",
        "recoverability": "low",
        "typical_recovery_rate": 60.0,
        "required_documents": ["Coinsurance statement"],
        "typical_resolution_days": 30,
        "common_payers": [],
        "references": ["X12 Claim Adjustment Reason Code (CARC) official code list"],
    },
]
