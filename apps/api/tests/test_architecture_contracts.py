import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

import app.models  # noqa: F401
from app.db.base import Base
from app.main import app

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MASTER_FILES = {
    "API_SPEC.md",
    "BUILD_STATUS.md",
    "DATABASE_SCHEMA.md",
    "ROADMAP.md",
}
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _contract(name: str) -> str:
    return (REPOSITORY_ROOT / name).read_text(encoding="utf-8")


def _manifest(name: str, language: str) -> list[str]:
    content = _contract(name)
    fence = "`" * 3
    return (
        content.split(f"{fence}{language}", maxsplit=1)[1]
        .split(fence, maxsplit=1)[0]
        .strip()
        .splitlines()
    )


def _declared_count(content: str, label: str) -> int:
    match = re.search(rf"^{re.escape(label)}: (\d+)$", content, re.MULTILINE)
    assert match is not None
    return int(match.group(1))


def test_all_master_architecture_contracts_exist() -> None:
    existing = {path.name for path in REPOSITORY_ROOT.glob("*.md")}

    assert MASTER_FILES <= existing


def test_database_manifest_matches_registered_sqlalchemy_metadata() -> None:
    content = _contract("DATABASE_SCHEMA.md")
    documented = _manifest("DATABASE_SCHEMA.md", "tables")
    registered = sorted(Base.metadata.tables)

    assert len(documented) == len(set(documented))
    assert documented == sorted(documented)
    assert documented == registered
    assert _declared_count(content, "Registered SQLAlchemy tables") == len(registered)


def test_api_manifest_matches_generated_openapi_operations() -> None:
    content = _contract("API_SPEC.md")
    documented = _manifest("API_SPEC.md", "http")
    openapi = app.openapi()
    registered = sorted(
        f"{method.upper()} {path}"
        for path, path_item in openapi["paths"].items()
        for method in path_item
        if method.upper() in HTTP_METHODS
    )

    assert len(documented) == len(set(documented))
    assert set(documented) == set(registered)
    assert _declared_count(content, "Registered operations") == len(registered)


def test_alembic_has_exactly_one_head() -> None:
    content = _contract("DATABASE_SCHEMA.md")
    expected_head = re.search(r"^Alembic head: `([^`]+)`", content, re.MULTILINE)
    assert expected_head is not None

    config = Config(str(REPOSITORY_ROOT / "apps" / "api" / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(REPOSITORY_ROOT / "apps" / "api" / "alembic"),
    )
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == [expected_head.group(1)]
