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
    """
    Extracts 11-character YouTube ID from ANY format:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://www.youtube.com/watch?w=VIDEO_ID (typos)
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/shorts/VIDEO_ID
      - https://www.youtube.com/embed/VIDEO_ID
      - Raw 11-char ID (e.g. VIDEO_ID)
    """
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
    Uses yt-dlp with Android/iOS client spoofing to extract exact video subtitles/captions.
    Bypasses AWS EC2 datacenter IP blocks.
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
        uploader = info.get('uploader', 'Speaker/Creator')
        description = info.get('description', '')

        subtitles = info.get('subtitles') or {}
        auto_subs = info.get('automatic_captions') or {}
        all_subs = {**subtitles, **auto_subs}

        if not all_subs:
            # Metadata fallback if captions are completely disabled by uploader
            return (
                f"VIDEO TITLE: {title}\n"
                f"SPEAKER / CHANNEL: {uploader}\n"
                f"DESCRIPTION / OVERVIEW:\n{description[:1500]}\n"
                f"(Note: Captions disabled for this video. Generate notes strictly for the subject matter described above)."
            )

        # Priority language selection
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
            return f"VIDEO TITLE: {title}\nDESCRIPTION:\n{description[:1500]}"

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
            return f"VIDEO TITLE: {title}\nDESCRIPTION:\n{description[:1500]}"

        return (
            f"VIDEO TITLE: {title}\n"
            f"SPEAKER / CHANNEL: {uploader}\n"
            f"TRANSCRIPT LANGUAGE: {chosen_lang}\n\n"
            f"FULL VERBATIM TRANSCRIPT:\n{full_text}"
        )


@tool
def fetch_transcript_tool(url: str) -> str:
    """
    LangChain tool: fetches exact video transcript and title for a YouTube URL.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL or Video ID: {url}")

    normalized_url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        return _fetch_transcript_ytdlp(normalized_url)
    except Exception as e1:
        print(f"[Transcript Warning] yt-dlp failed ({e1}). Trying YouTubeTranscriptApi...")

    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        chosen = transcript_list.find_transcript(['en', 'hi']) or transcript_list.find_generated_transcript(['en', 'hi'])
        if chosen:
            fetched = chosen.fetch()
            text = " ".join(entry.text for entry in fetched)
            return f"VIDEO ID: {video_id}\nTRANSCRIPT LANGUAGE: {chosen.language_code}\n\nFULL VERBATIM TRANSCRIPT:\n{text}"
    except Exception:
        pass

    return f"VIDEO ID: {video_id}\nPlease generate comprehensive structured study notes based on this video."


# ──────────────────────────────────────────────
# 3.  LCEL Notes Chain (STRICT VIDEO-BASED NOTES)
# ──────────────────────────────────────────────

_NOTES_TEMPLATE = """\
You are an expert master educator who creates detailed, high-accuracy study notes.
Your task is to generate comprehensive structured study notes STRICTLY based on the provided YouTube video transcript and title below.

PRIMARY SOURCE OF TRUTH:
The YouTube Video Transcript & Title provided under 'INPUT VIDEO CONTENT'.

RULES FOR NOTE GENERATION:
1. TITLE: Set the 'title' field to match the exact topic or main title of the video.
2. STRICT VIDEO FIDELITY: Your summary, key concepts, bullet points, and flashcards MUST accurately capture the specific ideas, explanations, steps, code, facts, and examples presented by the speaker in this video.
3. ENRICHMENT WITHOUT HALLUCINATION: You may use your background knowledge to clarify technical terms or add definitions, but the core content MUST remain 100% focused on what is covered in the video. Do NOT write generic unrelated textbook fluff.
4. SUMMARY: Provide a clear, comprehensive summary of the main arguments and explanations in the video.
5. BULLET POINTS: Write detailed, actionable, self-contained bullet points covering every major section or step explained in the video.
6. FLASHCARDS & KEY CONCEPTS: Extract the key terms defined or explained in the video and generate flashcards testing understanding of the video content.
7. LANGUAGE: All output fields MUST be in clean, high-quality ENGLISH regardless of the video spoken language (Hindi, Hinglish, English, etc.).

INPUT VIDEO CONTENT:
{transcript}
"""

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

def fetch_transcript_node(state: NotesState) -> NotesState:
    """Node 1: fetch exact video transcript from YouTube."""
    try:
        transcript = fetch_transcript_tool.invoke({"url": state["url"]})
        return {**state, "transcript": transcript, "error": None}
    except Exception as e:
        return {**state, "transcript": "", "error": f"Transcript error: {e}"}


def generate_notes_node(state: NotesState) -> NotesState:
    """Node 2: run LCEL chain for strict video-based structured notes."""
    if state.get("error"):
        return state

    try:
        chain = build_notes_chain(instructions=state.get("instructions", ""))
        notes: NotesOutput = chain.invoke({"transcript": state["transcript"]})
        return {**state, "notes": notes, "error": None}
    except Exception as e:
        return {**state, "notes": None, "error": f"LLM error: {e}"}


def generate_pdfs_node(state: NotesState) -> NotesState:
    """Node 3: convert NotesOutput into downloadable PDF files."""
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
