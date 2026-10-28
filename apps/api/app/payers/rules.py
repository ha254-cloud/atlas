from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.payers.models import PayerRule
from app.payers.repository import PayerRepository
from app.payers.schemas import RuleCreate, ValidationFinding


class PayerRulesService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repository = PayerRepository(db, organization_id)

    def create_version(self, payer_id: int, payload: RuleCreate, actor_id: int) -> PayerRule:
        if self.repository.get(payer_id) is None:
            raise ValueError("Payer not found")
        rule_code = payload.rule_code.strip().upper()
        versions = [
            rule.version
            for rule in self.repository.list_rules(payer_id)
            if rule.rule_code == rule_code
        ]
        rule = PayerRule(
            organization_id=self.organization_id,
            payer_id=payer_id,
            rule_code=rule_code,
            rule_type=payload.rule_type,
            version=max(versions, default=0) + 1,
            requirement=payload.requirement,
            value=payload.value,
            conditions=payload.conditions,
            source=payload.source.strip(),
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            created_by=actor_id,
            change_reason=payload.reason.strip(),
        )
        self.db.add(rule)
        self.db.flush()
        return rule

    def list(self, payer_id: int) -> list[PayerRule]:
        if self.repository.get(payer_id) is None:
            raise ValueError("Payer not found")
        return self.repository.list_rules(payer_id)

    def validate_claim(self, claim: Claim, *, as_of: date | None = None) -> list[ValidationFinding]:
        current_date = as_of or date.today()
        rules = self._latest_rules(claim.payer_id, claim.service_date)
        findings: list[ValidationFinding] = []
        for rule in rules:
            if rule.requirement not in {"required", "conditional"} or not self._matches(
                rule, claim
            ):
                continue
            if rule.rule_type == "authorization" and not claim.authorization_number:
                findings.append(self._finding(rule, "Required payer authorization is missing."))
            elif rule.rule_type == "submission_deadline":
                deadline_days = int(rule.value["days"])
                if (current_date - claim.service_date).days > deadline_days:
                    findings.append(
                        self._finding(
                            rule, f"The {deadline_days}-day submission deadline has passed."
                        )
                    )
            elif rule.rule_type in {"referral", "document"}:
                required = rule.value.get("documents") or ["referral"]
                available = " ".join(
                    f"{document.document_type.value} {document.filename}"
                    for document in claim.documents
                ).lower()
                missing = [name for name in required if str(name).lower() not in available]
                if missing:
                    findings.append(
                        self._finding(
                            rule, f"Required documents are missing: {', '.join(missing)}."
                        )
                    )
        return findings

    def _latest_rules(self, payer_id: int, on_date: date) -> list[PayerRule]:
        latest: dict[str, PayerRule] = {}
        for rule in self.repository.list_rules(payer_id, on_date=on_date):
            latest.setdefault(rule.rule_code, rule)
        return list(latest.values())

    @staticmethod
    def _matches(rule: PayerRule, claim: Claim) -> bool:
        procedure_codes = {line.cpt_code.upper() for line in claim.claim_lines}
        expected_codes = {str(code).upper() for code in rule.conditions.get("procedure_codes", [])}
        if expected_codes and procedure_codes.isdisjoint(expected_codes):
            return False
        minimum_amount = rule.conditions.get("minimum_amount")
        return minimum_amount is None or claim.billed_amount >= Decimal(str(minimum_amount))

    @staticmethod
    def _finding(rule: PayerRule, message: str) -> ValidationFinding:
        return ValidationFinding(
            code=f"payer_rule.{rule.rule_code.lower()}",
            severity="warning",
            message=message,
        )
