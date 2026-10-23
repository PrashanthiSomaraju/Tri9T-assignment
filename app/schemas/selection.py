from pydantic import BaseModel, Field, ConfigDict


class SelectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=150)
    document_id: int = Field(gt=0)
    version: int = Field(gt=0)
    node_revision_ids: list[int] = Field(min_length=1, max_length=100)
    include_descendants: bool = False


class SelectionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    document_version_id: int
    node_revision_ids: list[int]
    include_descendants: bool
    fingerprint: str
