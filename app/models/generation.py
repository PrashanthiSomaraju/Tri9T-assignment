from datetime import datetime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.document import now


class Generation(Base):
    __tablename__ = "generations"
    id: Mapped[str] = mapped_column(primary_key=True)
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"))
    provider: Mapped[str]
    model_name: Mapped[str]
    prompt_version: Mapped[str]
    input_fingerprint: Mapped[str]
    cache_key: Mapped[str] = mapped_column(index=True)
    status: Mapped[str]
    retry_count: Mapped[int]
    json_location: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=now)
