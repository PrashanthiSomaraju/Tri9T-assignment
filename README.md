# CardioTrack CT-200 document intelligence

A PDF-first FastAPI application for versioned technical requirements, pinned selections,
traceable QA ideas and historical-generation impact review. SQLite stores immutable
version snapshots and stable logical identities; atomic JSON documents store provider
outputs with exact source hashes and quotes.

**Validation scope:** the original `ct200_manual.pdf` and `ct200_manual_v2.pdf` were not
provided. Synthetic PDFs, real OCR, API integration and historical traceability are tested.
No extraction-accuracy claim is made for the employer's manuals. A live LLM call also
requires a configured provider/model/key and has not been validated with a real account.
See [verification](docs/VERIFICATION.md), [approach](docs/APPROACH.md),
[decisions](docs/DECISION_LOG.md) and [API examples](docs/API_EXAMPLES.md).

## Run from a fresh checkout

Prerequisites: Python 3.11+, Tesseract with English data, and a supported PyMuPDF/Pillow
wheel platform. The verified environment uses Python 3.12 and Tesseract 5.5.
On Debian/Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-eng`.
The Linux OCR test also needs the DejaVu Sans font (`fonts-dejavu-core`).

```bash
cd Tri9T-assignment
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
cp .env.example .env
.venv/bin/python -m pytest -q
.venv/bin/python -m scripts.demo_end_to_end --synthetic
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`requirements.txt` pins direct dependencies; `requirements.lock` records the complete
clean-environment resolution used for verification. Neither command needs a provider key
in mock mode. On Windows use `.venv\Scripts\python` and install Tesseract separately.
The application initializes tables on startup; no database server is needed.
Swagger is available at path `/docs` on the running application; OpenAPI at `/openapi.json`.
Health/readiness is checked using `GET /health` and an actual ingest/generation workflow.

## Use the original PDFs

Place the supplied originals at `data/ct200_manual.pdf` and `data/ct200_manual_v2.pdf`.
PDFs and generated databases are ignored by Git. Different filenames can be passed directly.
Inspect before relying on any hierarchy:

```bash
.venv/bin/python -m scripts.inspect_pdf data/ct200_manual.pdf
.venv/bin/python -m scripts.inspect_pdf data/ct200_manual_v2.pdf
.venv/bin/python -m scripts.validate_hierarchy data/ct200_manual.pdf --reference-checks
.venv/bin/python -m scripts.validate_hierarchy data/ct200_manual_v2.pdf --reference-checks --output generated/v2_validation.json
```

Inspection writes JSON layout evidence (all spans, coordinates, tables, OCR provenance,
confidence and warnings) and a readable Markdown report under `generated/`. Reference
checks are assertions from the assignment, not proof of complete extraction. Compare
suspicious regions visually with the originals. Do not relabel synthetic fixtures as originals.

With the server running, upload v1, create a selection and generate **before** uploading v2:

```bash
curl -f -F document_key=ct200 -F file=@data/ct200_manual.pdf http://127.0.0.1:8000/api/documents/ingest
# Browse /api/documents/1/tree?version=1 and use returned revision IDs.
curl -f -H 'Content-Type: application/json' -d '{"name":"Pressure Safety QA","document_id":1,"version":1,"node_revision_ids":[10,14,18]}' http://127.0.0.1:8000/api/selections
# IDs above are illustrative: use actual IDs returned by your tree.
curl -f -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8000/api/selections/1/generate
curl -f -F document_key=ct200 -F file=@data/ct200_manual_v2.pdf http://127.0.0.1:8000/api/documents/ingest
```

Alternatively initialize/ingest with the same service layer, from the repository root:

```bash
.venv/bin/python -m scripts.ingest_documents data/ct200_manual.pdf --document-key ct200
.venv/bin/python -m scripts.ingest_documents data/ct200_manual_v2.pdf --document-key ct200
.venv/bin/python -m scripts.demo_end_to_end
```

The demo uses its own fresh database and unique output directory, not the application
database. It exercises the API, checks pinned snapshots, reports stale and unchanged
sources, and writes `demo.json`, `demo.md`, inspection and validation JSON files.
The synthetic demo uses `--synthetic`; originals mode fails visibly if either file is missing.

## Provider configuration

Default: `CT_PROVIDER=mock`. It is an explicit deterministic integration-test double;
its bench-review templates are not a substitute for expert-reviewed QA design.
Live OpenAI-compatible mode uses httpx with TLS verification and no automatic mock fallback:

```dotenv
CT_PROVIDER=openai-compatible
CT_MODEL=<model supported by your account>
CT_LLM_BASE_URL=https://api.groq.com/openai/v1
CT_LLM_API_KEY=<enter securely in your local environment>
```

Do not commit `.env`. Restart the application after changing settings. The endpoint must
support `/chat/completions` and JSON-object responses. Output is strictly validated:
3–5 cases, enumerations, required steps/results, selection membership, and exact
whitespace-normalized supporting quotes. Two repair attempts maximum. A persistent
failure is saved with status `failed`, sanitized errors and HTTP 502, never as a success.
The provider adapter is tested using a stubbed HTTP response; this is not a live-provider test.
Quote verification proves source anchoring, not that every proposed step is semantically valid.

## Behavior and identifiers

- `revision_id` identifies one immutable snapshot; `logical_node_id` identifies its history.
  The node-detail endpoint expects a revision ID. History, diff and node-generation endpoints
  expect a logical ID. Both appear explicitly in responses.
- Sections retain physical `order_index`; `3.4` can precede `3.3`. A missing `2.1.1` is
  never manufactured: `2.1.1.1` attaches to existing `2.1` with a warning.
- Native ruled tables retain cell rows/columns and multiline cells. Unsupported layouts
  keep evidence and warnings; heavily rotated/multicolumn scans need human review.
- Identical PDF bytes for the same document key return the existing version. A different
  PDF byte stream creates the next version even when its semantic text is unchanged.
- Exact section number + parent context has precedence in matching; heading/body
  similarity is secondary and reviewable. Ambiguous candidates get a new logical ID.
- Selections include only explicit revisions by default. `include_descendants=true`
  expands once, within the pinned version. Input order is retained; repeated IDs rejected.
  Same name/version/ordered IDs/settings returns the existing selection; conflicting
  content with that name/version returns 409.
- Successful generations are cached per selection, fingerprint, provider/model,
  prompt version and fixed temperature. `force_regenerate=true` creates another history item.
- Generation retrieval computes current impact without changing saved generated text.
  `stale` means a supporting source hash changed; it does not prove the QA expectation is wrong.
  `source_removed`, `unresolved`, `review_required`, and `current` have explicit semantics
  in the approach document. Row-level table quote anchoring is retained, but hash impact is
  conservatively at section level.

## Layout and verification

`app/core`: settings/database/errors; `app/models`: relational entities;
`app/schemas`: Pydantic validation; `app/api`: endpoints;
`app/services`: extraction, hierarchy, matching, ingestion, selection, generation and impact;
`app/prompts`: versioned provider instructions; `scripts`: inspect/ingest/validate/demo;
`tests`: isolated temporary databases, JSON stores and synthetic PDF factory.

```bash
.venv/bin/python -m pytest -q --junitxml=generated/pytest-results.xml
# Optional development formatter/linter:
.venv/bin/python -m pip install ruff==0.17.2
.venv/bin/ruff check app scripts tests --select F,E9
.venv/bin/ruff format --check app scripts tests
```

No standard test uses live provider calls. OCR tests invoke the actual installed Tesseract.
Generated artifacts are recreated by the commands; the concise verified results are committed
in `docs/VERIFICATION.md`. Application initialization uses `create_all` for the initial schema;
Alembic is deferred. Future schema changes require a migration before reusing existing data.
Back up both SQLite and the JSON directory together.

## Troubleshooting and limits

- Missing original PDFs: provide the files or use the explicitly synthetic demo.
- Tesseract missing/timeouts: ingestion records warnings and unreadable regions; it does
  not pretend OCR succeeded. Install the executable and English language data, then re-ingest
  under a new document key to force a fresh extraction of byte-identical files.
- Provider 502: inspect the persisted generation's validation errors and check account/model
  configuration. Provider response bodies and keys are never copied into failure records.
- Missing JSON file: retrieval returns 503; restore the matching storage backup.
- SQLite conflicts: retry a 409. Generation cache lookup is sequentially idempotent, not a
  distributed concurrency lock; simultaneous requests can create distinct generations.
- Upload cap is 25 MiB and synchronous processing is capped at 200 pages. OCR may take
  time. This is a single-instance assignment backend, not a horizontally scaled ingestion service.
- The current Starlette/httpx test adapter emits a deprecation warning; tests still execute.
- Original document accuracy, uncommon table layouts, major section renumbering and live
  model behavior remain outside the demonstrated evidence. See the decision log.
