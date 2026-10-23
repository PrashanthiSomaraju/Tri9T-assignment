# API examples

Run commands from the repository root with Uvicorn running. These examples use curl and
Python (no jq dependency). They discover IDs instead of assuming particular SQLite IDs.
Start with a fresh application database and use the original files when available.
For synthetic input, first run `python -m scripts.demo_end_to_end --synthetic` and replace
the PDF paths with `generated/synthetic/synthetic_v1.pdf` and `synthetic_v2.pdf`.

```bash
API=http://127.0.0.1:8000
mkdir -p generated/curl
curl -fsS -F document_key=ct200 -F file=@data/ct200_manual.pdf "$API/api/documents/ingest" > generated/curl/ingest.json
DOC_ID=$(python -c "import json;print(json.load(open('generated/curl/ingest.json'))['document_id'])")
curl -fsS "$API/api/documents/$DOC_ID/versions"
curl -fsS "$API/api/documents/$DOC_ID/sections?version=1"
curl -fsS "$API/api/documents/$DOC_ID/tree?version=1" > generated/curl/v1-tree.json
curl -fsS --get --data-urlencode q=299 --data-urlencode document_id="$DOC_ID" --data-urlencode version=1 "$API/api/nodes/search"
```

Ingestion returns `{ "document_id": 1, "version_id": 1, "version": 1,
"duplicate": false, "report": { ... } }`. Repeating identical PDF bytes returns
`duplicate: true` and the same version. The tree returns nested `children`, physical
`order_index`, version-specific `id`, stable `logical_node_id`, source pages and warnings.

Create a selection using discovered revisions:

```bash
python - <<'PY'
import json
from pathlib import Path

def flatten(tree):
    return [item for node in tree for item in [node, *flatten(node['children'])]]

nodes = {n['section_number']: n for n in flatten(json.loads(Path('generated/curl/v1-tree.json').read_text()))}
document_id = json.loads(Path('generated/curl/ingest.json').read_text())['document_id']
selected = [nodes[number]['id'] for number in ['2.1.1.1', '3.2', '4.1']]
Path('generated/curl/selection-request.json').write_text(json.dumps({
    'name': 'Pressure Safety QA', 'document_id': document_id,
    'version': 1, 'node_revision_ids': selected, 'include_descendants': False,
}))
Path('generated/curl/node-ids.json').write_text(json.dumps({
    'revision_id': nodes['2.1.1.1']['id'],
    'logical_node_id': nodes['2.1.1.1']['logical_node_id'],
}))
PY
REV_ID=$(python -c "import json;print(json.load(open('generated/curl/node-ids.json'))['revision_id'])")
LOGICAL_ID=$(python -c "import json;print(json.load(open('generated/curl/node-ids.json'))['logical_node_id'])")
curl -fsS "$API/api/nodes/$REV_ID"
curl -fsS "$API/api/nodes/$LOGICAL_ID/history"
curl -fsS -H 'Content-Type: application/json' --data-binary @generated/curl/selection-request.json "$API/api/selections" > generated/curl/selection.json
SEL_ID=$(python -c "import json;print(json.load(open('generated/curl/selection.json'))['id'])")
curl -fsS "$API/api/selections/$SEL_ID"
curl -fsS -H 'Content-Type: application/json' -d '{}' "$API/api/selections/$SEL_ID/generate" > generated/curl/generation.json
GEN_ID=$(python -c "import json;print(json.load(open('generated/curl/generation.json'))['generation']['id'])")
curl -fsS "$API/api/generations/$GEN_ID"
```

The result contains `generation` (immutable sources, hashes, quotes, cases and validation),
`created_at` and a computed `staleness` object. Mock generation identifies itself as provider
`mock`, model `mock-v1`. Failed responses return HTTP 502 with `status: failed`, zero cases
and sanitized validation errors. A failed generation remains retrievable by its UUID.

Now ingest v2, browse both snapshots, inspect the diff, and retrieve history:

```bash
curl -fsS -F document_key=ct200 -F file=@data/ct200_manual_v2.pdf "$API/api/documents/ingest"
curl -fsS "$API/api/documents/$DOC_ID/tree?version=1"
curl -fsS "$API/api/documents/$DOC_ID/tree?version=2"
curl -fsS "$API/api/nodes/$LOGICAL_ID/diff?from_version=1&to_version=2"
curl -fsS "$API/api/generations/$GEN_ID"
curl -fsS "$API/api/selections/$SEL_ID/generations"
curl -fsS "$API/api/nodes/$LOGICAL_ID/generations"
# Intentional new generation, preserving the earlier history:
curl -fsS -H 'Content-Type: application/json' -d '{"force_regenerate":true}' "$API/api/selections/$SEL_ID/generate"
```

Representative synthetic battery diff: `changed: true`, distinct `previous_hash` and
`current_hash`, removed text containing `300 measurement cycles`/`15%`, added text containing
`250 measurement cycles`/`10%`, and summary `Content changed; review required`.
Representative test-level impact after v2:

```json
{
  "status": "stale",
  "requires_review": true,
  "tests": [
    {"title": "<battery test title>", "status": "stale", "sources": ["<source and diff details>"]},
    {"title": "<inflation test title>", "status": "stale", "sources": ["<source and diff details>"]},
    {"title": "<venting test title>", "status": "current", "sources": ["<unchanged source details>"]}
  ]
}
```

The abbreviated response above illustrates shape, not a literal response body. Full real
outputs are generated in `generated/demo-*/demo.json`. Original-PDF outcomes remain
unverified. An invalid document/version/revision yields 404; mixed-version selection
membership yields 422; a conflicting selection name/version yields 409; oversize uploads
return 413. Search accepts document and version filters and escapes SQL LIKE wildcards.
