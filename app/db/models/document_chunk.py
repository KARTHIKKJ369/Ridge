"""
Document Chunk Model with Small-to-Big Hierarchy & Full-Text Search TSVector
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

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
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    contextual_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)  # text, table, code, figure, list

    heading: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    section: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_boilerplate: Mapped[bool] = mapped_column(default=False, nullable=False)
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    document = relationship("Document", back_populates="chunks")
    parent_chunk = relationship("DocumentChunk", remote_side=[id], foreign_keys=[parent_chunk_id], back_populates="child_chunks")
    child_chunks = relationship("DocumentChunk", foreign_keys=[parent_chunk_id], back_populates="parent_chunk", cascade="all, delete-orphan")
    ingestion_run = relationship("IngestionRun", back_populates="chunks")
    embeddings = relationship("ChunkEmbedding", back_populates="chunk", cascade="all, delete-orphan")
    citations = relationship("MessageCitation", back_populates="chunk")
    retrieval_results = relationship("RetrievalResult", back_populates="chunk")

    __table_args__ = (
        Index("ix_chunks_doc_index", "document_id", "chunk_index"),
        Index("ix_chunks_content_type", "content_type"),
        Index("ix_chunks_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_chunks_metadata_json", "metadata_json", postgresql_using="gin"),
    )

