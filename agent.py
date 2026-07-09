import os
from pydantic import BaseModel, Field
from typing import List
from typing_extensions import TypedDict
from langchain_openrouter import ChatOpenRouter
from langgraph.graph import StateGraph, END

# 1. Define the Graph State
class GraphState(TypedDict):
    question: str
    documents: List[str]
    generation: str

# 2. Setup the Grader Engine
class Grade(BaseModel):
    score: str = Field(description="Are the documents relevant to the question? 'yes' or 'no'")

llm = ChatOpenRouter(model="nvidia/nemotron-3-ultra-550b-a55b:free", temperature=0)
structured_grader = llm.with_structured_output(Grade)

# --- 3. DEFINE THE NODES ---

def grade_documents(state: GraphState):
    """Determines whether the retrieved documents are relevant to the question."""
    print("\n--- NODE: GRADING DOCUMENTS ---")
    question = state["question"]
    doc_text = state["documents"][0] # We will just look at the first doc for this test

    prompt = f"You are a grader assessing relevance.\n\nDocument: {doc_text}\nQuestion: {question}"
    result = structured_grader.invoke(prompt)
    
    # We update the state with a flag that our router will read
    print(f"Decision: '{result.score}'")
    return {"generation": result.score} 

def generate(state: GraphState):
    """Drafts the final answer."""
    print("--- NODE: GENERATING ANSWER ---")
    return {"generation": "This is where the final answer will go."}

def rewrite(state: GraphState):
    """Rewrites the query to try searching again."""
    print("--- NODE: REWRITING QUERY ---")
    return {"question": f"Optimized query for: {state['question']}"}

# --- 4. DEFINE THE ROUTER ---

def decide_to_generate(state: GraphState):
    """Reads the state and dictates the next step in the graph."""
    if state["generation"] == "yes":
        print("--- ROUTER: Document is relevant. Routing to Generate. ---")
        return "generate"
    else:
        print("--- ROUTER: Document is irrelevant. Routing to Rewrite. ---")
        return "rewrite"

# --- 5. BUILD THE GRAPH ---
workflow = StateGraph(GraphState)

# Add the nodes
workflow.add_node("grade_node", grade_documents)
workflow.add_node("generate_node", generate)
workflow.add_node("rewrite_node", rewrite)

# Set the starting point
workflow.set_entry_point("grade_node")

# Add the conditional logic (The Edge)
workflow.add_conditional_edges(
    "grade_node",           # Start from this node
    decide_to_generate,     # Run this routing function
    {
        "generate": "generate_node", # If router returns "generate", go here
        "rewrite": "rewrite_node"    # If router returns "rewrite", go here
    }
)

# End the graph after generating or rewriting (for now)
workflow.add_edge("generate_node", END)
workflow.add_edge("rewrite_node", END)

# Compile the machine
app = workflow.compile()

# --- LET'S TEST IT ---
print("\n=== TEST 1: BAD DOCUMENT ===")
bad_state = {
    "question": "How do I bake a chocolate cake?",
    "documents": ["Python is a high-level programming language used for web development and AI."]
}
app.invoke(bad_state)

print("\n=== TEST 2: GOOD DOCUMENT ===")
good_state = {
    "question": "What is Python used for?",
    "documents": ["Python is a high-level programming language used for web development and AI."]
}
app.invoke(good_state)