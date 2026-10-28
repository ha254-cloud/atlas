from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.mcp.schemas.responses import MCPResponse


class BaseTool(ABC):
    """
    Every MCP tool must implement `execute()`.
    Tools never own business logic — they delegate to services.

    Dependency injection pattern:
        execute(db, organization_id, **params) -> MCPResponse
    """

    name: str

    @abstractmethod
    async def execute(
        self,
        db: Session,
        organization_id: int,
        **params,
    ) -> MCPResponse: ...

    def _ok(self, data: dict) -> MCPResponse:
        return MCPResponse(success=True, tool=self.name, data=data)

    def _err(self, message: str) -> MCPResponse:
        return MCPResponse(success=False, tool=self.name, data={}, error=message)
