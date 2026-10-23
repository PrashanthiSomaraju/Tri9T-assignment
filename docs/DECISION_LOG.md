# Decisions in my own engineering terms

## 1. What is most likely to silently give wrong results without erroring?

I consider hierarchy or table-row corruption the highest risk. A valid JSON tree and a
successful HTTP response cannot prove that a PDF's E3 behavior was not assigned to E4.
I retain page boxes, raw spans, structured rows and extraction warnings so I can trace a
suspect value back to the page. I test nearest-existing-ancestor parentage, physical 3.4/3.3
order, duplicate-title separation and exact E3 multiline cell association. Element accounting
checks every nonsuppressed source element is assigned once; it does not prove PyMuPDF
extracted everything. I rendered and visually compared the synthetic fixture pages. I
cannot honestly claim the same check on the original manuals because they were not supplied.

## 2. Where did I choose simplicity, and what breaks first in production?

I chose section-level hashes rather than semantic impact analysis or stable table-row IDs.
That favors conservative review over precision: an unrelated addition in a selected section
can flag a test whose quoted requirement is unchanged. I also chose deterministic numbered
matching rather than a learned matcher. A reused section number can preserve an identity
incorrectly. The likely first operational failures at scale are synchronous OCR latency,
SQLite write contention, concurrent duplicate-generation cache misses and maintaining two
stores. I'd add background jobs, reviewed match decisions, a migration process and a single
transactional document store before scaling horizontally. I did not introduce MongoDB for
an assignment that needs only a small single-host JSON history.

## 3. Name an input I did not handle and its observable behavior

I do not reliably reconstruct heavily rotated multi-column scanned tables. Native rotated
spans and suspected parallel columns trigger warnings; OCR returns lines with confidence
rather than pretending it recovered table semantics. The raw evidence is retained, uncertain
structures are flagged, and downstream unchanged sources can require review. Detection is
heuristic, so a warning is not guaranteed for every possible layout. A reviewer must compare
suspicious pages. Persistently invalid LLM JSON is another deliberately bounded case: after
two repair attempts I save an explicit failed record, return HTTP 502 and never fabricate
missing tests locally.

## Other concrete choices

- Different bytes create versions; same bytes/document key return the existing version.
- Version-specific revision IDs and stable logical IDs have separate endpoint semantics.
- Missing numbered parents are never synthesized; the nearest existing ancestor is used.
- Table-cell text and source quotes are retained verbatim except canonical whitespace in hashes.
- JSON is written atomically before the database metadata; crashes can leave orphan files,
  while application write failures cannot leave metadata pointing at nonexistent output.
- Mock mode is explicit and labeled. Live transport never silently becomes mock output.
- I deferred Alembic until schema evolution is required; initial create_all is repeatable,
  but is not a database migration tool.
