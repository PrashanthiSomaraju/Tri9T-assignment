import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from tests.fixtures.pdf_factory import make_pdf


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f'sqlite:///{tmp_path}/test.db',generation_dir=tmp_path/'json',_env_file=None)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def pdfs():
    return make_pdf(1),make_pdf(2)


def upload(client,raw,key='ct200'):
    response=client.post('/api/documents/ingest',files={'file':('synthetic.pdf',raw,'application/pdf')},data={'document_key':key})
    assert response.status_code==200,response.text
    return response.json()


def flat(tree):
    result=[]
    for n in tree:
        result.append(n)
        result.extend(flat(n['children']))
    return result


def nodes(client,document=1,version=1):
    response=client.get(f'/api/documents/{document}/tree',params={'version':version})
    assert response.status_code==200,response.text
    return {n['section_number']:n for n in flat(response.json()) if n['section_number']}


def selection(client,ids,name='Safety',version=1,**kwargs):
    r=client.post('/api/selections',json=dict(name=name,document_id=1,version=version,node_revision_ids=ids,**kwargs))
    assert r.status_code==200,r.text
    return r.json()
