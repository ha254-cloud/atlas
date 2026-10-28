from app.ai.engine import AIEngine


class DenialClassifier:
    def __init__(self):
        self.ai = AIEngine()

    async def classify(self, claim):
        prompt = f"""
Classify the denial reason for this healthcare claim.

Claim Number:
{claim.claim_number}

Status:
{claim.status}

Billed Amount:
{claim.billed_amount}

Paid Amount:
{claim.paid_amount}

Please provide a category from the following list:
- Missing Modifier
- Eligibility
- Duplicate Claim
- Prior Authorization
- Coding Error
- Medical Necessity
- Timely Filing
- Documentation Required
- Bundling
- Coordination of Benefits

Explain why this classification was chosen.
"""

        return await self.ai.generate(prompt)
