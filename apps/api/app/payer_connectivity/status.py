from app.models.appeal_submission import AppealSubmissionStatus

_COMMON_STATUS_MAP = {
    "pending": AppealSubmissionStatus.PENDING,
    "queued": AppealSubmissionStatus.PENDING,
    "submitted": AppealSubmissionStatus.SUBMITTED,
    "accepted": AppealSubmissionStatus.ACKNOWLEDGED,
    "acknowledged": AppealSubmissionStatus.ACKNOWLEDGED,
    "in review": AppealSubmissionStatus.UNDER_REVIEW,
    "in medical review": AppealSubmissionStatus.UNDER_REVIEW,
    "under review": AppealSubmissionStatus.UNDER_REVIEW,
    "additional information requested": AppealSubmissionStatus.ADDITIONAL_INFO_REQUIRED,
    "accepted for payment": AppealSubmissionStatus.ACCEPTED,
    "approved": AppealSubmissionStatus.ACCEPTED,
    "rejected": AppealSubmissionStatus.REJECTED,
    "denied": AppealSubmissionStatus.DENIED,
    "paid": AppealSubmissionStatus.PAID,
    "failed": AppealSubmissionStatus.FAILED,
}

_PROVIDER_STATUS_MAP = {
    "availity": {
        "received": AppealSubmissionStatus.ACKNOWLEDGED,
        "pended": AppealSubmissionStatus.UNDER_REVIEW,
    },
    "waystar": {
        "delivered": AppealSubmissionStatus.ACKNOWLEDGED,
        "payer review": AppealSubmissionStatus.UNDER_REVIEW,
    },
}


def normalize_status(connector: str, external_status: str) -> AppealSubmissionStatus:
    key = external_status.strip().lower().replace("_", "-")
    provider_map = _PROVIDER_STATUS_MAP.get(connector.lower(), {})
    if key in provider_map:
        return provider_map[key]
    common_key = key.replace("-", " ")
    if common_key in _COMMON_STATUS_MAP:
        return _COMMON_STATUS_MAP[common_key]
    raise ValueError(
        f"Unknown {connector} status '{external_status}'; mapping must be configured before processing"
    )
