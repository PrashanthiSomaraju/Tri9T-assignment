from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.selection import Selection
from app.services.documents import get_version, revisions
from app.services.canonical import digest
from app.core.errors import DomainError


def create_selection(session, request):
    version=get_version(session,request.document_id,request.version)
    rows=revisions(session,version.id)
    by_id={r.id:r for r in rows}
    ids=list(dict.fromkeys(request.node_revision_ids))
    if len(ids)!=len(request.node_revision_ids):
        raise DomainError(422,'Duplicate revision IDs are not allowed')
    if any(i not in by_id for i in ids):
        raise DomainError(422,'Every revision must belong to the selected document version')
    if request.include_descendants:
        changed=True
        while changed:
            changed=False
            for r in rows:
                if r.parent_revision_id in ids and r.id not in ids:
                    ids.append(r.id)
                    changed=True
    fingerprint=digest([{'revision':i,'logical':by_id[i].logical_node_id,'version':version.id,'hash':by_id[i].content_hash} for i in ids])
    existing=session.scalar(select(Selection).where(Selection.document_version_id==version.id,Selection.name==request.name))
    if existing:
        if existing.node_revision_ids==ids and existing.include_descendants==request.include_descendants:
            return existing
        raise DomainError(409,'Selection name already exists with different content/settings in this version')
    selection=Selection(name=request.name,document_version_id=version.id,node_revision_ids=ids,include_descendants=request.include_descendants,fingerprint=fingerprint)
    session.add(selection)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(409,'Concurrent selection creation; retry request') from exc
    return selection
