"""
Ridge: External Web Search Fallback Node
========================================
Executes DuckDuckGo web search when internal documents lack sufficient confidence
or when multi-hop coverage requires live web grounding.
"""
import time
from typing import Callable
from ddgs import DDGS
from app.graph.state import GraphState


def make_web_search_node() -> Callable[[GraphState], dict]:

    def web_search_node(state: GraphState) -> dict:
        t0 = time.time()
        search_query = state.get("original_question") or state["question"]
        print(f"--- NODE: WEB SEARCH: '{search_query}' ---")
        
        web_docs = []
        web_doc_grades = []
        web_metadata = []
        try:
            with DDGS(timeout=6) as ddgs:
                results = list(ddgs.text(search_query, max_results=3))
                for i, r in enumerate(results):
                    title = r.get("title", "Web Source")
                    body = r.get("body", "")[:450].strip()
                    href = r.get("href", "")
                    if body:
                        web_docs.append(f"Web Source [{i+1}]: {title} ({href})\n{body}")
                        web_doc_grades.append({
                            "index": i + 1,
                            "source": f"{title} ({href})",
                            "score": "yes",
                            "rationale": f"Live search result from DuckDuckGo: {title}",
                            "text": body,
                            "breadcrumb": "Web Search Fallback"
                        })
                        web_metadata.append({"source": href, "title": title, "type": "web"})
        except Exception as e:
            print(f"Web search note: {e}")
            
        return {
            "documents": web_docs,
            "doc_grades": web_doc_grades,
            "documents_metadata": web_metadata,
            "latency_ms": int((time.time() - t0) * 1000)
        }

    return web_search_node
