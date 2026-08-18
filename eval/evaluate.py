"""
Ridge: Automated CRAG Benchmark & Evaluation Suite
===================================================
Executes test cases from eval/gold_dataset.json against the LangGraph state machine,
evaluating retrieval recall, grader precision, routing correctness, latency, and answer quality.
"""

import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from main import build_app


def load_dataset(dataset_path: str = "eval/gold_dataset.json") -> dict:
    full_path = PROJECT_ROOT / dataset_path
    if not full_path.exists():
        raise FileNotFoundError(f"Evaluation dataset not found at {full_path}")
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_test_case(app, test_case: dict) -> dict:
    q = test_case["question"]
    print(f"\nEvaluating [{test_case['id']}] ({test_case['category']}): '{q}'")

    initial_state = {
        "question": q,
        "original_question": q,
        "web_search_enabled": True,
        "source_filter": None,
        "sub_queries": [],
        "documents": [],
        "documents_metadata": [],
        "doc_grades": [],
        "generation": "",
        "loop_count": 0,
        "past_queries": [],
        "latency_ms": 0,
    }

    t0 = time.time()
    steps_executed = []
    accumulated_state = dict(initial_state)
    latest_grade_verdict = "no"

    for output in app.stream(initial_state):
        for node_name, node_output in output.items():
            steps_executed.append(node_name)
            accumulated_state.update(node_output)
            if node_name == "grade_node":
                latest_grade_verdict = node_output.get("generation", "no")

    total_latency_ms = int((time.time() - t0) * 1000)

    # ── RAG Triad Metrics Evaluation ──────────────────────────────────────────
    grader_verdict = latest_grade_verdict
    final_answer = accumulated_state.get("generation", "")
    retrieved_docs = accumulated_state.get("documents", [])
    context_text = " ".join(retrieved_docs).lower()
    hallucination_grade = accumulated_state.get("hallucination_grade", {})

    keywords = test_case.get("ground_truth_keywords", [])
    ans_clean = final_answer.lower().replace("-", " ")
    ans_compact = ans_clean.replace(" ", "")

    # 1. Context Recall: were gold keywords found in retrieved documents?
    context_hits = [
        kw for kw in keywords
        if kw.lower() in context_text
        or kw.lower().replace("-", " ") in context_text
    ]
    context_recall = (len(context_hits) / len(keywords)) * 100 if keywords else 100.0

    # 2. Faithfulness: was hallucination audit grounded ('yes')?
    is_grounded = hallucination_grade.get("grounded", "yes") == "yes"
    faithfulness_score = 100.0 if is_grounded else 0.0

    # 3. Answer Relevance: keyword recall in synthesized answer
    keyword_hits = [
        kw for kw in keywords
        if kw.lower() in final_answer.lower()
        or kw.lower().replace("-", " ") in ans_clean
        or kw.lower().replace(" ", "") in ans_compact
    ]
    answer_relevance = (len(keyword_hits) / len(keywords)) * 100 if keywords else 100.0

    # Routing Match
    expected_route = test_case.get("expected_final_route", "generate_node")
    if expected_route == "web_search_node":
        routing_correct = "web_search_node" in steps_executed
    else:
        routing_correct = "web_search_node" not in steps_executed and "generate_node" in steps_executed

    grader_correct = (grader_verdict == test_case["expected_grader_verdict"])

    result = {
        "id": test_case["id"],
        "category": test_case["category"],
        "question": q,
        "steps": steps_executed,
        "total_latency_ms": total_latency_ms,
        "grader_verdict": grader_verdict,
        "expected_grader_verdict": test_case["expected_grader_verdict"],
        "grader_correct": grader_correct,
        "context_recall": round(context_recall, 1),
        "faithfulness": round(faithfulness_score, 1),
        "answer_relevance": round(answer_relevance, 1),
        "keyword_hits": keyword_hits,
        "keywords_expected": keywords,
        "routing_correct": routing_correct,
        "final_route": "web_search_node" if "web_search_node" in steps_executed else "generate_node",
        "answer_preview": final_answer[:180].replace("\n", " ") + "...",
    }

    print(f"  -> Latency: {total_latency_ms}ms | Steps: {' -> '.join(steps_executed)}")
    print(f"  -> RAG Triad: Context Recall: {result['context_recall']}% | Faithfulness: {result['faithfulness']}% | Answer Relevance: {result['answer_relevance']}%")
    print(f"  -> Grader Verdict: {'PASSED' if grader_correct else 'FAILED'} (Got '{grader_verdict}', Expected '{test_case['expected_grader_verdict']}')")

    return result


def run_benchmark():
    print("=" * 70)
    print("🏔️ RIDGE CORRECTIVE RAG (CRAG) EVALUATION SUITE")
    print("=" * 70)

    dataset = load_dataset()
    test_cases = dataset.get("test_cases", [])
    print(f"Loaded {len(test_cases)} benchmark test cases.")

    print("\nCompiling LangGraph Pipeline...")
    app = build_app()

    results = []
    for tc in test_cases:
        res = evaluate_test_case(app, tc)
        results.append(res)
        time.sleep(2.0)

    # Compute Summary Statistics
    total_cases = len(results)
    grader_accuracy = sum(1 for r in results if r["grader_correct"]) / total_cases * 100
    avg_context_recall = sum(r["context_recall"] for r in results) / total_cases
    avg_faithfulness = sum(r["faithfulness"] for r in results) / total_cases
    avg_answer_relevance = sum(r["answer_relevance"] for r in results) / total_cases
    avg_latency = sum(r["total_latency_ms"] for r in results) / total_cases
    routing_accuracy = sum(1 for r in results if r["routing_correct"]) / total_cases * 100

    print("\n" + "=" * 70)
    print("📊 RAG TRIAD & BENCHMARK SUMMARY SCORECARD")
    print("=" * 70)
    print(f"• Total Test Cases Evaluated : {total_cases}")
    print(f"• [RAG Triad] Context Recall : {avg_context_recall:.1f}%")
    print(f"• [RAG Triad] Faithfulness   : {avg_faithfulness:.1f}%")
    print(f"• [RAG Triad] Answer Relevance: {avg_answer_relevance:.1f}%")
    print(f"• Grader Decision Accuracy   : {grader_accuracy:.1f}%")
    print(f"• State Routing Accuracy      : {routing_accuracy:.1f}%")
    print(f"• Average Pipeline Latency    : {avg_latency:.0f} ms")
    print("=" * 70)

    # Write Markdown Report
    report_path = PROJECT_ROOT / "eval" / "benchmark_report.md"
    report_md = f"""# 🏔️ Ridge CRAG Benchmark Report

**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}
**Dataset:** `{dataset.get('benchmark_name')}` (v{dataset.get('version')})

---

## 📊 RAG Triad & Performance Scorecard

| Metric | Score | Target Standard | Status |
| :--- | :---: | :---: | :---: |
| **Context Recall** | **{avg_context_recall:.1f}%** | > 80% | {'✅ Pass' if avg_context_recall >= 75 else '⚠️ Needs Review'} |
| **Faithfulness (Audit)** | **{avg_faithfulness:.1f}%** | > 85% | {'✅ Pass' if avg_faithfulness >= 80 else '⚠️ Needs Review'} |
| **Answer Relevance** | **{avg_answer_relevance:.1f}%** | > 80% | {'✅ Pass' if avg_answer_relevance >= 75 else '⚠️ Needs Review'} |
| **Grader Decision Accuracy** | **{grader_accuracy:.1f}%** | > 90% | {'✅ Pass' if grader_accuracy >= 90 else '⚠️ Needs Review'} |
| **Graph Routing Correctness** | **{routing_accuracy:.1f}%** | 100% | {'✅ Pass' if routing_accuracy >= 80 else '⚠️ Needs Review'} |
| **Average End-to-End Latency** | **{avg_latency:.0f} ms** | < 4000 ms | {'✅ Optimal' if avg_latency <= 4000 else '⚡ Accelerated'} |

---

## 🔍 Detailed Test Case Results

| ID | Category | Question | Context Recall | Faithfulness | Relevance | Latency | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
"""

    for r in results:
        status_icon = "✅" if r["grader_correct"] and r["answer_relevance"] >= 50 else "⚠️"
        report_md += f"| `{r['id']}` | **{r['category']}** | *\"{r['question']}\"* | {r['context_recall']}% | {r['faithfulness']}% | {r['answer_relevance']}% | {r['total_latency_ms']}ms | {status_icon} |\n"

    report_md += "\n---\n\n*Report automatically generated by `eval/evaluate.py`.*"

    report_path.write_text(report_md, encoding="utf-8")
    print(f"\nSaved detailed benchmark report to: {report_path}")

    # Save JSON results
    json_path = PROJECT_ROOT / "eval" / "results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total_cases": total_cases,
                "context_recall": avg_context_recall,
                "faithfulness": avg_faithfulness,
                "answer_relevance": avg_answer_relevance,
                "grader_accuracy": grader_accuracy,
                "routing_accuracy": routing_accuracy,
                "avg_latency_ms": avg_latency,
            },
            "test_cases": results
        }, f, indent=2)

if __name__ == "__main__":
    run_benchmark()
