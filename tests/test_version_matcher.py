from types import SimpleNamespace
from tests.conftest import upload,nodes
from tests.fixtures.pdf_factory import make_pdf
from app.services.version_matcher import match_nodes


def test_unchanged_and_changed_identity(client,pdfs):
    upload(client,pdfs[0]); a=nodes(client)
    upload(client,pdfs[1]); b=nodes(client,version=2)
    for number in ['1','2.1.1.1','3.2','4.2','7.1']:
        assert a[number]['logical_node_id']==b[number]['logical_node_id']
        assert a[number]['id']!=b[number]['id']
    assert a['1']['content_hash']==b['1']['content_hash']
    assert a['2.1.1.1']['content_hash']!=b['2.1.1.1']['content_hash']
    assert '5.3' not in a and '5.3' in b
    assert 'E6' not in a['4.2']['body_text'] and 'E6' in b['4.2']['body_text']
    assert len(client.get('/api/documents/1/versions').json())==2


def test_duplicate_upload(client,pdfs):
    first=upload(client,pdfs[0]); second=upload(client,pdfs[0])
    assert first['version_id']==second['version_id'] and second['duplicate']
    assert len(client.get('/api/documents/1/versions').json())==1


def test_ambiguous_match():
    prior=[SimpleNamespace(id=i,logical_node_id=i,section_number=str(i),parent_revision_id=None,heading='Renamed heading',body_text='Exactly identical content') for i in (1,2)]
    n=dict(section_number='3',heading='Renamed heading',body_text='Exactly identical content',parent_index=None,warnings=[])
    result=match_nodes([n],prior)
    assert result[0][0] is None
    assert result[0][1]['candidate_logical_ids']==[1,2]
    assert n['warnings']


def test_removed_diff(client,pdfs):
    upload(client,pdfs[0]); a=nodes(client)
    upload(client,make_pdf(2,removed=True))
    r=client.get(f"/api/nodes/{a['8.1']['logical_node_id']}/diff",params={'from_version':1,'to_version':2})
    assert r.status_code==200 and r.json()['current_hash'] is None
