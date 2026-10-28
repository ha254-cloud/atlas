# Atlas Security

## Multi-Tenancy

Every database query is scoped by `organization_id`. The `BaseRepository` base class enforces this — no query ever reaches a table without filtering by org. The organization ID is derived from the authenticated JWT, never from the client request body.

## Authentication

- Passwords hashed with bcrypt (passlib)
- JWT tokens signed with HS256, configurable expiry
- New JWTs are linked to tenant-owned server-side sessions and can be revoked by
	logout, password reset, or a hospital administrator
- `SECRET_KEY` must be a cryptographically random 32+ byte string

## Governance Evidence

- Audit records include tenant, actor, resource, before/after state, reason,
	correlation ID, IP address, user agent, and device classification where available.
- PostgreSQL rejects audit record updates and deletes through an always-enabled trigger.
- Sensitive credential-like values are redacted before structured state is persisted.
- Patient consent and retention policy changes create append-only versions.
- See `docs/governance-risk-compliance.md` and ADR 0005 for boundaries and residual risk.

## API Keys (MCP)

- Raw key shown exactly once at creation time
- Only the bcrypt hash stored in the database
- Key prefix stored for O(1) lookup before hash comparison
- Keys can be revoked instantly via `DELETE /api/v1/mcp/keys/{id}`

## Integration Tokens

OAuth access/refresh tokens for EHR integrations are encrypted with **Fernet** (AES-128-CBC + HMAC-SHA256) before storage. The encryption key lives in `INTEGRATION_ENCRYPTION_KEY` environment variable — never in the database.

## OWASP Top 10

| Risk | Mitigation |
|------|-----------|
| Injection | SQLAlchemy ORM — no raw SQL |
| Broken Access Control | Org-scoped `BaseRepository`, JWT on every endpoint |
| Cryptographic Failures | bcrypt for passwords, Fernet for tokens, HTTPS required |
| Insecure Design | Defense in depth; auth at HTTP layer + service layer |
| Security Misconfiguration | `.env.example` documents all secrets; no defaults in production |
| Sensitive Data Exposure | Tokens encrypted at rest; API keys hashed |
| Auth Failures | JWT expiry, bcrypt, no plaintext secrets in DB |
| Data Integrity Failures | Pydantic validation on all inputs |
| Logging Failures | AuditLog table records every significant action |
| SSRF | Connectors use configured base URLs; no user-supplied URLs |
