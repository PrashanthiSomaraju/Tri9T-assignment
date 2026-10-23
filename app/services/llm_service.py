import json
from typing import Protocol
import httpx
from app.prompts.qa_generation import SYSTEM


class ProviderError(Exception):
    pass


class Provider(Protocol):
    name: str
    model: str
    def generate_test_cases(self, sources: list[dict], schema: dict, repair: list[str] | None = None) -> str: ...


class OpenAIProvider:
    name='openai-compatible'
    def __init__(self, settings):
        self.model=settings.model
        self.url=settings.llm_base_url.rstrip('/')+'/chat/completions'
        self.key=settings.llm_api_key.get_secret_value()
        if not self.key:
            raise ProviderError('CT_LLM_API_KEY is not configured')
        if not self.url.startswith('https://'):
            raise ProviderError('Provider endpoint must use HTTPS')

    def generate_test_cases(self, sources, schema, repair=None):
        messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps({'source_snapshots':sources,'schema':schema,'repair_errors':repair or []})}]
        try:
            response=httpx.post(self.url,headers={'Authorization':f'Bearer {self.key}'},json={'model':self.model,'temperature':0,'messages':messages,'response_format':{'type':'json_object'}},timeout=60)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            # Never expose response bodies, headers, URLs with query parameters or credentials.
            raise ProviderError(f'Provider request failed ({type(exc).__name__})') from None


class MockProvider:
    name='mock'
    model='mock-v1'
    def generate_test_cases(self, sources, schema, repair=None):
        """Explicit offline test double. These ideas are not live clinical QA recommendations."""
        cases=[]
        for i in range(3):
            source=sources[i%len(sources)]
            text=source['body_text'] or source['heading']
            mode=['nominal simulated behavior','specified boundary','controlled failure recovery'][i]
            cases.append(dict(title=f"Offline idea {i+1}: {source['heading']} — {mode}",objective=f"Review {mode} against the quoted requirement; identify applicability before execution",preconditions=['Controlled bench simulator; source requirement reviewed by an engineer'],steps=[f"Configure the simulator for {mode} only where supported by the quoted requirement",f"Capture observations and compare with: {text}"],expected_result=text,priority='high',category=['functional','boundary','failure'][i],source_revision_ids=[source['id']],source_quotes=[text]))
        return json.dumps({'test_cases':cases})


def provider_for(settings):
    if settings.provider=='mock':
        return MockProvider()
    if settings.provider=='openai-compatible':
        return OpenAIProvider(settings)
    raise ProviderError('Unknown CT_PROVIDER; use mock or openai-compatible')
