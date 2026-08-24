"""
Retrieval Interfaces and Candidate Models
=========================================
Defines the clean boundary between LangGraph orchestration and vector/lexical retrieval engines.
"""
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field


class RetrievalCandidate(BaseModel):
    text: str
    metadata: dict = Field(default_factory=dict)
    dense_score: float = 0.0
    sparse_score: float = 0.0
    rrf_score: float = 0.0
    final_score: float = 0.0
    chunk_id: Optional[str] = None
    parent_id: Optional[str] = None
    is_expanded: bool = False


class BaseRetriever(ABC):
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        source_filter: Optional[str] = None,
        k: int = 50,
    ) -> list[RetrievalCandidate]:
        """Performs dense + sparse search with Reciprocal Rank Fusion."""
        pass
