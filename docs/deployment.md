# Atlas Deployment

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node.js 20+

## Local Development

```bash
# Start infrastructure (PostgreSQL + Redis + ClamAV + Mailpit)
make up

# Run database migrations
make migrate

# Seed demo data
make seed-demo

# Start the API (port 8000)
make dev-api

# Start the web app (port 3000)
make install-web
make dev-web
```

Visit `http://localhost:3000` and log in with:
- Email: `admin@atlasdemo.com`
- Password: `AtlasDemo2026!`

The separate Atlas-company control plane at `http://localhost:3000/atlas-admin`
uses:
- Email: `platform-admin@atlasdemo.com`
- Password: `AtlasPlatform2026!`

Local transactional email is delivered to Mailpit at `http://localhost:8025`.
Password resets, organization verification, team invitations, and test outbound
messages appear there instead of being sent to the public internet.

## Environment Variables

### API (`apps/api/.env`)

```
SECRET_KEY=<generate with: openssl rand -hex 32>
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=atlas
POSTGRES_USER=atlas
POSTGRES_PASSWORD=<strong password>
REDIS_HOST=localhost
REDIS_PORT=6379
DOCUMENT_STORAGE_BACKEND=s3
DOCUMENT_S3_BUCKET=<tenant-evidence-bucket>
DOCUMENT_S3_PREFIX=documents
DOCUMENT_S3_REGION=<provider-region>
DOCUMENT_S3_ENDPOINT_URL=<optional-s3-compatible-endpoint>
DOCUMENT_S3_SERVER_SIDE_ENCRYPTION=AES256
DOCUMENT_S3_KMS_KEY_ID=<optional-kms-key-id>
DOCUMENT_MALWARE_SCAN_ENABLED=true
DOCUMENT_MALWARE_SCAN_HOST=clamav
DOCUMENT_MALWARE_SCAN_PORT=3310
DOCUMENT_MALWARE_SCAN_TIMEOUT_SECONDS=10
INTEGRATION_ENCRYPTION_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
AI_PROVIDER=openai
AI_MODEL=gpt-4.1
SMTP_HOST=<authenticated-smtp-host>
SMTP_PORT=587
SMTP_USER=<smtp-user>
SMTP_PASSWORD=<smtp-password>
SMTP_FROM_EMAIL=<verified-sender-address>
SMTP_USE_TLS=true
```

### Web (`apps/web/.env.local`)

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Static Web Hosting with FileZilla

Atlas can export the web application as static files for an Apache-compatible
`public_html` host. The API remains a separate FastAPI deployment; static
hosting does not run the API, workers, PostgreSQL, Redis, scheduled jobs, or
document scanning.

For the current `www` deployment, configure DNS and TLS for both:

- `https://www.atlashealth.ke` — static frontend uploaded to `public_html`
- `https://api.atlashealth.ke` — deployed API service

The certificate must also include `atlashealth.ke` before redirecting the apex
domain to `www.atlashealth.ke`; otherwise browsers show a certificate error
before they can follow the redirect.

Build the upload directory from `apps/web`:

```powershell
$env:NEXT_PUBLIC_API_URL = "https://api.atlashealth.ke"
npm ci
npm run build:static
```

The command validates that the API URL is public HTTPS and creates
`apps/web/out`. In FileZilla:

1. Connect using SFTP or FTPS. Do not send credentials over plain FTP.
2. Open the hosting account's `public_html` directory.
3. Upload the **contents** of `apps/web/out`, not the `out` directory itself.
4. Enable display of hidden files and verify `.htaccess` was uploaded.
5. Confirm `https://www.atlashealth.ke/login/` loads and browser requests go to
   `https://api.atlashealth.ke`.

The included `.htaccess` forces HTTPS, disables directory listing, provides the
static 404 document, adds baseline browser security headers, and controls cache
behavior. If the host does not run Apache or disallows `.htaccess`, reproduce
those settings in its control panel.

Before production use, set the API `FRONTEND_URL=https://www.atlashealth.ke`
and allow CORS only from `https://www.atlashealth.ke`. Rebuild and re-upload
the static files whenever a `NEXT_PUBLIC_*` value changes because those values
are embedded at build time. Roll back by restoring the prior complete
`public_html` snapshot; do not mix files from different builds.

## HCode Testing Backend

The HostAfrica HCode Developer plan can run an internet-accessible testing
backend with synthetic data. It is not the production healthcare deployment
gate: local document storage is ephemeral, in-container ClamAV exceeds the
available runtime memory, and the plan's capacity, monitoring, SMTP,
object-storage, and recovery controls have not been accepted for real patient
data. PostgreSQL and Redis backups are scheduled daily with seven-day retention,
but a backup file is not recovery evidence until an isolated restore rehearsal
passes.

Create one HCode **Web app** project from the GitHub repository with:

- root directory: `/apps/api`
- build type: `Dockerfile`
- Dockerfile path: `./Dockerfile`
- Docker context: `.`
- runtime port: `8000`
- health check: `/health/ready`
- branch: `main`

HCode databases are private to one project. The test image therefore runs the
API, Celery worker, and Celery scheduler together so they can share the same
PostgreSQL and Redis services. A production deployment should separate those
processes on infrastructure with an explicitly shared private network.

Create one PostgreSQL 16 database and one Redis 7 database in the project, then
attach their internal connection strings as secret `DATABASE_URL` and
`REDIS_URL` variables. Add these project variables:

```text
APP_ENV=staging
FRONTEND_URL=https://www.atlashealth.ke
CORS_ALLOWED_ORIGINS=https://www.atlashealth.ke,https://atlashealth.ke
SEED_DEMO_DATA=true
SECRET_KEY=<random 32-byte-or-longer value>
INTEGRATION_ENCRYPTION_KEY=<Fernet key>
DOCUMENT_STORAGE_BACKEND=local
DOCUMENT_MALWARE_SCAN_ENABLED=false
COPILOT_ENABLED=false
AI_PROVIDER=openai
AI_MODEL=gpt-4.1
AI_MODEL_FAST=gpt-4.1-mini
AI_MONTHLY_BUDGET_USD=20
```

Mark connection URLs, `SECRET_KEY`, and `INTEGRATION_ENCRYPTION_KEY` as secret.
Demo seeding is blocked in production and is restart-safe in staging. It uses
documented synthetic credentials only; never load patient or payer production
data into this environment.

AI must remain disabled until a provider key has been created or rotated,
stored as a secret `OPENAI_API_KEY`, and protected by an account-side budget.
`AI_MONTHLY_BUDGET_USD` is a fail-closed application circuit breaker based on
persisted approximate model costs; it is not a prepaid limit and does not
replace the provider's hard project budget. All AI calls continue through
`AIGateway`, and generated appeals still require explicit human approval before
submission.

The HCode image can start a local ClamAV daemon only when
`DOCUMENT_MALWARE_SCAN_HOST` is `127.0.0.1` or `localhost`. The Developer
runtime killed `freshclam` with signal 9 while testing the signature database on
2026-10-31, so local scanning must remain disabled on this plan. To enable
fail-closed scanning, provision a private, adequately sized scanner, set its
host and port, enable `DOCUMENT_MALWARE_SCAN_ENABLED`, and confirm that
`/health/ready` reports `malware_scanner: ok` before accepting uploads.

After the generated HCode address passes `/health/ready`, add
`api.atlashealth.ke` under the project's Domains tab and create the exact CNAME
record HCode displays. Wait until HCode reports HTTPS active before testing
authentication from the static frontend.

The synthetic staging deployment was verified on 2026-10-31 at
`https://api.atlashealth.ke`: PostgreSQL and Redis readiness, HTTPS, login, and
frontend-origin CORS passed. Manual PostgreSQL and Redis backup artifacts were
created and reached `Ready`; restore validation remains open. AI and malware
scanning remain disabled pending a rotated AI key and an external scanner.

## Production Checklist

- [ ] Use a secrets manager (AWS Secrets Manager / Azure Key Vault) for all secrets
- [ ] Never commit `.env` files
- [ ] Set `INTEGRATION_ENCRYPTION_KEY` before connecting any EHR
- [ ] Run `alembic upgrade head` as part of every deployment
- [ ] Enable HTTPS — never run with plain HTTP in production
- [ ] Configure CORS to allow only your frontend domain
- [ ] Configure authenticated SMTP with a verified sender domain and test delivery, bounce, and outage behavior
- [ ] Restrict the document bucket to the API workload identity and deny public access
- [ ] Monitor ClamAV health/signature freshness and alert on scanner-unavailable rejections
- [ ] Verify clean, EICAR, quarantine-denial, S3 retrieval, and tenant-key isolation paths

Document uploads fail closed when scanning or configured storage is unavailable. During
rollback, keep the scanner and object store available, deploy the prior compatible API,
and do not switch production to local storage. Existing `s3://` document locators remain
readable through the Documents storage facade; quarantined locators must never be served.

## Backup and Disaster Recovery Gate

Application audit and retention controls do not replace infrastructure recovery. Before
production healthcare data is accepted, the deployment owner must document and test:

- encrypted scheduled database backups and provider-managed point-in-time recovery;
- versioned, cross-zone document storage with deletion protection;
- a named recovery point objective (RPO) and recovery time objective (RTO);
- quarterly restore rehearsal into an isolated environment, including checksum and
	tenant-boundary validation;
- backup access logging, key rotation, retention, and legal-hold handling;
- an incident commander, escalation contacts, evidence template, and recovery runbook.

The first design-partner pilot remains blocked until a measured restore rehearsal meets
the approved RPO/RTO. Docker Compose volumes are development storage, not a backup or
disaster-recovery strategy.
