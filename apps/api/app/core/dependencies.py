from fastapi import Depends, HTTPException, status

from app.models.user import User
from app.security.dependencies import get_current_user


def get_current_organization(
    current_user: User = Depends(get_current_user),
) -> int:
    """
    Extract the organization_id from the authenticated user.
    Never trust the client to supply an organization_id.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with an organization",
        )
    return current_user.organization_id
