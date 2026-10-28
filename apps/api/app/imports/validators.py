REQUIRED_COLUMNS = [
    "claim_number",
    "patient_first_name",
    "patient_last_name",
    "payer_code",
    "billed_amount",
    "paid_amount",
    "service_date",
]


class ClaimValidator:
    def validate(self, row: dict) -> list[str]:
        missing = []

        for column in REQUIRED_COLUMNS:
            if not row.get(column):
                missing.append(column)

        return missing
