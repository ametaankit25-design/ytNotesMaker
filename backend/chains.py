"""
chains.py
---------
LCEL notes chain + LangGraph StateGraph pipeline.

Graph flow:
  fetch_transcript → generate_notes → generate_pdfs → END
  (with error short-circuit after each node)
"""

import json
import re
import xml.etree.ElementTree as ET
from typing import TypedDict, Optional
import requests
import yt_dlp

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
# 2.  LangChain Tool (transcript fetching with yt-dlp)
# ──────────────────────────────────────────────

def _extract_video_id(url: str) -> Optional[str]:
    """Support standard watch URLs and short youtu.be links."""
    patterns = [
        r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def _fetch_transcript_ytdlp(url: str) -> str:
    """
    Primary method: Uses yt-dlp with Android/iOS client spoofing.
    Bypasses AWS EC2 datacenter IP blocks by requesting Android/iOS API client endpoints.
    """
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'en-US', 'en-GB', 'hi', 'hi-IN', 'all'],
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
            }
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        subtitles = info.get('subtitles') or {}
        auto_subs = info.get('automatic_captions') or {}

        all_subs = {**auto_subs, **subtitles}
        if not all_subs:
            raise ValueError("No subtitles or captions found for this YouTube video.")

        # Find best language track (English > Hindi > any)
        chosen_lang = None
        for lang in ['en', 'en-US', 'en-GB', 'hi', 'hi-IN']:
            if lang in all_subs:
                chosen_lang = lang
                break
        if not chosen_lang:
            chosen_lang = list(all_subs.keys())[0]

        formats = all_subs[chosen_lang]
        sub_url = None
        for fmt in formats:
            if fmt.get('ext') in ['json3', 'srv1', 'ttml', 'vtt']:
                sub_url = fmt.get('url')
                break
        if not sub_url and formats:
            sub_url = formats[0].get('url')

        if not sub_url:
            raise ValueError(f"Could not retrieve caption URL for language {chosen_lang}")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Android 14; Mobile; rv:120.0) Gecko/120.0 Firefox/120.0"
            )
        }
        resp = requests.get(sub_url, headers=headers, timeout=10)
        content = resp.text

        text_snippets = []
        if 'json3' in sub_url or content.strip().startswith('{'):
            data = json.loads(content)
            for ev in data.get('events', []):
                for s in ev.get('segs', []):
                    t = s.get('utf8', '').strip()
                    if t and t != '\n':
                        text_snippets.append(t)
        elif '<transcript>' in content or '<tt' in content:
            root = ET.fromstring(content)
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    text_snippets.append(elem.text.strip())
        else:
            lines = content.splitlines()
            for line in lines:
                if '-->' not in line and not line.isdigit() and line.strip() and not line.startswith('WEBVTT'):
                    text_snippets.append(line.strip())

        full_text = " ".join(text_snippets)
        if not full_text.strip():
            raise ValueError("Extracted caption content was empty.")

        return f"[Transcript language: {chosen_lang}]\n" + full_text


@tool
def fetch_transcript_tool(url: str) -> str:
    """
    LangChain tool: fetches transcript for a YouTube video.
    Uses yt-dlp Android client spoofing first (bypasses AWS IP blocks),
    then falls back to YouTubeTranscriptApi.
    """
    # 1. Try yt-dlp first (best for AWS EC2 / Cloud IPs)
    try:
        return _fetch_transcript_ytdlp(url)
    except Exception as e1:
        print(f"[Transcript yt-dlp Warning] {e1}. Trying YouTubeTranscriptApi fallback...")

    # 2. Fallback to YouTubeTranscriptApi
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)

    manual_en, auto_en, manual_any, auto_any = None, None, None, None
    for t in transcript_list:
        is_en = t.language_code.startswith('en')
        if is_en and not t.is_generated and manual_en is None:
            manual_en = t
        elif is_en and t.is_generated and auto_en is None:
            auto_en = t
        elif not is_en and not t.is_generated and manual_any is None:
            manual_any = t
        elif not is_en and t.is_generated and auto_any is None:
            auto_any = t

    chosen = manual_en or auto_en or manual_any or auto_any
    if chosen:
        fetched = chosen.fetch()
        text = " ".join(entry.text for entry in fetched)
        return f"[Transcript language: {chosen.language_code}]\n" + text

    raise ValueError("Could not retrieve transcript from YouTube using any method.")


# ──────────────────────────────────────────────
# 3.  LCEL Notes Chain
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
    if llm is None:
        llm = llm_model()

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
        return state

    try:
        chain = build_notes_chain(instructions=state.get("instructions", ""))
        notes: NotesOutput = chain.invoke({"transcript": state["transcript"]})
        return {**state, "notes": notes, "error": None}
    except Exception as e:
        return {**state, "notes": None, "error": f"LLM error: {e}"}


def generate_pdfs_node(state: NotesState) -> NotesState:
    """Node 3: convert the NotesOutput into downloadable PDF files."""
    if state.get("error"):
        return state

    try:
        pdf_paths = generate_all_pdfs(state["notes"])
        return {**state, "pdf_paths": pdf_paths, "error": None}
    except Exception as e:
        return {**state, "pdf_paths": {}, "error": f"PDF error: {e}"}


# ──────────────────────────────────────────────
# 5.  Build & Compile the LangGraph
# ──────────────────────────────────────────────

def build_graph():
    graph = StateGraph(NotesState)

    graph.add_node("fetch_transcript", fetch_transcript_node)
    graph.add_node("generate_notes", generate_notes_node)
    graph.add_node("generate_pdfs", generate_pdfs_node)

    graph.set_entry_point("fetch_transcript")
    graph.add_edge("fetch_transcript", "generate_notes")
    graph.add_edge("generate_notes", "generate_pdfs")
    graph.add_edge("generate_pdfs", END)

    return graph.compile()


notes_graph = build_graph()
