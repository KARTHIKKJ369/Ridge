"""
Ingestion Run & Lineage Model
=============================
Tracks the provenance and execution lineage of every document ingestion:
parser, parser_version, chunker_version, embedding_model, OCR metrics,
dedup statistics, and processing latency for full reproducibility.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

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
    parser_name: Mapped[str] = mapped_column(String(128), default="unified", nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), default="1.0.0", nullable=False)
    chunker_version: Mapped[str] = mapped_column(String(64), default="structure_v1", nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    contextualization_model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    processing_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processing_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    table_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    figure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ocr_page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dedup_removed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)  # pending, completed, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    document = relationship("Document", back_populates="ingestion_runs")
    chunks = relationship("DocumentChunk", back_populates="ingestion_run")

    __table_args__ = (
        Index("ix_ingestion_runs_doc_status", "document_id", "status"),
        Index("ix_ingestion_runs_parser", "parser_name", "parser_version"),
    )
