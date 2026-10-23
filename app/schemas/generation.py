from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True,min_length=1)]


class TestCase(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    title: Text
    objective: Text
    preconditions: list[Text]
    no_preconditions_reason: Text | None = None
    steps: list[Text] = Field(min_length=1)
    expected_result: Text
    priority: Literal['critical','high','medium','low']
    category: Literal['safety','functional','boundary','failure','performance']
    source_revision_ids: list[int] = Field(min_length=1)
    source_quotes: list[Text] = Field(min_length=1)

    @model_validator(mode='after')
    def preconditions_or_reason(self):
        if not self.preconditions and not self.no_preconditions_reason:
            raise ValueError('Empty preconditions require a justification')
        if len(set(self.source_revision_ids))!=len(self.source_revision_ids):
            raise ValueError('Duplicate source revisions')
        return self


class TestCases(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    test_cases: list[TestCase] = Field(min_length=3,max_length=5)


class GenerateRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    force_regenerate: bool = False
