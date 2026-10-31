import pytest

from app.appeals.evaluation import REQUIRED_SECTIONS, evaluate_appeal_manifest


def output(**overrides):
    data = {
        "appeal_letter": (
            "Appeal for claim SYN-KE-001 concerning SYNTHETIC-PATIENT and denial PA-01."
        ),
        "sections": {section: f"Reviewed {section}" for section in REQUIRED_SECTIONS},
        "citations": [
            {
                "source": "Reviewed SHA Guidance",
                "reference": "Circular 2, section 1",
            }
        ],
        "missing_information": ["authorization number"],
        "requested_action": "Please reconsider and reprocess the claim.",
    }
    data.update(overrides)
    return data


def test_evaluation_passes_safe_synthetic_case():
    result = evaluate_appeal_manifest(
        {
            "cases": [
                {
                    "case_id": "synthetic-prior-auth-1",
                    "data_classification": "synthetic",
                    "expected": {
                        "claim_number": "SYN-KE-001",
                        "patient_identifier": "SYNTHETIC-PATIENT",
                        "denial_code": "PA-01",
                        "evidence_gaps": ["authorization number"],
                    },
                    "verified_citations": [
                        {
                            "source": "Reviewed SHA Guidance",
                            "reference": "Circular 2, section 1",
                        }
                    ],
                    "output": output(),
                }
            ]
        }
    )

    assert result.passed is True
    assert result.metrics["unsupported_citation_rate"] == 0
    assert "not clinical accuracy" in result.limitation


def test_evaluation_fails_invented_reference_and_missing_identity():
    result = evaluate_appeal_manifest(
        {
            "cases": [
                {
                    "case_id": "synthetic-failure",
                    "data_classification": "synthetic",
                    "expected": {
                        "claim_number": "SYN-KE-001",
                        "patient_identifier": "SYNTHETIC-PATIENT",
                        "denial_code": "PA-01",
                        "evidence_gaps": ["authorization number"],
                    },
                    "verified_citations": [],
                    "output": output(
                        appeal_letter="Generic appeal with no claim identity.",
                        citations=[{"source": "Invented manual", "reference": "Section 99"}],
                    ),
                }
            ]
        }
    )

    assert result.passed is False
    assert result.metrics["unsupported_citation_rate"] == 1
    assert result.metrics["claim_fidelity_rate"] == 0


def test_evaluation_rejects_unclassified_case():
    with pytest.raises(ValueError, match="synthetic or deidentified"):
        evaluate_appeal_manifest(
            {
                "cases": [
                    {
                        "case_id": "unsafe",
                        "expected": {},
                        "output": output(),
                    }
                ]
            }
        )
