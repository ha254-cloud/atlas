from app.ai.engine import AIEngine


class AppealGenerator:
    def __init__(self):
        self.ai = AIEngine()

    async def generate_appeal(self, claim):
        prompt = f"""
Generate a concise appeal letter for this denied or unpaid healthcare claim.

Claim Number:
{claim.claim_number}

Patient Name:
{claim.patient_name}

Payer:
{claim.payer_name}

Billed Amount:
{claim.billed_amount}

Paid Amount:
{claim.paid_amount}

Denial Reason:
{claim.denial_reason}

Write an appeal that includes:
- A summary of the claim status
- The reason for appeal
- Requested action from the payer
"""

        return await self.ai.generate(prompt)
