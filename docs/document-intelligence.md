# Document Intelligence

## Current Scope

Atlas provides a tenant-scoped evidence library for claim documents. Authenticated
users with `EDIT_CLAIMS` can upload, classify, tag, summarize, and delete evidence;
users with `VIEW_CLAIMS` can list, search, and download it.

The database stores metadata and extracted text only. File bytes are stored beneath
`uploads/documents/{organization_id}` and the database records the opaque storage
path. Every upload is streamed through a 25 MB limit and assigned a SHA-256 checksum.
Uploading identical content to the same claim returns HTTP `409` and removes the
redundant stored object.

All metadata queries are scoped by the authenticated organization. Claim ownership
is checked before upload and listing, and direct document access uses the same tenant
boundary. Upload, metadata update, AI summary, and deletion write immutable audit
records with organization, actor, before/after state, and reason. Upload also appends
an event to the claim timeline.

Text extraction is best effort and records status, method, engine/version, and OCR
confidence on the tenant-owned document:

- text PDFs use `pypdf`;
- UTF-8 text files are read directly;
- images use Tesseract from the API image and average accepted word confidence;
- unavailable, unsupported, no-text, and failed extraction remain explicit states;
- extraction failure does not make the evidence upload fail.

AI summaries route through `AIGateway` with organization and claim context. They are
analyst aids, not clinical conclusions or automatic submission decisions.

Document classification also routes through `AIGateway` using the configured fast
model. Atlas persists the predicted type, confidence, provider, model, and prompt
version separately from the uploader-selected type. Every prediction remains pending
until an authorized reviewer accepts or corrects it with a reason; corrections update
the canonical type without erasing the original prediction and are audited.

## OCR And Classification Acceptance

Authorized representative-document acceptance uses a local JSON manifest and the
deterministic evaluator in `app.documents.acceptance`. The manifest must remain outside
source control and contain only the minimum de-identified ground truth and observed
output needed to compute aggregate evidence. Engineering does not choose acceptance
thresholds; the hospital acceptance owner and Atlas data/AI governance owner record
the agreed thresholds in the manifest.

Run the evaluator from `apps/api`:

```text
python scripts/evaluate_document_acceptance.py C:\secure\document-acceptance.json
```

The command exits `0` when every threshold passes, `1` when measured evidence fails,
and `2` for an invalid or unreadable manifest. Output contains only sample counts,
classification accuracy, OCR word accuracy, OCR success rate, and failure reasons.
It never outputs source or extracted document text.

The manifest shape is:

```json
{
	"policy": {
		"minimum_classification_samples": 1,
		"minimum_ocr_samples": 1,
		"minimum_classification_accuracy": 0.0,
		"minimum_ocr_word_accuracy": 0.0,
		"minimum_ocr_success_rate": 0.0
	},
	"classifications": [
		{"expected": "authorization", "predicted": "authorization"}
	],
	"ocr_observations": [
		{
			"expected_text": "de-identified ground truth",
			"extracted_text": "de-identified observed text",
			"extraction_status": "succeeded"
		}
	]
}
```

The zero thresholds above document structure only and are not an acceptance policy.
The signed manifest must use representative sample minimums and approved non-zero
quality thresholds. Keep the manifest, aggregate output, model/prompt provenance, and
reviewer sign-off together in the controlled acceptance evidence store.

## Data Classification

`documents` is directly tenant-owned through its non-null `organization_id` and is
also attached to a tenant-owned claim. The claim and organization boundaries must
both remain enforced for every query, background task, storage key, and AI call.
Document contents may contain protected health information and require least-privilege
access, encryption, retention, and deletion controls in production.

## Deployment

Migration `f6b2d8a4c1e9` adds the non-null SHA-256 checksum and a unique constraint on
organization, claim, and checksum. Existing rows receive deterministic legacy values;
they are not represented as content hashes and may be re-hashed by a future governed
backfill.

The configured storage provider requires shared durable access from API and worker
processes. Production deployment remains blocked on external object-store and restore
certification, representative OCR/classification threshold acceptance, and monitored
asynchronous extraction processing.

## Next Increments

1. Certify the configured production object store and restore procedure.
2. Validate OCR and classification thresholds against representative authorized documents.
3. Add source-page OCR provenance and monitored asynchronous retry processing.
4. Add entity extraction, missing-document rules, and search indexing.
5. Build a permission-filtered context service for AI and retrieval-grounded knowledge.

The broader Knowledge Engine must preserve source provenance, effective dates,
organization ownership, human review, and prompt/model version attribution. Historical
appeal outcomes must not be treated as payer policy without reviewed provenance.