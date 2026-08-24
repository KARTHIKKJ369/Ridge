"""
Document Model
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, BigInteger, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream", nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), default="file", nullable=False)  # file, url, text, youtube
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="indexed", nullable=False)  # pending, indexed, failed
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

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
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    uploader = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    ingestion_runs = relationship("IngestionRun", back_populates="document", cascade="all, delete-orphan")
    tables = relationship("DocumentTable", back_populates="document", cascade="all, delete-orphan")
    figures = relationship("DocumentFigure", back_populates="document", cascade="all, delete-orphan")
    glossary_terms = relationship("GlossaryTerm", back_populates="source_document")


    __table_args__ = (
        Index("ix_documents_kb_filename", "knowledge_base_id", "filename"),
        Index("ix_documents_source_url", "source_url"),
    )
