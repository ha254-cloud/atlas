from collections import defaultdict
from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ai_call_log import AICallLog
from app.models.claim import Claim
from app.models.integration import Integration, IntegrationStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.recovery import Recovery
from app.organizations.models import Organization


class PlatformAdminRepository:
    """Explicitly global, aggregate-only queries for Atlas platform operators."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _money(rows) -> list[dict]:
        return [
            {"currency": currency, "amount": amount or Decimal("0")} for currency, amount in rows
        ]

    def customer_metrics(self) -> dict:
        organizations = self.db.query(Organization).all()
        return {
            "total": len(organizations),
            "active": sum(item.is_active and item.status == "active" for item in organizations),
            "trial": sum(item.subscription_plan == "trial" for item in organizations),
            "suspended": sum(
                not item.is_active or item.status == "suspended" for item in organizations
            ),
        }

    def platform_metrics(self) -> dict:
        today_start = datetime.combine(date.today(), time.min, tzinfo=UTC)
        recovered = self._money(
            self.db.query(Claim.currency, func.sum(Recovery.recovered_amount))
            .join(Claim, Claim.id == Recovery.claim_id)
            .filter(Recovery.verified.is_(True))
            .group_by(Claim.currency)
            .all()
        )
        fees = self._money(
            self.db.query(Claim.currency, func.sum(Recovery.atlas_fee_amount))
            .join(Claim, Claim.id == Recovery.claim_id)
            .filter(Recovery.verified.is_(True))
            .group_by(Claim.currency)
            .all()
        )
        return {
            "claims_processed": self.db.query(Claim).count(),
            "claims_today": self.db.query(Claim).filter(Claim.created_at >= today_start).count(),
            "verified_recovery": recovered,
            "atlas_fees_earned": fees,
        }

    def atlas_revenue_metrics(self) -> dict:
        def totals(*filters) -> list[dict]:
            return self._money(
                self.db.query(Invoice.currency, func.sum(Invoice.total_amount))
                .filter(*filters)
                .group_by(Invoice.currency)
                .all()
            )

        return {
            "paid_invoices": totals(Invoice.status == InvoiceStatus.PAID),
            "outstanding_invoices": totals(Invoice.status == InvoiceStatus.SENT),
            "overdue_invoices": totals(
                Invoice.status == InvoiceStatus.SENT,
                Invoice.due_date < date.today(),
            ),
        }

    def ai_operations(self) -> dict:
        today_start = datetime.combine(date.today(), time.min, tzinfo=UTC)
        row = (
            self.db.query(
                func.count(AICallLog.id),
                func.coalesce(func.sum(AICallLog.input_tokens), 0)
                + func.coalesce(func.sum(AICallLog.output_tokens), 0),
                func.coalesce(func.sum(AICallLog.cost_usd), 0),
                func.avg(AICallLog.duration_ms),
            )
            .filter(AICallLog.created_at >= today_start)
            .one()
        )
        return {
            "requests_today": row[0],
            "tokens_today": row[1],
            "estimated_cost_usd_today": row[2],
            "average_latency_ms_today": float(row[3]) if row[3] is not None else None,
        }

    def integration_error_count(self) -> int:
        return (
            self.db.query(Integration).filter(Integration.status == IntegrationStatus.ERROR).count()
        )

    def alerts(self) -> list[dict]:
        alerts: list[dict] = []
        overdue = (
            self.db.query(Invoice, Organization.name)
            .join(Organization, Organization.id == Invoice.organization_id)
            .filter(
                Invoice.status == InvoiceStatus.SENT,
                Invoice.due_date < date.today(),
            )
            .order_by(Invoice.due_date)
            .limit(5)
            .all()
        )
        for invoice, organization_name in overdue:
            alerts.append(
                {
                    "severity": "warning",
                    "organization_id": invoice.organization_id,
                    "message": (
                        f"{organization_name} invoice {invoice.invoice_number} is overdue: "
                        f"{invoice.currency} {invoice.total_amount:,.2f}"
                    ),
                }
            )

        integrations = (
            self.db.query(Integration, Organization.name)
            .join(Organization, Organization.id == Integration.organization_id)
            .filter(Integration.status == IntegrationStatus.ERROR)
            .order_by(Integration.updated_at.desc())
            .limit(5)
            .all()
        )
        for integration, organization_name in integrations:
            alerts.append(
                {
                    "severity": "error",
                    "organization_id": integration.organization_id,
                    "message": f"{integration.provider} integration is failing for {organization_name}",
                }
            )
        return alerts

    def hospitals(self) -> list[dict]:
        claim_counts = dict(
            self.db.query(Claim.organization_id, func.count(Claim.id))
            .group_by(Claim.organization_id)
            .all()
        )
        recovery_by_org: dict[int, list[dict]] = defaultdict(list)
        recovery_rows = (
            self.db.query(
                Recovery.organization_id,
                Claim.currency,
                func.sum(Recovery.recovered_amount),
            )
            .join(Claim, Claim.id == Recovery.claim_id)
            .filter(Recovery.verified.is_(True))
            .group_by(Recovery.organization_id, Claim.currency)
            .all()
        )
        for organization_id, currency, amount in recovery_rows:
            recovery_by_org[organization_id].append({"currency": currency, "amount": amount})

        revenue_by_org: dict[int, list[dict]] = defaultdict(list)
        revenue_rows = (
            self.db.query(Invoice.organization_id, Invoice.currency, func.sum(Invoice.total_amount))
            .filter(Invoice.status == InvoiceStatus.PAID)
            .group_by(Invoice.organization_id, Invoice.currency)
            .all()
        )
        for organization_id, currency, amount in revenue_rows:
            revenue_by_org[organization_id].append({"currency": currency, "amount": amount})

        return [
            {
                "id": organization.id,
                "name": organization.name,
                "status": organization.status,
                "subscription_plan": organization.subscription_plan,
                "currency": organization.currency,
                "claim_count": claim_counts.get(organization.id, 0),
                "verified_recovery": recovery_by_org[organization.id],
                "atlas_revenue": revenue_by_org[organization.id],
                "created_at": organization.created_at,
            }
            for organization in self.db.query(Organization).order_by(Organization.name).all()
        ]
