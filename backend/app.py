"""
app.py
------
YT Notes Maker — Gradio UI
Orchestrates the LangGraph pipeline:
  fetch_transcript → generate_notes → generate_pdfs
"""

import re
import gradio as gr
from chains import notes_graph


# ──────────────────────────────────────────────
# Pipeline entry point
# ──────────────────────────────────────────────

def run_pipeline(url: str):
    """
    Invokes the compiled LangGraph with the YouTube URL.
    Returns (status_message, summary_pdf, cheatsheet_pdf, flashcards_pdf).
    """
    url = url.strip()
    if not url:
        return "⚠️  Please paste a YouTube URL.", None, None, None

    # Initial state fed into the graph
    initial_state = {
        "url": url,
        "transcript": "",
        "notes": None,
        "pdf_paths": {},
        "error": None,
    }

    result = notes_graph.invoke(initial_state)

    if result.get("error"):
        return f"❌  Error: {result['error']}", None, None, None

    paths = result["pdf_paths"]
    notes = result["notes"]

    status = (
        f"✅  Done! Generated notes for: **{notes.title}**\n\n"
        f"📄 {len(notes.bullet_points)} bullet points · "
        f"🔑 {len(notes.key_concepts)} key concepts · "
        f"🃏 {len(notes.flashcards)} flashcards"
    )

    return (
        status,
        paths.get("summary"),
        paths.get("cheatsheet"),
        paths.get("flashcards"),
    )


# ──────────────────────────────────────────────
# Gradio UI
# ──────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* { font-family: 'Inter', sans-serif; box-sizing: border-box; }

body, .gradio-container {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%) !important;
    min-height: 100vh;
}

/* Hero header */
.hero {
    text-align: center;
    padding: 40px 20px 20px;
}
.hero h1 {
    font-size: 2.8rem;
    font-weight: 700;
    background: linear-gradient(90deg, #6366f1, #8b5cf6, #ec4899);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}
.hero p {
    color: #94a3b8;
    font-size: 1.1rem;
    margin-top: 10px;
}

/* Input panel */
.input-panel {
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 16px;
    padding: 24px;
    backdrop-filter: blur(12px);
}

/* URL textbox */
.url-input textarea {
    background: rgba(15, 23, 42, 0.9) !important;
    border: 1px solid rgba(99, 102, 241, 0.4) !important;
    border-radius: 12px !important;
    color: #f8fafc !important;
    font-size: 1rem !important;
    padding: 12px 16px !important;
    transition: border-color 0.2s;
}
.url-input textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
}

/* Generate button */
.generate-btn {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    border-radius: 12px !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    padding: 14px 32px !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.35) !important;
    width: 100% !important;
}
.generate-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(99, 102, 241, 0.5) !important;
}
.generate-btn:active { transform: translateY(0) !important; }

/* Status box */
.status-box {
    background: rgba(30, 41, 59, 0.7) !important;
    border: 1px solid rgba(16, 185, 129, 0.3) !important;
    border-radius: 12px !important;
    color: #f8fafc !important;
    padding: 16px !important;
}

/* Download cards */
.download-card {
    background: rgba(30, 41, 59, 0.8) !important;
    border: 1px solid rgba(99, 102, 241, 0.25) !important;
    border-radius: 14px !important;
    padding: 20px !important;
    transition: all 0.2s ease !important;
}
.download-card:hover {
    border-color: rgba(99, 102, 241, 0.6) !important;
    transform: translateY(-2px) !important;
}

/* Labels */
label span {
    color: #94a3b8 !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
}

/* Steps info strip */
.steps {
    display: flex;
    gap: 16px;
    justify-content: center;
    margin: 20px 0;
    flex-wrap: wrap;
}
.step {
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.25);
    border-radius: 999px;
    padding: 6px 18px;
    color: #a5b4fc;
    font-size: 0.85rem;
    font-weight: 500;
}
"""

HERO_HTML = """
<div class="hero">
    <h1>📺 YT Notes Maker</h1>
    <p>Paste any YouTube link · get instant PDF notes powered by Gemini + LangGraph</p>
    <div class="steps">
        <span class="step">1 · Paste URL</span>
        <span class="step">2 · Fetch Transcript</span>
        <span class="step">3 · LLM Generates Notes</span>
        <span class="step">4 · Download PDFs</span>
    </div>
</div>
"""

with gr.Blocks(title="YT Notes Maker") as demo:

    gr.HTML(HERO_HTML)

    with gr.Row():
        with gr.Column(scale=3):
            with gr.Group(elem_classes="input-panel"):
                url_input = gr.Textbox(
                    label="YouTube URL",
                    placeholder="https://www.youtube.com/watch?v=...",
                    elem_classes="url-input",
                    lines=1,
                )
                generate_btn = gr.Button(
                    "⚡  Generate Notes",
                    variant="primary",
                    elem_classes="generate-btn",
                )

        with gr.Column(scale=2):
            status_out = gr.Markdown(
                value="Waiting for a YouTube URL...",
                elem_classes="status-box",
            )

    gr.Markdown("### 📥 Download Your Notes")

    with gr.Row():
        with gr.Column(elem_classes="download-card"):
            gr.Markdown("#### 📋 Summary")
            gr.Markdown("*A thorough 2-3 paragraph summary + notable quotes*")
            summary_file = gr.File(
                label="Summary PDF",
                file_types=[".pdf"],
                interactive=False,
            )

        with gr.Column(elem_classes="download-card"):
            gr.Markdown("#### 📝 Cheatsheet")
            gr.Markdown("*Key concepts + 15–20 detailed bullet-point notes*")
            cheatsheet_file = gr.File(
                label="Cheatsheet PDF",
                file_types=[".pdf"],
                interactive=False,
            )

        with gr.Column(elem_classes="download-card"):
            gr.Markdown("#### 🃏 Flashcards")
            gr.Markdown("*10 Q&A pairs to test your knowledge*")
            flashcards_file = gr.File(
                label="Flashcards PDF",
                file_types=[".pdf"],
                interactive=False,
            )

    # Wire button → pipeline
    generate_btn.click(
        fn=run_pipeline,
        inputs=[url_input],
        outputs=[status_out, summary_file, cheatsheet_file, flashcards_file],
        show_progress="full",
    )

    gr.HTML("""
    <div style="text-align:center; margin-top:30px; color:#475569; font-size:0.8rem;">
        Powered by Gemini · LangGraph · LangChain · fpdf2
    </div>
    """)


if __name__ == "__main__":
    demo.launch(share=False, css=CSS)
