from sqlalchemy import select
from app.models.document import NodeRevision
from app.services.documents import get_version, revisions, diff

# Multiple statuses are retained in source details; aggregate uses this precedence.
PRECEDENCE={'current':0,'review_required':1,'stale':2,'source_removed':3,'unresolved':4}


def impact(session, content):
    latest=get_version(session,content['document_id'])
    latest_rows=revisions(session,latest.id)
    current={r.logical_node_id:r for r in latest_rows}
    source_status={}
    for source in content['sources']:
        old=session.get(NodeRevision,source['id'])
        new=current.get(source['logical_node_id'])
        ambiguous=any(source['logical_node_id'] in r.matching_evidence.get('candidate_logical_ids',[]) for r in latest_rows)
        if old is None or ambiguous:
            status='unresolved'
        elif new is None:
            status='source_removed'
        elif new.content_hash!=source['content_hash']:
            status='stale'
        elif new.matching_evidence.get('method')=='heading_body_similarity' or any(any(marker in w for marker in ('ambiguous','truncated','uncertain')) for w in new.parser_warnings) or any('OCR' in w or 'columns' in w for w in latest.report['warnings']):
            status='review_required'
        else:
            status='current'
        source_status[source['id']]={'status':status,'requires_review':status!='current','source_revision_id':source['id'],'logical_node_id':source['logical_node_id'],'source_section':old.section_number if old else None,'generated_from_version':content['version_number'],'latest_version':latest.version_number,'diff':diff(old,new)}
    tests=[]
    for test in content['test_cases']:
        details=[source_status[i] for i in test['source_revision_ids']]
        status=max((d['status'] for d in details),key=PRECEDENCE.get)
        tests.append({'title':test['title'],'status':status,'requires_review':status!='current','sources':details})
    aggregate=max((t['status'] for t in tests),key=PRECEDENCE.get,default='unresolved')
    return {'status':aggregate,'requires_review':aggregate!='current','tests':tests,'sources':list(source_status.values()),'latest_version':latest.version_number,'note':'Hash changes indicate changed source text, not proven behavioral invalidity.'}
