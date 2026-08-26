"""
Ridge: Prompt Templates & Output Cleaners
=========================================
Centralized system prompts, evaluation criteria, and robust LLM response sanitizers.
"""
import re
import json
from typing import Any
from app.graph.state import BatchGrades, DocGrade


def clean_llm_response(text: Any) -> str:
    """Strip reasoning/thought blocks, normalize raw html break tags, convert citation tokens, format equations, and clean whitespace."""
    if not text:
        return ""
    if isinstance(text, list):
        extracted = []
        for item in text:
            if isinstance(item, str):
                extracted.append(item)
            elif isinstance(item, dict) and "text" in item:
                extracted.append(str(item["text"]))
            elif hasattr(item, "text"):
                extracted.append(str(item.text))
            else:
                extracted.append(str(item))
        text = "".join(extracted)
    elif not isinstance(text, str):
        text = str(text)

    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    text = text.replace("<think>", "").replace("</think>", "")
    # Convert raw citation tokens like 【1†L1-L4】 or 【1】 into clean readable citations [1]
    text = re.sub(r"【(\d+)†[^】]*】", r" [\1]", text)
    text = re.sub(r"【(\d+)】", r" [\1]", text)
    text = re.sub(r"【[^】]*】", "", text)
    # Normalize accidental raw HTML breaks into clean newlines
    text = re.sub(r"<br\s*/?>\s*•", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>\s*-", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n\n", text, flags=re.IGNORECASE)

    # Fix collapsed Markdown tables where row newlines were omitted
    text = re.sub(r"(\|[-:]+[-| :]*)\|([^\n\-\|])", r"\1|\n| \2", text)
    text = re.sub(r"\|[ \t]*\|", "|\n|", text)

    # Standardize LaTeX display equations with $$ ... $$
    text = re.sub(r"\\\[([\s\S]*?)\\\]", r"\n\n$$\n\1\n$$\n\n", text)
    text = re.sub(r"\\\(([\s\S]*?)\\\)", r"$\1$", text)
    # Convert multiline single $ blocks to $$ blocks
    text = re.sub(r"(?:^|\n)[ \t]*\$[ \t]*\n([\s\S]*?)\n[ \t]*\$[ \t]*(?=\n|$)", r"\n\n$$\n\1\n$$\n\n", text)

    return text.strip()


def extract_batch_grades(raw_text: str, num_docs: int) -> BatchGrades:
    """Safely extracts BatchGrades from markdown/JSON text output with regex fallback."""
    raw = clean_llm_response(raw_text)
    
    # 1. Try standard JSON decode
    json_candidate = raw
    if "```json" in json_candidate:
        json_candidate = json_candidate.split("```json")[1].split("```")[0]
    elif "```" in json_candidate:
        json_candidate = json_candidate.split("```")[1].split("```")[0]
    
    match = re.search(r"\{.*\}", json_candidate, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            grades = []
            for idx, item in enumerate(data.get("grades", [])):
                doc_idx = int(item.get("index", idx))
                rationale = str(item.get("rationale", "")).strip()
                score_val = str(item.get("score", "no")).strip().lower()
                score = "yes" if score_val in ["yes", "true", "1"] else "no"
                grades.append(DocGrade(index=doc_idx, rationale=rationale, score=score))
            if grades:
                return BatchGrades(grades=grades)
        except Exception:
            pass

    # 2. Resilient regex field extraction if JSON has unescaped quotes
    grades = []
    items = re.findall(r'\{[^{}]*?"index"[^{}]*?\}', raw, re.DOTALL)
    for idx, item_str in enumerate(items):
        idx_match = re.search(r'"index"\s*:\s*(\d+)', item_str)
        doc_idx = int(idx_match.group(1)) if idx_match else idx
        
        score_match = re.search(r'"score"\s*:\s*"(yes|no|true|false|1|0)"', item_str, re.IGNORECASE)
        score_val = score_match.group(1).lower() if score_match else "no"
        score = "yes" if score_val in ["yes", "true", "1"] else "no"
        
        rat_match = re.search(r'"rationale"\s*:\s*"(.*?)"(?=,\s*"score"|\s*\})', item_str, re.DOTALL)
        rationale = rat_match.group(1) if rat_match else ""
        
        grades.append(DocGrade(index=doc_idx, rationale=rationale, score=score))
    
    if grades:
        return BatchGrades(grades=grades)
    
    raise ValueError(f"Could not extract JSON grades: {raw[:150]}")


def build_grade_prompt(question: str, docs_str: str) -> str:
    return (
        "You are an expert relevance evaluator for a technical document retrieval system.\n"
        "Assess whether the retrieved documents are relevant, helpful, or topical for answering the user question.\n\n"
        f"User Question: {question}\n\n"
        f"Retrieved Documents:\n{docs_str}\n\n"
        "Evaluation Rules:\n"
        "1. GIBBERISH / NOISE FILTER: If the user question is random characters or nonsensical gibberish (e.g. 'euhygvdvg vbhsd'), you MUST score 'no' for all documents.\n"
        "2. IDENTITY & PROFILE QUESTIONS: If the question asks about a person, and the document contains their resume, biography, or background, score 'yes'.\n"
        "3. TECHNICAL CONCEPTS & DEFINITIONS: If the question asks about a concept, entity, definition, architecture, or methodology (e.g. 'what is a digital twin', 'PEAS model', 'DSU optimization'), score 'yes' if the document defines, discusses, mentions, or describes the topic or its related components.\n"
        "4. PARTIAL RELEVANCE: Score 'yes' if the passage contains useful context or background, even if it does not answer the question completely on its own.\n"
        "5. UNRELATED DOCUMENTS: Only score 'no' if the document is completely off-topic or discussing an unrelated domain.\n\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        '{"grades": [{"index": 0, "rationale": "...", "score": "yes" | "no"}]}'
    )


def get_generation_messages(
    question: str,
    context: str,
    conflict_instruction: str = ""
) -> list:
    """Creates structured SystemMessage and HumanMessage for Chat LLMs to eliminate instruction leaks."""
    from langchain_core.messages import SystemMessage, HumanMessage
    
    system_text = (
        "You are Ridge, an advanced AI research assistant.\n"
        "Synthesize a well-structured, authoritative, and cleanly formatted answer to the user's question based strictly on the provided context findings.\n\n"
        "Formatting & Quality Rules:\n"
        "1. DIRECT EXECUTIVE ANSWER: Start with a clear, direct answer before expanding into details.\n"
        "2. CLEAN MARKDOWN STRUCTURE: Use clean markdown hierarchy (## Section, ### Subsections, bullet points, bold keywords).\n"
        "3. TABLES & MULTI-ROW DATA:\n"
        "   - Every table row MUST be on its own line starting with `|` and ending with `|`.\n"
        "   - NEVER concatenate multiple table rows on the same line with `||`.\n"
        "4. NOTEBOOKLM-STYLE INLINE CITATIONS & STRICT GROUNDING:\n"
        "   - Every factual claim, definition, metric, or finding MUST be immediately supported by an inline citation badge corresponding to the numbered context findings: e.g. [1], [2], or [1, 2].\n"
        "   - Place citations at the exact sentence or clause level where the fact is asserted.\n"
        "   - Use ONLY clean bracketed numbers like [1] or [1, 2]. Never output raw HTML tags or tokens like 【1†L1-L4】.\n"
        "5. ACCURACY & EVIDENCE: Base factual assertions directly on the verified context findings. If context is missing or unrelated, state that clearly.\n"
        "6. MATHEMATICAL EQUATIONS & LATEX: Format formulas with standard LaTeX ($ for inline, $$ on separate lines for blocks).\n"
        "7. MERMAID DIAGRAMS:\n"
        "   - ONLY include Mermaid diagrams when explaining system architectures, workflows, or when explicitly requested. Never for resumes/profiles.\n"
        "   - Use standard ASCII arrows (`-->`, `-.->`, `==>`). Wrap labels in double quotes.\n\n"
        "Do NOT repeat these system rules in your response. Output ONLY the formatted answer."
    )
    if conflict_instruction:
        system_text += f"\n\n{conflict_instruction}"

    user_text = (
        f"Context findings:\n{context or 'No local document match found.'}\n\n"
        f"User Question: {question}"
    )

    return [
        SystemMessage(content=system_text),
        HumanMessage(content=user_text),
    ]


def build_generation_prompt(
    question: str,
    context: str,
    conflict_instruction: str = ""
) -> str:
    return (
        "You are Ridge, an advanced AI research assistant.\n"
        "Synthesize a well-structured, authoritative, and cleanly formatted answer to the user's question based on the provided context.\n\n"
        f"{conflict_instruction}"
        f"Context findings:\n{context or 'No local document match found.'}\n\n"
        f"Question: {question}\n\n"
        "Formatting & Quality Rules:\n"
        "1. DIRECT EXECUTIVE ANSWER: Start with a clear, direct 1-2 sentence answer before expanding into details.\n"
        "2. CLEAN MARKDOWN STRUCTURE: Use clean markdown hierarchy (## Section, ### Subsections, bullet points, bold keywords).\n"
        "3. TABLES & MULTI-ROW DATA:\n"
        "   - When presenting step-by-step flows, comparisons, or structured data in a table, every single row MUST be on its own line starting with `|` and ending with `|`.\n"
        "   - NEVER concatenate multiple table rows on the same line with `||` or `| |`.\n"
        "   - NEVER put physical newlines or raw markdown bullet lists inside table cells. To separate multiple points inside a single cell, use `<br>• ` or concise phrases separated by semicolons.\n"
        "4. NOTEBOOKLM-STYLE INLINE CITATIONS & STRICT GROUNDING:\n"
        "   - Every factual claim, definition, metric, or finding MUST be immediately supported by an inline citation badge corresponding to the numbered context findings: e.g. [1], [2], or [1, 2].\n"
        "   - Place citations at the exact sentence or clause level where the fact is asserted (e.g. 'Corrective RAG integrates a retrieval evaluator to assess document quality [1], falling back to web search when confidence is low [2].').\n"
        "   - Use ONLY clean bracketed numbers like [1] or [1, 2]. Never output raw HTML tags or internal tokens like 【1†L1-L4】.\n"
        "5. ACCURACY & EVIDENCE: Base factual assertions directly on the verified context findings. If the context is unrelated to the question, state that clearly and provide a grounded explanation.\n"
        "6. NO GIBBERISH: If the question is unintelligible keyboard mash, politely ask for clarification.\n"
        "7. MATHEMATICAL EQUATIONS & LATEX: Format all mathematical formulas and variables using standard LaTeX syntax. Use inline `$ ... $` for inline variables and terms (e.g., `$p_c$`, `$\\alpha$`, `$p^s_{T,c}$`), and block `$$ ... $$` on separate lines for display equations. Never output bracketed formulas like `[ p_c := ... ]` or `(\\alpha)` without dollar signs.\n"
        "8. MERMAID DIAGRAMS (STRICT USAGE CRITERIA):\n"
        "   - ONLY include a Mermaid diagram if the user EXPLICITLY asks for a diagram/flowchart/visual representation, or when explaining a complex technical system architecture, data pipeline, protocol sequence, or algorithm execution flow that strictly benefits from visual progression.\n"
        "   - NEVER include Mermaid diagrams for simple definitions, person profiles/biographies/resumes (e.g. 'who is X'), single facts, or general Q&A.\n"
        "   - When a diagram IS appropriate, CRITICAL SYNTAX RULES:\n"
        "     * Use ONLY standard ASCII arrows: `-->`, `-.->`, `==>`. NEVER use Unicode em-dashes or box characters (`─`, `—`, `–`, `→`).\n"
        "     * Wrap all node and subgraph text in double quotes: `A[\"Node Label\"]`, `subgraph ID [\"Group Name\"]`.\n"
        "     * Never use raw HTML tags (`<b>`, `<span>`, `<br>`) inside Mermaid diagrams.\n\n"
        "Do NOT repeat these rules in your response. Begin your answer directly."
    )
