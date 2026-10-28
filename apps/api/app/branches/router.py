from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.branches.schemas import (
    BranchCreate,
    BranchMembershipCreate,
    BranchMembershipRead,
    BranchRead,
    BranchUpdate,
    DepartmentCreate,
    DepartmentRead,
)
from app.branches.service import BranchService
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/branches", tags=["Branches"])


def _not_found(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("", response_model=list[BranchRead])
def list_branches(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_BRANCHES)),
):
    return BranchService(db, organization_id).list_for_user(current_user)


@router.post("", response_model=BranchRead, status_code=201)
def create_branch(
    payload: BranchCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BRANCHES)),
):
    try:
        return BranchService(db, organization_id).create_branch(
            payload,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Branch code already exists") from exc


@router.patch("/{branch_id}", response_model=BranchRead)
def update_branch(
    branch_id: int,
    payload: BranchUpdate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BRANCHES)),
):
    try:
        return BranchService(db, organization_id).update_branch(
            branch_id,
            payload,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
        )
    except ValueError as exc:
        raise _not_found(exc) from exc


@router.get("/{branch_id}/departments", response_model=list[DepartmentRead])
def list_departments(
    branch_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_BRANCHES)),
):
    service = BranchService(db, organization_id)
    try:
        service.require_access(branch_id, current_user)
    except ValueError as exc:
        raise _not_found(exc) from exc
    return service.repository.list_departments(branch_id)


@router.post("/{branch_id}/departments", response_model=DepartmentRead, status_code=201)
def create_department(
    branch_id: int,
    payload: DepartmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BRANCHES)),
):
    try:
        return BranchService(db, organization_id).create_department(
            branch_id,
            payload,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
        )
    except ValueError as exc:
        raise _not_found(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Department code already exists") from exc


@router.get("/{branch_id}/memberships", response_model=list[BranchMembershipRead])
def list_memberships(
    branch_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.MANAGE_BRANCHES)),
):
    service = BranchService(db, organization_id)
    if service.repository.get_branch(branch_id) is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    return service.repository.list_memberships(branch_id)


@router.post("/{branch_id}/memberships", response_model=BranchMembershipRead, status_code=201)
def assign_membership(
    branch_id: int,
    payload: BranchMembershipCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BRANCHES)),
):
    try:
        return BranchService(db, organization_id).assign_membership(
            branch_id,
            payload,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
        )
    except ValueError as exc:
        raise _not_found(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Branch membership already exists") from exc
