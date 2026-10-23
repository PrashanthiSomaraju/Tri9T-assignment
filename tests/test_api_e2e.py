from fastapi.testclient import TestClient
from app.main import create_app
from tests.conftest import upload, nodes, selection


def test_restart_persistence(settings, pdfs):
    with TestClient(create_app(settings)) as client:
        upload(client, pdfs[0])
        a = nodes(client)
        s = selection(client, [a["4.1"]["id"]])
        g = client.post(f"/api/selections/{s['id']}/generate", json={}).json()[
            "generation"
        ]
    with TestClient(create_app(settings)) as client:
        assert len(client.get("/api/documents/1/versions").json()) == 1
        assert client.get(f"/api/generations/{g['id']}").json()["generation"] == g
        assert client.get("/health").json()["status"] == "ok"


def test_errors_and_search(client, pdfs):
    assert (
        client.post(
            "/api/documents/ingest",
            files={"file": ("x.pdf", b"not pdf")},
            data={"document_key": "x"},
        ).status_code
        == 422
    )
    upload(client, pdfs[0])
    a = nodes(client)
    assert client.get("/api/documents/999/tree").status_code == 404
    assert client.get("/api/documents/1/tree?version=999").status_code == 404
    assert client.get("/api/documents/1/tree?version=0").status_code == 422
    assert client.get("/api/nodes/9999").status_code == 404
    assert client.get("/api/nodes/search?q=299&document_id=1&version=1").json()
    assert (
        len(client.get("/api/nodes/search?q=%25").json()) == 1
    )  # literal percent in battery text, not SQL wildcard
    assert client.get(f"/api/nodes/{a['4.1']['id']}").json()["full_text"]
    assert (
        len(client.get(f"/api/nodes/{a['4.1']['logical_node_id']}/history").json()) == 1
    )
    assert client.get("/openapi.json").status_code == 200
