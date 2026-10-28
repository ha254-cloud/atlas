from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.mcp.auth import resolve_api_key
from app.models.api_key import APIKey

_api_key_header = APIKeyHeader(name="X-Atlas-API-Key", auto_error=False)


def get_mcp_context(
    raw_key: str = Security(_api_key_header),
    db: Session = Depends(get_db),
) -> APIKey:
    """
    Validate the MCP API key and return the resolved APIKey record.
    Every MCP endpoint must declare this dependency — it ensures:
      1. The request is authenticated.
      2. The organization_id is injected from the key, never from the client.
    """
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Atlas-API-Key header",
        )

    api_key = resolve_api_key(db, raw_key)

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )

    return api_key
