"""
Retrieval Observability Models: Runs and Results
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Float, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class RetrievalRun(Base):
    __tablename__ = "retrieval_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    rewritten_query: Mapped[str] = mapped_column(Text, default="", nullable=False)
    retrieval_strategy: Mapped[str] = mapped_column(String(64), default="hybrid_rrf", nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    conversation = relationship("Conversation", back_populates="retrieval_runs")
    message = relationship("Message", back_populates="retrieval_runs")
    results = relationship("RetrievalResult", back_populates="retrieval_run", cascade="all, delete-orphan")


class RetrievalResult(Base):
    __tablename__ = "retrieval_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    retrieval_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("retrieval_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dense_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sparse_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rrf_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rerank_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    final_rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    retrieval_run = relationship("RetrievalRun", back_populates="results")
    chunk = relationship("DocumentChunk", back_populates="retrieval_results")

    __table_args__ = (
        Index("ix_retrieval_results_run_rank", "retrieval_run_id", "final_rank"),
    )
