"""
Unit tests for the Recovery Engine.
Tests real engine behaviour — no mocks, no DB.
"""

from decimal import Decimal

import pytest

from app.recovery.engine import RecoveryEngine
from app.recovery.opportunities import Priority


@pytest.fixture
def engine():
    return RecoveryEngine()


class _Claim:
    """Minimal claim stub — only fields the engine reads."""

    def __init__(self, id, billed, paid):
        self.id = id
        self.billed_amount = Decimal(str(billed))
        self.paid_amount = Decimal(str(paid))


def test_no_opportunity_below_minimum_balance(engine):
    claim = _Claim(1, billed=20.00, paid=0.00)
    result = engine.analyze(claim, denial_probability=0.9, claim_age_days=10)
    assert result is None


def test_no_opportunity_when_claim_too_old(engine):
    claim = _Claim(1, billed=5000.00, paid=0.00)
    result = engine.analyze(claim, denial_probability=0.9, claim_age_days=400)
    assert result is None


def test_opportunity_created_for_qualifying_claim(engine):
    claim = _Claim(1, billed=2000.00, paid=500.00)
    result = engine.analyze(claim, denial_probability=0.8, claim_age_days=30)
    assert result is not None
    assert result.claim_id == 1
    assert result.score > 0
    assert result.estimated_recovery > 0
    assert result.balance == Decimal("1500.00")


def test_critical_priority_for_high_score_high_value(engine):
    claim = _Claim(1, billed=10000.00, paid=0.00)
    result = engine.analyze(claim, denial_probability=1.0, claim_age_days=0)
    assert result is not None
    assert result.priority == Priority.CRITICAL


def test_low_priority_for_low_score(engine):
    claim = _Claim(1, billed=100.00, paid=50.00)
    result = engine.analyze(claim, denial_probability=0.1, claim_age_days=5)
    assert result is not None
    assert result.priority == Priority.LOW


def test_estimated_recovery_is_fraction_of_balance(engine):
    claim = _Claim(1, billed=1000.00, paid=0.00)
    result = engine.analyze(claim, denial_probability=1.0, claim_age_days=0)
    assert result is not None
    assert result.estimated_recovery <= result.balance
