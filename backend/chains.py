"""
chains.py
---------
LCEL notes chain + LangGraph StateGraph pipeline.

Graph flow:
  fetch_transcript → generate_notes → generate_pdfs → END
  (with error short-circuit after each node)
"""

import re
from typing import TypedDict, Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from youtube_transcript_api import YouTubeTranscriptApi

from llm import llm_model
from notes_schema import NotesOutput
from pdf_generator import generate_all_pdfs


# ──────────────────────────────────────────────
# 1.  LangGraph State
# ──────────────────────────────────────────────

class NotesState(TypedDict):
    url: str
    instructions: Optional[str]   # optional user instructions from the frontend
    transcript: str
    notes: Optional[NotesOutput]
    pdf_paths: dict          # {"summary": path, "cheatsheet": path, "flashcards": path}
    error: Optional[str]


# ──────────────────────────────────────────────
# 2.  LangChain Tool (transcript fetching)
#     Decorated with @tool so it's agent-compatible
#     and reusable outside the graph too.
# ──────────────────────────────────────────────

def _extract_video_id(url: str) -> Optional[str]:
    """Support standard watch URLs and short youtu.be links."""
    patterns = [
        r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


@tool
def fetch_transcript_tool(url: str) -> str:
    """
    LangChain tool: fetches and returns the plain-text transcript
    for a given YouTube video URL.

    Priority order:
      1. Manual (human-created) English captions
      2. Auto-generated English captions
      3. Manual captions in any other language (Hindi, etc.)
      4. Auto-generated captions in any other language

    Accepts any language — the LLM handles translation to English notes.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)

    # Collect candidates by priority bucket
    manual_en   = None   # priority 1 — best
    auto_en     = None   # priority 2
    manual_any  = None   # priority 3
    auto_any    = None   # priority 4 — last resort

    for t in transcript_list:
        is_english = t.language_code.startswith('en')
        if is_english and not t.is_generated and manual_en is None:
            manual_en = t
        elif is_english and t.is_generated and auto_en is None:
            auto_en = t
        elif not is_english and not t.is_generated and manual_any is None:
            manual_any = t
        elif not is_english and t.is_generated and auto_any is None:
            auto_any = t

    chosen = manual_en or auto_en or manual_any or auto_any

    if chosen is None:
        raise ValueError(
            "No transcript found for this video. "
            "The video may have captions disabled."
        )

    fetched = chosen.fetch()
    lang = chosen.language_code
    text = " ".join(entry.text for entry in fetched)

    # Prepend language hint so the LLM knows what it's reading
    header = f"[Transcript language: {lang}]\n"
    return header + text


# ──────────────────────────────────────────────
# 3.  LCEL Notes Chain
#     prompt | llm.with_structured_output(NotesOutput)
# ──────────────────────────────────────────────

_NOTES_TEMPLATE = """\
You are an expert educator who creates concise, high-quality study notes.
Given the transcript of a YouTube video, produce structured notes by combining
two sources of knowledge:

  1. PRIMARY SOURCE — the video transcript provided below.
  2. YOUR OWN KNOWLEDGE BASE — use your training knowledge to:
       - Add clear definitions for any terms or concepts mentioned.
       - Provide relevant background context the video may have skipped.
       - Include real-world examples or analogies to strengthen understanding.
       - Fill in gaps where the transcript is brief or unclear.
       - Add extra depth to bullet points beyond what was literally said.

Rules:
- ALWAYS write all output fields in ENGLISH, regardless of the transcript language.
- If the transcript is in Hindi, Hinglish, or any other language, translate the
  content to English and generate notes in English.
- The transcript is the anchor — do not go off-topic or invent unrelated content.
- Enrich, expand, and deepen — do not just copy the transcript word for word.
- Bullet points should be self-contained, information-dense, and enriched with
  context from your knowledge where helpful.
- Flashcard questions should test deep understanding, not just surface recall.
- Key concepts should include a brief definition even if the video didn't define them.

TRANSCRIPT:
{transcript}
"""

def build_notes_chain(llm=None, instructions: str = ""):
    """
    Returns an LCEL chain:
        PromptTemplate | llm.with_structured_output(NotesOutput)

    The chain accepts {"transcript": <str>} and returns a NotesOutput object.
    Optionally accepts user instructions to focus the note generation.
    """
    if llm is None:
        llm = llm_model()

    # Append user instructions to the template if provided
    extra = (
        f"\nUser Instructions (follow these specifically): {instructions.strip()}\n"
        if instructions and instructions.strip()
        else ""
    )
    template = _NOTES_TEMPLATE + extra

    prompt = PromptTemplate(
        input_variables=["transcript"],
        template=template,
    )

    # LCEL pipe — with_structured_output enforces the Pydantic schema
    return prompt | llm.with_structured_output(NotesOutput)


# ──────────────────────────────────────────────
# 4.  LangGraph Nodes
# ──────────────────────────────────────────────

def fetch_transcript_node(state: NotesState) -> NotesState:
    """Node 1: fetch the transcript from YouTube."""
    try:
        transcript = fetch_transcript_tool.invoke({"url": state["url"]})
        return {**state, "transcript": transcript, "error": None}
    except Exception as e:
        return {**state, "transcript": "", "error": f"Transcript error: {e}"}


def generate_notes_node(state: NotesState) -> NotesState:
    """Node 2: run the LCEL chain to produce structured notes (JSON → Pydantic)."""
    if state.get("error"):
        return state  # short-circuit on prior error

    try:
        chain = build_notes_chain(instructions=state.get("instructions", ""))
        notes: NotesOutput = chain.invoke({"transcript": state["transcript"]})
        return {**state, "notes": notes, "error": None}
    except Exception as e:
        return {**state, "notes": None, "error": f"LLM error: {e}"}


def generate_pdfs_node(state: NotesState) -> NotesState:
    """Node 3: convert the NotesOutput into downloadable PDF files."""
    if state.get("error"):
        return state  # short-circuit on prior error

    try:
        pdf_paths = generate_all_pdfs(state["notes"])
        return {**state, "pdf_paths": pdf_paths, "error": None}
    except Exception as e:
        return {**state, "pdf_paths": {}, "error": f"PDF error: {e}"}


# ──────────────────────────────────────────────
# 5.  Build & Compile the LangGraph
# ──────────────────────────────────────────────

def build_graph():
    """
    Builds and compiles the LangGraph StateGraph.

    Nodes:  fetch_transcript → generate_notes → generate_pdfs → END
    """
    graph = StateGraph(NotesState)

    graph.add_node("fetch_transcript", fetch_transcript_node)
    graph.add_node("generate_notes", generate_notes_node)
    graph.add_node("generate_pdfs", generate_pdfs_node)

    graph.set_entry_point("fetch_transcript")
    graph.add_edge("fetch_transcript", "generate_notes")
    graph.add_edge("generate_notes", "generate_pdfs")
    graph.add_edge("generate_pdfs", END)

    return graph.compile()


# Singleton compiled graph (imported by app.py)
notes_graph = build_graph()
