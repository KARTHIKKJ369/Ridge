"""
Document Figure & Visual Asset Model
====================================
Relational storage for diagrams, charts, and figures extracted from documents.
Preserves image reference, captions, OCR text, and visual descriptions for multi-modal indexing.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class DocumentFigure(Base):
    __tablename__ = "document_figures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    figure_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    caption: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    section_path: Mapped[str] = mapped_column(String(512), default="", nullable=False)

    image_path: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    ocr_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    nearby_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    document = relationship("Document", back_populates="figures")

    __table_args__ = (
        Index("ix_document_figures_doc_page", "document_id", "page_number"),
    )
