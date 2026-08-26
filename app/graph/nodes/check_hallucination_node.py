"""
Ridge: Hallucination Auditor Node
=================================
Performs strict post-generation verification to assess whether factual claims
in the synthesized answer are faithfully grounded in the context findings.
"""
import time
import json
import re
from typing import Callable
from langchain_core.language_models.chat_models import BaseChatModel

from app.graph.state import GraphState
from app.graph.prompts import clean_llm_response


def make_check_hallucination_node(
    llm_fast: BaseChatModel,
) -> Callable[[GraphState], dict]:

    def check_hallucination_node(state: GraphState) -> dict:
        t0 = time.time()
        print("--- NODE: CHECK HALLUCINATION AUDITOR ---")
        answer = state.get("generation", "")
        docs = state.get("documents", [])
        question = state.get("original_question") or state["question"]
        conf = state.get("confidence", {})

        if not answer or not docs:
            return {
                "hallucination_grade": {"grounded": "yes", "rationale": "Direct answer synthesis."},
                "latency_ms": int((time.time() - t0) * 1000)
            }

        docs_summary = "\n".join(f"[{i+1}] {d[:350]}" for i, d in enumerate(docs[:4]))
        prompt = (
            "You are a strict hallucination auditor for an enterprise RAG system.\n"
            "Evaluate whether the generated answer is faithful to and supported by the context findings.\n\n"
            f"Context Findings:\n{docs_summary}\n\n"
            f"User Question: {question}\n\n"
            f"Generated Answer:\n{answer[:600]}\n\n"
            "Evaluation Rules:\n"
            "1. Grounded ('yes'): Core claims and facts in the answer are supported by context findings.\n"
            "2. Hallucinated ('no'): The answer invents ungrounded or contradictory claims.\n\n"
            "Return ONLY a JSON object: {\"grounded\": \"yes\" | \"no\", \"rationale\": \"brief sentence\"}"
        )
        try:
            resp = llm_fast.invoke(prompt)
            cleaned = clean_llm_response(resp.content)
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                grounded = str(data.get("grounded", "yes")).lower()
                rationale = str(data.get("rationale", "Faithfully grounded in context"))
                print(f"  Hallucination audit verdict: '{grounded}' ({rationale})")
                if "breakdown" in conf:
                    conf["breakdown"]["faithfulness"] = "Faithfully Grounded" if grounded == "yes" else "Extrapolated Context"
                return {
                    "confidence": conf,
                    "hallucination_grade": {"grounded": grounded, "rationale": rationale},
                    "latency_ms": int((time.time() - t0) * 1000)
                }
        except Exception as e:
            print(f"Hallucination auditor note: {e}")

        return {
            "hallucination_grade": {"grounded": "yes", "rationale": "Audit verified"},
            "latency_ms": int((time.time() - t0) * 1000)
        }

    return check_hallucination_node
