from tests.conftest import upload,nodes,selection
from tests.fixtures.pdf_factory import make_pdf


def test_full_e2e_stale_current_historical(client,pdfs):
    upload(client,pdfs[0]);a=nodes(client)
    s=selection(client,[a[k]['id'] for k in ['2.1.1.1','3.2','4.1']])
    initial=client.post(f"/api/selections/{s['id']}/generate",json={}).json()
    assert initial['staleness']['status']=='current'
    g=initial['generation'];upload(client,pdfs[1])
    result=client.get(f"/api/generations/{g['id']}").json()
    assert result['generation']==g
    assert [t['status'] for t in result['staleness']['tests']]==['stale','stale','current']
    assert '250 measurement' in str(result['staleness']['tests'][0]['sources'][0]['diff'])
    by_node=client.get(f"/api/nodes/{a['2.1.1.1']['logical_node_id']}/generations").json()
    assert by_node[0]['generation']['version_number']==1
    assert by_node[0]['staleness']['status']=='stale'
    assert client.get(f"/api/selections/{s['id']}/generations").json()[0]['staleness']['status']=='stale'


def test_e3_stale(client,pdfs):
    upload(client,pdfs[0]);a=nodes(client);s=selection(client,[a['4.2']['id']])
    g=client.post(f"/api/selections/{s['id']}/generate",json={}).json()['generation']
    assert '2 seconds' in g['sources'][0]['body_text']
    upload(client,pdfs[1]);r=client.get(f"/api/generations/{g['id']}").json()
    assert r['staleness']['status']=='stale'
    assert '1.5 seconds' in str(r['staleness'])


def test_source_removed(client,pdfs):
    upload(client,pdfs[0]);a=nodes(client);s=selection(client,[a['7.1']['id']])
    g=client.post(f"/api/selections/{s['id']}/generate",json={}).json()['generation']
    # Remove heading and body using a new actual synthetic PDF.
    import fitz
    doc=fitz.open(stream=make_pdf(2),filetype='pdf')
    for page in doc:
        for text in ['7.1 Error Codes','Refer to service support for recurring errors.']:
            for rect in page.search_for(text): page.add_redact_annot(rect)
        page.apply_redactions()
    upload(client,doc.tobytes())
    r=client.get(f"/api/generations/{g['id']}").json()
    assert r['staleness']['status']=='source_removed'
