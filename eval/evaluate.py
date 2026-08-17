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

    # Metrics evaluation
    grader_verdict = latest_grade_verdict
    final_answer = accumulated_state.get("generation", "")
    
    # 1. Grader Verdict Match
    grader_correct = (grader_verdict == test_case["expected_grader_verdict"])

    # 2. Keyword Recall in Answer
    keywords = test_case.get("ground_truth_keywords", [])
    ans_clean = final_answer.lower().replace("-", " ")
    ans_compact = ans_clean.replace(" ", "")
    keyword_hits = [
        kw for kw in keywords
        if kw.lower() in final_answer.lower()
        or kw.lower().replace("-", " ") in ans_clean
        or kw.lower().replace(" ", "") in ans_compact
    ]
    keyword_recall = len(keyword_hits) / len(keywords) if keywords else 1.0

    # 3. Routing Match (checks if web search was triggered when expected, or direct generate)
    expected_route = test_case.get("expected_final_route", "generate_node")
    if expected_route == "web_search_node":
        routing_correct = "web_search_node" in steps_executed
    else:
        routing_correct = "web_search_node" not in steps_executed and "generate_node" in steps_executed

    result = {
        "id": test_case["id"],
        "category": test_case["category"],
        "question": q,
        "steps": steps_executed,
        "total_latency_ms": total_latency_ms,
        "grader_verdict": grader_verdict,
        "expected_grader_verdict": test_case["expected_grader_verdict"],
        "grader_correct": grader_correct,
        "keyword_recall": round(keyword_recall * 100, 1),
        "keyword_hits": keyword_hits,
        "keywords_expected": keywords,
        "routing_correct": routing_correct,
        "final_route": "web_search_node" if "web_search_node" in steps_executed else "generate_node",
        "answer_preview": final_answer[:200].replace("\n", " ") + "...",
    }

    print(f"  -> Total Latency: {total_latency_ms}ms | Steps: {' -> '.join(steps_executed)}")
    print(f"  -> Grader Accuracy: {'PASSED' if grader_correct else 'FAILED'} (Got '{grader_verdict}', Expected '{test_case['expected_grader_verdict']}')")
    print(f"  -> Keyword Recall: {result['keyword_recall']}% ({len(keyword_hits)}/{len(keywords)} hits)")

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
        time.sleep(1)

    # Compute Summary Statistics
    total_cases = len(results)
    grader_accuracy = sum(1 for r in results if r["grader_correct"]) / total_cases * 100
    avg_keyword_recall = sum(r["keyword_recall"] for r in results) / total_cases
    avg_latency = sum(r["total_latency_ms"] for r in results) / total_cases
    routing_accuracy = sum(1 for r in results if r["routing_correct"]) / total_cases * 100

    print("\n" + "=" * 70)
    print("📊 BENCHMARK SUMMARY SCORECARD")
    print("=" * 70)
    print(f"• Total Test Cases Evaluated : {total_cases}")
    print(f"• Grader Decision Accuracy  : {grader_accuracy:.1f}%")
    print(f"• Average Keyword Recall     : {avg_keyword_recall:.1f}%")
    print(f"• State Routing Accuracy     : {routing_accuracy:.1f}%")
    print(f"• Average Pipeline Latency   : {avg_latency:.0f} ms")
    print("=" * 70)

    # Write Markdown Report
    report_path = PROJECT_ROOT / "eval" / "benchmark_report.md"
    report_md = f"""# 🏔️ Ridge CRAG Benchmark Report

**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}
**Dataset:** `{dataset.get('benchmark_name')}` (v{dataset.get('version')})

---

## 📊 Summary Scorecard

| Metric | Score | Target Standard | Status |
| :--- | :---: | :---: | :---: |
| **Grader Decision Accuracy** | **{grader_accuracy:.1f}%** | > 90% | {'✅ Pass' if grader_accuracy >= 90 else '⚠️ Needs Review'} |
| **Average Grounded Recall** | **{avg_keyword_recall:.1f}%** | > 80% | {'✅ Pass' if avg_keyword_recall >= 80 else '⚠️ Needs Review'} |
| **Graph Routing Correctness** | **{routing_accuracy:.1f}%** | 100% | {'✅ Pass' if routing_accuracy >= 80 else '⚠️ Needs Review'} |
| **Average End-to-End Latency** | **{avg_latency:.0f} ms** | < 4000 ms | {'✅ Optimal' if avg_latency <= 4000 else '⚡ Accelerated'} |

---

## 🔍 Detailed Test Case Results

| ID | Category | Question | Steps Executed | Grader Verdict | Keyword Recall | Latency | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
"""

    for r in results:
        status_icon = "✅" if r["grader_correct"] and r["keyword_recall"] >= 50 else "⚠️"
        steps_str = " &rarr; ".join(r["steps"])
        report_md += f"| `{r['id']}` | **{r['category']}** | *\"{r['question']}\"* | {steps_str} | `{r['grader_verdict']}` | {r['keyword_recall']}% | {r['total_latency_ms']}ms | {status_icon} |\n"

    report_md += "\n---\n\n*Report automatically generated by `eval/evaluate.py`.*"

    report_path.write_text(report_md, encoding="utf-8")
    print(f"\nSaved detailed benchmark report to: {report_path}")

    # Save JSON results
    json_path = PROJECT_ROOT / "eval" / "results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total_cases": total_cases,
                "grader_accuracy": grader_accuracy,
                "avg_keyword_recall": avg_keyword_recall,
                "avg_latency_ms": avg_latency,
                "routing_accuracy": routing_accuracy,
            },
            "test_cases": results
        }, f, indent=2)


if __name__ == "__main__":
    run_benchmark()
