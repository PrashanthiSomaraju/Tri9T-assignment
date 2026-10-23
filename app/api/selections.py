from fastapi import APIRouter, Depends
from app.api.documents import db
from app.models.selection import Selection
from app.schemas.selection import SelectionCreate
from app.services.selection_service import create_selection
from app.services.documents import require, revision_dict
from app.models.document import NodeRevision

router=APIRouter(prefix='/api/selections')


@router.post('')
def create(request:SelectionCreate,session=Depends(db)):
    return create_selection(session,request)


@router.get('/{selection_id}')
def get(selection_id:int,session=Depends(db)):
    s=require(session,Selection,selection_id)
    return {'id':s.id,'name':s.name,'document_version_id':s.document_version_id,'node_revision_ids':s.node_revision_ids,'include_descendants':s.include_descendants,'fingerprint':s.fingerprint,'nodes':[revision_dict(require(session,NodeRevision,i)) for i in s.node_revision_ids]}
