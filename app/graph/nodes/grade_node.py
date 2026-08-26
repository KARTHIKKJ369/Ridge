"""
Ridge: Document Relevance Grading Node
======================================
Evaluates retrieved candidate passages against strict relevance criteria,
filtering out noise, off-topic documents, and gibberish queries.
"""
import time
from typing import Callable
from langchain_core.language_models.chat_models import BaseChatModel
from app.graph.state import GraphState
from app.graph.prompts import build_grade_prompt, extract_batch_grades


def make_grade_node(
    llm_fast: BaseChatModel,
    settings: dict,
) -> Callable[[GraphState], dict]:

    def grade_node(state: GraphState) -> dict:
        t0 = time.time()
        print("--- NODE: GRADE DOCUMENTS ---")
        question = state["question"]
        doc_texts = state.get("documents", [])
        doc_metas = state.get("documents_metadata", [])

        if not doc_texts:
            print("Decision: 'no' (empty database results)")
            return {
                "generation": "no",
                "documents": [],
                "documents_metadata": [],
                "doc_grades": [],
                "latency_ms": int((time.time() - t0) * 1000),
            }

        grade_limit = settings.get("grade_doc_limit", 4)
        docs_to_grade = doc_texts[:grade_limit]

        import re
        clean_docs = [
            re.sub(r"^\[Context:\s*[^\]]+\]\s*\n*", "", doc[:1200].strip(), flags=re.IGNORECASE)
            for doc in docs_to_grade
        ]
        docs_str = "\n".join(
            f"--- Document {i} ---\n{clean_text}\n" for i, clean_text in enumerate(clean_docs)
        )
        prompt = build_grade_prompt(question, docs_str)

        result = None
        last_err = None
        for attempt in range(2):
            try:
                resp = llm_fast.invoke(prompt)
                result = extract_batch_grades(resp.content, len(docs_to_grade))
                break
            except Exception as e:
                last_err = e
                print(f"  Grading attempt {attempt + 1} failed: {e}")
                time.sleep(0.5)

        if result is None:
            print(f"  Grading gave up. Last error: {last_err}")
            return {
                "generation": "no",
                "documents": [],
                "documents_metadata": [],
                "doc_grades": [],
                "latency_ms": int((time.time() - t0) * 1000),
            }

        relevant_docs = []
        relevant_metas = []
        doc_grades = []
        for g in result.grades:
            if 0 <= g.index < len(docs_to_grade):
                score = g.score.lower()
                meta = doc_metas[g.index] if g.index < len(doc_metas) else {}
                doc_grades.append({
                    "index": g.index,
                    "score": score,
                    "rationale": g.rationale,
                    "source": meta.get("source", "unknown"),
                    "breadcrumb": meta.get("breadcrumb", ""),
                    "relevance": float(meta.get("score", 0)),
                    "text": docs_to_grade[g.index],
                })
                print(f"  Doc {g.index + 1}/{len(docs_to_grade)} decision: '{score}'")
                print(f"    rationale: {g.rationale}")
                if score == "yes":
                    relevant_docs.append(docs_to_grade[g.index])
                    relevant_metas.append(meta)

        lat = int((time.time() - t0) * 1000)
        if relevant_docs:
            print(f"Decision: 'yes' ({len(relevant_docs)}/{len(docs_to_grade)} docs relevant)")
            return {
                "generation": "yes",
                "documents": relevant_docs,
                "documents_metadata": relevant_metas,
                "doc_grades": doc_grades,
                "latency_ms": lat,
            }

        print("Decision: 'no' (no relevant docs found)")
        return {
            "generation": "no",
            "documents": [],
            "documents_metadata": [],
            "doc_grades": doc_grades,
            "latency_ms": lat,
        }

    return grade_node
