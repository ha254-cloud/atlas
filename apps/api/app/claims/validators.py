from datetime import date
from decimal import Decimal


class ClaimValidationError(Exception):
    pass


class DuplicateClaimError(ClaimValidationError):
    pass


class MissingPatientError(ClaimValidationError):
    pass


class InvalidPayerError(ClaimValidationError):
    pass


class InvalidAmountError(ClaimValidationError):
    pass


class FutureServiceDateError(ClaimValidationError):
    pass


class NegativeBalanceError(ClaimValidationError):
    pass


def validate_create(payload: dict, repo) -> None:
    # Duplicate claim number
    claim_number = payload.get("claim_number")
    if claim_number and repo.get_by_claim_number(claim_number):
        raise DuplicateClaimError("Duplicate claim number")

    # Missing patient
    if not payload.get("patient_id"):
        raise MissingPatientError("Missing patient_id")

    # Invalid payer
    if not payload.get("payer_id"):
        raise InvalidPayerError("Missing payer_id")

    # Invalid amount
    billed = payload.get("billed_amount")
    paid = payload.get("paid_amount", 0)
    if billed is None:
        raise InvalidAmountError("Missing billed_amount")

    try:
        billed_dec = Decimal(str(billed))
        paid_dec = Decimal(str(paid))
    except Exception:
        raise InvalidAmountError("Invalid amount format")

    if billed_dec < 0:
        raise InvalidAmountError("Negative billed_amount")

    # Future service date
    service_date = payload.get("service_date")
    if service_date:
        if isinstance(service_date, str):
            try:
                service_date = date.fromisoformat(service_date)
            except Exception:
                raise ClaimValidationError("Invalid service_date format")
        if service_date > date.today():
            raise FutureServiceDateError("Service date is in the future")

    # Negative balance
    balance = billed_dec - paid_dec
    if balance < 0:
        raise NegativeBalanceError("Negative balance")
