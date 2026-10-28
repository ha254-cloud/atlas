from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.payers.models import ContractTariff, PayerContract
from app.payers.repository import PayerRepository
from app.payers.schemas import ContractCreate, ContractValidationResult, ValidationFinding


class ContractService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repository = PayerRepository(db, organization_id)

    def create_version(
        self, payer_id: int, payload: ContractCreate, actor_id: int
    ) -> PayerContract:
        if self.repository.get(payer_id) is None:
            raise ValueError("Payer not found")
        contract_code = payload.contract_code.strip().upper()
        prior_versions = [
            contract
            for contract in self.repository.list_contracts(payer_id)
            if contract.contract_code == contract_code
        ]
        contract = PayerContract(
            organization_id=self.organization_id,
            payer_id=payer_id,
            contract_code=contract_code,
            name=payload.name.strip(),
            version=max((item.version for item in prior_versions), default=0) + 1,
            currency=payload.currency.upper(),
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            terms=payload.terms,
            created_by=actor_id,
            change_reason=payload.reason.strip(),
        )
        self.db.add(contract)
        self.db.flush()
        for item in payload.tariffs:
            self.db.add(
                ContractTariff(
                    contract_id=contract.id,
                    procedure_code=item.procedure_code.strip().upper(),
                    description=item.description,
                    unit_price=item.unit_price,
                    rules=item.rules,
                )
            )
        self.db.flush()
        return contract

    def list(self, payer_id: int) -> list[dict]:
        if self.repository.get(payer_id) is None:
            raise ValueError("Payer not found")
        return [self._read_model(contract) for contract in self.repository.list_contracts(payer_id)]

    def validate_claim(self, payer_id: int, claim_id: int) -> ContractValidationResult:
        if self.repository.get(payer_id) is None:
            raise ValueError("Payer not found")
        claim = (
            self.db.query(Claim)
            .filter(
                Claim.id == claim_id,
                Claim.organization_id == self.organization_id,
                Claim.payer_id == payer_id,
            )
            .first()
        )
        if claim is None:
            raise ValueError("Claim not found")
        contract = self.repository.active_contract(payer_id, claim.service_date)
        if contract is None:
            finding = ValidationFinding(
                code="contract_not_found",
                severity="warning",
                message="No effective contract was found for the claim service date.",
            )
            return ContractValidationResult(
                claim_id=claim.id,
                payer_id=payer_id,
                contract_id=None,
                contract_version=None,
                currency=None,
                valid=False,
                findings=[finding],
            )
        tariffs = {tariff.procedure_code: tariff for tariff in self.repository.tariffs(contract.id)}
        findings: list[ValidationFinding] = []
        for line in claim.claim_lines:
            tariff = tariffs.get(line.cpt_code.strip().upper())
            if tariff is None:
                findings.append(
                    ValidationFinding(
                        code="tariff_not_found",
                        severity="warning",
                        message=f"No contract tariff exists for procedure {line.cpt_code}.",
                        claim_line_id=line.id,
                        actual_amount=line.charge_amount,
                    )
                )
                continue
            expected = tariff.unit_price * Decimal(line.units)
            if line.charge_amount != expected:
                findings.append(
                    ValidationFinding(
                        code="tariff_mismatch",
                        severity="warning",
                        message=f"Procedure {line.cpt_code} does not match the effective contract tariff.",
                        claim_line_id=line.id,
                        expected_amount=expected,
                        actual_amount=line.charge_amount,
                    )
                )
        return ContractValidationResult(
            claim_id=claim.id,
            payer_id=payer_id,
            contract_id=contract.id,
            contract_version=contract.version,
            currency=contract.currency,
            valid=not findings,
            findings=findings,
        )

    def _read_model(self, contract: PayerContract) -> dict:
        return {
            "id": contract.id,
            "organization_id": contract.organization_id,
            "payer_id": contract.payer_id,
            "contract_code": contract.contract_code,
            "name": contract.name,
            "version": contract.version,
            "currency": contract.currency,
            "effective_from": contract.effective_from,
            "effective_to": contract.effective_to,
            "terms": contract.terms,
            "created_by": contract.created_by,
            "change_reason": contract.change_reason,
            "tariffs": [
                {
                    "id": tariff.id,
                    "procedure_code": tariff.procedure_code,
                    "description": tariff.description,
                    "unit_price": tariff.unit_price,
                    "rules": tariff.rules,
                }
                for tariff in self.repository.tariffs(contract.id)
            ],
        }
