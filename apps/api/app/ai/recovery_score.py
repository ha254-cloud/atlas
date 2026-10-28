from app.ai.engine import AIEngine


class RecoveryScore:
    def __init__(self):
        self.ai = AIEngine()

    async def score(self, claim):
        prompt = f"""
Estimate the recovery potential for this healthcare claim.

Claim Number:
{claim.claim_number}

Status:
{claim.status}

Billed Amount:
{claim.billed_amount}

Paid Amount:
{claim.paid_amount}

Provide a score from 0 to 100 and a short reason.
"""

        return await self.ai.generate(prompt)
