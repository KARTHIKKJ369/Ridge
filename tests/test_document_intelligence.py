"""
Document Intelligence & Ingestion Lineage Test Suite
===================================================
Tests AST representation, structure-aware parsing, table/figure preservation,
and IngestionRun lineage tracking across document types.
"""
import os
import uuid
import pytest
from datetime import datetime, timezone

from app.document_intelligence.ast import (
    ElementType,
    BlockAST,
    TableBlock,
    FigureBlock,
    PageAST,
    DocumentAST,
)
from app.document_intelligence.parser import (
    PDFStructureParser,
    OfficeDocumentParser,
    MarkdownAndWebParser,
    UnifiedDocumentParser,
    get_document_parser,
)
from app.document_intelligence.chunker import (
    StructureAwareChunker,
    StructuredChunk,
)
from app.db.models.ingestion_run import IngestionRun


from app.db.models.document_table import DocumentTable
from app.db.models.document_figure import DocumentFigure
from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk


class TestDocumentAST:
    def test_ast_block_search_representation(self):
        block = BlockAST(
            element_type=ElementType.PARAGRAPH,
            content="This is the model architecture description.",
            raw_content="This is the model architecture description.",
            section_path="System Whitepaper > Architecture",
            heading="Architecture",
        )
        search_text = block.get_search_text()
        assert "[Context: System Whitepaper > Architecture]" in search_text
        assert "This is the model architecture description." in search_text

    def test_table_block_markdown_generation(self):
        tbl = TableBlock(
            caption="Q3 Financial Highlights",
            section_path="Annual Report > Financials",
            headers=["Metric", "2023", "2024"],
            rows=[
                ["Revenue", "$100M", "$125M"],
                ["Operating Margin", "22%", "28%"],
            ],
        )
        md = tbl.generate_markdown()
        assert "### Table: Q3 Financial Highlights" in md
        assert "| Metric | 2023 | 2024 |" in md
        assert "| Revenue | $100M | $125M |" in md
        assert tbl.element_type == ElementType.TABLE

    def test_figure_block_search_text(self):
        fig = FigureBlock(
            caption="System Latency Benchmark",
            section_path="Paper > Evaluation",
            description="Bar chart showing p95 latency under 60ms",
            ocr_text="p95 < 60ms; Throughput 500 req/s",
        )
        search_text = fig.get_search_text()
        assert "Figure: System Latency Benchmark" in search_text
        assert "Description: Bar chart showing p95 latency under 60ms" in search_text
        assert "Text in figure: p95 < 60ms" in search_text

    def test_document_ast_serialization(self):
        doc = DocumentAST(
            filename="test_doc.md",
            source_type="file",
        )
        page = PageAST(page_number=1)
        page.add_block(BlockAST(
            element_type=ElementType.HEADING,
            content="Introduction",
            metadata={"level": 1},
        ))
        page.add_block(BlockAST(
            element_type=ElementType.PARAGRAPH,
            content="Ridge is a corrective RAG platform.",
        ))
        doc.pages.append(page)

        assert len(doc.all_blocks()) == 2
        md = doc.to_markdown()
        assert "# Introduction" in md
        assert "Ridge is a corrective RAG platform." in md


class TestDocumentParsers:
    def test_markdown_parser(self):
        parser = MarkdownAndWebParser()
        raw_text = "# Overview\nRidge provides pgvector retrieval.\n\n## Performance\nFlashRank reranker reduces noise."
        ast = parser.parse(raw_text, original_filename="readme.md")

        assert len(ast.pages) == 1
        blocks = ast.all_blocks()
        assert len(blocks) >= 3
        assert any(b.element_type == ElementType.HEADING and b.content == "Overview" for b in blocks)
        assert any(b.element_type == ElementType.HEADING and b.content == "Performance" for b in blocks)

    def test_unified_parser_routing(self):
        unified = get_document_parser()
        ast, parser_name, parser_version = unified.parse(
            "# Ridge Ingestion\nValidating unified parser abstraction.",
            original_filename="sample.txt"
        )
        assert parser_name == "markdown_web_parser"
        assert len(ast.all_blocks()) >= 1


class TestIngestionLineageModels:
    def test_ingestion_run_initialization(self):
        doc_id = uuid.uuid4()
        run = IngestionRun(
            document_id=doc_id,
            parser_name="pdf_structure_parser",
            parser_version="1.1.0",
            chunker_version="structure_v1",
            embedding_model="BAAI/bge-large-en-v1.5",
            chunk_count=12,
            parent_count=3,
            table_count=2,
            figure_count=1,
            ocr_page_count=0,
            status="completed",
        )
        assert run.document_id == doc_id
        assert run.chunk_count == 12
        assert run.table_count == 2
        assert run.status == "completed"

    def test_document_chunk_lineage_fields(self):
        doc_id = uuid.uuid4()
        run_id = uuid.uuid4()
        chunk = DocumentChunk(
            document_id=doc_id,
            ingestion_run_id=run_id,
            content="Child chunk content with breadcrumb",
            raw_content="Raw verbatim chunk text without prefixes",
            contextual_content="[Document: Apple 10-K] Services margin discussion",
            content_type="text",
            is_boilerplate=False,
        )
        assert chunk.raw_content == "Raw verbatim chunk text without prefixes"
        assert chunk.contextual_content == "[Document: Apple 10-K] Services margin discussion"
        assert chunk.content_type == "text"
        assert chunk.is_boilerplate is False


class TestStructureAwareChunker:
    def test_chunk_document_with_table_and_paragraphs(self):
        from app.document_intelligence.chunker import StructureAwareChunker

        doc = DocumentAST(
            filename="financial_report.pdf",
            source_type="file",
        )
        page = PageAST(page_number=1)
        page.add_block(BlockAST(
            element_type=ElementType.HEADING,
            content="Executive Summary",
            metadata={"level": 1},
        ))
        page.add_block(BlockAST(
            element_type=ElementType.PARAGRAPH,
            content="The company delivered strong Q3 financial results with revenue growing 18% year-over-year.",
            raw_content="The company delivered strong Q3 financial results with revenue growing 18% year-over-year.",
        ))
        page.add_block(TableBlock(
            caption="Q3 Segment Breakdown",
            section_path="financial_report.pdf > Executive Summary",
            headers=["Division", "Revenue", "Growth"],
            rows=[
                ["Enterprise Cloud", "$85M", "+24%"],
                ["Consumer Hardware", "$40M", "+6%"],
            ],
        ))
        page.add_block(FigureBlock(
            caption="Operating Margin Trajectory",
            section_path="financial_report.pdf > Executive Summary",
            description="Line chart showing margin expansion from 22% to 28%",
            ocr_text="Operating Margin 28%",
        ))
        doc.pages.append(page)

        chunker = StructureAwareChunker(target_chunk_size=500, child_chunk_size=200)
        parents, children = chunker.chunk_document(doc)

        assert len(parents) >= 3  # Paragraphs parent, Table parent, Figure parent
        assert len(children) >= 3

        # Verify Table chunk integrity
        table_parent = next((p for p in parents if p.content_type == "table"), None)
        assert table_parent is not None
        assert "Table: Q3 Segment Breakdown" in table_parent.content
        assert "| Enterprise Cloud | $85M | +24% |" in table_parent.raw_content

        # Verify Figure chunk integrity
        fig_parent = next((p for p in parents if p.content_type == "figure"), None)
        assert fig_parent is not None
        assert "Figure: Operating Margin Trajectory" in fig_parent.content

        # Verify Parent-Child linkage
        for c in children:
            assert c.parent_id is not None
            assert any(p.id == c.parent_id for p in parents)


class TestContextualRetrievalEngine:
    def test_deterministic_context_generation(self):
        from app.retrieval.contextual import ContextualRetrievalEngine

        engine = ContextualRetrievalEngine(enabled=True)
        chunk = StructuredChunk(
            content_type="table",
            page_number=3,
            heading="Services Revenue",
            section_path="Apple 10-Q > Financial Results > Services Revenue",
            raw_content="| Services | $24.2B | +12% |",
        )
        context = engine.generate_deterministic_context(chunk, doc_title="Apple_Q3_2024_10Q.pdf")
        assert "Document: Apple_Q3_2024_10Q.pdf" in context
        assert "Section: Apple 10-Q > Financial Results > Services Revenue" in context
        assert "Page 3" in context
        assert "Tabular Data" in context

    def test_enrich_chunks_preserves_raw_content(self):
        from app.retrieval.contextual import ContextualRetrievalEngine

        engine = ContextualRetrievalEngine(enabled=True)
        chunks = [
            StructuredChunk(
                raw_content="Operating margin reached 28.4% in the third quarter.",
                section_path="Financials > Operating Metrics",
                page_number=2,
            )
        ]
        enriched = engine.enrich_chunks(chunks, doc_title="Annual_Report.pdf", use_llm=False)
        assert len(enriched) == 1
        c = enriched[0]
        assert c.contextual_content is not None
        assert "[Document: Annual_Report.pdf | Section: Financials > Operating Metrics | Page 2]" in c.contextual_content
        assert c.raw_content == "Operating margin reached 28.4% in the third quarter."
        assert c.raw_content in c.content


class TestContextPacker:
    def test_context_packing_and_deduplication(self):
        from app.retrieval.context_packer import ContextPacker
        from parent_store import save_parents

        # Save a parent in memory
        save_parents([{
            "id": "pid_sample_123",
            "text": "Full parent section regarding neural reranking and cross-entropy scoring in Ridge CRAG.",
            "metadata": {"source": "architecture.md", "h1": "Reranking"},
        }])

        packer = ContextPacker(max_chars_per_passage=1000, max_total_chars=2000)

        passages = [
            {
                "text": "child chunk 1",
                "meta": {"chunk_id": "c1", "parent_id": "pid_sample_123", "score": 0.95},
                "score": 0.95,
            },
            {
                "text": "child chunk 2 (same parent)",
                "meta": {"chunk_id": "c2", "parent_id": "pid_sample_123", "score": 0.88},
                "score": 0.88,
            },
            {
                "text": "independent chunk 3",
                "meta": {"chunk_id": "c3", "parent_id": "pid_diff_456", "score": 0.75},
                "score": 0.75,
            },
        ]

        packed_texts, packed_metas, exp_count = packer.pack_context(passages, top_k=5)

        # Child 1 and Child 2 should be deduplicated into a single parent passage
        assert len(packed_texts) == 2
        assert "Full parent section regarding neural reranking" in packed_texts[0]
        assert exp_count >= 1


class TestDeduplicationEngine:
    def test_simhash_fingerprinting_and_hamming(self):
        from app.document_intelligence.dedup import SimHasher

        t1 = "Ridge is a state-of-the-art corrective RAG system powered by pgvector and FlashRank."
        t2 = "Ridge is a state-of-the-art corrective RAG platform powered by pgvector and FlashRank."
        t3 = "Photosynthesis is the biological process converting light energy into chemical energy."

        fp1 = SimHasher.fingerprint(t1)
        fp2 = SimHasher.fingerprint(t2)
        fp3 = SimHasher.fingerprint(t3)

        # Near-duplicate texts should have significantly lower Hamming distance than unrelated texts
        dist_near = SimHasher.hamming_distance(fp1, fp2)
        dist_diff = SimHasher.hamming_distance(fp1, fp3)

        assert dist_near <= 12
        assert dist_diff >= 24
        assert dist_near < dist_diff


    def test_boilerplate_detection(self):
        from app.document_intelligence.dedup import BoilerplateDetector

        assert BoilerplateDetector.is_boilerplate("Page 14 of 95") is True
        assert BoilerplateDetector.is_boilerplate("Confidential - For Internal Eyes Only") is True
        assert BoilerplateDetector.is_boilerplate("Copyright © 2024 Ridge Systems Inc. All rights reserved.") is True
        assert BoilerplateDetector.is_boilerplate("The neural reranking cross-encoder evaluates mutual passage relevance.") is False

    def test_deduplicator_pipeline(self):
        from app.document_intelligence.dedup import Deduplicator

        deduplicator = Deduplicator(near_dup_threshold=3)
        chunks = [
            StructuredChunk(raw_content="Deep Learning principles and gradient descent optimization in modern neural networks."),
            StructuredChunk(raw_content="Deep Learning principles and gradient descent optimization in modern neural networks."), # Exact duplicate
            StructuredChunk(raw_content="Page 12 of 40"), # Boilerplate
            StructuredChunk(raw_content="Unique independent section regarding vector databases and HNSW graph indexing."),
        ]

        clean, dedup_count = deduplicator.deduplicate_chunks(chunks)
        assert len(clean) == 2
        assert dedup_count == 2
        assert any("Deep Learning principles" in c.raw_content for c in clean)
        assert any("vector databases" in c.raw_content for c in clean)


class TestSummarizerAndRouter:
    def test_hierarchical_summarizer(self):
        from app.document_intelligence.summarizer import HierarchicalSummarizer

        summarizer = HierarchicalSummarizer(enabled=True)
        doc_ast = DocumentAST(filename="NVIDIA_Earnings_Report.pdf")
        page = PageAST(page_number=1)
        page.add_block(BlockAST(element_type=ElementType.HEADING, content="Data Center Revenue"))
        page.add_block(BlockAST(element_type=ElementType.PARAGRAPH, content="Data Center compute demand surged 150% YoY."))
        doc_ast.pages.append(page)

        summary_chunk = summarizer.generate_document_summary(doc_ast)
        assert summary_chunk is not None
        assert summary_chunk.content_type == "summary"
        assert "NVIDIA_Earnings_Report.pdf" in summary_chunk.content
        assert summary_chunk.metadata.get("is_summary") is True

    def test_query_intent_router_archetypes(self):
        from app.retrieval.router import QueryIntentRouter, QueryArchetype

        # 1. Summary
        p_summary = QueryIntentRouter.route_query("Summarize the key findings of this report")
        assert p_summary.archetype == QueryArchetype.SUMMARY
        assert p_summary.prioritize_summaries is True

        # 2. Tabular
        p_tab = QueryIntentRouter.route_query("What is the Q3 revenue breakdown and operating margin percentage?")
        assert p_tab.archetype == QueryArchetype.TABULAR
        assert p_tab.prioritize_tables is True

        # 3. Multi-Hop Compare
        p_compare = QueryIntentRouter.route_query("How does HNSW compare to IVFFlat in pgvector?")
        assert p_compare.archetype == QueryArchetype.MULTI_HOP

        # 4. Exact Lookup
        p_exact = QueryIntentRouter.route_query("DSU")
        assert p_exact.archetype == QueryArchetype.EXACT
        assert p_exact.sparse_weight >= 0.6

        # 5. Semantic Concept
        p_semantic = QueryIntentRouter.route_query("Explain the biological process of photosynthesis in plants")
        assert p_semantic.archetype == QueryArchetype.SEMANTIC





