from typing import Any

from pydantic import BaseModel


class MCPResponse(BaseModel):
    """
    Every MCP tool returns this exact shape.
    Consistent structure makes client integrations trivial.
    """

    success: bool
    tool: str
    data: dict[str, Any]
    error: str | None = None


class APIKeyCreateResponse(BaseModel):
    """Returned once at key creation — raw key is never stored."""

    id: int
    name: str
    raw_key: str  # shown once; not persisted
    key_prefix: str


class APIKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    is_active: bool
    expires_at: str | None = None
    last_used_at: str | None = None

    class Config:
        orm_mode = True
