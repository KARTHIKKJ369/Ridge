"""
Document Table Model
====================
Relational storage for structured tables extracted from documents (PDFs, DOCX, XLSX, etc.).
Preserves headers, structured JSON, markdown text, and search text representation.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class DocumentTable(Base):
    __tablename__ = "document_tables"

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
    table_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    caption: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    section_path: Mapped[str] = mapped_column(String(512), default="", nullable=False)

    headers_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    rows_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    markdown_text: Mapped[str] = mapped_column(Text, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    document = relationship("Document", back_populates="tables")

    __table_args__ = (
        Index("ix_document_tables_doc_page", "document_id", "page_number"),
    )
