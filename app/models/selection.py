from datetime import datetime
from sqlalchemy import ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.document import now


class Selection(Base):
    __tablename__ = "selections"
    __table_args__ = (UniqueConstraint("document_version_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    document_version_id: Mapped[int] = mapped_column(ForeignKey("versions.id"))
    node_revision_ids: Mapped[list] = mapped_column(JSON)
    include_descendants: Mapped[bool]
    fingerprint: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=now)
