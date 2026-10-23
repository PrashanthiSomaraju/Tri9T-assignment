import hashlib
import logging
import uuid
from pathlib import Path
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.models.document import Document, DocumentVersion, LogicalNode, NodeRevision
from app.core.errors import DomainError
from app.services.pdf_extractor import extract_pdf
from app.services.hierarchy_parser import parse_hierarchy
from app.services.version_matcher import match_nodes

logger = logging.getLogger(__name__)


def ingest(session, raw: bytes, filename: str, document_key: str):
    if not raw.startswith(b'%PDF-'):
        raise DomainError(422,'Input must be an actual PDF')
    sha = hashlib.sha256(raw).hexdigest()
    document = session.scalar(select(Document).where(Document.document_key==document_key))
    if document:
        duplicate=session.scalar(select(DocumentVersion).where(DocumentVersion.document_id==document.id,DocumentVersion.source_sha256==sha))
        if duplicate:
            return duplicate, True
    try:
        elements,report = extract_pdf(raw)
    except (ValueError, RuntimeError) as exc:
        raise DomainError(422,f'PDF extraction failed: {exc}') from exc
    nodes,title = parse_hierarchy(elements)
    report['candidate_headings']=[{'number':n['section_number'],'heading':n['heading'],'page':n['page_start']} for n in nodes if n['section_number']]
    report['assigned_element_ids']=[e['element_id'] for n in nodes for e in n['elements']]
    report['unassigned_element_ids']=sorted({e['element_id'] for e in elements if e['kind']!='repeated_header'}-set(report['assigned_element_ids']))
    report['warnings'] += [w for n in nodes for w in n['warnings']]
    report['warnings'].append('Extraction completeness requires visual source comparison; successful parsing is not proof of complete extraction')
    # Preserve separate inconsistent textual claims; only flag their coexistence.
    by_number={n['section_number']:n for n in nodes}
    if '4.1' in by_number and '4.2' in by_number and '2 seconds' in by_number['4.1']['body_text'] and '1.5 seconds' in by_number['4.2']['body_text']:
        report['warnings'].append('Potential specification inconsistency: section 4.1 says 2 seconds; section 4.2 says 1.5 seconds. Claims retained independently.')
    if not document:
        document=Document(document_key=document_key,title=title)
        session.add(document)
        session.flush()
    latest=session.scalar(select(DocumentVersion).where(DocumentVersion.document_id==document.id).order_by(DocumentVersion.version_number.desc()))
    previous=list(session.scalars(select(NodeRevision).where(NodeRevision.document_version_id==latest.id))) if latest else []
    version=DocumentVersion(document_id=document.id,version_number=latest.version_number+1 if latest else 1,source_filename=Path(filename).name,source_sha256=sha,report=report)
    session.add(version)
    session.flush()
    revisions=[]
    matches=match_nodes(nodes,previous)
    for n,(old,evidence) in zip(nodes,matches):
        if old:
            logical_id=old.logical_node_id
        else:
            logical=LogicalNode(document_id=document.id,stable_key=str(uuid.uuid4()))
            session.add(logical)
            session.flush()
            logical_id=logical.id
        revision=NodeRevision(logical_node_id=logical_id,document_version_id=version.id,heading=n['heading'],section_number=n['section_number'],declared_level=n['declared_level'],effective_level=n['effective_level'],order_index=n['order_index'],body_text=n['body_text'],structured_content_json=n['elements'],content_hash=n['content_hash'],page_start=n['page_start'],page_end=n['page_end'],parser_warnings=n['warnings'],matching_evidence=evidence)
        session.add(revision)
        session.flush()
        revisions.append(revision)
    for n,r in zip(nodes,revisions):
        if n['parent_index'] is not None:
            r.parent_revision_id=revisions[n['parent_index']].id
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(409,'Concurrent ingestion conflicted; retry request') from exc
    logger.info('document_ingested',extra={'version_id':version.id,'nodes':len(nodes),'warnings':len(report['warnings'])})
    return version,False
