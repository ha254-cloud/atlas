from datetime import datetime
from decimal import Decimal


class ClaimNormalizer:
    def normalize(self, row: dict) -> dict:
        return {
            "claim_number": row["claim_number"].strip(),
            "patient_first_name": row["patient_first_name"].strip(),
            "patient_last_name": row["patient_last_name"].strip(),
            "payer_code": row["payer_code"].strip(),
            "billed_amount": Decimal(row["billed_amount"]),
            "paid_amount": Decimal(row["paid_amount"]),
            "service_date": datetime.strptime(
                row["service_date"],
                "%Y-%m-%d",
            ).date(),
        }
