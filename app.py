import os
import json
import time
import tempfile
import gradio as gr
from main import build_app, get_settings, ingest_document, get_vectorstore

# Initialize RAG LangGraph Pipeline
rag_app = None

def get_pipeline():
    global rag_app
    if rag_app is None:
        rag_app = build_app()
    return rag_app

def handle_ingest(file_obj, url_text, api_key):
    if api_key:
        os.environ["GROQ_API_KEY"] = api_key.strip()
    
    if not os.getenv("GROQ_API_KEY"):
        return "⚠️ Error: Please provide a GROQ_API_KEY in the sidebar or Space Secrets.", get_suggestions_list(), get_stats_text()

    target = None
    if file_obj is not None:
        target = file_obj.name
    elif url_text and url_text.strip():
        target = url_text.strip()
    else:
        return "⚠️ Please upload a file (PDF/MD/TXT) or provide a valid URL.", get_suggestions_list(), get_stats_text()

    try:
        res = ingest_document(target)
        msg = f"✅ Ingested successfully! Created {res.get('chunks_added', 0)} chunks."
        return msg, get_suggestions_list(), get_stats_text()
    except Exception as e:
        return f"❌ Ingestion failed: {str(e)}", get_suggestions_list(), get_stats_text()

def get_suggestions_list():
    if os.path.exists("suggestions.json"):
        try:
            with open("suggestions.json", "r") as f:
                data = json.load(f)
                return "\n".join([f"• {q}" for q in data.get("suggestions", [])])
        except Exception:
            pass
    return "• What is task decomposition in LLM agents?\n• What are the key components of an agent?\n• How does self-reflection work?"

def get_stats_text():
    try:
        vs = get_vectorstore()
        count = vs._collection.count()
        return f"📚 Knowledge Base: {count} chunks indexed"
    except Exception:
        return "📚 Knowledge Base: Ready"

def respond(message, chat_history, api_key):
    if not message or not message.strip():
        yield "", chat_history, ""
        return

    if api_key:
        os.environ["GROQ_API_KEY"] = api_key.strip()

    if not os.getenv("GROQ_API_KEY"):
        bot_message = "⚠️ Please provide your **GROQ_API_KEY** in the sidebar to activate the assistant."
        chat_history.append((message, bot_message))
        yield "", chat_history, "Status: Missing API Key"
        return

    pipeline = get_pipeline()
    chat_history.append((message, ""))
    
    initial_state = {
        "question": message,
        "documents": [],
        "documents_metadata": [],
        "generation": "",
        "loop_count": 0,
        "past_queries": [],
        "latency_ms": 0,
    }

    logs = []
    final_answer = ""

    try:
        for event in pipeline.stream(initial_state):
            node_name = list(event.keys())[0]
            node_output = event[node_name]

            if node_name == "retrieve_node":
                docs = node_output.get("documents", [])
                logs.append(f"🔍 **Retrieved & Re-ranked**: {len(docs)} passages")
            elif node_name == "grade_node":
                decision = node_output.get("generation", "unknown")
                docs = node_output.get("documents", [])
                logs.append(f"⚖️ **Grading Decision**: `{decision}` ({len(docs)} relevant passages)")
            elif node_name == "web_search_node":
                logs.append("🌐 **Fallback**: Performed DuckDuckGo search")
            elif node_name == "rewrite_node":
                new_q = node_output.get("question", "")
                logs.append(f"✏️ **Rewrote Query**: *{new_q}*")
            elif node_name == "generate_node":
                final_answer = node_output.get("generation", "")
                logs.append("✨ **Answer Generated**")

            status_str = "\n".join(logs)
            chat_history[-1] = (message, final_answer if final_answer else f"⏳ *Processing...*\n\n{status_str}")
            yield "", chat_history, status_str

        chat_history[-1] = (message, final_answer)
        yield "", chat_history, "\n".join(logs)

    except Exception as e:
        chat_history[-1] = (message, f"❌ Error: {str(e)}")
        yield "", chat_history, f"Error: {str(e)}"

# Custom CSS for modern theme
custom_css = """
.gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}
#header {
    text-align: center;
    margin-bottom: 1.5rem;
}
#status-box {
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    padding: 12px;
    font-size: 0.9rem;
}
"""

with gr.Blocks(css=custom_css, title="Recall — Corrective RAG LangGraph") as demo:
    gr.Markdown(
        """
        # 🔁 Recall — Corrective RAG
        ### Self-correcting LangGraph pipeline with FlashRank re-ranking & Groq LLM grading
        """,
        elem_id="header"
    )

    with gr.Row():
        with gr.Column(scale=1):
            with gr.Accordion("🔑 API Configuration", open=True):
                api_key_input = gr.Textbox(
                    label="Groq API Key",
                    placeholder="gsk_...",
                    type="password",
                    value=os.getenv("GROQ_API_KEY", ""),
                    info="Used for LLM grading and answer generation"
                )

            with gr.Accordion("📥 Ingest Knowledge Base", open=True):
                file_upload = gr.File(
                    label="Upload File (PDF, MD, TXT)",
                    file_types=[".pdf", ".md", ".txt"]
                )
                url_input = gr.Textbox(
                    label="Or Web URL",
                    placeholder="https://lilianweng.github.io/posts/2023-06-23-agent/"
                )
                ingest_btn = gr.Button("⚡ Index Document", variant="primary")
                ingest_output = gr.Textbox(label="Ingestion Status", interactive=False)

            stats_display = gr.Markdown(get_stats_text())

            with gr.Accordion("💡 Suggested Questions", open=True):
                suggestions_box = gr.Markdown(get_suggestions_list())

        with gr.Column(scale=2):
            chatbot = gr.Chatbot(
                label="Conversation",
                height=520,
                show_copy_button=True
            )
            with gr.Row():
                msg_input = gr.Textbox(
                    placeholder="Ask a question about your documents...",
                    show_label=False,
                    scale=8
                )
                send_btn = gr.Button("Ask", variant="primary", scale=1)

            with gr.Accordion("🔍 Live LangGraph Trace", open=True):
                trace_box = gr.Markdown(
                    "Pipeline events will appear here as nodes execute.",
                    elem_id="status-box"
                )

    # Event handlers
    ingest_btn.click(
        fn=handle_ingest,
        inputs=[file_upload, url_input, api_key_input],
        outputs=[ingest_output, suggestions_box, stats_display]
    )

    send_btn.click(
        fn=respond,
        inputs=[msg_input, chatbot, api_key_input],
        outputs=[msg_input, chatbot, trace_box]
    )
    
    msg_input.submit(
        fn=respond,
        inputs=[msg_input, chatbot, api_key_input],
        outputs=[msg_input, chatbot, trace_box]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
