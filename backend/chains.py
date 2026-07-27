"""
chains.py
---------
LCEL notes chain + LangGraph StateGraph pipeline.

Graph flow:
  fetch_transcript → generate_notes → generate_pdfs → END
  (with error short-circuit after each node)
"""

import json
import os
import re
import html
import time
import xml.etree.ElementTree as ET
from typing import TypedDict, Optional
import requests
import yt_dlp

from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END

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
# 2.  Helpers
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


def _clean_text(text: str) -> str:
    """Remove HTML tags and decode HTML entities."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


# ──────────────────────────────────────────────
# 3.  Transcript Strategies
# ──────────────────────────────────────────────

# ── Strategy 1: pytubefix (Modern active engine with auto bot-bypass) ───────────────
def _fetch_via_pytubefix(video_id: str) -> tuple[Optional[str], str, str, str]:
    """
    Uses pytubefix library — active pytube fork with built-in PO Token generator
    and client rotation (WEB/IOS/ANDROID) to bypass bot detection automatically.
    Returns (transcript_text, title, uploader, description).
    """
    title = uploader = description = ""
    url = f"https://www.youtube.com/watch?v={video_id}"

    for client_type in ['WEB', 'IOS', 'MWEB', 'ANDROID']:
        try:
            from pytubefix import YouTube
            yt = YouTube(url, client=client_type)
            title = yt.title or ""
            uploader = yt.author or ""
            description = yt.description or ""

            captions = yt.captions
            if not captions:
                print(f"[Transcript] Strategy 1 (pytubefix/{client_type}): No captions available for {video_id}")
                continue

            chosen_caption = None
            for lang_code in ['en', 'en-US', 'en-GB', 'hi', 'hi-IN']:
                if lang_code in captions:
                    chosen_caption = captions[lang_code]
                    break
            if not chosen_caption:
                chosen_caption = list(captions.values())[0]

            raw_srt = chosen_caption.generate_srt_captions()
            lines = []
            for line in raw_srt.splitlines():
                cleaned = _clean_text(line)
                if cleaned and not cleaned.isdigit() and '-->' not in cleaned:
                    lines.append(cleaned)

            transcript_text = " ".join(lines).strip() or None

            if transcript_text:
                print(f"[Transcript] Strategy 1 (pytubefix/{client_type}) SUCCESS: {len(transcript_text)} chars, title='{title}'")
                return transcript_text, title, uploader, description

        except Exception as e:
            print(f"[Transcript] Strategy 1 (pytubefix/{client_type}) failed: {e}")

    return None, title, uploader, description


# ── Strategy 2: youtube-transcript-api v1.x (from Manual-tool-calling-agent notebook) ──
def _fetch_via_transcript_api(video_id: str) -> Optional[str]:
    """
    Uses the v1.x API pattern: YouTubeTranscriptApi().fetch(video_id, languages=[...])
    Returns transcript text joined from .snippets (not the old .get_transcript dict format).
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt_api = YouTubeTranscriptApi()

        # Try multiple language codes
        for langs in [["en"], ["en-US"], ["en-GB"], ["hi"], ["hi-IN"]]:
            try:
                transcript = ytt_api.fetch(video_id, languages=langs)
                text = " ".join(_clean_text(snippet.text) for snippet in transcript.snippets)
                if text.strip():
                    print(f"[Transcript] Strategy 2 (TranscriptAPI v1.x) SUCCESS: {len(text)} chars, lang={langs[0]}")
                    return text
            except Exception:
                continue

        print(f"[Transcript] Strategy 2 (TranscriptAPI v1.x): No transcript found in any language")
    except Exception as e:
        print(f"[Transcript] Strategy 2 (TranscriptAPI v1.x) failed: {e}")
    return None


# ── Strategy 3: yt-dlp with cookies.txt + retry ────────────────────────────────────
def _fetch_via_ytdlp(video_id: str) -> Optional[str]:
    url = f"https://www.youtube.com/watch?v={video_id}"

    cookies_path = "/app/cookies.txt"
    use_cookies = os.path.isfile(cookies_path) and os.path.getsize(cookies_path) > 10

    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "hi"],
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {"youtube": {"player_client": ["web", "ios", "android"]}},
        "socket_timeout": 15,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    if use_cookies:
        ydl_opts["cookiefile"] = cookies_path
        print(f"[Transcript] Strategy 3 (yt-dlp): Using cookies.txt for auth ({os.path.getsize(cookies_path)} bytes)")
    else:
        print(f"[Transcript] Strategy 3 (yt-dlp): No cookies.txt found, trying without auth")

    # Retry up to 2 times with backoff
    for attempt in range(1, 3):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                all_subs = {**(info.get("subtitles") or {}), **(info.get("automatic_captions") or {})}
                if not all_subs:
                    print(f"[Transcript] Strategy 3 (yt-dlp) attempt {attempt}: No subtitles found")
                    break
                chosen_lang = next((l for l in ["en", "en-US", "hi"] if l in all_subs), list(all_subs.keys())[0])
                formats = all_subs[chosen_lang]
                sub_url = next((f.get("url") for f in formats if f.get("ext") in ["json3", "vtt", "srv1"]), None)
                if not sub_url and formats:
                    sub_url = formats[0].get("url")
                if not sub_url:
                    break
                resp = requests.get(sub_url, headers={"User-Agent": "com.google.ios.youtube/19.29.1"}, timeout=10)
                content = resp.text
                snippets = []
                try:
                    jdata = json.loads(content)
                    for ev in jdata.get("events", []):
                        for s in ev.get("segs", []):
                            t = _clean_text(s.get("utf8", ""))
                            if t:
                                snippets.append(t)
                except Exception:
                    for line in content.splitlines():
                        c = _clean_text(line)
                        if c and not c.isdigit() and "-->" not in c and not c.startswith("WEBVTT"):
                            snippets.append(c)
                text = " ".join(snippets).strip()
                if text:
                    print(f"[Transcript] Strategy 3 (yt-dlp+OAuth) SUCCESS on attempt {attempt}: {len(text)} chars")
                    return text
        except Exception as e:
            print(f"[Transcript] Strategy 3 (yt-dlp) attempt {attempt} failed: {e}")
            if attempt < 2:
                time.sleep(2)
    return None


# ──────────────────────────────────────────────
# 4.  Main Transcript Tool
# ──────────────────────────────────────────────

@tool
def fetch_transcript_tool(url: str) -> str:
    """Multi-strategy YouTube transcript fetcher robust to AWS IP blocks."""
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL or Video ID: {url}")

    print(f"\n[Transcript] Fetching for Video ID: {video_id}")

    # ── Strategy 1: pytubefix (PO token generator & client rotation) ────────────
    text, title, uploader, description = _fetch_via_pytubefix(video_id)
    title_header = (
        f"VIDEO TITLE: {title}\nSPEAKER / CHANNEL: {uploader}\n"
        if title else f"VIDEO ID: {video_id}\n"
    )
    if text:
        return f"{title_header}\nTRANSCRIPT:\n{text}"

    # ── Strategy 2: youtube-transcript-api ──────────────────────────────────
    text = _fetch_via_transcript_api(video_id)
    if text:
        return f"{title_header}\nTRANSCRIPT:\n{text}"

    # ── Strategy 3: yt-dlp ──────────────────────────────────────────────────
    text = _fetch_via_ytdlp(video_id)
    if text:
        return f"{title_header}\nTRANSCRIPT:\n{text}"

    # ── Strategy 4: Metadata fallback ───────────────────────────────────────
    print(f"[Transcript] ALL strategies failed for {video_id}. Using metadata.")
    desc_excerpt = (description or "")[:2000]
    return (
        f"{title_header}\n"
        f"NOTE: Live transcript unavailable (YouTube bot-detection on server IP).\n"
        f"Generate notes strictly based on the VIDEO TITLE and DESCRIPTION below:\n"
        f"VIDEO DESCRIPTION:\n{desc_excerpt}"
    )


# ──────────────────────────────────────────────
# 5.  LCEL Notes Chain
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
        f"\nSPECIAL USER INSTRUCTIONS: {instructions.strip()}\n"
        if instructions and instructions.strip() else ""
    )
    prompt = PromptTemplate(
        input_variables=["transcript"],
        template=_NOTES_TEMPLATE + extra,
    )
    return prompt | llm.with_structured_output(NotesOutput)


# ──────────────────────────────────────────────
# 6.  LangGraph Nodes
# ──────────────────────────────────────────────

MAX_TRANSCRIPT_LENGTH = 12000

def fetch_transcript_node(state: NotesState) -> NotesState:
    """Node 1: fetch video transcript with safe dynamic truncation."""
    try:
        raw = fetch_transcript_tool.invoke({"url": state["url"]})

        print(f"\n{'='*60}")
        print(f"[DEBUG] Transcript fetched: {len(raw)} characters")
        print(f"[DEBUG] First 300 chars:\n{raw[:300]}")
        print(f"{'='*60}\n")

        if len(raw) <= MAX_TRANSCRIPT_LENGTH:
            return {**state, "transcript": raw, "error": None}

        # Dynamic header/body split
        lines = raw.split('\n')
        header_lines, body_start = [], 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if any(k in stripped for k in ['VIDEO TITLE:', 'SPEAKER / CHANNEL:', 'VIDEO ID:', 'DESCRIPTION:']):
                header_lines.append(line)
                body_start = i + 1
            elif stripped in ['TRANSCRIPT:', 'FULL VERBATIM TRANSCRIPT:']:
                header_lines.append(line)
                body_start = i + 1
                break
            elif i >= 10:
                break

        header_str = '\n'.join(header_lines)
        body = '\n'.join(lines[body_start:]).strip() or raw

        budget = max(1000, MAX_TRANSCRIPT_LENGTH - len(header_str) - 150)
        truncated = body[:budget]
        cut = max(0, len(body) - len(truncated))

        print(f"⚠️  Truncation: kept {len(truncated)} chars, cut {cut} from end")

        final = (
            (header_str + "\n\n" if header_str else "")
            + truncated
            + (f"\n\n[...{cut} chars truncated...]" if cut > 0 else "")
        )
        return {**state, "transcript": final, "error": None}
    except Exception as e:
        return {**state, "transcript": "", "error": f"Transcript error: {e}"}


def generate_notes_node(state: NotesState) -> NotesState:
    if state.get("error"):
        return state
    try:
        chain = build_notes_chain(instructions=state.get("instructions", ""))
        notes: NotesOutput = chain.invoke({"transcript": state["transcript"]})
        return {**state, "notes": notes, "error": None}
    except Exception as e:
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
# 7.  Build & Compile the LangGraph
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
