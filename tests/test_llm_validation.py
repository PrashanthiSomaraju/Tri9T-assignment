import json
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.llm_service import MockProvider, ProviderError
from app.services.generation_service import validate_output
from tests.conftest import upload, nodes, selection

SOURCES = [{"id": 1, "heading": "Battery", "body_text": "300 cycles"}]


def valid():
    return json.loads(MockProvider().generate_test_cases(SOURCES, {}))


def test_valid_provider_json():
    assert len(validate_output(json.dumps(valid()), SOURCES)["test_cases"]) == 3


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "wrong_type",
        "bad_id",
        "bad_quote",
        "short",
        "empty",
        "duplicate",
        "preconditions",
    ],
)
def test_invalid_outputs(mutation):
    value = valid()
    case = value["test_cases"][0]
    if mutation == "missing":
        del case["title"]
    if mutation == "wrong_type":
        case["source_revision_ids"] = ["1"]
    if mutation == "bad_id":
        case["source_revision_ids"] = [99]
    if mutation == "bad_quote":
        case["source_quotes"] = ["Invented threshold"]
    if mutation == "short":
        value["test_cases"] = value["test_cases"][:2]
    if mutation == "empty":
        case["steps"] = []
    if mutation == "duplicate":
        value["test_cases"][1]["title"] = case["title"]
    if mutation == "preconditions":
        case["preconditions"] = []
    with pytest.raises(ValueError):
        validate_output(json.dumps(value), SOURCES)


class SequenceProvider(MockProvider):
    def __init__(self, failures):
        self.failures = failures
        self.calls = 0
        self.repairs = []

    def generate_test_cases(self, sources, schema, repair=None):
        self.calls += 1
        self.repairs.append(repair)
        return (
            "{bad json"
            if self.calls <= self.failures
            else super().generate_test_cases(sources, schema, repair)
        )


@pytest.mark.parametrize("failures,expected_status,calls", [(1, 200, 2), (10, 502, 3)])
def test_repair_failure_persistence(settings, pdfs, failures, expected_status, calls):
    provider = SequenceProvider(failures)
    with TestClient(create_app(settings, provider)) as client:
        upload(client, pdfs[0])
        a = nodes(client)
        s = selection(client, [a["4.1"]["id"]])
        r = client.post(f"/api/selections/{s['id']}/generate", json={})
        assert r.status_code == expected_status, r.text
        assert provider.calls == calls and provider.repairs[1]
        g = r.json()["generation"]
        assert g["status"] == ("success" if failures == 1 else "failed")
        assert client.get(f"/api/generations/{g['id']}").status_code == 200
        assert len(list(settings.generation_dir.glob("*.json"))) == 1
        if failures > 1:
            assert g["test_cases"] == [] and g["validation"]["errors"]


def test_generation_cache(client, pdfs):
    upload(client, pdfs[0])
    a = nodes(client)
    s = selection(client, [a["4.1"]["id"]])
    path = f"/api/selections/{s['id']}/generate"
    first = client.post(path, json={}).json()["generation"]
    assert client.post(path, json={}).json()["generation"]["id"] == first["id"]
    assert (
        client.post(path, json={"force_regenerate": True}).json()["generation"]["id"]
        != first["id"]
    )
    assert len(client.get(f"/api/selections/{s['id']}/generations").json()) == 2


def test_file_write_failure_no_database_row(client, pdfs, monkeypatch):
    from sqlalchemy import select
    from app.models.generation import Generation

    upload(client, pdfs[0])
    a = nodes(client)
    s = selection(client, [a["4.1"]["id"]])

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(client.app.state.store, "write", fail)
    assert (
        client.post(f"/api/selections/{s['id']}/generate", json={}).status_code == 503
    )
    with client.app.state.sessions() as session:
        assert list(session.scalars(select(Generation))) == []


def test_provider_transport_failure_is_recorded(settings, pdfs):
    class Broken(MockProvider):
        def generate_test_cases(self, *args, **kwargs):
            raise ProviderError("Provider request failed (ConnectError)")

    with TestClient(create_app(settings, Broken())) as client:
        upload(client, pdfs[0])
        a = nodes(client)
        s = selection(client, [a["4.1"]["id"]])
        r = client.post(f"/api/selections/{s['id']}/generate", json={})
        assert (
            r.status_code == 502
            and r.json()["generation"]["validation"]["repair_attempts"] == 0
        )


def test_real_provider_adapter_without_live_network(settings, monkeypatch):
    from app.services.llm_service import OpenAIProvider
    import httpx

    settings.model = "configured-model"
    settings.llm_api_key = "not-a-real-key"

    def post(url, **kwargs):
        assert kwargs["json"]["model"] == "configured-model"
        assert kwargs["json"]["response_format"] == {"type": "json_object"}
        assert kwargs["json"]["temperature"] == 0
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(valid())}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", post)
    raw = OpenAIProvider(settings).generate_test_cases(SOURCES, {})
    assert len(validate_output(raw, SOURCES)["test_cases"]) == 3


def test_heading_only_selection_cannot_generate(client, pdfs):
    upload(client, pdfs[0])
    a = nodes(client)
    s = selection(client, [a["2"]["id"]])
    r = client.post(f"/api/selections/{s['id']}/generate", json={})
    assert r.status_code == 422 and "no readable requirement" in r.json()["detail"]
