from tests.conftest import upload,nodes,selection


def test_pinned_and_duplicate(client,pdfs):
    upload(client,pdfs[0]); a=nodes(client)
    s=selection(client,[a['2.1.1.1']['id']])
    assert selection(client,[a['2.1.1.1']['id']])['id']==s['id']
    before=client.get(f"/api/selections/{s['id']}").json()
    upload(client,pdfs[1])
    assert client.get(f"/api/selections/{s['id']}").json()==before
    assert '300 measurement' in before['nodes'][0]['body_text']


def test_conflict_and_invalid(client,pdfs):
    upload(client,pdfs[0]); a=nodes(client)
    selection(client,[a['1']['id']])
    body=dict(name='Safety',document_id=1,version=1,node_revision_ids=[a['3.2']['id']])
    assert client.post('/api/selections',json=body).status_code==409
    body['name']='Invalid';body['node_revision_ids']=[9999]
    assert client.post('/api/selections',json=body).status_code==422
    upload(client,pdfs[1]); b=nodes(client,version=2)
    body['node_revision_ids']=[a['1']['id'],b['1']['id']]
    assert client.post('/api/selections',json=body).status_code==422


def test_descendants(client,pdfs):
    upload(client,pdfs[0]); a=nodes(client)
    s=selection(client,[a['2']['id']],include_descendants=True)
    assert set(s['node_revision_ids'])=={a[k]['id'] for k in ['2','2.1','2.1.1.1']}
