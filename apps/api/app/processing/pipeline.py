import time

from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.imports.parser import CSVParser
from app.imports.validators import REQUIRED_COLUMNS
from app.processing.chunker import chunked
from app.processing.exceptions import CSVSchemaError, DuplicateClaimError
from app.processing.processor import ClaimProcessor
from app.processing.progress import ProgressTracker
from app.workflows.service import WorkflowService


class ImportPipeline:
    def __init__(self, db, organization_id: int, batch_size: int = 1000):
        self.db = db
        self.organization_id = organization_id
        self.batch_size = batch_size
        self.parser = CSVParser()
        self.processor = ClaimProcessor(db, organization_id)
        self.progress = ProgressTracker()
        self.publisher = EventPublisher()

    def run(self, filepath: str, on_progress=None) -> dict:
        start = time.perf_counter()

        # Fail fast on a structurally wrong file (e.g. someone uploads a
        # spreadsheet with entirely different columns) instead of processing
        # every row only to reject each one individually for the same reason.
        headers = self.parser.get_headers(filepath)
        missing_columns = [c for c in REQUIRED_COLUMNS if c not in headers]
        if missing_columns:
            raise CSVSchemaError(missing_columns)

        expected_total = self.parser.count_rows(filepath)
        errors: list[dict] = []
        row_number = 0

        if on_progress:
            on_progress(
                {
                    "total": self.progress.total,
                    "successful": self.progress.success,
                    "failed": self.progress.failed,
                    "duplicates": self.progress.duplicates,
                    "expected_total": expected_total,
                }
            )

        for batch in chunked(self.parser.parse(filepath), self.batch_size):
            for row in batch:
                row_number += 1
                try:
                    # Each row runs inside its own SAVEPOINT so one bad row
                    # only unwinds its own work, not the whole in-flight batch.
                    with self.db.begin_nested():
                        claim = self.processor.process(row)
                    # Recovery Workflow Engine: start tracking this claim's
                    # lifecycle now that its SAVEPOINT has been released —
                    # WorkflowService.transition() commits the session,
                    # which must never happen while a SAVEPOINT is active.
                    WorkflowService(self.db, self.organization_id).start_workflow(claim)
                    self.publisher.publish(
                        EventType.CLAIM_IMPORTED,
                        {
                            "claim_id": claim.id,
                            "claim_number": claim.claim_number,
                            "organization_id": self.organization_id,
                        },
                    )
                    self.progress.success_row()
                except DuplicateClaimError as exc:
                    self.progress.duplicate_row()
                    errors.append(
                        {
                            "row": row_number,
                            "claim_number": row.get("claim_number"),
                            "error": str(exc),
                        }
                    )
                    continue
                except Exception as exc:
                    self.progress.failed_row()
                    errors.append(
                        {
                            "row": row_number,
                            "claim_number": row.get("claim_number"),
                            "error": str(exc),
                        }
                    )
                    continue

            # Commit once per batch rather than once per row (or once for the
            # whole file) — bounds both lock/WAL bloat on large files and the
            # amount of work lost if the worker dies mid-import.
            self.db.commit()

            if on_progress:
                on_progress(
                    {
                        "total": self.progress.total,
                        "successful": self.progress.success,
                        "failed": self.progress.failed,
                        "duplicates": self.progress.duplicates,
                        "expected_total": expected_total,
                    }
                )

        duration_ms = int((time.perf_counter() - start) * 1000)

        return {
            "total": self.progress.total,
            "successful": self.progress.success,
            "failed": self.progress.failed,
            "duplicates": self.progress.duplicates,
            "valid_rows": self.progress.success + self.progress.duplicates,
            "expected_total": expected_total,
            "duration_ms": duration_ms,
            "errors": errors[:100],
        }
