"""AI Analyzer orchestration utilities."""
from .denial_classifier import classify_denial
from .recovery_score import score_recovery


def analyze_claim(claim_text: str) -> dict:
    """Run classification and recovery scoring for a claim."""
    denial = classify_denial(claim_text)
    score = score_recovery(claim_text)

    return {
        "denial": denial,
        "recovery_score": score,
    }
