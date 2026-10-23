from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, Request
from sqlalchemy import select, or_
from app.models.document import Document, DocumentVersion, NodeRevision, LogicalNode
from app.services.documents import require, get_version, revisions, tree, revision_dict, diff
from app.services.ingestion import ingest
from app.core.errors import DomainError

router=APIRouter(prefix='/api')


def db(request: Request):
    with request.app.state.sessions() as session:
        yield session


@router.post('/documents/ingest')
async def upload(request: Request, file: UploadFile=File(...), document_key: str=Form(...,min_length=1,max_length=150), session=Depends(db)):
    raw=await file.read(request.app.state.settings.max_upload_bytes+1)
    if len(raw)>request.app.state.settings.max_upload_bytes:
        raise DomainError(413,'PDF upload too large')
    version,duplicate=ingest(session,raw,file.filename or 'upload.pdf',document_key)
    return {'document_id':version.document_id,'version_id':version.id,'version':version.version_number,'duplicate':duplicate,'report':version.report}


@router.get('/documents')
def documents(session=Depends(db)):
    return list(session.scalars(select(Document).order_by(Document.id)))


@router.get('/documents/{document_id}/versions')
def versions(document_id:int,session=Depends(db)):
    require(session,Document,document_id)
    return list(session.scalars(select(DocumentVersion).where(DocumentVersion.document_id==document_id).order_by(DocumentVersion.version_number)))


@router.get('/documents/{document_id}/sections')
def sections(document_id:int,version:int|None=Query(None,gt=0),session=Depends(db)):
    v=get_version(session,document_id,version)
    return [revision_dict(r) for r in revisions(session,v.id) if r.parent_revision_id is None and r.section_number is not None]


@router.get('/documents/{document_id}/tree')
def full_tree(document_id:int,version:int|None=Query(None,gt=0),session=Depends(db)):
    return tree(session,get_version(session,document_id,version).id)


# Register search before the revision ID route.
@router.get('/nodes/search')
def search(q:str=Query(...,min_length=1,max_length=200),document_id:int|None=None,version:int|None=Query(None,gt=0),session=Depends(db)):
    query=select(NodeRevision).join(DocumentVersion).where(or_(NodeRevision.heading.contains(q,autoescape=True),NodeRevision.body_text.contains(q,autoescape=True)))
    if document_id is not None:
        require(session,Document,document_id)
        query=query.where(DocumentVersion.document_id==document_id)
        if version is not None:
            get_version(session,document_id,version)
    if version is not None:
        query=query.where(DocumentVersion.version_number==version)
    return [revision_dict(r) for r in session.scalars(query.order_by(DocumentVersion.id,NodeRevision.order_index).limit(200))]


@router.get('/nodes/{logical_node_id}/history')
def history(logical_node_id:int,session=Depends(db)):
    require(session,LogicalNode,logical_node_id)
    return [revision_dict(r) for r in session.scalars(select(NodeRevision).where(NodeRevision.logical_node_id==logical_node_id).order_by(NodeRevision.document_version_id))]


@router.get('/nodes/{logical_node_id}/diff')
def difference(logical_node_id:int,from_version:int=Query(...,gt=0),to_version:int=Query(...,gt=0),session=Depends(db)):
    logical=require(session,LogicalNode,logical_node_id)
    a=get_version(session,logical.document_id,from_version)
    b=get_version(session,logical.document_id,to_version)
    old=session.scalar(select(NodeRevision).where(NodeRevision.logical_node_id==logical.id,NodeRevision.document_version_id==a.id))
    new=session.scalar(select(NodeRevision).where(NodeRevision.logical_node_id==logical.id,NodeRevision.document_version_id==b.id))
    return diff(old,new)


@router.get('/nodes/{revision_id}')
def node(revision_id:int,session=Depends(db)):
    r=require(session,NodeRevision,revision_id)
    return {**revision_dict(r),'full_text':r.heading+'\n'+r.body_text,'children':[x.id for x in session.scalars(select(NodeRevision).where(NodeRevision.parent_revision_id==r.id).order_by(NodeRevision.order_index))]}
