# Repository File Inventory

## Purpose

This inventory assigns every file in the Atlas repository to an ownership and
lifecycle category. It is a review aid, not deletion authorization. Files marked
for review remain in place until an owner explicitly approves archival or removal.

The canonical product owners remain defined in `docs/module-registry.md`. This
document covers repository hygiene: why a path exists, whether it is source,
evidence, local state, generated output, or a compatibility surface, and how it
should be maintained.

`docs/implementation-backlog.md` indexes dependency-ordered delivery slices and their
evidence gates. It is not a source-file allowlist and does not reserve proposed paths.

## Audit Snapshot

The 2026-08-01 audit classified 767 files after excluding dependency, cache, build,
and upload trees. Every file in that snapshot matched exactly one category below.
The scan excluded `.git/`, `.venv/`, `node_modules/`, `.next/`, `__pycache__/`,
`.pytest_cache/`, `.ruff_cache/`, and upload directories because their purpose is
defined by the generated/runtime directory rules rather than individual filenames.

| Category | Files | Path contract | Purpose and owner |
|---|---:|---|---|
| Backend production | 433 | `apps/api/app/**` | FastAPI application, domain modules, workers, integrations, and shared platform code. Ownership is resolved through the module registry. |
| Backend tests | 52 | `apps/api/tests/**` | Executable backend behavior, security, tenant-boundary, migration, and regression evidence. |
| Database migrations | 53 | `apps/api/alembic/**` | Alembic environment and immutable schema history. The database owner must preserve one head and rehearse upgrades. |
| Backend tooling | 6 | `apps/api/Dockerfile`, `alembic.ini`, `pyproject.toml`, `requirements.txt`, `seed.py`, `scripts/**` | API build, dependency, migration, lint, and intentional demo/knowledge seeding support. |
| Web production | 92 | `apps/web/src/**` | Next.js portal pages, components, API clients, types, and user workflows. |
| Web tooling | 8 | `apps/web/package*.json`, framework and TypeScript configuration, `.env.local.example` | Reproducible web dependency, build, type-check, and safe local configuration contracts. |
| Documentation | 28 | `docs/**` | Architecture, operational contracts, ADRs, readiness, security, and this inventory. Documentation must describe implemented readiness accurately. |
| Automation and governance | 2 | `.github/**` | CI workflow and repository-specific Copilot engineering rules. |
| Repository tooling | 7 | `.env.example`, `.gitignore`, `.pre-commit-config.yaml`, `CONTRIBUTING.md`, `docker-compose.yml`, `Makefile`, `README.md` | Repository setup, local orchestration, contributor workflow, and generated-file boundaries. |
| Editor configuration | 1 | `.vscode/**` | Shared VS Code behavior that is appropriate for all contributors. |
| Legacy backend | 34 | `app/**` | Historical repository-root implementation. It is not copied into the API image and must not receive product changes. Retain until a separately approved archival decision. |
| Generated test/build evidence | 47 | root `pytest_*.txt`, `denial_kb*_test_out.txt`, `docker_build.log`, `apps/pytest_*.txt`, `apps/api/sprint*_scoped_out.txt`, `apps/api/e2e_claim_*.csv`, `apps/web/tsconfig.tsbuildinfo` | Local test transcripts, synthetic import artifacts, logs, and incremental compiler state. Kept on disk when useful but ignored by Git; they are not authoritative test coverage. |
| Local secret/runtime configuration | 2 | `apps/api/.env`, `apps/web/.env.local` | Developer-specific settings and secrets. Always ignored; committed examples are the configuration contract. |
| Diagnostic review candidates | 2 | `apps/api/test_hash.py`, `apps/api/test_jwt.py` | Unreferenced one-off scripts that print a demo password/hash or JWT. They are not pytest tests or supported tooling. Keep pending explicit owner decision; do not run in shared logs. |

Empty directories under `apps/worker/`, `packages/`, and `infrastructure/` contain no
tracked files and therefore do not represent implemented modules. They reserve no
business ownership. A future file added there must first satisfy the module registry
and definition of done.

## Generated And Runtime Trees

| Path | Purpose | Source-control rule |
|---|---|---|
| `.git/` | Local Git object database and repository metadata | Never commit as content. |
| `.venv/`, `node_modules/` | Locally installed dependencies | Recreate from lock/dependency files; ignore. |
| `.next/`, `*.tsbuildinfo` | Next.js and TypeScript build state | Recreate with the web build; ignore. |
| `__pycache__/`, `.pytest_cache/`, `.ruff_cache/` | Python bytecode and tool caches | Recreate with Python tools; ignore. |
| `apps/api/uploads/` | Runtime document/import objects mounted as the API upload volume | Ignore. Production requires governed durable object storage, retention, and backup. |
| Nested `apps/api/apps/api/` and `apps/web/apps/api/` | Accidental cache/upload paths produced by prior working-directory choices | No product ownership. Ignore generated contents and prevent new source files there. |

## Purpose Checks And Findings

### Confirmed purposeful

- Empty `__init__.py` files under `apps/api/app/` are Python package markers.
- `apps/api/seed.py` is the documented `make seed-demo` entrypoint.
- Alembic revision files are schema history and must not be removed because a newer
  migration supersedes them.
- Tests and fixtures remain purposeful even when production code has changed; remove
  them only when the behavior contract is deliberately retired.
- The root `app/` tree has compatibility/history purpose but no production runtime
  purpose. Docker copies only `apps/api/app/`.

### Implemented scaffolds, not live capabilities

The following production paths have a valid architectural purpose but contain
explicit unfinished behavior. Their presence must not be represented as a working
integration:

- `apps/api/app/ai/providers/anthropic.py`, `gemini.py`, and `ollama.py`;
- `apps/api/app/canonical/normalizers/fhir.py` and `x12.py`;
- vendor connectors under `apps/api/app/integrations/connectors/` and
  `apps/api/app/integrations/fhir/` that raise `NotImplementedError`;
- pass-through source adapters under `apps/api/app/imports/adapters/`.

Abstract base classes and exception classes that use `NotImplementedError` or `pass`
are intentional language patterns and are not unfinished merely for that reason.

### Review before keeping in source control

- The API-root `test_hash.py` and `test_jwt.py` scripts expose credential/token
  material to stdout and have no repository callers. Convert a needed assertion into
  a real test or documented admin command before treating either as supported.
- Dated CSVs and pytest transcripts are reproducibility evidence only when linked
  from a release record with the exact code revision and command. Otherwise they are
  disposable local output, not durable compliance evidence.
- Local `.env` files may contain secrets. Review secret history before the first
  remote push even though current ignore rules exclude them.

## File Admission Rules

Every new file must satisfy all applicable checks:

1. Name the canonical module or platform owner.
2. Identify whether the file is production source, test, migration, documentation,
   tooling, fixture, generated output, runtime data, or compatibility code.
3. Put production backend code only under `apps/api/app/` and production web code
   only under `apps/web/src/`.
4. Keep generated outputs and secrets out of Git; add a safe example or generating
   command when contributors need the artifact.
5. Do not create source files in empty placeholder or accidentally nested trees to
   establish a new owner.
6. Link temporary evidence to a release or incident record with a retention owner;
   otherwise keep it local and ignored.
7. Require explicit approval before archiving or deleting an existing user-owned
   file, including files marked as review candidates here.

## Repeatable Audit

Repository hygiene review should run before a release and after major restructuring:

1. List files while excluding dependencies, caches, builds, and runtime uploads.
2. Require each remaining path to match one category in this inventory.
3. Search production code for explicit stubs, placeholders, and unimplemented
   transports; reconcile the result with `docs/release-plan.md`.
4. Verify `.env.example` loads through the typed API settings without real secrets.
5. Verify generated artifacts are ignored and that no ignored source file is needed
   to build, test, migrate, or operate Atlas.
6. Run focused tests, Ruff, web type-check/build, and editor diagnostics for any
   source or configuration edits made from the findings.