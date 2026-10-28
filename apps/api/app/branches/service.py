from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.branches.models import Branch, BranchMembership, Department
from app.branches.repository import BranchRepository
from app.branches.schemas import (
    BranchCreate,
    BranchMembershipCreate,
    BranchUpdate,
    DepartmentCreate,
)
from app.governance.audit.service import AuditService
from app.models.user import User, UserRole

ORG_LEVEL_BRANCH_ROLES = {UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER}


class BranchService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repository = BranchRepository(db, organization_id)
        self.audit = AuditService(db)

    def list_for_user(self, user: User) -> list[Branch]:
        if user.organization_id != self.organization_id:
            return []
        if user.is_superuser or user.role in ORG_LEVEL_BRANCH_ROLES:
            return self.repository.list_branches()
        return self.repository.list_for_user(user.id)

    def require_access(self, branch_id: int, user: User) -> Branch:
        branch = self.repository.get_branch(branch_id)
        if branch is None or branch not in self.list_for_user(user):
            raise ValueError("Branch not found")
        return branch

    def validate_claim_scope(
        self, branch_id: int | None, department_id: int | None
    ) -> tuple[Branch | None, Department | None]:
        if branch_id is None:
            if department_id is not None:
                raise ValueError("department_id requires branch_id")
            return None, None
        branch = self.repository.get_branch(branch_id)
        if branch is None or not branch.is_active:
            raise ValueError("Branch not found")
        department = None
        if department_id is not None:
            department = self.repository.get_department(branch_id, department_id)
            if department is None or not department.is_active:
                raise ValueError("Department not found")
        return branch, department

    def create_branch(
        self, payload: BranchCreate, *, actor_id: int, correlation_id: str | None
    ) -> Branch:
        branch = Branch(
            organization_id=self.organization_id,
            name=payload.name.strip(),
            code=payload.code,
        )
        self.db.add(branch)
        self.db.flush()
        self.audit.log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=AuditAction.BRANCH_CREATED,
            entity="branch",
            entity_id=branch.id,
            correlation_id=correlation_id,
            reason=payload.reason,
            after_state={"name": branch.name, "code": branch.code, "is_active": True},
        )
        self.db.commit()
        self.db.refresh(branch)
        return branch

    def update_branch(
        self,
        branch_id: int,
        payload: BranchUpdate,
        *,
        actor_id: int,
        correlation_id: str | None,
    ) -> Branch:
        branch = self.repository.get_branch(branch_id)
        if branch is None:
            raise ValueError("Branch not found")
        before = {"name": branch.name, "is_active": branch.is_active}
        fields = payload.model_dump(exclude={"reason"}, exclude_unset=True)
        for field, value in fields.items():
            setattr(branch, field, value.strip() if isinstance(value, str) else value)
        self.audit.log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=AuditAction.BRANCH_UPDATED,
            entity="branch",
            entity_id=branch.id,
            correlation_id=correlation_id,
            reason=payload.reason,
            before_state=before,
            after_state={"name": branch.name, "is_active": branch.is_active},
        )
        self.db.commit()
        self.db.refresh(branch)
        return branch

    def create_department(
        self,
        branch_id: int,
        payload: DepartmentCreate,
        *,
        actor_id: int,
        correlation_id: str | None,
    ) -> Department:
        if self.repository.get_branch(branch_id) is None:
            raise ValueError("Branch not found")
        department = Department(
            organization_id=self.organization_id,
            branch_id=branch_id,
            name=payload.name.strip(),
            code=payload.code,
        )
        self.db.add(department)
        self.db.flush()
        self.audit.log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=AuditAction.DEPARTMENT_CREATED,
            entity="department",
            entity_id=department.id,
            correlation_id=correlation_id,
            reason=payload.reason,
            after_state={"branch_id": branch_id, "name": department.name, "code": department.code},
        )
        self.db.commit()
        self.db.refresh(department)
        return department

    def assign_membership(
        self,
        branch_id: int,
        payload: BranchMembershipCreate,
        *,
        actor_id: int,
        correlation_id: str | None,
    ) -> BranchMembership:
        if self.repository.get_branch(branch_id) is None:
            raise ValueError("Branch not found")
        user = (
            self.db.query(User)
            .filter(
                User.id == payload.user_id,
                User.organization_id == self.organization_id,
            )
            .first()
        )
        if user is None:
            raise ValueError("User not found")
        membership = BranchMembership(
            organization_id=self.organization_id,
            branch_id=branch_id,
            user_id=user.id,
            role_template=payload.role_template.strip(),
        )
        self.db.add(membership)
        self.db.flush()
        self.audit.log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=AuditAction.BRANCH_MEMBERSHIP_ASSIGNED,
            entity="branch_membership",
            entity_id=membership.id,
            correlation_id=correlation_id,
            reason=payload.reason,
            after_state={
                "branch_id": branch_id,
                "user_id": user.id,
                "role_template": membership.role_template,
            },
        )
        self.db.commit()
        self.db.refresh(membership)
        return membership
