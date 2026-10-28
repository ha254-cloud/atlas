import json
import sys

import pytest

from app.documents.acceptance import (
    ClassificationObservation,
    DocumentAcceptancePolicy,
    OCRObservation,
    evaluate_acceptance_manifest,
    evaluate_document_acceptance,
    word_accuracy,
)
from app.models.document import DocumentType
from scripts.evaluate_document_acceptance import main


def _policy() -> DocumentAcceptancePolicy:
    return DocumentAcceptancePolicy(
        minimum_classification_samples=3,
        minimum_ocr_samples=2,
        minimum_classification_accuracy=0.90,
        minimum_ocr_word_accuracy=0.80,
        minimum_ocr_success_rate=0.95,
    )


def test_acceptance_passes_when_all_corpus_thresholds_are_met():
    result = evaluate_document_acceptance(
        classifications=[
            ClassificationObservation(DocumentType.IMAGING, DocumentType.IMAGING),
            ClassificationObservation(DocumentType.AUTHORIZATION, DocumentType.AUTHORIZATION),
            ClassificationObservation(DocumentType.LAB_RESULTS, DocumentType.LAB_RESULTS),
        ],
        ocr_observations=[
            OCRObservation(
                "Member authorization approved", "Member authorization approved", "succeeded"
            ),
            OCRObservation("Discharge date 14 August", "Discharge date 14 August", "succeeded"),
        ],
        policy=_policy(),
    )

    assert result.passed is True
    assert result.classification_accuracy == 1.0
    assert result.ocr_word_accuracy == 1.0
    assert result.ocr_success_rate == 1.0
    assert result.failures == ()


def test_acceptance_reports_each_failed_gate():
    result = evaluate_document_acceptance(
        classifications=[
            ClassificationObservation(DocumentType.IMAGING, DocumentType.OTHER),
        ],
        ocr_observations=[
            OCRObservation("Member authorization approved", None, "failed"),
        ],
        policy=_policy(),
    )

    assert result.passed is False
    assert result.classification_accuracy == 0.0
    assert result.ocr_word_accuracy == 0.0
    assert result.ocr_success_rate == 0.0
    assert len(result.failures) == 5


def test_word_accuracy_is_case_and_punctuation_insensitive():
    assert word_accuracy("Claim No: CLM-123, approved.", "claim no clm 123 approved") == 1.0


def test_word_accuracy_rejects_empty_ground_truth():
    with pytest.raises(ValueError, match="ground truth"):
        word_accuracy("", "observed text")


def test_manifest_evaluation_returns_aggregate_evidence_only():
    result = evaluate_acceptance_manifest(
        {
            "policy": {
                "minimum_classification_samples": 1,
                "minimum_ocr_samples": 1,
                "minimum_classification_accuracy": 1.0,
                "minimum_ocr_word_accuracy": 1.0,
                "minimum_ocr_success_rate": 1.0,
            },
            "classifications": [{"expected": "imaging", "predicted": "imaging"}],
            "ocr_observations": [
                {
                    "expected_text": "Authorization approved",
                    "extracted_text": "Authorization approved",
                    "extraction_status": "succeeded",
                }
            ],
        }
    )

    assert result.as_dict() == {
        "classification_samples": 1,
        "ocr_samples": 1,
        "classification_accuracy": 1.0,
        "ocr_word_accuracy": 1.0,
        "ocr_success_rate": 1.0,
        "passed": True,
        "failures": [],
    }


def test_manifest_rejects_unknown_document_type():
    with pytest.raises(ValueError, match="Invalid document acceptance manifest"):
        evaluate_acceptance_manifest(
            {
                "policy": {
                    "minimum_classification_samples": 1,
                    "minimum_ocr_samples": 1,
                    "minimum_classification_accuracy": 1.0,
                    "minimum_ocr_word_accuracy": 1.0,
                    "minimum_ocr_success_rate": 1.0,
                },
                "classifications": [{"expected": "unknown", "predicted": "imaging"}],
                "ocr_observations": [],
            }
        )


def test_cli_returns_success_and_does_not_print_document_text(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "acceptance.json"
    sensitive_marker = "deidentified-sensitive-marker"
    manifest.write_text(
        json.dumps(
            {
                "policy": {
                    "minimum_classification_samples": 1,
                    "minimum_ocr_samples": 1,
                    "minimum_classification_accuracy": 1.0,
                    "minimum_ocr_word_accuracy": 1.0,
                    "minimum_ocr_success_rate": 1.0,
                },
                "classifications": [{"expected": "imaging", "predicted": "imaging"}],
                "ocr_observations": [
                    {
                        "expected_text": sensitive_marker,
                        "extracted_text": sensitive_marker,
                        "extraction_status": "succeeded",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["evaluate_document_acceptance", str(manifest)])

    assert main() == 0
    output = capsys.readouterr().out
    assert '"passed": true' in output
    assert sensitive_marker not in output


def test_cli_returns_failure_when_thresholds_are_not_met(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "acceptance.json"
    manifest.write_text(
        json.dumps(
            {
                "policy": {
                    "minimum_classification_samples": 1,
                    "minimum_ocr_samples": 1,
                    "minimum_classification_accuracy": 1.0,
                    "minimum_ocr_word_accuracy": 1.0,
                    "minimum_ocr_success_rate": 1.0,
                },
                "classifications": [{"expected": "imaging", "predicted": "other"}],
                "ocr_observations": [
                    {
                        "expected_text": "expected words",
                        "extracted_text": None,
                        "extraction_status": "failed",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["evaluate_document_acceptance", str(manifest)])

    assert main() == 1
    assert '"passed": false' in capsys.readouterr().out
