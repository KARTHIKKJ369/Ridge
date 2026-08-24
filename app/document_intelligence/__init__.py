"""
Ridge Document Intelligence Package
===================================
Provides structure-aware document parsing, layout-preserving AST representations,
multimodal extraction, and lineage-backed chunking.
"""
from app.document_intelligence.ast import (
    ElementType,
    BlockAST,
    TableBlock,
    FigureBlock,
    PageAST,
    DocumentAST,
)
from app.document_intelligence.parser import (
    BaseDocumentParser,
    UnifiedDocumentParser,
    get_document_parser,
)
from app.document_intelligence.chunker import (
    StructureAwareChunker,
    StructuredChunk,
)
from app.document_intelligence.dedup import (
    SimHasher,
    BoilerplateDetector,
    Deduplicator,
    get_deduplicator,
)

__all__ = [
    "ElementType",
    "BlockAST",
    "TableBlock",
    "FigureBlock",
    "PageAST",
    "DocumentAST",
    "BaseDocumentParser",
    "UnifiedDocumentParser",
    "get_document_parser",
    "StructureAwareChunker",
    "StructuredChunk",
    "SimHasher",
    "BoilerplateDetector",
    "Deduplicator",
    "get_deduplicator",
]


