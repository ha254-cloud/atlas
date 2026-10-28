from sqlalchemy.orm import Session

from app.branches.models import Branch, BranchMembership, Department


class BranchRepository:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def list_branches(self) -> list[Branch]:
        return (
            self.db.query(Branch)
            .filter(Branch.organization_id == self.organization_id)
            .order_by(Branch.name, Branch.id)
            .all()
        )

    def list_for_user(self, user_id: int) -> list[Branch]:
        return (
            self.db.query(Branch)
            .join(BranchMembership, BranchMembership.branch_id == Branch.id)
            .filter(
                Branch.organization_id == self.organization_id,
                Branch.is_active.is_(True),
                BranchMembership.organization_id == self.organization_id,
                BranchMembership.user_id == user_id,
                BranchMembership.is_active.is_(True),
            )
            .order_by(Branch.name, Branch.id)
            .all()
        )

    def get_branch(self, branch_id: int) -> Branch | None:
        return (
            self.db.query(Branch)
            .filter(
                Branch.id == branch_id,
                Branch.organization_id == self.organization_id,
            )
            .first()
        )

    def get_department(self, branch_id: int, department_id: int) -> Department | None:
        return (
            self.db.query(Department)
            .filter(
                Department.id == department_id,
                Department.branch_id == branch_id,
                Department.organization_id == self.organization_id,
            )
            .first()
        )

    def list_departments(self, branch_id: int) -> list[Department]:
        return (
            self.db.query(Department)
            .filter(
                Department.branch_id == branch_id,
                Department.organization_id == self.organization_id,
            )
            .order_by(Department.name, Department.id)
            .all()
        )

    def list_memberships(self, branch_id: int) -> list[BranchMembership]:
        return (
            self.db.query(BranchMembership)
            .filter(
                BranchMembership.branch_id == branch_id,
                BranchMembership.organization_id == self.organization_id,
            )
            .order_by(BranchMembership.id)
            .all()
        )
