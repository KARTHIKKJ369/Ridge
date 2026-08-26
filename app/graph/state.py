"""
Ridge: LangGraph State & Data Schemas
=====================================
Defines the state structures, document grading models, and type definitions
used throughout the Corrective RAG state graph execution.
"""
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class GraphState(TypedDict):
    question: str
    original_question: str
    web_search_enabled: bool
    source_filter: Optional[str]         # Scoped retrieval to specific document/source
    user_id: Optional[str]               # Multi-tenant user isolation
    tenant_id: Optional[str]             # Multi-tenant organization isolation
    sub_queries: List[str]               # populated by decompose_node for multi-hop
    documents: List[str]
    documents_metadata: List[Dict[str, Any]]
    generation: str
    confidence: Dict[str, Any]
    conflict_data: Dict[str, Any]
    loop_count: int
    past_queries: List[str]
    latency_ms: int
    doc_grades: List[Dict[str, Any]]
    hallucination_grade: Dict[str, Any]
    expanded_count: Optional[int]


class DocGrade(BaseModel):
    index: int = Field(description="Index of the document")
    rationale: str = Field(description="Brief explanation of why the document is relevant or not")
    score: Literal["yes", "no"] = Field(description="'yes' if relevant or partially relevant, 'no' if completely unrelated")


class BatchGrades(BaseModel):
    grades: List[DocGrade] = Field(
        description="List of grades for all provided documents"
    )
