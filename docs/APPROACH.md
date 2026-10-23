# Engineering approach

## Interpretation and evidence boundary

Regulated-document QA needs recoverable provenance before fluent generated prose.
The application models a technical document as immutable version snapshots and a separate
logical-node identity. Generated ideas depend on exact selected revisions, not a mutable
"latest" view. No original CT-200 PDF was supplied in this workspace. The observed PDFs
in this work are deliberately synthetic two-page fixtures derived from the assignment's
reference cases. Their properties do not establish properties of the employer's manuals.

## Extraction and structure

PyMuPDF supplies native blocks, lines, spans, font flags, bounding boxes and ruled-table
cell arrays. The intermediate representation retains kind, raw text, page, box, reading
order, extraction method, confidence and span evidence. Line-level elements stay available
even when paragraph display text joins visual lines. Tables retain rows and columns;
multiline cells stay in the owning row. Images remain figure elements and are OCR'd
regionally, including on otherwise native-text pages. Empty or replacement-character-heavy
pages use whole-page Tesseract OCR through Pillow at 144 dpi. OCR word confidence is
aggregated per line; low confidence, missing OCR and timeouts are visible warnings.
OCR is not run on reliable native text, except raster regions requiring separate reading.

Reading order is y then x, not a universal column solver. Side-by-side lines and rotated
text trigger review warnings. Native table text inside detected table boxes is suppressed
from the parallel line stream to avoid duplicate content. Only exact repeated text in
page margins is treated as a repeated header; suppressed source evidence remains in
reports. Borderless tables are not guaranteed; pipe-containing raw lines are preserved
as uncertain structure, and suspected columns are flagged. Unsupported contents are not
silently dropped.

The hierarchy parser combines anchored numbering with font emphasis and context. Numeric
prose units and the named blood-pressure classifications cannot become headings. Numbered
sections attach to their nearest existing numbered ancestor. Missing levels are warned,
not fabricated. Declared numbering depth differs from effective tree depth when necessary.
Sibling order follows extraction, even for 3.4 before 3.3. Duplicate heading titles are
separate sections, never lookup keys. Titles before the first section are joined and
retained in an explicit preamble. Uncertain, unstyled numbered candidates remain body
text with a warning rather than becoming confident headings.

Observed synthetic cases: a two-line title, out-of-order siblings, 2.1.1.1 without 2.1.1,
list/prose distractors, duplicate Error Codes titles, multiline E3 table cells, a table
starting on the page after its heading, and a short 8.1 body. Separate fixtures cover
repeated headers, paragraphs crossing pages, mixed raster/native pages and image-only OCR.
Both synthetic manual versions were rendered and visually inspected, including E3's
multiline association and E6's added row. All of these are synthetic observations.
The short 8.1-body warning is a conservative heuristic, not evidence of actual truncation.

## Persistence and matching

SQLite/SQLAlchemy 2 stores Document, DocumentVersion, LogicalNode, NodeRevision, Selection
and Generation. Unique constraints prevent duplicate version numbers/source digests and
multiple revisions of one logical node within a version. Foreign keys are enabled on every
SQLite connection. Revisions hold version-specific parent revision IDs; each version's tree
can be rebuilt independently. Upload ingestion is a transaction. The API exposes no snapshot
update/delete operations. The initial schema uses metadata initialization; Alembic was deferred
rather than adding a migration framework without any schema evolution yet.

Matching first uses exact number plus parent-number context. A one-to-one used set prevents
two new nodes from sharing an old revision. A weighted score (45% title, 55% body similarity)
of at least .83 can identify a probable move/rename; scores within .08 are ambiguous.
Ambiguity creates a fresh logical node, records candidate old IDs and requests review.
These are deterministic heuristics, not proof against a document author reusing a section
number for a different purpose. Large renumbering requires review. A removed identity has
no revision in the latest version. An ambiguous candidate's historical generation is
reported unresolved instead of confidently removed.

Content SHA-256 hashes cover normalized heading and ordered element kinds/text, plus
structured table cell arrays. Consecutive paragraph lines form one canonical text run.
Coordinates, page breaks, OCR method/confidence and warnings are excluded. Whitespace
normalization never deletes units, thresholds, comparison characters or error codes.
Paragraph-boundary distinctions are deliberately coarse; lists and tables remain separate.
Heading changes are content changes even when body text remains identical. Source-file
SHA-256 is separately byte-based for duplicate ingestion. Subtree changes do not
implicitly change a parent's own-content hash: selections need explicit descendants when
that is intended.

## Selections, generation and storage

Selections persist the exact ordered expanded revision list. The fingerprint hashes
revision IDs, logical IDs, version IDs and content hashes. Descendants are expanded once
only if requested. Repeated identical requests return the original selection; same name
and version with different content/settings returns 409. API retry caching for generations
uses the fingerprint, provider/model, prompt version and fixed temperature=0; force creates
new history. Concurrent cache misses are an acknowledged limitation.

The provider protocol has an explicit mock implementation and an httpx OpenAI-compatible
implementation. The real adapter requires HTTPS and a key; it never silently switches to
mock. Versioned prompts treat document text as untrusted source data and instruct exact
thresholds, controlled bench scenarios and JSON-only output. Pydantic validates strict types,
3–5 ideas, distinct titles, preconditions or justification, steps, expected results and
enumerations. All referenced revision IDs must belong to the pinned selection. Every quote
must occur in a referenced source after whitespace normalization, and every referenced
revision needs a supporting quote. This catches broken provenance, not every semantic
hallucination. A domain engineer must review test ideas. The mock provides transparent,
generic source-driven bench-review templates for integration demonstrations.

Validation failures produce sanitized, targeted repair errors; there are at most two repair
attempts. Persistent invalid output produces a failed generation with no fabricated cases,
HTTP 502 and a retrievable failure record. Transport errors are not retried as JSON repairs.
The real HTTP adapter was tested with a stubbed response; no live account generation ran.

A filesystem JSON store was chosen over MongoDB because this single-host assignment needs
nested, auditable immutable outputs without another database service. UUID-only filenames
prevent path traversal and collisions. Temp writes, file fsync, atomic replace and directory
fsync finish before a relational row is committed. A write failure cannot create a dangling
row; a DB-commit failure removes its new file. A crash between file and DB commit can leave
an orphan file, a safer failure than a row with missing data. Distributed atomicity and
orphan collection remain future work. Retrieval derives paths from UUIDs, not stored
arbitrary path strings. Missing/corrupt storage returns 503. Backups must include both stores.

## Staleness semantics

Retrieval leaves the saved generation document unchanged and compares its source identities
with the latest document version. Test-level status uses only that test's referenced revisions.

| Status | Meaning |
| --- | --- |
| current | Corresponding source exists and has the same content hash, without an identified matching/extraction review condition |
| review_required | Hash unchanged but matching, truncated/uncertain parsing, OCR or column warnings require review |
| stale | Supporting source hash changed; semantic invalidity has not been proven |
| source_removed | Identity absent from latest version and no ambiguous candidate recorded |
| unresolved | Historical source missing or latest matching evidence explicitly ambiguous |

Aggregate precedence: unresolved, source_removed, stale, review_required, current.
All source details and diffs remain present, so aggregate status does not conceal another
source's outcome. Document-wide OCR/column warnings conservatively affect unchanged tests.
A deterministic missing-parent warning alone does not invalidate resolved identity.
Section 4.1's 2-second claim and section 4.2's 1.5-second claim remain independent;
coexistence triggers a review warning without rewriting either.

Hashes are deliberately conservative. An unrelated sentence in 4.2 can flag every test
anchored in that section; quotes identify the exact support, but semantic/row-level impact
is not claimed. Future work should version table-row anchors and distinguish wording changes
from behavior changes behind a review gate.

## Actual development and debugging

The first full run executed 31 tests: 29 passed and two failed. One search assertion wrongly
expected no result for literal `%`, overlooking the battery percentage. It was corrected
to assert exactly the literal-matching node. The other failure showed that a known missing
intermediate-level warning made an otherwise current test review-required. The policy was
narrowed to uncertain extraction/matching conditions. The expanded 37-test suite then passed,
including actual Tesseract invocation.

Further review identified two implementation improvements: canonical hashes now merge visual
paragraph lines, and the title preamble now receives its physical position rather than being
appended after numbered sections. A hash wrapping regression was added. A new stub-provider
test exposed that assigning a string to Settings could bypass SecretStr conversion;
assignment validation was enabled. These are actual development events, not an invented
history of original-manual extraction problems.

## Verification and next steps

Tests use isolated temporary SQLite/JSON paths and actual generated PDFs. They cover
hierarchy, table association, matching, deletion, pinned selections, malformed and unsupported
provider output, bounded repairs, storage failure, cache behavior, each impact status,
API errors and persistence across application recreation. The demo exercises real FastAPI
routes through TestClient; a separate running-server smoke flow verifies actual HTTP.
Reports distinguish reference-content assertions from independent PDF evidence.
See VERIFICATION.md for final executed counts and limitations.

Before claiming original-document readiness: inspect both originals, compare suspicious
regions visually, validate expected version differences and rerun the originals demo.
Before production: add reviewed matching resolutions, robust column/table OCR, finer source
anchors, migrations, storage consistency jobs, background ingestion, and concurrency control.
These are deliberate future improvements, not hidden implemented capabilities.
