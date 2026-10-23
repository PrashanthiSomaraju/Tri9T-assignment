import uuid
from sqlalchemy import select
from pydantic import ValidationError
from app.core.errors import DomainError
from app.models.document import NodeRevision, DocumentVersion
from app.models.selection import Selection
from app.models.generation import Generation
from app.services.documents import require
from app.services.canonical import digest, normalize
from app.services.llm_service import ProviderError
from app.schemas.generation import TestCases
from app.prompts.qa_generation import PROMPT_VERSION


def validate_output(raw: str, sources: list[dict]):
    output = TestCases.model_validate_json(raw)
    by_id = {s["id"]: normalize(s["heading"] + "\n" + s["body_text"]) for s in sources}
    titles = []
    for test in output.test_cases:
        titles.append(normalize(test.title).casefold())
        if any(i not in by_id for i in test.source_revision_ids):
            raise ValueError("Source revision ID is outside selection")
        for quote in test.source_quotes:
            if not any(normalize(quote) in by_id[i] for i in test.source_revision_ids):
                raise ValueError("Unsupported source quote")
        for i in test.source_revision_ids:
            if not any(normalize(q) in by_id[i] for q in test.source_quotes):
                raise ValueError("Referenced revision lacks a supporting quote")
    if len(set(titles)) != len(titles):
        raise ValueError("Test titles must be distinct")
    return output.model_dump()


def generate(session, selection_id, provider, store, force=False):
    selection = require(session, Selection, selection_id)
    rows = [require(session, NodeRevision, i) for i in selection.node_revision_ids]
    if not any(
        e["kind"] in ("paragraph", "list_item", "table", "caption")
        and normalize(e["text"])
        for r in rows
        for e in r.structured_content_json
    ):
        raise DomainError(
            422,
            "Selection has no readable requirement body; select text-bearing revisions or include descendants",
        )
    sources = [
        {
            "id": r.id,
            "logical_node_id": r.logical_node_id,
            "version_id": r.document_version_id,
            "content_hash": r.content_hash,
            "heading": r.heading,
            "body_text": r.body_text,
        }
        for r in rows
    ]
    key = digest(
        {
            "fingerprint": selection.fingerprint,
            "prompt": PROMPT_VERSION,
            "provider": provider.name,
            "model": provider.model,
            "parameters": {"temperature": 0},
        }
    )
    if not force:
        cached = session.scalar(
            select(Generation)
            .where(
                Generation.selection_id == selection.id,
                Generation.cache_key == key,
                Generation.status == "success",
            )
            .order_by(Generation.created_at)
        )
        if cached:
            return cached
    errors = []
    result = {}
    status = "failed"
    attempt = 0
    for attempt in range(3):
        try:
            raw = provider.generate_test_cases(
                sources, TestCases.model_json_schema(), errors or None
            )
            result = validate_output(raw, sources)
            status = "success"
            break
        except ValidationError as exc:
            errors = [
                f"{'.'.join(str(x) for x in error['loc'])}: {error['type']}"
                for error in exc.errors(include_input=False, include_url=False)
            ]
        except ValueError as exc:
            errors = [str(exc)]
        except ProviderError as exc:
            errors = [str(exc)]
            break
    identifier = str(uuid.uuid4())
    version = require(session, DocumentVersion, selection.document_version_id)
    content = {
        "id": identifier,
        "selection_id": selection.id,
        "document_id": version.document_id,
        "document_version_id": version.id,
        "version_number": version.version_number,
        "sources": sources,
        "provider": provider.name,
        "model": provider.model,
        "prompt_version": PROMPT_VERSION,
        "input_fingerprint": selection.fingerprint,
        "status": status,
        "test_cases": result.get("test_cases", []),
        "validation": {
            "valid": status == "success",
            "errors": errors if status == "failed" else [],
            "repair_attempts": attempt,
        },
    }
    # File first: failure cannot commit a database row referencing a missing file.
    try:
        location = store.write(identifier, content)
    except OSError as exc:
        raise DomainError(503, "Generation document could not be saved") from exc
    generation = Generation(
        id=identifier,
        selection_id=selection.id,
        provider=provider.name,
        model_name=provider.model,
        prompt_version=PROMPT_VERSION,
        input_fingerprint=selection.fingerprint,
        cache_key=key,
        status=status,
        retry_count=attempt,
        json_location=location,
    )
    session.add(generation)
    try:
        session.commit()
    except Exception:
        session.rollback()
        store.path(identifier).unlink(missing_ok=True)
        raise
    return generation
