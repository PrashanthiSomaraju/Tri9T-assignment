from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from app.api.documents import db
from app.core.errors import DomainError
from app.models.document import LogicalNode, NodeRevision
from app.models.selection import Selection
from app.models.generation import Generation
from app.schemas.generation import GenerateRequest, GenerationView
from app.services.documents import require
from app.services.generation_service import generate
from app.services.llm_service import provider_for, ProviderError
from app.services.staleness_service import impact

router = APIRouter(prefix="/api")


def retrieve(session, generation, store):
    try:
        content = store.read(generation.id)
    except (OSError, ValueError) as exc:
        raise DomainError(
            503, "Generation document is missing or corrupted; restore storage backup"
        ) from exc
    return {
        "generation": content,
        "created_at": generation.created_at,
        "staleness": impact(session, content),
    }


@router.post(
    "/selections/{selection_id}/generate",
    response_model=GenerationView,
    response_model_exclude_none=True,
)
def create_generation(
    selection_id: int,
    request: Request,
    response: Response,
    body: GenerateRequest = GenerateRequest(),
    session=Depends(db),
):
    require(session, Selection, selection_id)
    try:
        provider = request.app.state.provider or provider_for(
            request.app.state.settings
        )
    except ProviderError as exc:
        raise DomainError(503, str(exc)) from exc
    generation = generate(
        session, selection_id, provider, request.app.state.store, body.force_regenerate
    )
    result = retrieve(session, generation, request.app.state.store)
    response.status_code = 200 if generation.status == "success" else 502
    return result


@router.get(
    "/generations/{generation_id}",
    response_model=GenerationView,
    response_model_exclude_none=True,
)
def get_generation(generation_id: UUID, request: Request, session=Depends(db)):
    return retrieve(
        session,
        require(session, Generation, str(generation_id)),
        request.app.state.store,
    )


@router.get(
    "/selections/{selection_id}/generations",
    response_model=list[GenerationView],
    response_model_exclude_none=True,
)
def selection_generations(selection_id: int, request: Request, session=Depends(db)):
    require(session, Selection, selection_id)
    rows = session.scalars(
        select(Generation)
        .where(Generation.selection_id == selection_id)
        .order_by(Generation.created_at)
    )
    return [retrieve(session, r, request.app.state.store) for r in rows]


@router.get(
    "/nodes/{logical_node_id}/generations",
    response_model=list[GenerationView],
    response_model_exclude_none=True,
)
def node_generations(logical_node_id: int, request: Request, session=Depends(db)):
    require(session, LogicalNode, logical_node_id)
    revision_ids = set(
        session.scalars(
            select(NodeRevision.id).where(
                NodeRevision.logical_node_id == logical_node_id
            )
        )
    )
    results = []
    for g in session.scalars(select(Generation).order_by(Generation.created_at)):
        result = retrieve(session, g, request.app.state.store)
        cases = [
            t
            for t in result["generation"]["test_cases"]
            if revision_ids.intersection(t["source_revision_ids"])
        ]
        if cases:
            result["matching_test_cases"] = cases
            results.append(result)
    return results
