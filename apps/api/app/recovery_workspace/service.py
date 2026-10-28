from sqlalchemy.orm import Session

from app.recovery_workspace.repository import RecoveryWorkspaceRepository
from app.recovery_workspace.schemas import (
    WorkspaceCase,
    WorkspaceDenial,
    WorkspaceResponse,
    WorkspaceSummary,
)


class RecoveryWorkspaceService:
    def __init__(self, db: Session, organization_id: int):
        self.repo = RecoveryWorkspaceRepository(db, organization_id)

    def get_workspace(
        self,
        status_filter: list[str] | None = None,
        priority_filter: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> WorkspaceResponse:
        summary_data = self.repo.get_summary()
        cases_data, total = self.repo.get_workspace_cases(
            status_filter=status_filter,
            priority_filter=priority_filter,
            search=search,
            limit=limit,
            offset=offset,
        )

        summary = WorkspaceSummary(**summary_data)

        cases = [
            WorkspaceCase(
                **{k: v for k, v in c.items() if k != "denial"},
                denial=WorkspaceDenial(**c["denial"]) if c.get("denial") else None,
            )
            for c in cases_data
        ]

        return WorkspaceResponse(
            summary=summary,
            cases=cases,
            total=total,
            limit=limit,
            offset=offset,
        )
