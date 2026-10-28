# Atlas Deployment

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node.js 20+

## Local Development

```bash
# Start infrastructure (PostgreSQL + Redis)
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
```

### Web (`apps/web/.env.local`)

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Production Checklist

- [ ] Use a secrets manager (AWS Secrets Manager / Azure Key Vault) for all secrets
- [ ] Never commit `.env` files
- [ ] Set `INTEGRATION_ENCRYPTION_KEY` before connecting any EHR
- [ ] Run `alembic upgrade head` as part of every deployment
- [ ] Enable HTTPS — never run with plain HTTP in production
- [ ] Configure CORS to allow only your frontend domain
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
