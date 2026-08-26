"""
Ridge: Answer Generation & Grounding Synthesis Node
===================================================
Synthesizes verified answers with NotebookLM-style citations, mathematical LaTeX,
strict Mermaid gating, and multi-document discrepancy auditing.
"""
import time
import json
import re
from typing import Callable
from langchain_core.language_models.chat_models import BaseChatModel

from app.graph.state import GraphState
from app.graph.prompts import build_generation_prompt, get_generation_messages, clean_llm_response


def make_generate_node(
    llm_generate: BaseChatModel,
    llm_fast: BaseChatModel,
    settings: dict,
) -> Callable[[GraphState], dict]:

    def generate_node(state: GraphState) -> dict:
        t0 = time.time()
        print("--- NODE: GENERATE ---")
        question = state.get("original_question") or state["question"]
        docs = state.get("documents", [])
        doc_metas = state.get("documents_metadata", [])
        doc_grades = state.get("doc_grades", [])
        loop_count = state.get("loop_count", 0)
        max_docs = settings.get("max_context_docs", 6)
        max_chars = settings.get("max_context_chars", 1200)

        # Use ContextPacker for token-budgeted context assembly with parent expansion
        packed_texts = []
        packed_metas = []
        if docs:
            try:
                from app.retrieval.context_packer import get_context_packer
                packer = get_context_packer()
                ranked_passages = [
                    {"text": doc, "meta": doc_metas[i] if i < len(doc_metas) else {}, "score": 1.0 - i * 0.05}
                    for i, doc in enumerate(docs[:max_docs])
                ]
                packed_texts, packed_metas, _ = packer.pack_context(ranked_passages, top_k=max_docs)
            except Exception as pack_err:
                print(f"Context packer note ({pack_err}), falling back to direct context")

        if not packed_texts and docs:
            packed_texts = [d[:max_chars].strip() for d in docs[:max_docs]]
            packed_metas = doc_metas[:max_docs]

        # Strip internal [Context: ...] heading tags so raw file names do not leak to the LLM
        cleaned_packed_texts = [
            re.sub(r"^\[Context:\s*[^\]]+\]\s*\n*", "", txt.strip(), flags=re.IGNORECASE)
            for txt in packed_texts
        ]

        context = "\n\n".join(f"[{i+1}] {txt.strip()}" for i, txt in enumerate(cleaned_packed_texts)).strip()
        doc_metas = packed_metas

        print(f"  Total context length: {len(context)} chars ({len(packed_texts)} chunks)")

        # CRAG Strict Grounding Guard: When no verified documents exist and web fallback is disabled/empty
        if not docs:
            print("  [CRAG Guard] No relevant documents found and external web search is disabled/empty.")
            no_context_answer = (
                "## Direct Answer\n\n"
                "I could not find any relevant information in your indexed documents to answer this question, "
                "and **Web Search Fallback is currently disabled**.\n\n"
                "### Recommended Actions:\n"
                "* **Enable Web Fallback**: Toggle **Web fallback: ON** in the toolbar to search and verify live external sources.\n"
                "* **Upload Knowledge**: Ingest or upload relevant files (PDF, DOCX, TXT, MD) into your local knowledge crag."
            )
            confidence_data = {
                "score": 15,
                "level": "LOW",
                "breakdown": {
                    "grader_consensus": 0.0,
                    "source_trust": "No Context Available (Web Search OFF)",
                    "relevant_chunks": 0,
                    "reformulation_loops": loop_count,
                    "faithfulness": "Direct Fallback Guard"
                }
            }
            return {
                "generation": no_context_answer,
                "confidence": confidence_data,
                "latency_ms": int((time.time() - t0) * 1000)
            }

        # --- COMPUTE COMPOSITE GROUNDED CONFIDENCE METRIC ---
        yes_count = sum(1 for g in doc_grades if g.get("score") == "yes")
        total_grades = len(doc_grades)
        grader_ratio = (yes_count / total_grades) if total_grades > 0 else (0.85 if docs else 0.0)

        is_web = any("duckduckgo" in str(d).lower() or "web" in str(d).lower() for d in docs)
        if docs and not is_web:
            source_weight = 1.0
            source_type_name = "Local Knowledge Base"
        elif docs and is_web:
            source_weight = 0.82
            source_type_name = "Web Search Fallback"
        else:
            source_weight = 0.40
            source_type_name = "General Synthesized Knowledge"

        if len(docs) >= 2:
            coverage_weight = 1.0
        elif len(docs) == 1:
            coverage_weight = 0.75
        else:
            coverage_weight = 0.35

        if loop_count == 0:
            loop_weight = 1.0
        elif loop_count == 1:
            loop_weight = 0.85
        else:
            loop_weight = 0.65

        raw_confidence = (grader_ratio * 35) + (source_weight * 25) + (coverage_weight * 25) + (loop_weight * 15)
        confidence_score = max(15, min(99, int(round(raw_confidence))))

        if confidence_score >= 80:
            confidence_level = "HIGH"
        elif confidence_score >= 60:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        confidence_data = {
            "score": confidence_score,
            "level": confidence_level,
            "breakdown": {
                "grader_consensus": round(grader_ratio * 100, 1),
                "source_trust": source_type_name,
                "relevant_chunks": len(docs),
                "reformulation_loops": loop_count,
            }
        }

        # --- MULTI-DOCUMENT CONFLICT AUDIT ---
        distinct_sources = list(set(
            g.get("source", "").split("/")[-1] for g in doc_grades 
            if g.get("score") == "yes" and g.get("source") and g.get("breadcrumb") != "Web Search Fallback"
        ))
        
        conflict_data = {"detected": False, "summary": "", "sources": distinct_sources}
        conflict_instruction = ""
        
        if len(distinct_sources) >= 2 and len(docs) >= 2:
            print(f"--- RUNNING CONFLICT DETECTOR ACROSS {len(distinct_sources)} SOURCES ---")
            docs_paired = "\n\n".join(
                f"--- Source: {g.get('source', f'Doc #{i+1}').split('/')[-1]} ---\n{g.get('text', docs[i] if i < len(docs) else '')[:400]}"
                for i, g in enumerate(doc_grades[:4]) if g.get("score") == "yes"
            )
            conflict_prompt = (
                "You are a strict inconsistency auditor for an enterprise document store.\n"
                f"User Question: {question}\n\n"
                f"Retrieved Passages from Multiple Documents:\n{docs_paired}\n\n"
                "Task: Check if these documents present differing numbers, conflicting policy rules/allowances across versions/years, or incompatible statements regarding the question.\n"
                "Return ONLY a JSON object: {\"conflict\": true | false, \"summary\": \"1-2 sentence description of the discrepancy or differing terms across sources, or empty string\"}"
            )

            try:
                c_resp = llm_fast.invoke(conflict_prompt)
                c_clean = clean_llm_response(c_resp.content)
                c_match = re.search(r"\{.*\}", c_clean, re.DOTALL)
                if c_match:
                    c_json = json.loads(c_match.group(0))
                    if c_json.get("conflict") is True and c_json.get("summary"):
                        conflict_data["detected"] = True
                        conflict_data["summary"] = c_json.get("summary")
                        conflict_data["passages"] = [
                            {
                                "source": g.get("source", f"Doc #{i+1}"),
                                "name": g.get("source", f"Doc #{i+1}").split("/")[-1],
                                "text": g.get("text", docs[i] if i < len(docs) else ""),
                                "rationale": g.get("rationale", "")
                            }
                            for i, g in enumerate(doc_grades)
                            if g.get("score") == "yes" and g.get("source") and g.get("breadcrumb") != "Web Search Fallback"
                        ]
                        print(f"  ⚠️ Document Conflict Detected: {conflict_data['summary']}")
                        conflict_instruction = (
                            f"\nIMPORTANT - DOCUMENT CONFLICT DETECTED: The knowledge base contains differing perspectives across documents:\n"
                            f"Discrepancy: {conflict_data['summary']}\n"
                            "You MUST begin your response with a structured callout block:\n"
                            f"> ⚠️ **Document Conflict Detected**: Multiple indexed documents present differing information on this topic:\n"
                            "> - State what each document asserts clearly with their source names.\n"
                            "> - Do not silently favor one over the other; surface both perspectives.\n\n"
                        )
            except Exception as ce:
                print(f"Conflict detector note: {ce}")

        messages = get_generation_messages(question, context, conflict_instruction)

        # Primary Model with instant fast model fallback on rate-limit
        try:
            response = llm_generate.invoke(messages)
            gen_text = clean_llm_response(response.content)
            return {
                "generation": gen_text,
                "confidence": confidence_data,
                "conflict_data": conflict_data,
                "latency_ms": int((time.time() - t0) * 1000)
            }
        except Exception as e:
            print(f"Primary generation rate-limited or error ({e}). Switching instantly to fast model...")
            try:
                response = llm_fast.invoke(messages)
                gen_text = clean_llm_response(response.content)
                return {
                    "generation": gen_text,
                    "confidence": confidence_data,
                    "conflict_data": conflict_data,
                    "latency_ms": int((time.time() - t0) * 1000)
                }
            except Exception as e2:
                print(f"Fallback generation error: {e2}")
                return {
                    "generation": f"Model provider error: {e2}",
                    "confidence": confidence_data,
                    "conflict_data": conflict_data,
                    "latency_ms": int((time.time() - t0) * 1000)
                }

    return generate_node
