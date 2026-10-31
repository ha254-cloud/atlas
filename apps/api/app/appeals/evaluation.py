"""Deterministic, PHI-safe appeal draft acceptance evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass

REQUIRED_SECTIONS = (
    "introduction",
    "medical_necessity",
    "coding_justification",
    "policy_references",
    "supporting_documents",
    "requested_action",
    "signature",
)


@dataclass(frozen=True)
class EvaluationThresholds:
    claim_fidelity_rate: float = 1.0
    patient_fidelity_rate: float = 1.0
    denial_fidelity_rate: float = 1.0
    unsupported_citation_rate: float = 0.0
    required_section_rate: float = 1.0
    evidence_gap_disclosure_rate: float = 0.9
    requested_action_rate: float = 1.0


@dataclass(frozen=True)
class AppealCaseResult:
    case_id: str
    claim_fidelity: bool
    patient_fidelity: bool
    denial_fidelity: bool
    unsupported_citation_count: int
    citation_count: int
    required_sections_present: int
    required_sections_total: int
    evidence_gaps_disclosed: int
    evidence_gaps_total: int
    requested_action_present: bool


@dataclass(frozen=True)
class AppealEvaluationResult:
    passed: bool
    case_count: int
    metrics: dict[str, float]
    thresholds: EvaluationThresholds
    cases: list[AppealCaseResult]
    limitation: str = (
        "This benchmark measures deterministic safety and fidelity checks, not clinical "
        "accuracy. Expert-reviewed Kenyan pilot cases and outcome monitoring are still required."
    )

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "case_count": self.case_count,
            "metrics": self.metrics,
            "thresholds": asdict(self.thresholds),
            "cases": [asdict(case) for case in self.cases],
            "limitation": self.limitation,
        }


def _contains(text: str, expected: str) -> bool:
    return expected.strip().casefold() in text.casefold()


def _rate(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _evaluate_case(case: dict) -> AppealCaseResult:
    if case.get("data_classification") not in {"synthetic", "deidentified"}:
        raise ValueError(
            f"Case {case.get('case_id', '<unknown>')} must be marked synthetic or deidentified"
        )
    output = case.get("output")
    expected = case.get("expected")
    if not isinstance(output, dict) or not isinstance(expected, dict):
        raise ValueError("Each evaluation case requires expected and output objects")
    for field in ("claim_number", "patient_identifier", "denial_code"):
        if not str(expected.get(field) or "").strip():
            raise ValueError(f"Case {case.get('case_id', '<unknown>')} requires expected.{field}")

    sections = output.get("sections") or {}
    text = "\n".join(
        [
            str(output.get("appeal_letter") or ""),
            *(str(value) for value in sections.values()),
        ]
    )
    verified_keys = {
        (
            str(item.get("source", "")).strip().casefold(),
            str(item.get("reference", "")).strip().casefold(),
        )
        for item in case.get("verified_citations") or []
        if isinstance(item, dict)
    }
    proposed = [item for item in output.get("citations") or [] if isinstance(item, dict)]
    unsupported = [
        item
        for item in proposed
        if (
            str(item.get("source", "")).strip().casefold(),
            str(item.get("reference", "")).strip().casefold(),
        )
        not in verified_keys
    ]
    gaps = [str(item) for item in expected.get("evidence_gaps") or []]
    disclosed = "\n".join(str(item) for item in output.get("missing_information") or [])
    requested_action = str(
        output.get("requested_action") or sections.get("requested_action") or ""
    ).strip()

    return AppealCaseResult(
        case_id=str(case.get("case_id") or ""),
        claim_fidelity=_contains(text, str(expected.get("claim_number") or "")),
        patient_fidelity=_contains(text, str(expected.get("patient_identifier") or "")),
        denial_fidelity=_contains(text, str(expected.get("denial_code") or "")),
        unsupported_citation_count=len(unsupported),
        citation_count=len(proposed),
        required_sections_present=sum(
            bool(str(sections.get(section) or "").strip()) for section in REQUIRED_SECTIONS
        ),
        required_sections_total=len(REQUIRED_SECTIONS),
        evidence_gaps_disclosed=sum(_contains(disclosed, gap) for gap in gaps),
        evidence_gaps_total=len(gaps),
        requested_action_present=bool(requested_action),
    )


def evaluate_appeal_manifest(
    manifest: dict,
    thresholds: EvaluationThresholds | None = None,
) -> AppealEvaluationResult:
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation manifest must contain at least one case")
    thresholds = thresholds or EvaluationThresholds()
    results = [_evaluate_case(case) for case in cases]
    case_count = len(results)
    citation_count = sum(case.citation_count for case in results)

    metrics = {
        "claim_fidelity_rate": _rate(sum(case.claim_fidelity for case in results), case_count),
        "patient_fidelity_rate": _rate(sum(case.patient_fidelity for case in results), case_count),
        "denial_fidelity_rate": _rate(sum(case.denial_fidelity for case in results), case_count),
        "unsupported_citation_rate": _rate(
            sum(case.unsupported_citation_count for case in results),
            citation_count,
        ),
        "required_section_rate": _rate(
            sum(case.required_sections_present for case in results),
            sum(case.required_sections_total for case in results),
        ),
        "evidence_gap_disclosure_rate": _rate(
            sum(case.evidence_gaps_disclosed for case in results),
            sum(case.evidence_gaps_total for case in results),
        ),
        "requested_action_rate": _rate(
            sum(case.requested_action_present for case in results),
            case_count,
        ),
    }
    expected = asdict(thresholds)
    passed = all(
        value <= expected[name]
        if name == "unsupported_citation_rate"
        else value >= expected[name]
        for name, value in metrics.items()
    )
    return AppealEvaluationResult(
        passed=passed,
        case_count=case_count,
        metrics=metrics,
        thresholds=thresholds,
        cases=results,
    )
