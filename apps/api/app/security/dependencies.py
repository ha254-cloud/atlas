from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.governance.models import UserSession
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.security.jwt import decode_access_token
from app.security.permissions import ROLE_PERMISSIONS, Permission

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    try:
        payload = decode_access_token(token)

        user_id = payload.get("sub")
        session_id = payload.get("sid")

        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = UserRepository(db).get_by_id(int(user_id))

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise credentials_exception

    if session_id is not None:
        session = (
            db.query(UserSession)
            .filter(
                UserSession.id == session_id,
                UserSession.user_id == user.id,
                UserSession.organization_id == user.organization_id,
            )
            .first()
        )
        expires_at = session.expires_at if session is not None else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if session is None or session.revoked_at is not None or expires_at <= datetime.now(UTC):
            raise credentials_exception

    return user


def require_role(*roles: UserRole):
    """FastAPI dependency factory enforcing role-based access control.
    Usage: current_user: User = Depends(require_role(UserRole.ADMIN))"""

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return dependency


def require_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Atlas platform administrator access is required",
        )
    return current_user


def require_permission(*permissions: Permission):
    """FastAPI dependency factory enforcing fine-grained permission checks.
    Grants access if the user's role has ANY of the listed permissions, or
    if the user is a superuser (bypasses all permission checks).
    Usage: current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS))"""

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user

        allowed = ROLE_PERMISSIONS.get(current_user.role, set())
        if not any(p in allowed for p in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return dependency
