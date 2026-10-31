"""Add claims list/search performance indexes.

The claims list endpoint filters by organization_id and orders by
created_at descending, and supports free-text search (ILIKE) on
claim_number, patient name, and payer name. Those access patterns had no
supporting indexes, forcing sequential scans as data grows. This adds:

* a composite (organization_id, created_at) index for the paginated,
  org-scoped list query's filter + sort.
* pg_trgm GIN indexes on the columns used in ILIKE search, since a
  leading-wildcard LIKE/ILIKE pattern cannot use a standard B-tree index.

Revision ID: d4f7a2c6e9b3
Revises: 6b8f1e3d9a2c
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4f7a2c6e9b3"
down_revision: str | Sequence[str] | None = "6b8f1e3d9a2c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_index(
        "ix_claims_organization_id_created_at",
        "claims",
        ["organization_id", "created_at"],
    )

    op.create_index(
        "ix_claims_claim_number_trgm",
        "claims",
        ["claim_number"],
        postgresql_using="gin",
        postgresql_ops={"claim_number": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_patients_first_name_trgm",
        "patients",
        ["first_name"],
        postgresql_using="gin",
        postgresql_ops={"first_name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_patients_last_name_trgm",
        "patients",
        ["last_name"],
        postgresql_using="gin",
        postgresql_ops={"last_name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_payers_name_trgm",
        "payers",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_payers_name_trgm", table_name="payers")
    op.drop_index("ix_patients_last_name_trgm", table_name="patients")
    op.drop_index("ix_patients_first_name_trgm", table_name="patients")
    op.drop_index("ix_claims_claim_number_trgm", table_name="claims")
    op.drop_index("ix_claims_organization_id_created_at", table_name="claims")
    # pg_trgm extension is left in place intentionally: other code/indexes in
    # this database may depend on it, and dropping it is not safe to infer.
