from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.appeal import Appeal, AppealStatus
from app.models.claim import Claim
from app.models.denial import Denial
from app.models.payer import Payer
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.models.user import User
from app.repositories.denial_code_repository import DenialCodeRepository

# Terminal, payer-decided outcomes for an appeal — used to compute
# payer-perspective acceptance/success rates (distinct from the dashboard's
# existing get_ai_success_rate(), which measures internal AI-recommendation
# acceptance by specialists, not payer decisions).
_APPEAL_OUTCOME_STATUSES = [AppealStatus.ACCEPTED, AppealStatus.REJECTED, AppealStatus.DENIED]

# Recovery cases still considered "outstanding" (not yet resolved one way
# or the other) — the denominator for outstanding recoverable revenue.
_OUTSTANDING_STATUSES = [RecoveryStatus.OPEN, RecoveryStatus.IN_PROGRESS, RecoveryStatus.APPEALED]

_DEFAULT_RESOLUTION_DAYS = 30  # fallback when the denial code isn't in the KB


def _naive(dt: datetime) -> datetime:
    """Strip tzinfo for arithmetic/comparisons — Postgres returns aware
    datetimes for DateTime(timezone=True) columns, but SQLite (used in
    tests) always returns naive ones. Normalizing to naive keeps the same
    bucketing/comparison logic correct on both."""
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


class AnalyticsRepository:
    """Aggregate queries that power the analytics section of the dashboard."""

    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def denial_breakdown(self) -> list[dict]:
        """Count of denials grouped by denial_type."""
        rows = (
            self.db.query(
                Denial.denial_type.label("type"),
                func.count(Denial.id).label("count"),
            )
            .filter(Denial.organization_id == self.organization_id)
            .group_by(Denial.denial_type)
            .all()
        )
        return [{"type": str(r.type), "count": r.count} for r in rows]

    def recovery_by_payer(self) -> list[dict]:
        """Estimated recovery total grouped by payer."""
        rows = (
            self.db.query(
                Payer.name.label("payer"),
                func.sum(RecoveryCase.estimated_value).label("estimated"),
                func.count(RecoveryCase.id).label("cases"),
            )
            .join(Claim, RecoveryCase.claim_id == Claim.id)
            .join(Payer, Claim.payer_id == Payer.id)
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status.in_([RecoveryStatus.OPEN, RecoveryStatus.IN_PROGRESS]),
            )
            .group_by(Payer.name)
            .order_by(func.sum(RecoveryCase.estimated_value).desc())
            .all()
        )
        return [
            {"payer": r.payer, "estimated_recovery": float(r.estimated or 0), "cases": r.cases}
            for r in rows
        ]

    def recovery_rate_summary(self) -> dict:
        """Overall collection rate and average payment ratio."""
        billed = self.db.query(func.sum(Claim.billed_amount)).filter(
            Claim.organization_id == self.organization_id
        ).scalar() or Decimal("0")
        paid = self.db.query(func.sum(Claim.paid_amount)).filter(
            Claim.organization_id == self.organization_id
        ).scalar() or Decimal("0")
        rate = float(paid / billed * 100) if billed > Decimal("0") else 0.0
        return {
            "total_billed": float(billed),
            "total_paid": float(paid),
            "recovery_rate_pct": round(rate, 2),
        }

    # --- Revenue Recovery Intelligence -----------------------------------

    def _avg_days_to_recovery(self) -> float:
        """Average days between a recovery case being opened and its
        payment being received — used for both the executive "Average
        Recovery Time" KPI and the financial "Average Reimbursement Time" KPI
        (same underlying measurement, two names in the source spec)."""
        rows = (
            self.db.query(RecoveryCase.created_at, RecoveryCase.payment_received_at)
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status == RecoveryStatus.RECOVERED,
                RecoveryCase.payment_received_at.isnot(None),
            )
            .all()
        )
        if not rows:
            return 0.0
        days = [(paid_at - created).days for created, paid_at in rows if paid_at and created]
        return round(sum(days) / len(days), 1) if days else 0.0

    def executive_summary(self) -> dict:
        """Top-line KPIs for the executive dashboard: outstanding recoverable
        revenue (with a trend proxy), claims awaiting review, appeals ready
        to submit, org-wide recovery probability, and average recovery time.
        """
        now = datetime.now(UTC)
        thirty_days_ago = now - timedelta(days=30)
        sixty_days_ago = now - timedelta(days=60)

        outstanding = self.db.query(func.sum(RecoveryCase.estimated_value)).filter(
            RecoveryCase.organization_id == self.organization_id,
            RecoveryCase.status.in_(_OUTSTANDING_STATUSES),
        ).scalar() or Decimal("0")

        # Trend proxy: Atlas doesn't keep historical snapshots of the
        # outstanding total, so the trend is approximated by comparing new
        # recoverable value opened in the last 30 days vs the 30 days before
        # that — a real, if imperfect, signal of whether the pipeline is
        # growing or shrinking.
        recent_new = self.db.query(func.sum(RecoveryCase.estimated_value)).filter(
            RecoveryCase.organization_id == self.organization_id,
            RecoveryCase.created_at >= thirty_days_ago,
        ).scalar() or Decimal("0")
        prior_new = self.db.query(func.sum(RecoveryCase.estimated_value)).filter(
            RecoveryCase.organization_id == self.organization_id,
            RecoveryCase.created_at >= sixty_days_ago,
            RecoveryCase.created_at < thirty_days_ago,
        ).scalar() or Decimal("0")
        if prior_new > Decimal("0"):
            trend_pct = float((recent_new - prior_new) / prior_new * 100)
        else:
            trend_pct = 100.0 if recent_new > Decimal("0") else 0.0

        # "Awaiting review" = flagged (denied/pending) claims nobody has
        # picked up yet — distinct from get_claims_requiring_attention(),
        # which doesn't care about assignment.
        claims_awaiting_review = (
            self.db.query(func.count(Claim.id))
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.status.in_(["denied", "pending"]),
                Claim.assigned_user_id.is_(None),
            )
            .scalar()
            or 0
        )

        # "Ready" = human-approved and just waiting to be submitted.
        appeals_ready = (
            self.db.query(func.count(Appeal.id))
            .filter(
                Appeal.organization_id == self.organization_id,
                Appeal.status == AppealStatus.APPROVED,
            )
            .scalar()
            or 0
        )

        avg_probability = (
            self.db.query(func.avg(Claim.recovery_probability))
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.recovery_probability.isnot(None),
            )
            .scalar()
        )

        return {
            "outstanding_recoverable_revenue": float(outstanding),
            "outstanding_recoverable_revenue_trend_pct": round(trend_pct, 1),
            "claims_awaiting_review": claims_awaiting_review,
            "appeals_ready": appeals_ready,
            "recovery_probability_pct": round(float(avg_probability), 1)
            if avg_probability is not None
            else 0.0,
            "avg_recovery_time_days": self._avg_days_to_recovery(),
        }

    def financial_kpis(self) -> dict:
        """Leadership-level financial metrics for the org."""
        gross_charges = self.db.query(func.sum(Claim.billed_amount)).filter(
            Claim.organization_id == self.organization_id
        ).scalar() or Decimal("0")
        denied_revenue = self.db.query(func.sum(Claim.billed_amount)).filter(
            Claim.organization_id == self.organization_id, Claim.status == "denied"
        ).scalar() or Decimal("0")
        recoverable_revenue = self.db.query(func.sum(RecoveryCase.estimated_value)).filter(
            RecoveryCase.organization_id == self.organization_id,
            RecoveryCase.status.in_([RecoveryStatus.OPEN, RecoveryStatus.IN_PROGRESS]),
        ).scalar() or Decimal("0")
        recovered_revenue = self.db.query(func.sum(RecoveryCase.recovered_amount)).filter(
            RecoveryCase.organization_id == self.organization_id,
            RecoveryCase.recovered_amount.isnot(None),
        ).scalar() or Decimal("0")
        atlas_fees = self.db.query(func.sum(RecoveryCase.atlas_fee)).filter(
            RecoveryCase.organization_id == self.organization_id,
            RecoveryCase.atlas_fee.isnot(None),
        ).scalar() or Decimal("0")
        net_recovered_revenue = recovered_revenue - atlas_fees

        outcomes = (
            self.db.query(Appeal.status, func.count(Appeal.id))
            .filter(
                Appeal.organization_id == self.organization_id,
                Appeal.status.in_(_APPEAL_OUTCOME_STATUSES),
            )
            .group_by(Appeal.status)
            .all()
        )
        outcome_counts = dict(outcomes)
        total_outcomes = sum(outcome_counts.values())
        accepted = outcome_counts.get(AppealStatus.ACCEPTED, 0)
        appeal_success_rate_pct = (
            round(accepted / total_outcomes * 100, 1) if total_outcomes else 0.0
        )

        cost_per_recovered_dollar = (
            round(float(atlas_fees / recovered_revenue), 4)
            if recovered_revenue > Decimal("0")
            else 0.0
        )

        return {
            "gross_charges": float(gross_charges),
            "denied_revenue": float(denied_revenue),
            "recoverable_revenue": float(recoverable_revenue),
            "recovered_revenue": float(recovered_revenue),
            "net_recovered_revenue": float(net_recovered_revenue),
            "appeal_success_rate_pct": appeal_success_rate_pct,
            "avg_reimbursement_time_days": self._avg_days_to_recovery(),
            "cost_per_recovered_dollar": cost_per_recovered_dollar,
        }

    def appeal_dashboard(self) -> dict:
        """Sprint 12 Appeal Dashboard — the five manager-facing numbers:
        appeals generated today, ready for submission, waiting on documents,
        waiting on approval, and the estimated recoverable revenue still
        tied up in in-flight appeals."""
        today = datetime.utcnow().date()
        day_start = datetime(today.year, today.month, today.day)
        day_end = day_start + timedelta(days=1)

        generated_today = (
            self.db.query(func.count(Appeal.id))
            .filter(
                Appeal.organization_id == self.organization_id,
                Appeal.created_at >= day_start,
                Appeal.created_at < day_end,
            )
            .scalar()
            or 0
        )
        ready_for_submission = (
            self.db.query(func.count(Appeal.id))
            .filter(
                Appeal.organization_id == self.organization_id,
                Appeal.status == AppealStatus.APPROVED,
            )
            .scalar()
            or 0
        )
        waiting_approval = (
            self.db.query(func.count(Appeal.id))
            .filter(
                Appeal.organization_id == self.organization_id,
                Appeal.status == AppealStatus.REVIEW,
            )
            .scalar()
            or 0
        )
        waiting_documents = (
            self.db.query(Appeal.id, Appeal.missing_documents)
            .filter(
                Appeal.organization_id == self.organization_id,
                Appeal.missing_documents.isnot(None),
            )
            .all()
        )
        waiting_documents_count = sum(1 for _id, docs in waiting_documents if docs)

        in_flight_statuses = [
            AppealStatus.DRAFT,
            AppealStatus.REVIEW,
            AppealStatus.APPROVED,
            AppealStatus.SUBMITTED,
        ]
        estimated_recoverable = (
            self.db.query(func.sum(Claim.billed_amount - Claim.paid_amount))
            .join(Appeal, Appeal.claim_id == Claim.id)
            .filter(
                Appeal.organization_id == self.organization_id,
                Appeal.status.in_(in_flight_statuses),
            )
            .scalar()
        ) or Decimal("0")

        return {
            "appeals_generated_today": generated_today,
            "ready_for_submission": ready_for_submission,
            "waiting_documents": waiting_documents_count,
            "waiting_approval": waiting_approval,
            "estimated_recoverable_revenue": float(estimated_recoverable),
        }

    def payer_performance(self) -> list[dict]:
        """Per-payer performance profile: how much they deny, how much of
        it Atlas recovers, how long it takes, and their most common denial."""
        base_claims = (
            self.db.query(
                Payer.id.label("payer_id"),
                Payer.name.label("payer"),
                func.count(Claim.id).label("denied_claims"),
                func.sum(Claim.billed_amount).label("billed"),
                func.sum(Claim.paid_amount).label("paid"),
            )
            .join(Claim, Claim.payer_id == Payer.id)
            .filter(
                Payer.organization_id == self.organization_id,
                Claim.status == "denied",
            )
            .group_by(Payer.id, Payer.name)
            .all()
        )
        if not base_claims:
            return []

        # Average days-to-recovery per payer.
        recovery_rows = (
            self.db.query(Payer.id, RecoveryCase.created_at, RecoveryCase.payment_received_at)
            .join(Claim, RecoveryCase.claim_id == Claim.id)
            .join(Payer, Claim.payer_id == Payer.id)
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status == RecoveryStatus.RECOVERED,
                RecoveryCase.payment_received_at.isnot(None),
            )
            .all()
        )
        days_by_payer: dict[int, list[int]] = defaultdict(list)
        for payer_id, created, paid_at in recovery_rows:
            if created and paid_at:
                days_by_payer[payer_id].append((paid_at - created).days)

        # Most common denial code per payer (computed in Python — a mode
        # aggregation isn't portable across SQLite/Postgres without raw SQL).
        denial_rows = (
            self.db.query(Payer.id, Denial.denial_code)
            .join(Claim, Denial.claim_id == Claim.id)
            .join(Payer, Claim.payer_id == Payer.id)
            .filter(Denial.organization_id == self.organization_id)
            .all()
        )
        codes_by_payer: dict[int, Counter] = defaultdict(Counter)
        for payer_id, code in denial_rows:
            if code:
                codes_by_payer[payer_id][code] += 1

        results = []
        for row in base_claims:
            billed = row.billed or Decimal("0")
            paid = row.paid or Decimal("0")
            recovery_rate_pct = (
                round(float(paid / billed * 100), 1) if billed > Decimal("0") else 0.0
            )
            days = days_by_payer.get(row.payer_id, [])
            avg_days = round(sum(days) / len(days), 1) if days else 0.0
            top_codes = codes_by_payer.get(row.payer_id)
            most_common_denial_code = top_codes.most_common(1)[0][0] if top_codes else None
            avg_revenue_lost = (
                round(float((billed - paid) / row.denied_claims), 2) if row.denied_claims else 0.0
            )

            results.append(
                {
                    "payer_id": row.payer_id,
                    "payer": row.payer,
                    "denied_claims": row.denied_claims,
                    "recovery_rate_pct": recovery_rate_pct,
                    "avg_days_to_recovery": avg_days,
                    "most_common_denial_code": most_common_denial_code,
                    "avg_revenue_lost": avg_revenue_lost,
                }
            )

        return sorted(results, key=lambda r: r["denied_claims"], reverse=True)

    def analyst_performance(self) -> list[dict]:
        """Per-analyst productivity/effectiveness metrics, attributed via
        Claim.assigned_user_id (claims/revenue) and Appeal.submitted_by
        (appeal outcomes) — the only two user-attribution fields that exist
        on the claim/appeal workflow today."""
        user_ids = set()
        for (uid,) in (
            self.db.query(Claim.assigned_user_id)
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.assigned_user_id.isnot(None),
            )
            .distinct()
        ):
            user_ids.add(uid)
        for (uid,) in (
            self.db.query(Appeal.submitted_by)
            .filter(
                Appeal.organization_id == self.organization_id,
                Appeal.submitted_by.isnot(None),
            )
            .distinct()
        ):
            user_ids.add(uid)

        if not user_ids:
            return []

        users = {u.id: u for u in self.db.query(User).filter(User.id.in_(user_ids)).all()}

        results = []
        for uid in user_ids:
            user = users.get(uid)
            if user is None:
                continue

            claims_assigned = (
                self.db.query(func.count(Claim.id))
                .filter(
                    Claim.organization_id == self.organization_id, Claim.assigned_user_id == uid
                )
                .scalar()
                or 0
            )
            revenue_recovered = self.db.query(func.sum(RecoveryCase.recovered_amount)).join(
                Claim, RecoveryCase.claim_id == Claim.id
            ).filter(
                RecoveryCase.organization_id == self.organization_id,
                Claim.assigned_user_id == uid,
                RecoveryCase.recovered_amount.isnot(None),
            ).scalar() or Decimal("0")

            appeal_outcomes = (
                self.db.query(Appeal.status, func.count(Appeal.id))
                .filter(
                    Appeal.organization_id == self.organization_id,
                    Appeal.submitted_by == uid,
                    Appeal.status.in_(_APPEAL_OUTCOME_STATUSES + [AppealStatus.SUBMITTED]),
                )
                .group_by(Appeal.status)
                .all()
            )
            outcome_counts = dict(appeal_outcomes)
            appeals_completed = sum(outcome_counts.values())
            terminal_total = sum(outcome_counts.get(s, 0) for s in _APPEAL_OUTCOME_STATUSES)
            accepted = outcome_counts.get(AppealStatus.ACCEPTED, 0)
            success_rate_pct = round(accepted / terminal_total * 100, 1) if terminal_total else 0.0

            resolution_rows = (
                self.db.query(Appeal.created_at, Appeal.submitted_at)
                .filter(
                    Appeal.organization_id == self.organization_id,
                    Appeal.submitted_by == uid,
                    Appeal.submitted_at.isnot(None),
                )
                .all()
            )
            resolution_days = [
                (submitted - created).days
                for created, submitted in resolution_rows
                if created and submitted
            ]
            avg_resolution_time_days = (
                round(sum(resolution_days) / len(resolution_days), 1) if resolution_days else 0.0
            )

            results.append(
                {
                    "user_id": uid,
                    "name": f"{user.first_name} {user.last_name}",
                    "appeals_completed": appeals_completed,
                    "revenue_recovered": float(revenue_recovered),
                    "success_rate_pct": success_rate_pct,
                    "avg_resolution_time_days": avg_resolution_time_days,
                    "claims_assigned": claims_assigned,
                }
            )

        return sorted(results, key=lambda r: r["revenue_recovered"], reverse=True)

    def revenue_forecast(self, months: int = 3) -> list[dict]:
        """Predicted cash recovery by month, computed from currently-open
        recovery cases: expected amount = estimated_value * historical
        success rate for that denial code (falls back to the org's overall
        recovery rate if the code isn't in the knowledge base), bucketed by
        an expected resolution month = case opened date + typical
        resolution days for that denial code (falls back to 30 days)."""
        now = datetime.now(UTC)
        now = _naive(now)
        current_month_start = datetime(now.year, now.month, 1)

        overall = self.recovery_rate_summary()
        fallback_rate_pct = overall["recovery_rate_pct"] or 0.0

        cases = (
            self.db.query(RecoveryCase)
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status.in_(_OUTSTANDING_STATUSES),
            )
            .all()
        )

        denial_repo = DenialCodeRepository(self.db)
        buckets: dict[str, float] = defaultdict(float)

        for case in cases:
            denial = (
                self.db.query(Denial)
                .filter(
                    Denial.claim_id == case.claim_id, Denial.organization_id == self.organization_id
                )
                .order_by(Denial.id.desc())
                .first()
            )
            entry = denial_repo.get_by_code(denial.denial_code) if denial else None

            rate_pct = (
                float(entry.typical_recovery_rate)
                if entry and entry.typical_recovery_rate is not None
                else fallback_rate_pct
            )
            resolution_days = (
                entry.typical_resolution_days
                if entry and entry.typical_resolution_days
                else _DEFAULT_RESOLUTION_DAYS
            )

            created = _naive(case.created_at) if case.created_at else now
            expected_date = created + timedelta(days=resolution_days)
            if expected_date < current_month_start:
                expected_date = current_month_start

            month_key = f"{expected_date.year}-{expected_date.month:02d}"
            expected_amount = float(case.estimated_value or Decimal("0")) * (rate_pct / 100)
            buckets[month_key] += expected_amount

        # Always return exactly `months` consecutive buckets starting this
        # month, even if some have zero predicted recovery.
        forecast = []
        month_cursor = current_month_start
        for _ in range(months):
            key = f"{month_cursor.year}-{month_cursor.month:02d}"
            forecast.append({"month": key, "expected_recovery": round(buckets.get(key, 0.0), 2)})
            # Advance to the first day of next month.
            if month_cursor.month == 12:
                month_cursor = month_cursor.replace(year=month_cursor.year + 1, month=1)
            else:
                month_cursor = month_cursor.replace(month=month_cursor.month + 1)

        return forecast

    def generate_insights(self) -> list[dict]:
        """Rule-based, auto-generated natural-language findings — surfaces
        what changed instead of making users interpret raw charts."""
        now = datetime.now(UTC)
        this_week_start = now - timedelta(days=7)
        last_week_start = now - timedelta(days=14)

        insights: list[dict] = []

        # 1. Denial-type trend: this week vs last week.
        this_week_counts = self._denial_type_counts(this_week_start, now)
        last_week_counts = self._denial_type_counts(last_week_start, this_week_start)
        for denial_type, this_count in this_week_counts.items():
            last_count = last_week_counts.get(denial_type, 0)
            if last_count >= 3 and this_count > last_count:
                pct = round((this_count - last_count) / last_count * 100)
                if pct >= 10:
                    insights.append(
                        {
                            "category": "denial_trend",
                            "message": f"{denial_type.replace('_', ' ').title()} denials increased by {pct}% this week.",
                        }
                    )

        # 2. Payer appeal-acceptance-rate trend: this month vs last month.
        insights.extend(self._payer_acceptance_trend_insights(now))

        # 3. Concentrated opportunity: top 20 open recovery cases by score.
        top_case_ids = [
            row.id
            for row in (
                self.db.query(RecoveryCase.id)
                .filter(
                    RecoveryCase.organization_id == self.organization_id,
                    RecoveryCase.status == RecoveryStatus.OPEN,
                )
                .order_by(RecoveryCase.recovery_score.desc())
                .limit(20)
                .all()
            )
        ]
        if top_case_ids:
            total = self.db.query(func.sum(RecoveryCase.estimated_value)).filter(
                RecoveryCase.id.in_(top_case_ids)
            ).scalar() or Decimal("0")
            if total > Decimal("0"):
                insights.append(
                    {
                        "category": "opportunity",
                        "message": (
                            f"Recovering the top {len(top_case_ids)} pending claims could generate "
                            f"approximately ${float(total):,.0f}."
                        ),
                    }
                )

        return insights

    def _denial_type_counts(self, start: datetime, end: datetime) -> dict[str, int]:
        rows = (
            self.db.query(Denial.denial_type, func.count(Denial.id))
            .filter(
                Denial.organization_id == self.organization_id,
                Denial.created_at >= start,
                Denial.created_at < end,
            )
            .group_by(Denial.denial_type)
            .all()
        )
        return {
            str(denial_type.value if hasattr(denial_type, "value") else denial_type): count
            for denial_type, count in rows
        }

    def _payer_acceptance_trend_insights(self, now: datetime) -> list[dict]:
        this_month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
        if now.month == 1:
            last_month_start = datetime(now.year - 1, 12, 1, tzinfo=UTC)
        else:
            last_month_start = datetime(now.year, now.month - 1, 1, tzinfo=UTC)

        def _acceptance_by_payer(start: datetime, end: datetime) -> dict[str, tuple[int, int]]:
            rows = (
                self.db.query(Payer.name, Appeal.status, func.count(Appeal.id))
                .join(Claim, Appeal.claim_id == Claim.id)
                .join(Payer, Claim.payer_id == Payer.id)
                .filter(
                    Appeal.organization_id == self.organization_id,
                    Appeal.status.in_(_APPEAL_OUTCOME_STATUSES),
                    Appeal.updated_at >= start,
                    Appeal.updated_at < end,
                )
                .group_by(Payer.name, Appeal.status)
                .all()
            )
            totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [accepted, total]
            for payer_name, status, count in rows:
                totals[payer_name][1] += count
                if status == AppealStatus.ACCEPTED:
                    totals[payer_name][0] += count
            return {payer: (accepted, total) for payer, (accepted, total) in totals.items()}

        this_month = _acceptance_by_payer(this_month_start, now)
        last_month = _acceptance_by_payer(last_month_start, this_month_start)

        insights = []
        for payer, (accepted, total) in this_month.items():
            if total < 3:
                continue
            prior = last_month.get(payer)
            if not prior or prior[1] < 3:
                continue
            old_pct = round(prior[0] / prior[1] * 100)
            new_pct = round(accepted / total * 100)
            if old_pct - new_pct >= 10:
                insights.append(
                    {
                        "category": "payer_trend",
                        "message": f"{payer} has reduced its appeal acceptance rate from {old_pct}% to {new_pct}%.",
                    }
                )
        return insights
