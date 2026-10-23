from difflib import ndiff
from sqlalchemy import select
from app.models.document import Document, DocumentVersion, LogicalNode, NodeRevision
from app.core.errors import DomainError


def require(session, model, identifier):
    obj=session.get(model,identifier)
    if obj is None:
        raise DomainError(404,f'{model.__name__} not found')
    return obj


def get_version(session, document_id: int, version: int | None=None):
    require(session,Document,document_id)
    query=select(DocumentVersion).where(DocumentVersion.document_id==document_id)
    query=query.where(DocumentVersion.version_number==version) if version is not None else query.order_by(DocumentVersion.version_number.desc())
    result=session.scalar(query)
    if result is None:
        raise DomainError(404,'Document version not found')
    return result


def revision_dict(r):
    return {k:getattr(r,k) for k in ('id','logical_node_id','document_version_id','parent_revision_id','heading','section_number','declared_level','effective_level','order_index','body_text','structured_content_json','content_hash','page_start','page_end','parser_warnings','matching_evidence')}


def revisions(session, version_id):
    return list(session.scalars(select(NodeRevision).where(NodeRevision.document_version_id==version_id).order_by(NodeRevision.order_index)))


def tree(session, version_id):
    rows=revisions(session,version_id)
    index={r.id:{**revision_dict(r),'children':[]} for r in rows}
    roots=[]
    for r in rows:
        if r.parent_revision_id:
            index[r.parent_revision_id]['children'].append(index[r.id])
        else:
            roots.append(index[r.id])
    return roots


def diff(old, new):
    a=(old.heading+'\n'+old.body_text) if old else ''
    b=(new.heading+'\n'+new.body_text) if new else ''
    changes=list(ndiff(a.splitlines(),b.splitlines()))
    changed=old is None or new is None or old.content_hash!=new.content_hash
    return {'changed':changed,'previous_hash':old.content_hash if old else None,'current_hash':new.content_hash if new else None,'added_text':[s[2:] for s in changes if s.startswith('+ ')],'removed_text':[s[2:] for s in changes if s.startswith('- ')],'summary':'Source removed' if new is None else 'Source added' if old is None else 'Content changed; review required' if changed else 'Content unchanged'}
