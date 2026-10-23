from datetime import datetime, timezone
from sqlalchemy import ForeignKey, UniqueConstraint, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def now():
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_key: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=now)


class DocumentVersion(Base):
    __tablename__ = "versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number"),
        UniqueConstraint("document_id", "source_sha256"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    version_number: Mapped[int]
    source_filename: Mapped[str]
    source_sha256: Mapped[str]
    report: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=now)


class LogicalNode(Base):
    __tablename__ = "logical_nodes"
    __table_args__ = (UniqueConstraint("document_id", "stable_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    stable_key: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=now)


class NodeRevision(Base):
    __tablename__ = "revisions"
    __table_args__ = (UniqueConstraint("logical_node_id", "document_version_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    logical_node_id: Mapped[int] = mapped_column(ForeignKey("logical_nodes.id"))
    document_version_id: Mapped[int] = mapped_column(ForeignKey("versions.id"))
    parent_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("revisions.id"), nullable=True
    )
    heading: Mapped[str]
    section_number: Mapped[str | None]
    declared_level: Mapped[int]
    effective_level: Mapped[int]
    order_index: Mapped[int]
    body_text: Mapped[str]
    structured_content_json: Mapped[list] = mapped_column(JSON)
    content_hash: Mapped[str]
    page_start: Mapped[int]
    page_end: Mapped[int]
    parser_warnings: Mapped[list] = mapped_column(JSON)
    matching_evidence: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=now)
