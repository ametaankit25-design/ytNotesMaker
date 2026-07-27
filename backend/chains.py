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
    instructions: Optional[str]
    transcript: str
    notes: Optional[NotesOutput]
    pdf_paths: dict
    error: Optional[str]


# ──────────────────────────────────────────────
# 2.  Resilient Video ID & Transcript Fetcher
# ──────────────────────────────────────────────

def _extract_video_id(url: str) -> Optional[str]:
    url = url.strip()
    patterns = [
        r'(?:v|w|vi)[=/]([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)

    fallback_m = re.search(r'([a-zA-Z0-9_-]{11})', url)
    if fallback_m:
        return fallback_m.group(1)

    return None


def _fetch_transcript_ytdlp(url: str) -> str:
    """
    Extracts video title and exact spoken transcript using yt-dlp.
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
        title = info.get('title', 'YouTube Video')
        uploader = info.get('uploader', 'Speaker')
        description = info.get('description', '')

        subtitles = info.get('subtitles') or {}
        auto_subs = info.get('automatic_captions') or {}
        all_subs = {**subtitles, **auto_subs}

        if not all_subs:
            print(f"[Transcript] No subtitles found for {url}. Using video description fallback.")
            return (
                f"VIDEO TITLE: {title}\n"
                f"SPEAKER / CHANNEL: {uploader}\n"
                f"VIDEO DESCRIPTION:\n{description[:2000]}\n"
            )

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
            return f"VIDEO TITLE: {title}\nDESCRIPTION:\n{description[:2000]}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Android 14; Mobile; rv:120.0) Gecko/120.0 Firefox/120.0"
            )
        }
        resp = requests.get(sub_url, headers=headers, timeout=10)
        content = resp.text

        text_snippets = []
        if 'json3' in sub_url or content.strip().startswith('{'):
            try:
                data = json.loads(content)
                for ev in data.get('events', []):
                    for s in ev.get('segs', []):
                        t = s.get('utf8', '').strip()
                        if t and t != '\n':
                            text_snippets.append(t)
            except Exception:
                pass

        if not text_snippets:
            # Fallback text parsing for XML/VTT/SRV1 formats
            lines = content.splitlines()
            for line in lines:
                cleaned_line = re.sub(r'<[^>]+>', '', line).strip()
                if (
                    cleaned_line
                    and not cleaned_line.isdigit()
                    and '-->' not in cleaned_line
                    and not cleaned_line.startswith('WEBVTT')
                ):
                    text_snippets.append(cleaned_line)

        full_text = " ".join(text_snippets)
        print(f"[Transcript Success] Fetched {len(full_text)} characters of transcript for '{title}'")

        if not full_text.strip():
            return f"VIDEO TITLE: {title}\nDESCRIPTION:\n{description[:2000]}"

        return (
            f"VIDEO TITLE: {title}\n"
            f"SPEAKER / CHANNEL: {uploader}\n"
            f"TRANSCRIPT:\n{full_text}"
        )


@tool
def fetch_transcript_tool(url: str) -> str:
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL or Video ID: {url}")

    normalized_url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        return _fetch_transcript_ytdlp(normalized_url)
    except Exception as e1:
        print(f"[Transcript Warning] yt-dlp failed ({e1}). Trying YouTubeTranscriptApi...")

    try:
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'hi'])
        text = " ".join(entry['text'] for entry in data)
        print(f"[Transcript API Success] Fetched {len(text)} characters for Video ID {video_id}")
        return f"VIDEO ID: {video_id}\nTRANSCRIPT:\n{text}"
    except Exception as e2:
        print(f"[Transcript API Error] {e2}")

    return f"VIDEO ID: {video_id}\nPlease generate structured notes based on this video subject matter."


# ──────────────────────────────────────────────
# 3.  LCEL Notes Chain (STRICT VIDEO-BASED NOTES)
# ──────────────────────────────────────────────

_NOTES_TEMPLATE = """\
You are a study notes generator. Your ONLY job is to extract information from the provided YouTube video transcript and create structured notes.

**STRICT RULES - READ CAREFULLY:**
1. READ the VIDEO TITLE from the transcript below and use it as your "title" field
2. READ the TRANSCRIPT carefully - every word matters
3. Create notes ONLY from what you read in the transcript - DO NOT add outside knowledge
4. If the video is about "Python Tutorial", write notes about what the speaker teaches in THIS video
5. If the video is about "Machine Learning", write notes about the specific ML concepts THIS speaker explains
6. Include specific examples, code snippets, or steps that appear in the transcript
7. Use the speaker's teaching flow - start to finish

**OUTPUT FORMAT:**
- title: Use the exact VIDEO TITLE from the transcript
- summary: 2-3 paragraphs summarizing what THIS video covers (not generic definitions)
- key_concepts: 5-10 terms/concepts that THIS speaker actually explains in THIS video
- bullet_points: 15-20 notes capturing the main points from THIS video transcript
- flashcards: 10 Q&A pairs based on what THIS video teaches
- important_quotes: Any notable statements from THIS speaker (if any)

**EXAMPLE - GOOD vs BAD:**
❌ BAD (generic): "Python is a programming language. Variables store data. Functions perform tasks."
✅ GOOD (video-specific): "The speaker explains Python basics starting with print() function. Shows example: print('Hello'). Then demonstrates variables: x = 5, name = 'John'. Explains that Python is dynamically typed."

**THE VIDEO TRANSCRIPT IS BELOW:**
---
{transcript}
---

NOW GENERATE NOTES FROM THIS SPECIFIC VIDEO TRANSCRIPT ONLY. DO NOT USE EXTERNAL KNOWLEDGE."""

def build_notes_chain(llm=None, instructions: str = ""):
    if llm is None:
        llm = llm_model()

    extra = (
        f"\nSPECIAL USER INSTRUCTIONS (apply these focus areas to the video notes): {instructions.strip()}\n"
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

MAX_TRANSCRIPT_LENGTH = 12000  # ~3000 tokens for context limit

def fetch_transcript_node(state: NotesState) -> NotesState:
    """Node 1: fetch exact video transcript from YouTube with safe dynamic truncation."""
    try:
        raw_transcript = fetch_transcript_tool.invoke({"url": state["url"]})
        
        # Debug: Print raw transcript length and preview
        print(f"\n{'='*60}")
        print(f"[DEBUG] Transcript fetched: {len(raw_transcript)} characters")
        print(f"[DEBUG] First 300 chars:\n{raw_transcript[:300]}")
        print(f"{'='*60}\n")
        
        # If total length is within limit, return unchanged
        if len(raw_transcript) <= MAX_TRANSCRIPT_LENGTH:
            return {**state, "transcript": raw_transcript, "error": None}

        # --- Fix: Dynamic Header vs Body Separation ---
        lines = raw_transcript.split('\n')
        header_lines = []
        body_start_index = 0

        # Dynamically locate header lines (TITLE, SPEAKER, TRANSCRIPT: label)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if any(k in stripped for k in ['VIDEO TITLE:', 'SPEAKER / CHANNEL:', 'TRANSCRIPT LANGUAGE:', 'VIDEO ID:', 'DESCRIPTION:']):
                header_lines.append(line)
                body_start_index = i + 1
            elif stripped in ['TRANSCRIPT:', 'FULL VERBATIM TRANSCRIPT:']:
                header_lines.append(line)
                body_start_index = i + 1
                break  # Stop header scan after TRANSCRIPT label
            elif i >= 10:
                # Safety cap: don't scan past first 10 lines for header
                break

        header_str = '\n'.join(header_lines) if header_lines else ""
        transcript_body = '\n'.join(lines[body_start_index:]).strip()

        # Fallback: if body separation failed, treat whole raw string as body
        if not transcript_body:
            transcript_body = raw_transcript
            header_str = ""

        # Calculate remaining character budget for transcript body
        header_len = len(header_str)
        available_body_budget = max(1000, MAX_TRANSCRIPT_LENGTH - header_len - 150)
        
        # Truncate body from the END (keeping the crucial beginning)
        truncated_body = transcript_body[:available_body_budget]
        cut_chars = max(0, len(transcript_body) - len(truncated_body))

        print(f"⚠️  [Transcript Node] Truncation Applied:")
        print(f"    - Kept header: {header_len} chars")
        print(f"    - Kept body:   {len(truncated_body)} chars")
        print(f"    - Cut off:     {cut_chars} chars from end")

        final_transcript = (
            (header_str + "\n\n" if header_str else "")
            + truncated_body
            + (f"\n\n[...transcript truncated for length ({cut_chars} characters cut)...]" if cut_chars > 0 else "")
        )

        return {**state, "transcript": final_transcript, "error": None}
    except Exception as e:
        return {**state, "transcript": "", "error": f"Transcript error: {e}"}


def generate_notes_node(state: NotesState) -> NotesState:
    if state.get("error"):
        return state

    try:
        print(f"\n{'='*60}")
        print(f"[DEBUG] Calling LLM with transcript ({len(state['transcript'])} chars)...")
        print(f"{'='*60}\n")
        
        chain = build_notes_chain(instructions=state.get("instructions", ""))
        notes: NotesOutput = chain.invoke({"transcript": state["transcript"]})
        
        # Debug: Print generated notes preview
        print(f"\n{'='*60}")
        print(f"[DEBUG] LLM Generated Notes:")
        print(f"  Title: {notes.title}")
        print(f"  Summary (first 200 chars): {notes.summary[:200]}...")
        print(f"  Key Concepts: {len(notes.key_concepts)} concepts")
        print(f"  Bullet Points: {len(notes.bullet_points)} points")
        print(f"  Flashcards: {len(notes.flashcards)} cards")
        print(f"{'='*60}\n")
        
        return {**state, "notes": notes, "error": None}
    except Exception as e:
        print(f"❌ [ERROR] LLM generation failed: {e}")
        return {**state, "notes": None, "error": f"LLM error: {e}"}


def generate_pdfs_node(state: NotesState) -> NotesState:
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
