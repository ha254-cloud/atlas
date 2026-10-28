from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.models.document import DocumentType


@dataclass(frozen=True)
class DocumentAcceptancePolicy:
    minimum_classification_samples: int
    minimum_ocr_samples: int
    minimum_classification_accuracy: float
    minimum_ocr_word_accuracy: float
    minimum_ocr_success_rate: float

    def __post_init__(self) -> None:
        if self.minimum_classification_samples < 1 or self.minimum_ocr_samples < 1:
            raise ValueError("Acceptance sample minimums must be greater than zero")
        for value in (
            self.minimum_classification_accuracy,
            self.minimum_ocr_word_accuracy,
            self.minimum_ocr_success_rate,
        ):
            if not 0 <= value <= 1:
                raise ValueError("Acceptance thresholds must be between zero and one")


@dataclass(frozen=True)
class ClassificationObservation:
    expected: DocumentType
    predicted: DocumentType


@dataclass(frozen=True)
class OCRObservation:
    expected_text: str
    extracted_text: str | None
    extraction_status: str


@dataclass(frozen=True)
class DocumentAcceptanceResult:
    classification_samples: int
    ocr_samples: int
    classification_accuracy: float
    ocr_word_accuracy: float
    ocr_success_rate: float
    passed: bool
    failures: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "classification_samples": self.classification_samples,
            "ocr_samples": self.ocr_samples,
            "classification_accuracy": self.classification_accuracy,
            "ocr_word_accuracy": self.ocr_word_accuracy,
            "ocr_success_rate": self.ocr_success_rate,
            "passed": self.passed,
            "failures": list(self.failures),
        }


def evaluate_acceptance_manifest(manifest: dict[str, Any]) -> DocumentAcceptanceResult:
    try:
        policy_data = manifest["policy"]
        classifications_data = manifest["classifications"]
        ocr_data = manifest["ocr_observations"]
        policy = DocumentAcceptancePolicy(
            minimum_classification_samples=int(policy_data["minimum_classification_samples"]),
            minimum_ocr_samples=int(policy_data["minimum_ocr_samples"]),
            minimum_classification_accuracy=float(policy_data["minimum_classification_accuracy"]),
            minimum_ocr_word_accuracy=float(policy_data["minimum_ocr_word_accuracy"]),
            minimum_ocr_success_rate=float(policy_data["minimum_ocr_success_rate"]),
        )
        classifications = [
            ClassificationObservation(
                expected=DocumentType(item["expected"]),
                predicted=DocumentType(item["predicted"]),
            )
            for item in classifications_data
        ]
        ocr_observations = [
            OCRObservation(
                expected_text=item["expected_text"],
                extracted_text=item.get("extracted_text"),
                extraction_status=item["extraction_status"],
            )
            for item in ocr_data
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid document acceptance manifest: {exc}") from exc
    if not isinstance(policy_data, dict):
        raise ValueError("Invalid document acceptance manifest: policy must be an object")
    if not isinstance(classifications_data, list) or not isinstance(ocr_data, list):
        raise ValueError("Invalid document acceptance manifest: observations must be arrays")
    return evaluate_document_acceptance(
        classifications=classifications,
        ocr_observations=ocr_observations,
        policy=policy,
    )


def evaluate_document_acceptance(
    *,
    classifications: list[ClassificationObservation],
    ocr_observations: list[OCRObservation],
    policy: DocumentAcceptancePolicy,
) -> DocumentAcceptanceResult:
    classification_accuracy = _classification_accuracy(classifications)
    ocr_word_accuracy = _mean_ocr_word_accuracy(ocr_observations)
    ocr_success_rate = _ocr_success_rate(ocr_observations)
    failures: list[str] = []

    _require_minimum(
        failures,
        "classification samples",
        len(classifications),
        policy.minimum_classification_samples,
    )
    _require_minimum(
        failures,
        "OCR samples",
        len(ocr_observations),
        policy.minimum_ocr_samples,
    )
    _require_threshold(
        failures,
        "classification accuracy",
        classification_accuracy,
        policy.minimum_classification_accuracy,
    )
    _require_threshold(
        failures,
        "OCR word accuracy",
        ocr_word_accuracy,
        policy.minimum_ocr_word_accuracy,
    )
    _require_threshold(
        failures,
        "OCR success rate",
        ocr_success_rate,
        policy.minimum_ocr_success_rate,
    )
    return DocumentAcceptanceResult(
        classification_samples=len(classifications),
        ocr_samples=len(ocr_observations),
        classification_accuracy=classification_accuracy,
        ocr_word_accuracy=ocr_word_accuracy,
        ocr_success_rate=ocr_success_rate,
        passed=not failures,
        failures=tuple(failures),
    )


def word_accuracy(expected_text: str, extracted_text: str | None) -> float:
    expected = _tokens(expected_text)
    if not expected:
        raise ValueError("OCR ground truth must contain at least one word")
    observed = _tokens(extracted_text or "")
    distance = _edit_distance(expected, observed)
    return round(max(0.0, 1 - distance / len(expected)), 4)


def _classification_accuracy(observations: list[ClassificationObservation]) -> float:
    if not observations:
        return 0.0
    correct = sum(item.expected == item.predicted for item in observations)
    return round(correct / len(observations), 4)


def _mean_ocr_word_accuracy(observations: list[OCRObservation]) -> float:
    if not observations:
        return 0.0
    scores = [word_accuracy(item.expected_text, item.extracted_text) for item in observations]
    return round(sum(scores) / len(scores), 4)


def _ocr_success_rate(observations: list[OCRObservation]) -> float:
    if not observations:
        return 0.0
    succeeded = sum(
        item.extraction_status == "succeeded" and bool(_tokens(item.extracted_text or ""))
        for item in observations
    )
    return round(succeeded / len(observations), 4)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold())


def _edit_distance(expected: list[str], observed: list[str]) -> int:
    previous = list(range(len(observed) + 1))
    for expected_index, expected_word in enumerate(expected, start=1):
        current = [expected_index]
        for observed_index, observed_word in enumerate(observed, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[observed_index] + 1,
                    previous[observed_index - 1] + (expected_word != observed_word),
                )
            )
        previous = current
    return previous[-1]


def _require_minimum(failures: list[str], label: str, observed: int, required: int) -> None:
    if observed < required:
        failures.append(f"{label} {observed} is below required minimum {required}")


def _require_threshold(failures: list[str], label: str, observed: float, required: float) -> None:
    if observed < required:
        failures.append(f"{label} {observed:.4f} is below required threshold {required:.4f}")
