from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.governance.models import PatientConsent, RetentionPolicy, UserSession
from app.governance.schemas import ConsentCreate, RetentionPolicyCreate
from app.models.ai_call_log import AICallLog
from app.models.appeal import Appeal, AppealStatus
from app.models.audit_log import AuditLog
from app.models.patient import Patient
from app.models.user import User


class GovernanceNotFoundError(ValueError):
    pass


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class ConsentService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def record(self, patient_id: int, payload: ConsentCreate, actor_id: int, correlation_id: str):
        patient = (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.organization_id == self.organization_id)
            .first()
        )
        if patient is None:
            raise GovernanceNotFoundError("Patient not found")
        previous = (
            self.db.query(PatientConsent)
            .filter(
                PatientConsent.organization_id == self.organization_id,
                PatientConsent.patient_id == patient_id,
                PatientConsent.purpose == payload.purpose.value,
            )
            .order_by(PatientConsent.version.desc())
            .first()
        )
        now = datetime.now(UTC)
        consent = PatientConsent(
            organization_id=self.organization_id,
            patient_id=patient_id,
            purpose=payload.purpose.value,
            decision=payload.decision.value,
            version=(previous.version + 1) if previous else 1,
            retention_years=payload.retention_years,
            effective_at=payload.effective_at or now,
            expires_at=payload.expires_at,
            recorded_by=actor_id,
            reason=payload.reason,
            correlation_id=correlation_id,
            created_at=now,
        )
        self.db.add(consent)
        self.db.flush()
        AuditService(self.db).log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=AuditAction.PATIENT_CONSENT_RECORDED,
            entity="patient_consent",
            entity_id=consent.id,
            correlation_id=correlation_id,
            reason=payload.reason,
            before_state={"decision": previous.decision, "version": previous.version}
            if previous
            else None,
            after_state={
                "patient_id": patient_id,
                "purpose": consent.purpose,
                "decision": consent.decision,
                "version": consent.version,
            },
        )
        self.db.commit()
        self.db.refresh(consent)
        return consent

    def list(self, patient_id: int):
        patient = (
            self.db.query(Patient.id)
            .filter(Patient.id == patient_id, Patient.organization_id == self.organization_id)
            .first()
        )
        if patient is None:
            raise GovernanceNotFoundError("Patient not found")
        return (
            self.db.query(PatientConsent)
            .filter(
                PatientConsent.organization_id == self.organization_id,
                PatientConsent.patient_id == patient_id,
            )
            .order_by(PatientConsent.purpose, PatientConsent.version.desc())
            .all()
        )


class RetentionService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def create(self, payload: RetentionPolicyCreate, actor_id: int, correlation_id: str):
        previous = (
            self.db.query(RetentionPolicy)
            .filter(
                RetentionPolicy.organization_id == self.organization_id,
                RetentionPolicy.resource_type == payload.resource_type,
            )
            .order_by(RetentionPolicy.version.desc())
            .first()
        )
        policy = RetentionPolicy(
            organization_id=self.organization_id,
            resource_type=payload.resource_type,
            version=(previous.version + 1) if previous else 1,
            retention_days=payload.retention_days,
            disposition=payload.disposition.value,
            legal_hold_default=payload.legal_hold_default,
            enforcement_mode=payload.enforcement_mode.value,
            created_by=actor_id,
            reason=payload.reason,
            correlation_id=correlation_id,
            created_at=datetime.now(UTC),
        )
        self.db.add(policy)
        self.db.flush()
        AuditService(self.db).log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=AuditAction.RETENTION_POLICY_VERSION_CREATED,
            entity="retention_policy",
            entity_id=policy.id,
            correlation_id=correlation_id,
            reason=payload.reason,
            before_state={"retention_days": previous.retention_days, "version": previous.version}
            if previous
            else None,
            after_state={
                "resource_type": policy.resource_type,
                "retention_days": policy.retention_days,
                "disposition": policy.disposition,
                "version": policy.version,
            },
        )
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def list(self):
        return (
            self.db.query(RetentionPolicy)
            .filter(RetentionPolicy.organization_id == self.organization_id)
            .order_by(RetentionPolicy.resource_type, RetentionPolicy.version.desc())
            .all()
        )


class SessionService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def create(
        self,
        user_id: int,
        expires_at: datetime,
        ip_address: str | None,
        user_agent: str | None,
        device: str | None,
    ):
        now = datetime.now(UTC)
        session = UserSession(
            id=str(uuid4()),
            organization_id=self.organization_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device=device,
            expires_at=expires_at,
            last_seen_at=now,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def list(self):
        return (
            self.db.query(UserSession)
            .filter(UserSession.organization_id == self.organization_id)
            .order_by(UserSession.created_at.desc())
            .all()
        )

    def revoke(self, session_id: str, actor_id: int, reason: str):
        session = (
            self.db.query(UserSession)
            .filter(
                UserSession.id == session_id,
                UserSession.organization_id == self.organization_id,
            )
            .first()
        )
        if session is None:
            raise GovernanceNotFoundError("Session not found")
        before = {"revoked_at": session.revoked_at.isoformat() if session.revoked_at else None}
        if session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            session.revoked_by = actor_id
            session.revoke_reason = reason
            AuditService(self.db).log(
                organization_id=self.organization_id,
                user_id=actor_id,
                action=AuditAction.USER_SESSION_TERMINATED,
                entity="user_session",
                reason=reason,
                correlation_id=str(uuid4()),
                before_state=before,
                after_state={"session_id": session.id, "user_id": session.user_id, "revoked": True},
            )
            self.db.commit()
            self.db.refresh(session)
        return session


class ComplianceService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def summary(self) -> dict:
        now = datetime.now(UTC)
        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)
        audit_query = self.db.query(AuditLog).filter(
            AuditLog.organization_id == self.organization_id
        )
        failed_logins = audit_query.filter(
            AuditLog.action == AuditAction.USER_LOGIN_FAILED.value,
            AuditLog.created_at >= thirty_days_ago,
        ).count()
        password_resets = audit_query.filter(
            AuditLog.action == AuditAction.PASSWORD_RESET_COMPLETED.value,
            AuditLog.created_at >= thirty_days_ago,
        ).count()
        users = self.db.query(User).filter(User.organization_id == self.organization_id).all()
        inactive = 0
        suspicious = 0
        for user in users:
            last_login = (
                audit_query.filter(
                    AuditLog.user_id == user.id,
                    AuditLog.action == AuditAction.USER_LOGIN.value,
                )
                .order_by(AuditLog.created_at.desc())
                .first()
            )
            if (
                not user.is_active
                or last_login is None
                or _as_utc(last_login.created_at) < ninety_days_ago
            ):
                inactive += 1
            user_failures = audit_query.filter(
                AuditLog.user_id == user.id,
                AuditLog.action == AuditAction.USER_LOGIN_FAILED.value,
                AuditLog.created_at >= thirty_days_ago,
            ).count()
            if user_failures >= 5:
                suspicious += 1
        appeals = self.db.query(Appeal).filter(Appeal.organization_id == self.organization_id).all()
        missing_documents = sum(bool(appeal.missing_documents) for appeal in appeals)
        outstanding = sum(
            appeal.status in {AppealStatus.GENERATED, AppealStatus.REVIEW} for appeal in appeals
        )
        missing_approver = sum(
            appeal.status in {AppealStatus.APPROVED, AppealStatus.SUBMITTED}
            and appeal.approved_by is None
            for appeal in appeals
        )
        ai_missing_prompt = (
            self.db.query(AICallLog)
            .filter(
                AICallLog.organization_id == self.organization_id,
                AICallLog.prompt_version.is_(None),
            )
            .count()
        )
        patient_count = (
            self.db.query(Patient).filter(Patient.organization_id == self.organization_id).count()
        )
        consented = (
            self.db.query(func.count(func.distinct(PatientConsent.patient_id)))
            .filter(PatientConsent.organization_id == self.organization_id)
            .scalar()
            or 0
        )
        policy_count = (
            self.db.query(func.count(func.distinct(RetentionPolicy.resource_type)))
            .filter(RetentionPolicy.organization_id == self.organization_id)
            .scalar()
            or 0
        )
        active_sessions = (
            self.db.query(UserSession)
            .filter(
                UserSession.organization_id == self.organization_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
            .count()
        )
        status = "PASS" if ai_missing_prompt == 0 and missing_approver == 0 else "REVIEW"
        return {
            "audit_status": status,
            "total_audit_events": audit_query.count(),
            "missing_document_claims": missing_documents,
            "outstanding_approvals": outstanding,
            "inactive_users": inactive,
            "ai_calls_without_prompt_version": ai_missing_prompt,
            "approved_appeals_without_approver": missing_approver,
            "consented_patients": consented,
            "patients_without_consent": max(patient_count - consented, 0),
            "configured_retention_policies": policy_count,
            "retention_enforcement_mode": "report_only",
            "security": {
                "failed_logins_30d": failed_logins,
                "password_resets_30d": password_resets,
                "inactive_users_90d": inactive,
                "suspicious_users": suspicious,
                "active_sessions": active_sessions,
            },
        }
