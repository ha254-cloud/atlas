import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUILD_STATUS_PATH = REPOSITORY_ROOT / "BUILD_STATUS.md"
ALLOWED_STATUSES = {"Not Started", "In Progress", "Complete"}
REQUIRED_MODULES = {
    "Authentication",
    "Organizations",
    "Branches",
    "Users",
    "Patients",
    "Claims",
    "Documents",
    "Payers",
    "Submissions",
    "Payments",
    "Recovery",
    "Appeals",
    "AI",
    "Finance",
    "Billing",
    "Tasks",
    "Notifications",
    "Reports",
    "Analytics",
    "Integrations",
    "Governance",
    "Administration",
    "Frontend",
    "Testing",
    "Deployment",
}
MODULE_ROW_PATTERN = re.compile(
    r"^\| (?P<module>[^|]+?) \| \*\*(?P<status>[^*]+)\*\* \|",
    re.MULTILINE,
)


def _build_status() -> str:
    return BUILD_STATUS_PATH.read_text(encoding="utf-8")


def _module_rows() -> list[tuple[str, str]]:
    content = _build_status()
    module_ledger = content.split("## Module Ledger", maxsplit=1)[1].split(
        "## Required Module Shape", maxsplit=1
    )[0]
    return MODULE_ROW_PATTERN.findall(module_ledger)


def test_build_status_tracks_every_canonical_delivery_module_once() -> None:
    rows = _module_rows()
    tracked_modules = [module for module, _ in rows if module in REQUIRED_MODULES]

    assert set(tracked_modules) == REQUIRED_MODULES
    assert len(tracked_modules) == len(REQUIRED_MODULES)


def test_build_status_uses_only_supported_states() -> None:
    rows = _module_rows()
    module_states = {status for module, status in rows if module in REQUIRED_MODULES}

    assert module_states <= ALLOWED_STATUSES


def test_build_status_names_the_active_delivery_slice() -> None:
    content = _build_status()

    for field in (
        "Active batch",
        "Active module",
        "Goal",
        "First acceptance slice",
        "Schema decision",
        "Blockers",
        "Last validation",
    ):
        assert re.search(rf"^\| {re.escape(field)} \| \S.+ \|$", content, re.MULTILINE)
