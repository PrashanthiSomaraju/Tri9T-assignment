from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DocumentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_key: str
    title: str
    created_at: datetime


class VersionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    version_number: int
    source_filename: str
    source_sha256: str
    report: dict
    created_at: datetime


class NodeView(BaseModel):
    id: int
    logical_node_id: int
    document_version_id: int
    parent_revision_id: int | None
    heading: str
    section_number: str | None
    declared_level: int
    effective_level: int
    order_index: int
    body_text: str
    structured_content_json: list[dict]
    content_hash: str
    page_start: int
    page_end: int
    parser_warnings: list[str]
    matching_evidence: dict


class TreeView(NodeView):
    children: list["TreeView"]


class NodeDetail(NodeView):
    full_text: str
    children: list[int]


class IngestionView(BaseModel):
    document_id: int
    version_id: int
    version: int
    duplicate: bool
    report: dict


class DiffView(BaseModel):
    changed: bool
    previous_hash: str | None
    current_hash: str | None
    added_text: list[str]
    removed_text: list[str]
    summary: str
