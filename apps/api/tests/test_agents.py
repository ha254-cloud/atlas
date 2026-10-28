"""
Tests for Atlas' Multi-Agent Intelligence layer (Sprint 4): the six
specialist agents, the AgentRegistry, and the AgentOrchestrator's
conflict-resolution logic. Individual agents are tested in isolation
(stub AI engines / monkeypatched gateway calls, no real network calls),
matching the existing ClaimAnalyzer test conventions. A lighter
end-to-end test exercises the orchestrator itself against a real
(SQLite) database using fake agents, to verify phasing, persistence,
and execution logging without depending on real LLM output.
"""

import asyncio
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 — registers every model on Base.metadata
from app.db.database import Base
from app.models.agent_execution import AgentExecutionLog
from app.models.claim import Claim, ClaimPriority
from app.models.claim_analysis import ClaimAnalysis
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer

# ---------------------------------------------------------------------------
# Shared fixtures / factories
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def make_claim(db_session, *, billed=Decimal("1000.00"), paid=Decimal("0.00"), service_date=None):
    org = Organization(name="Test Health System", email="ops@test-health.example")
    db_session.add(org)
    db_session.flush()

    patient = Patient(
        organization_id=org.id, first_name="Jane", last_name="Doe",
        medical_record_number="MRN-1", date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(organization_id=org.id, name="Acme Insurance", payer_code="ACME")
    db_session.add_all([patient, payer])
    db_session.flush()

    claim = Claim(
        organization_id=org.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-1",
        status="denied",
        billed_amount=billed,
        paid_amount=paid,
        service_date=service_date or date.today() - timedelta(days=10),
        priority=ClaimPriority.MEDIUM,
    )
    db_session.add(claim)
    db_session.commit()
    return org, claim


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# CodingAgent
# ---------------------------------------------------------------------------

class TestCodingAgent:
    def test_normalizes_a_valid_response(self, db_session, monkeypatch):
        import app.agents.coding.agent as coding_module
        from app.agents.coding.agent import CodingAgent

        async def fake_generate_json(*, task, prompt, system=None):
            return {
                "issues": [{"code": "M1", "type": "missing_modifier", "description": "x", "recommended_fix": "Add 25"}],
                "confidence": 150,  # out of range on purpose
                "summary": "Needs a modifier.",
                "resubmit_recommended": True,
            }

        monkeypatch.setattr(coding_module.gateway, "generate_json", fake_generate_json)

        org, claim = make_claim(db_session)
        context = _fake_context(claim, org)

        result = run(CodingAgent().run(context))

        assert result.status == "succeeded"
        assert result.output["confidence"] == 100.0  # clamped
        assert result.output["resubmit_recommended"] is True
        assert result.output["issues"][0]["code"] == "M1"

    def test_falls_back_when_gateway_raises(self, db_session, monkeypatch):
        import app.agents.coding.agent as coding_module
        from app.agents.coding.agent import CodingAgent

        async def broken_generate_json(*, task, prompt, system=None):
            raise RuntimeError("provider down")

        monkeypatch.setattr(coding_module.gateway, "generate_json", broken_generate_json)

        org, claim = make_claim(db_session)
        context = _fake_context(claim, org)

        result = run(CodingAgent().run(context))

        assert result.status == "failed"
        assert result.output["confidence"] == 0
        assert result.output["resubmit_recommended"] is False


# ---------------------------------------------------------------------------
# DocumentationAgent
# ---------------------------------------------------------------------------

class TestDocumentationAgent:
    def test_reports_complete_when_no_requirements(self, db_session):
        from app.agents.documentation.agent import DocumentationAgent

        org, claim = make_claim(db_session)
        context = _fake_context(claim, org, denial_code_info=None, documents=[])

        result = run(DocumentationAgent().run(context))

        assert result.status == "succeeded"
        assert result.output["completeness_score"] == 100.0
        assert result.output["is_complete"] is True

    def test_flags_missing_documents_when_required(self, db_session):
        from app.agents.documentation.agent import DocumentationAgent

        org, claim = make_claim(db_session)
        denial_code_info = {"required_documents": ["Operative report", "Referral"]}
        context = _fake_context(claim, org, denial_code_info=denial_code_info, documents=[])

        result = run(DocumentationAgent().run(context))

        assert result.status == "succeeded"
        assert result.output["is_complete"] is False
        assert result.output["completeness_score"] < 100.0


# ---------------------------------------------------------------------------
# ComplianceAgent
# ---------------------------------------------------------------------------

class TestComplianceAgent:
    def test_flags_timely_filing_as_blocking(self, db_session):
        from app.agents.compliance.agent import ComplianceAgent

        org, claim = make_claim(db_session, service_date=date.today() - timedelta(days=400))
        context = _fake_context(claim, org, denial=None)

        result = run(ComplianceAgent().run(context))

        assert result.status == "succeeded"
        assert result.output["timely_filing_ok"] is False
        assert result.output["blocking"] is True

    def test_no_issues_when_within_filing_window(self, db_session):
        from app.agents.compliance.agent import ComplianceAgent

        org, claim = make_claim(db_session, service_date=date.today() - timedelta(days=10))
        context = _fake_context(claim, org, denial=None)

        result = run(ComplianceAgent().run(context))

        assert result.status == "succeeded"
        assert result.output["blocking"] is False

    def test_skips_eligibility_check_when_no_denial(self, db_session):
        from app.agents.compliance.agent import ComplianceAgent

        org, claim = make_claim(db_session)
        context = _fake_context(claim, org, denial=None)

        result = run(ComplianceAgent().run(context))

        assert result.output["eligibility"] is None


# ---------------------------------------------------------------------------
# RiskAgent
# ---------------------------------------------------------------------------

class StubAIEngine:
    def __init__(self, response: dict):
        self._response = response

    async def generate_json(self, prompt, system=None):
        return self._response


class TestRiskAgent:
    def test_computes_risk_score_and_priority(self, db_session):
        from app.agents.risk.agent import RiskAgent

        engine = StubAIEngine({
            "denial_cause": "missing_modifier", "confidence": 0.9,
            "recovery_probability": 0.8, "explanation": "x",
            "recommended_corrections": ["Add modifier 25"],
        })
        org, claim = make_claim(db_session, billed=Decimal("1000.00"), paid=Decimal("0.00"))
        context = _fake_context(claim, org)

        result = run(RiskAgent(ai_engine=engine).run(context))

        assert result.status == "succeeded"
        assert result.output["recovery_probability_pct"] == 80.0
        assert result.output["risk_score"] == 20.0
        assert result.output["expected_recovery"] == 800.0
        assert result.output["priority"] in ("low", "medium", "high", "critical")
        assert result.output["estimated_effort"] == "low"

    def test_falls_back_on_analyzer_failure(self, db_session):
        from app.agents.risk.agent import RiskAgent

        class BrokenEngine:
            async def generate_json(self, prompt, system=None):
                raise RuntimeError("boom")

        org, claim = make_claim(db_session)
        context = _fake_context(claim, org)

        result = run(RiskAgent(ai_engine=BrokenEngine()).run(context))

        assert result.status == "failed"
        assert result.output["priority"] == "low"


# ---------------------------------------------------------------------------
# RecoveryAgent
# ---------------------------------------------------------------------------

class TestRecoveryAgent:
    def test_write_off_when_compliance_blocking(self, db_session):
        from app.agents.recovery.agent import RecoveryAgent

        org, claim = make_claim(db_session, billed=Decimal("2000.00"))
        context = _fake_context(claim, org)
        context.agent_outputs["risk"] = {"recovery_probability_pct": 90.0}
        context.agent_outputs["compliance"] = {"blocking": True}

        result = run(RecoveryAgent().run(context))

        assert result.output["recommended_action"] == "write_off"

    def test_recommends_appeal_when_high_probability_and_no_blockers(self, db_session):
        from app.agents.recovery.agent import RecoveryAgent

        org, claim = make_claim(db_session, billed=Decimal("2000.00"), paid=Decimal("0.00"))
        context = _fake_context(claim, org)
        context.agent_outputs["risk"] = {"recovery_probability_pct": 80.0}
        context.agent_outputs["compliance"] = {"blocking": False}

        result = run(RecoveryAgent().run(context))

        assert result.output["recommended_action"] == "appeal"

    def test_recommends_medical_review_for_moderate_probability(self, db_session):
        from app.agents.recovery.agent import RecoveryAgent

        org, claim = make_claim(db_session, billed=Decimal("2000.00"), paid=Decimal("0.00"))
        context = _fake_context(claim, org)
        context.agent_outputs["risk"] = {"recovery_probability_pct": 50.0}
        context.agent_outputs["compliance"] = {"blocking": False}

        result = run(RecoveryAgent().run(context))

        assert result.output["recommended_action"] == "medical_review"

    def test_low_probability_high_balance_gets_phone_follow_up(self, db_session):
        from app.agents.recovery.agent import RecoveryAgent

        org, claim = make_claim(db_session, billed=Decimal("2000.00"), paid=Decimal("0.00"))
        context = _fake_context(claim, org)
        context.agent_outputs["risk"] = {"recovery_probability_pct": 20.0}
        context.agent_outputs["compliance"] = {"blocking": False}

        result = run(RecoveryAgent().run(context))

        assert result.output["recommended_action"] in ("phone_follow_up", "write_off")

    def test_low_probability_low_balance_gets_provider_letter(self, db_session):
        from app.agents.recovery.agent import RecoveryAgent

        org, claim = make_claim(db_session, billed=Decimal("100.00"), paid=Decimal("0.00"))
        context = _fake_context(claim, org)
        context.agent_outputs["risk"] = {"recovery_probability_pct": 20.0}
        context.agent_outputs["compliance"] = {"blocking": False}

        result = run(RecoveryAgent().run(context))

        assert result.output["recommended_action"] in ("provider_letter", "write_off")


# ---------------------------------------------------------------------------
# AppealAgent
# ---------------------------------------------------------------------------

class TestAppealAgent:
    def test_wraps_appeal_service(self, db_session, monkeypatch):
        import app.agents.appeal.agent as appeal_module
        from app.agents.appeal.agent import AppealAgent

        class FakeAppeal:
            id = 42
            summary = "Draft appeal summary"
            missing_documents = ["Operative report"]

            class status:
                value = "draft"

        async def fake_generate_appeal(self, claim_id, recovery_case_id=None):
            return FakeAppeal()

        monkeypatch.setattr(appeal_module.AppealService, "generate_appeal", fake_generate_appeal)

        org, claim = make_claim(db_session)
        context = _fake_context(claim, org)

        result = run(AppealAgent(db=db_session, organization_id=org.id).run(context))

        assert result.status == "succeeded"
        assert result.output["appeal_id"] == 42
        assert result.output["missing_documents"] == ["Operative report"]

    def test_failure_is_caught(self, db_session, monkeypatch):
        import app.agents.appeal.agent as appeal_module
        from app.agents.appeal.agent import AppealAgent

        async def broken_generate_appeal(self, claim_id, recovery_case_id=None):
            raise ValueError("no denial on file")

        monkeypatch.setattr(appeal_module.AppealService, "generate_appeal", broken_generate_appeal)

        org, claim = make_claim(db_session)
        context = _fake_context(claim, org)

        result = run(AppealAgent(db=db_session, organization_id=org.id).run(context))

        assert result.status == "failed"
        assert result.output["appeal_id"] is None


# ---------------------------------------------------------------------------
# AgentRegistry
# ---------------------------------------------------------------------------

def test_registry_has_all_six_default_agents():
    from app.agents.registry import registry

    assert set(registry.list_names()) == {
        "coding", "documentation", "compliance", "risk", "recovery", "appeal",
    }


# ---------------------------------------------------------------------------
# AgentOrchestrator — conflict detection + end-to-end phasing/persistence
# ---------------------------------------------------------------------------

class TestOrchestratorConflictDetection:
    def test_detects_risk_vs_compliance_conflict(self, db_session):
        from app.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(db_session, organization_id=1)
        conflicts = orchestrator._detect_conflicts(
            risk={"recovery_probability_pct": 85.0},
            compliance={"blocking": True},
            recovery={"recommended_action": "write_off", "reason": "Compliance blocking issue."},
        )

        assert len(conflicts) == 1
        assert conflicts[0]["agents"] == ["risk", "compliance"]

    def test_no_conflict_when_agents_agree(self, db_session):
        from app.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(db_session, organization_id=1)
        conflicts = orchestrator._detect_conflicts(
            risk={"recovery_probability_pct": 85.0},
            compliance={"blocking": False},
            recovery={"recommended_action": "appeal", "reason": "High probability."},
        )

        assert conflicts == []


class TestOrchestratorEndToEnd:
    def test_run_persists_result_and_execution_logs(self, db_session, monkeypatch):
        """Full orchestration run against fake (stubbed) agents — verifies
        phasing, persistence to ClaimAnalysis.multi_agent_result, and
        AgentExecutionLog rows, without depending on any real LLM output."""
        from app.agents import registry as registry_module
        from app.agents.base import BaseAgent
        from app.agents.models import AgentResult
        from app.agents.orchestrator import AgentOrchestrator

        class FakeCodingAgent(BaseAgent):
            name = "coding"
            async def run(self, context):
                return AgentResult(agent=self.name, output={"issues": []}, duration_ms=1)

        class FakeDocumentationAgent(BaseAgent):
            name = "documentation"
            async def run(self, context):
                return AgentResult(agent=self.name, output={"is_complete": True}, duration_ms=1)

        class FakeComplianceAgent(BaseAgent):
            name = "compliance"
            async def run(self, context):
                return AgentResult(agent=self.name, output={"blocking": False}, duration_ms=1)

        class FakeRiskAgent(BaseAgent):
            name = "risk"
            async def run(self, context):
                return AgentResult(agent=self.name, output={"recovery_probability_pct": 90.0, "priority": "high"}, duration_ms=1)

        class FakeRecoveryAgent(BaseAgent):
            name = "recovery"
            async def run(self, context):
                return AgentResult(agent=self.name, output={"recommended_action": "appeal", "reason": "test", "estimated_recovery": 500.0}, duration_ms=1)

        class FakeAppealAgent(BaseAgent):
            name = "appeal"
            async def run(self, context):
                return AgentResult(agent=self.name, output={"appeal_id": 7}, duration_ms=1)

        real_registry = registry_module.registry
        monkeypatch.setattr(real_registry, "_agents", {
            "coding": FakeCodingAgent, "documentation": FakeDocumentationAgent,
            "compliance": FakeComplianceAgent, "risk": FakeRiskAgent,
            "recovery": FakeRecoveryAgent, "appeal": FakeAppealAgent,
        })

        org, claim = make_claim(db_session)
        orchestrator = AgentOrchestrator(db_session, organization_id=org.id)

        result = run(orchestrator.run(claim.id))

        assert result["agent_outputs"]["appeal"]["appeal_id"] == 7
        assert result["final_decision"]["recommended_action"] == "appeal"

        analysis = db_session.query(ClaimAnalysis).filter(ClaimAnalysis.claim_id == claim.id).first()
        assert analysis is not None
        assert analysis.multi_agent_result["run_id"] == result["run_id"]

        logs = db_session.query(AgentExecutionLog).filter(AgentExecutionLog.claim_id == claim.id).all()
        assert {log.agent_name for log in logs} == {
            "coding", "documentation", "compliance", "risk", "recovery", "appeal",
        }

    def test_run_skips_appeal_when_not_recommended(self, db_session, monkeypatch):
        from app.agents import registry as registry_module
        from app.agents.base import BaseAgent
        from app.agents.models import AgentResult
        from app.agents.orchestrator import AgentOrchestrator

        class FakeAgent(BaseAgent):
            async def run(self, context):
                return AgentResult(agent=self.name, output={}, duration_ms=1)

        class FakeComplianceAgent(FakeAgent):
            name = "compliance"
            async def run(self, context):
                return AgentResult(agent=self.name, output={"blocking": False}, duration_ms=1)

        class FakeRiskAgent(FakeAgent):
            name = "risk"

        class FakeCodingAgent(FakeAgent):
            name = "coding"

        class FakeDocumentationAgent(FakeAgent):
            name = "documentation"

        class FakeRecoveryAgent(FakeAgent):
            name = "recovery"
            async def run(self, context):
                return AgentResult(agent=self.name, output={"recommended_action": "write_off", "reason": "test"}, duration_ms=1)

        class FakeAppealAgent(FakeAgent):
            name = "appeal"

        real_registry = registry_module.registry
        monkeypatch.setattr(real_registry, "_agents", {
            "coding": FakeCodingAgent, "documentation": FakeDocumentationAgent,
            "compliance": FakeComplianceAgent, "risk": FakeRiskAgent,
            "recovery": FakeRecoveryAgent, "appeal": FakeAppealAgent,
        })

        org, claim = make_claim(db_session)
        orchestrator = AgentOrchestrator(db_session, organization_id=org.id)

        result = run(orchestrator.run(claim.id))

        assert "appeal" not in result["agent_outputs"]
        logs = db_session.query(AgentExecutionLog).filter(
            AgentExecutionLog.claim_id == claim.id, AgentExecutionLog.agent_name == "appeal",
        ).all()
        assert len(logs) == 1
        assert logs[0].status == "skipped"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_context(claim, org, *, denial_code_info=None, documents=None, denial=None):
    from app.agents.context import ClaimContext

    return ClaimContext(
        organization_id=org.id,
        claim=claim,
        patient=claim.patient,
        payer=claim.payer,
        organization=org,
        documents=documents if documents is not None else [],
        denial=denial,
        denial_code_info=denial_code_info,
        analysis=None,
        recovery_case=None,
        history=[],
    )
