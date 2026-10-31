from datetime import date, datetime

from sqlalchemy.orm import Session

from app.ai.cost_tracking import ai_call_context
from app.appeals.citations import citations_for_denial_type, merge_citations
from app.appeals.evidence import EvidenceCheck, EvidenceCollector, MissingEvidenceError
from app.appeals.generator import AppealGenerator
from app.appeals.grounding import (
    build_grounding_report,
    policy_source_citation,
    policy_source_prompt_context,
)
from app.appeals.quality import score_appeal
from app.appeals.repository import AppealRepository
from app.appeals.sectioned_generator import SectionedAppealGenerator
from app.claims.repository import ClaimRepository
from app.claims.timeline import ClaimTimeline
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.appeal import Appeal, AppealStatus
from app.models.appeal_version import AppealVersion
from app.models.claim_analysis import ClaimAnalysis
from app.models.claim_event import ClaimEventType
from app.models.claim_workflow import ClaimWorkflowState
from app.models.denial import Denial
from app.models.organization import Organization
from app.payers.policies import PayerPolicyService
from app.repositories.denial_code_repository import DenialCodeRepository
from app.validation.rules import TIMELY_FILING_DAYS
from app.workflows.service import WorkflowService


class AppealService:
    # Appeal-status transitions that also advance the claim's overall
    # Recovery Workflow Engine state (best-effort — see WorkflowService.try_transition).
    _APPEAL_TO_WORKFLOW_STATE = {
        AppealStatus.REVIEW: ClaimWorkflowState.UNDER_REVIEW,
        AppealStatus.APPROVED: ClaimWorkflowState.APPROVED,
        AppealStatus.REJECTED: ClaimWorkflowState.READY_FOR_APPEAL,
    }

    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repo = AppealRepository(db, organization_id)
        self.claim_repo = ClaimRepository(db, organization_id)
        self.publisher = EventPublisher()

    def _get_claim_and_denial(self, claim_id: int):
        claim = self.claim_repo.get(claim_id)
        if claim is None:
            raise ValueError(f"Claim {claim_id} not found")
        denial = (
            self.db.query(Denial)
            .filter(
                Denial.claim_id == claim_id,
                Denial.organization_id == self.organization_id,
            )
            .order_by(Denial.id.desc())
            .first()
        )
        analysis = (
            self.db.query(ClaimAnalysis)
            .filter(
                ClaimAnalysis.claim_id == claim_id,
                ClaimAnalysis.organization_id == self.organization_id,
            )
            .first()
        )
        return claim, denial, analysis

    def _get_organization(self) -> Organization | None:
        return self.db.query(Organization).filter(Organization.id == self.organization_id).first()

    def _denial_code_entry(self, denial):
        if denial is None:
            return None
        return DenialCodeRepository(self.db).get_by_code(denial.denial_code)

    def _evidence_check(self, claim, denial, denial_code_entry=None) -> EvidenceCheck:
        """Step 5 of the Appeal Generation Engine: flag denial-code-typical
        documents Atlas can't verify are on file for this claim (checking the
        Evidence Library's uploaded documents, then falling back to
        structural claim data), so a reviewer double-checks before
        submission. By default this is advisory only (see `require_evidence`
        on generate_appeal/generate_sectioned_appeal for the strict, gating
        mode)."""
        denial_code_info = None
        if denial_code_entry is not None:
            denial_code_info = {"required_documents": denial_code_entry.required_documents}
        return EvidenceCollector().check(claim, denial_code_info, claim.documents)

    @staticmethod
    def _denial_category(analysis=None, denial_code_entry=None) -> str | None:
        if analysis is not None and analysis.denial_category:
            return str(analysis.denial_category).upper()
        if denial_code_entry is None or denial_code_entry.category is None:
            return None
        category = denial_code_entry.category
        return str(getattr(category, "value", category)).upper()

    def _build_extra_context(self, claim, denial_code_entry=None, analysis=None) -> dict:
        """Sprint 12 richer AI context: a short human-readable summary of
        supporting documents already on file (drawn from real extracted
        text/AI summaries, not just filenames) and KB-grounded citation
        suggestions for the denial's category, so the AI cites something
        real instead of guessing."""
        extra: dict = {}

        doc_lines = []
        for doc in claim.documents or []:
            excerpt = (doc.ai_summary or doc.extracted_text or "").strip()
            if excerpt:
                excerpt = excerpt[:300]
                doc_lines.append(f"{doc.document_type.value} ({doc.filename}): {excerpt}")
            else:
                doc_lines.append(f"{doc.document_type.value} ({doc.filename})")
        if doc_lines:
            extra["documents_summary"] = "\n".join(doc_lines)

        denial_category = self._denial_category(analysis, denial_code_entry)
        procedure_codes = {line.cpt_code for line in claim.claim_lines if line.cpt_code}
        policy_sources = PayerPolicyService(self.db, self.organization_id).applicable(
            claim.payer_id,
            on_date=claim.service_date or date.today(),
            denial_category=denial_category,
            procedure_codes=procedure_codes,
        )
        prompt_sources = policy_source_prompt_context(policy_sources)
        kb_citations = (
            citations_for_denial_type(denial_code_entry.category) if denial_code_entry else []
        )
        verified_citations = kb_citations + [
            policy_source_citation(source) for source in policy_sources
        ]
        if verified_citations:
            extra["suggested_citations"] = [
                f"{citation.source} {citation.reference} — {citation.description}"
                for citation in verified_citations
            ]
        extra["verified_policy_sources"] = prompt_sources
        extra["_verified_citations"] = verified_citations
        extra["_policy_sources"] = policy_sources
        extra["_denial_category"] = denial_category
        extra["_procedure_codes"] = procedure_codes

        return extra

    def _finalize_grounding(self, data: dict, claim, extra_context: dict) -> dict:
        model_citations = data.get("citations")
        accepted_citations = merge_citations(
            model_citations,
            extra_context["_verified_citations"],
        )
        data["citations"] = accepted_citations
        return build_grounding_report(
            payer_id=claim.payer_id,
            service_date=claim.service_date or date.today(),
            denial_category=extra_context["_denial_category"],
            procedure_codes=extra_context["_procedure_codes"],
            sources=extra_context["_policy_sources"],
            model_citations=model_citations,
            accepted_citations=accepted_citations,
        )

    def _persist_appeal(
        self,
        claim_id,
        recovery_case_id,
        data,
        provider="anthropic",
        analysis_id=None,
        missing_documents=None,
        quality_score=None,
        grounding_report=None,
    ) -> Appeal:
        appeal = Appeal(
            organization_id=self.organization_id,
            claim_id=claim_id,
            recovery_case_id=recovery_case_id,
            analysis_id=analysis_id,
            status=AppealStatus.DRAFT,
            appeal_text=data.get("appeal_letter", ""),
            title=data.get("title"),
            summary=data.get("summary"),
            sections=data.get("sections"),
            citations=data.get("citations"),
            attachments=data.get("attachments") or None,
            missing_information=data.get("missing_information") or None,
            missing_documents=missing_documents or None,
            quality_score=quality_score,
            grounding_report=grounding_report,
            ai_provider=provider,
            generated_by="ai",
            current_version=1,
        )
        self.repo.create(appeal)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(appeal)

        # Version 1 is the original AI draft — snapshot it up front so the
        # full history (including the unedited original) is always available.
        self.db.add(
            AppealVersion(
                organization_id=self.organization_id,
                appeal_id=appeal.id,
                version_number=1,
                appeal_text=appeal.appeal_text,
                sections=appeal.sections,
            )
        )

        self.publisher.publish(
            EventType.APPEAL_GENERATED,
            {"appeal_id": appeal.id, "claim_id": claim_id, "organization_id": self.organization_id},
        )
        ClaimTimeline(self.db).record(
            organization_id=self.organization_id,
            claim_id=claim_id,
            event_type=ClaimEventType.APPEAL_GENERATED,
            description=f"Draft appeal generated (provider={provider})",
            metadata={"appeal_id": appeal.id},
        )
        self.db.commit()
        WorkflowService(self.db, self.organization_id).try_transition(
            claim_id,
            ClaimWorkflowState.APPEAL_GENERATED,
            reason="Draft appeal generated",
        )
        return appeal

    async def generate_appeal(
        self, claim_id: int, recovery_case_id: int | None = None, require_evidence: bool = False
    ) -> Appeal:
        claim, denial, analysis = self._get_claim_and_denial(claim_id)
        organization = self._get_organization()
        denial_code_entry = self._denial_code_entry(denial)
        evidence = self._evidence_check(claim, denial, denial_code_entry)
        if require_evidence and evidence.needs_verification:
            raise MissingEvidenceError(evidence.needs_verification)

        extra_context = self._build_extra_context(claim, denial_code_entry, analysis)
        with ai_call_context(organization_id=self.organization_id, claim_id=claim_id):
            data = await AppealGenerator().generate(
                claim, denial, analysis, organization, extra_context
            )
        grounding_report = self._finalize_grounding(data, claim, extra_context)
        quality_score = score_appeal(
            data,
            evidence,
            kb_citation_available=bool(extra_context.get("suggested_citations")),
            grounding_report=grounding_report,
        )
        return self._persist_appeal(
            claim_id,
            recovery_case_id,
            data,
            analysis_id=analysis.id if analysis else None,
            missing_documents=evidence.needs_verification,
            quality_score=quality_score,
            grounding_report=grounding_report,
        )

    async def generate_sectioned_appeal(
        self, claim_id: int, recovery_case_id: int | None = None, require_evidence: bool = False
    ) -> Appeal:
        claim, denial, analysis = self._get_claim_and_denial(claim_id)
        organization = self._get_organization()
        denial_code_entry = self._denial_code_entry(denial)
        evidence = self._evidence_check(claim, denial, denial_code_entry)
        if require_evidence and evidence.needs_verification:
            raise MissingEvidenceError(evidence.needs_verification)

        extra_context = self._build_extra_context(claim, denial_code_entry, analysis)
        with ai_call_context(organization_id=self.organization_id, claim_id=claim_id):
            data = await SectionedAppealGenerator().generate(
                claim, denial, analysis, organization, extra_context
            )
        grounding_report = self._finalize_grounding(data, claim, extra_context)
        quality_score = score_appeal(
            data,
            evidence,
            kb_citation_available=bool(extra_context.get("suggested_citations")),
            grounding_report=grounding_report,
        )
        return self._persist_appeal(
            claim_id,
            recovery_case_id,
            data,
            analysis_id=analysis.id if analysis else None,
            missing_documents=evidence.needs_verification,
            quality_score=quality_score,
            grounding_report=grounding_report,
        )

    def get_appeal(self, appeal_id: int) -> Appeal | None:
        return self.repo.get(appeal_id)

    def list_for_claim(self, claim_id: int) -> list[Appeal]:
        return self.repo.list_for_claim(claim_id)

    def _transition(
        self,
        appeal_id: int,
        from_statuses: list[AppealStatus],
        to_status: AppealStatus,
        description: str,
        actor_id: int | None = None,
    ) -> Appeal:
        appeal = self.repo.get(appeal_id)
        if appeal is None:
            raise ValueError(f"Appeal {appeal_id} not found")
        if appeal.status not in from_statuses:
            raise ValueError(
                f"Cannot move appeal {appeal_id} from {appeal.status.value} to "
                f"{to_status.value} (expected one of: {[s.value for s in from_statuses]})"
            )
        appeal.status = to_status
        self.db.commit()
        self.db.refresh(appeal)
        ClaimTimeline(self.db).record(
            organization_id=self.organization_id,
            claim_id=appeal.claim_id,
            event_type=ClaimEventType.STATUS_CHANGED,
            description=description,
            metadata={"appeal_id": appeal.id, "status": to_status.value},
        )
        self.db.commit()
        workflow_state = self._APPEAL_TO_WORKFLOW_STATE.get(to_status)
        if workflow_state is not None:
            WorkflowService(self.db, self.organization_id).try_transition(
                appeal.claim_id,
                workflow_state,
                actor_id=actor_id,
                reason=description,
            )
        return appeal

    def submit_for_review(self, appeal_id: int) -> Appeal:
        """Send a draft appeal to a revenue specialist for review."""
        return self._transition(
            appeal_id,
            [AppealStatus.DRAFT],
            AppealStatus.REVIEW,
            "Appeal sent for human review",
        )

    def approve_appeal(self, appeal_id: int, actor_id: int | None = None) -> Appeal:
        """A human reviewer approves the appeal — required before it can be submitted."""
        appeal = self._transition(
            appeal_id,
            [AppealStatus.REVIEW],
            AppealStatus.APPROVED,
            "Appeal approved by reviewer",
            actor_id=actor_id,
        )
        if actor_id is not None:
            appeal = self.repo.approve(appeal_id, actor_id)
            self.db.commit()
            self.db.refresh(appeal)
        self.publisher.publish(
            EventType.APPEAL_APPROVED,
            {
                "appeal_id": appeal.id,
                "claim_id": appeal.claim_id,
                "organization_id": self.organization_id,
            },
        )
        return appeal

    def reject_appeal(self, appeal_id: int, actor_id: int | None = None) -> Appeal:
        """A human reviewer rejects the appeal — it will not be submitted as-is."""
        return self._transition(
            appeal_id,
            [AppealStatus.REVIEW],
            AppealStatus.REJECTED,
            "Appeal rejected by reviewer",
            actor_id=actor_id,
        )

    def _submission_blockers(self, appeal: Appeal) -> list[str]:
        """Sprint 12 Submission Readiness checks — everything that must be
        true before an appeal is allowed to leave the building. Returns a
        list of human-readable blocker reasons; empty means ready."""
        blockers: list[str] = []

        if not appeal.appeal_text or not appeal.appeal_text.strip():
            blockers.append("Appeal letter has not been generated.")

        if appeal.status != AppealStatus.APPROVED:
            blockers.append(
                f"Reviewer approval has not been obtained (current status: {appeal.status.value})."
            )

        if appeal.missing_documents:
            blockers.append(
                "Required attachments are not confirmed on file: "
                + ", ".join(appeal.missing_documents)
            )

        claim = self.claim_repo.get(appeal.claim_id)
        if claim is not None and claim.service_date is not None:
            age_days = (date.today() - claim.service_date).days
            if age_days > TIMELY_FILING_DAYS:
                blockers.append(
                    f"Timely filing deadline exceeded ({age_days} days since service date, "
                    f"limit {TIMELY_FILING_DAYS})."
                )

        return blockers

    def check_submission_readiness(self, appeal_id: int) -> list[str]:
        """Public readiness check (used by the API to preview blockers
        without attempting submission)."""
        appeal = self.repo.get(appeal_id)
        if appeal is None:
            raise ValueError(f"Appeal {appeal_id} not found")
        return self._submission_blockers(appeal)

    def submit_appeal(
        self,
        appeal_id: int,
        submitted_by: int | None = None,
        confirmation_number: str | None = None,
    ) -> Appeal:
        """
        Record an appeal that a human submitted outside Atlas. Electronic
        delivery uses SubmissionService instead. Healthcare is a regulated
        domain, so every readiness check and an external confirmation or
        tracking reference are required before recording manual submission.
        """
        appeal = self.repo.get(appeal_id)
        if appeal is None:
            raise ValueError(f"Appeal {appeal_id} not found")

        blockers = self._submission_blockers(appeal)
        if blockers:
            raise ValueError(
                f"Appeal {appeal_id} is not ready for submission: " + " ".join(blockers)
            )
        confirmation_number = (confirmation_number or "").strip()
        if not confirmation_number:
            raise ValueError(
                "Manual submission requires the payer confirmation or tracking reference"
            )

        appeal = self.repo.update(
            appeal_id,
            status=AppealStatus.SUBMITTED,
            submitted_at=datetime.utcnow(),
            submitted_by=submitted_by,
            confirmation_number=confirmation_number,
        )
        ClaimTimeline(self.db).record(
            organization_id=self.organization_id,
            claim_id=appeal.claim_id,
            event_type=ClaimEventType.APPEAL_SUBMITTED,
            description="Appeal submitted to payer",
            metadata={"appeal_id": appeal.id, "confirmation_number": confirmation_number},
        )
        self.db.commit()
        self.db.refresh(appeal)
        self.publisher.publish(
            EventType.APPEAL_SUBMITTED,
            {
                "appeal_id": appeal.id,
                "claim_id": appeal.claim_id,
                "organization_id": self.organization_id,
                "confirmation_number": confirmation_number,
            },
        )
        WorkflowService(self.db, self.organization_id).try_transition(
            appeal.claim_id,
            ClaimWorkflowState.SUBMITTED,
            actor_id=submitted_by,
            reason="Appeal submitted to payer",
        )
        return appeal

    def update_appeal_text(
        self,
        appeal_id: int,
        text: str,
        edited_by: int | None = None,
        sections: dict[str, str] | None = None,
    ) -> Appeal | None:
        """Edit the draft appeal text. Every edit snapshots the prior version
        into AppealVersion before overwriting, so the full edit history is
        preserved (Appeal v1 -> edited -> v2 -> approved -> submitted).
        Version 1 is already snapshotted by _persist_appeal(), so this only
        adds a row if the currently-live version hasn't been captured yet."""
        appeal = self.repo.get(appeal_id)
        if appeal is None:
            return None
        if appeal.status not in (AppealStatus.DRAFT, AppealStatus.REVIEW):
            raise ValueError(
                f"Cannot edit appeal {appeal_id} in {appeal.status.value} status; "
                "only draft or in-review appeals can be edited"
            )

        existing = (
            self.db.query(AppealVersion)
            .filter(
                AppealVersion.appeal_id == appeal.id,
                AppealVersion.version_number == appeal.current_version,
            )
            .first()
        )
        if existing is None:
            self.db.add(
                AppealVersion(
                    organization_id=self.organization_id,
                    appeal_id=appeal.id,
                    version_number=appeal.current_version,
                    appeal_text=appeal.appeal_text,
                    sections=appeal.sections,
                    edited_by=edited_by,
                )
            )

        appeal.appeal_text = text
        if sections is not None:
            appeal.sections = sections
        appeal.current_version += 1
        appeal.generated_by = str(edited_by) if edited_by is not None else "reviewer"
        self.db.flush()
        self.db.refresh(appeal)
        return appeal

    async def regenerate_appeal(self, appeal_id: int, require_evidence: bool = False) -> Appeal:
        """AI Revision — re-run generation for an existing appeal and version
        the result (Appeal v1 (AI draft) -> v2 (AI revision) -> ... ),
        instead of only versioning manual reviewer edits. Only allowed while
        the appeal hasn't yet been approved/submitted — once a human has
        signed off, further changes go through `update_appeal_text`."""
        appeal = self.repo.get(appeal_id)
        if appeal is None:
            raise ValueError(f"Appeal {appeal_id} not found")
        if appeal.status not in (AppealStatus.DRAFT, AppealStatus.REVIEW):
            raise ValueError(
                f"Cannot regenerate appeal {appeal_id} in status {appeal.status.value} "
                "— only draft/in-review appeals can be AI-revised."
            )

        claim, denial, analysis = self._get_claim_and_denial(appeal.claim_id)
        organization = self._get_organization()
        denial_code_entry = self._denial_code_entry(denial)
        evidence = self._evidence_check(claim, denial, denial_code_entry)
        if require_evidence and evidence.needs_verification:
            raise MissingEvidenceError(evidence.needs_verification)

        extra_context = self._build_extra_context(claim, denial_code_entry, analysis)
        generator = SectionedAppealGenerator() if appeal.sections else AppealGenerator()
        with ai_call_context(organization_id=self.organization_id, claim_id=appeal.claim_id):
            data = await generator.generate(claim, denial, analysis, organization, extra_context)
        grounding_report = self._finalize_grounding(data, claim, extra_context)
        quality_score = score_appeal(
            data,
            evidence,
            kb_citation_available=bool(extra_context.get("suggested_citations")),
            grounding_report=grounding_report,
        )

        # Snapshot the version currently live before overwriting it with the
        # AI revision — same pattern as update_appeal_text().
        existing = (
            self.db.query(AppealVersion)
            .filter(
                AppealVersion.appeal_id == appeal.id,
                AppealVersion.version_number == appeal.current_version,
            )
            .first()
        )
        if existing is None:
            self.db.add(
                AppealVersion(
                    organization_id=self.organization_id,
                    appeal_id=appeal.id,
                    version_number=appeal.current_version,
                    appeal_text=appeal.appeal_text,
                    sections=appeal.sections,
                )
            )

        appeal.appeal_text = data.get("appeal_letter", "")
        appeal.title = data.get("title")
        appeal.summary = data.get("summary")
        appeal.sections = data.get("sections")
        appeal.citations = data.get("citations")
        appeal.attachments = data.get("attachments") or None
        appeal.missing_information = data.get("missing_information") or None
        appeal.missing_documents = evidence.needs_verification or None
        appeal.quality_score = quality_score
        appeal.grounding_report = grounding_report
        appeal.current_version += 1
        appeal.generated_by = "ai"
        self.db.commit()
        self.db.refresh(appeal)
        return appeal
