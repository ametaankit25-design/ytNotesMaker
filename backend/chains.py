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
import html
import urllib.parse
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


def _clean_text(text: str) -> str:
    """Remove HTML tags and decode HTML entities."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


# ── Strategy 1: YouTubeTranscriptApi (most reliable, no yt-dlp needed) ──────────
def _fetch_via_transcript_api(video_id: str) -> Optional[str]:
    """
    Use youtube-transcript-api to directly fetch subtitles.
    Works best from non-datacenter IPs but try anyway.
    """
    try:
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'en-GB', 'hi', 'hi-IN'])
        text = " ".join(_clean_text(entry['text']) for entry in data)
        if text.strip():
            print(f"[Transcript] Strategy 1 (TranscriptAPI) SUCCESS: {len(text)} chars")
            return text
    except Exception as e:
        print(f"[Transcript] Strategy 1 (TranscriptAPI) failed: {e}")
    return None


# ── Strategy 2: YouTube timedtext API (direct HTTP, no library needed) ───────────
def _fetch_via_timedtext(video_id: str) -> Optional[str]:
    """
    Fetch captions directly from YouTube's timedtext endpoint using the
    video's page-embedded caption track URL. Works even when libraries fail.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        resp = requests.get(watch_url, headers=headers, timeout=15)
        page = resp.text

        # Extract captions JSON blob from page source
        caption_match = re.search(r'"captionTracks":(\[.*?\])', page)
        if not caption_match:
            print(f"[Transcript] Strategy 2 (timedtext): No captionTracks found in page")
            return None

        caption_tracks = json.loads(caption_match.group(1))
        if not caption_tracks:
            return None

        # Prefer English, fall back to first available track
        chosen_url = None
        for track in caption_tracks:
            lang = track.get('languageCode', '')
            if lang.startswith('en'):
                chosen_url = track.get('baseUrl')
                break
        if not chosen_url:
            chosen_url = caption_tracks[0].get('baseUrl')

        if not chosen_url:
            return None

        # Fetch the caption XML
        cap_resp = requests.get(chosen_url, headers=headers, timeout=10)
        cap_xml = cap_resp.text

        root = ET.fromstring(cap_xml)
        snippets = []
        for elem in root.iter('text'):
            t = _clean_text(elem.text or '')
            if t:
                snippets.append(t)

        text = " ".join(snippets)
        if text.strip():
            print(f"[Transcript] Strategy 2 (timedtext) SUCCESS: {len(text)} chars")
            return text

    except Exception as e:
        print(f"[Transcript] Strategy 2 (timedtext) failed: {e}")
    return None


# ── Strategy 3: yt-dlp with client spoofing ────────────────────────────────────
def _fetch_via_ytdlp(video_id: str) -> tuple[Optional[str], str, str, str]:
    """
    Use yt-dlp with Android/iOS client spoofing. Returns (transcript, title, uploader, description).
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'en-US', 'en-GB', 'hi', 'hi-IN'],
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
            }
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', '') or ''
            uploader = info.get('uploader', '') or ''
            description = info.get('description', '') or ''

            subtitles = info.get('subtitles') or {}
            auto_subs = info.get('automatic_captions') or {}
            all_subs = {**subtitles, **auto_subs}

            if not all_subs:
                print(f"[Transcript] Strategy 3 (yt-dlp): No subtitles found")
                return None, title, uploader, description

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
                return None, title, uploader, description

            resp = requests.get(sub_url, headers={
                "User-Agent": "Mozilla/5.0 (Android 14; Mobile; rv:120.0) Gecko/120.0 Firefox/120.0"
            }, timeout=10)
            content = resp.text

            snippets = []
            if 'json3' in (sub_url or '') or content.strip().startswith('{'):
                try:
                    data = json.loads(content)
                    for ev in data.get('events', []):
                        for s in ev.get('segs', []):
                            t = _clean_text(s.get('utf8', ''))
                            if t:
                                snippets.append(t)
                except Exception:
                    pass

            if not snippets:
                lines = content.splitlines()
                for line in lines:
                    cleaned = _clean_text(line)
                    if (cleaned and not cleaned.isdigit() and
                            '-->' not in cleaned and
                            not cleaned.startswith('WEBVTT')):
                        snippets.append(cleaned)

            text = " ".join(snippets)
            if text.strip():
                print(f"[Transcript] Strategy 3 (yt-dlp) SUCCESS: {len(text)} chars")
                return text, title, uploader, description

    except Exception as e:
        print(f"[Transcript] Strategy 3 (yt-dlp) failed: {e}")

    return None, '', '', ''


# ── Strategy 4: video metadata via yt-dlp (title + description only) ─────────────
def _fetch_metadata_only(video_id: str) -> tuple[str, str, str]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {'skip_download': True, 'quiet': True, 'no_warnings': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return (info.get('title', ''), info.get('uploader', ''), info.get('description', ''))
    except Exception:
        return ('', '', '')


@tool
def fetch_transcript_tool(url: str) -> str:
    """
    Multi-strategy YouTube transcript fetcher. Tries 3 strategies before
    falling back to metadata-only note generation.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL or Video ID: {url}")

    print(f"\n[Transcript] Fetching transcript for Video ID: {video_id}")

    # Fetch title/uploader via yt-dlp regardless (needed for all strategies)
    title, uploader, description = '', '', ''
    try:
        title, uploader, description = _fetch_metadata_only(video_id)
    except Exception:
        pass

    title_header = f"VIDEO TITLE: {title}\nSPEAKER / CHANNEL: {uploader}\n" if title else f"VIDEO ID: {video_id}\n"

    # ── Strategy 1: youtube-transcript-api ──────────────────────────────────
    text = _fetch_via_transcript_api(video_id)
    if text:
        return f"{title_header}\nTRANSCRIPT:\n{text}"

    # ── Strategy 2: timedtext direct HTTP ───────────────────────────────────
    text = _fetch_via_timedtext(video_id)
    if text:
        return f"{title_header}\nTRANSCRIPT:\n{text}"

    # ── Strategy 3: yt-dlp with client spoofing ──────────────────────────────
    text, t, u, d = _fetch_via_ytdlp(video_id)
    if text:
        if t:
            title_header = f"VIDEO TITLE: {t}\nSPEAKER / CHANNEL: {u}\n"
        return f"{title_header}\nTRANSCRIPT:\n{text}"

    # ── Strategy 4: Metadata fallback ───────────────────────────────────────
    print(f"[Transcript] ALL strategies failed for {video_id}. Using metadata fallback.")
    desc_excerpt = (description or d or '')[:2000]
    return (
        f"{title_header}\n"
        f"NOTE: Live transcript could not be fetched (possibly blocked by YouTube for server IPs).\n"
        f"Please generate structured study notes based ONLY on the video title and description below.\n"
        f"VIDEO DESCRIPTION:\n{desc_excerpt}"
    )


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

MAX_TRANSCRIPT_LENGTH = 12000  # ~3000 tokens for context limit

def fetch_transcript_node(state: NotesState) -> NotesState:
    """Node 1: fetch exact video transcript from YouTube with safe dynamic truncation."""
    try:
        raw_transcript = fetch_transcript_tool.invoke({"url": state["url"]})

        print(f"\n{'='*60}")
        print(f"[DEBUG] Transcript fetched: {len(raw_transcript)} characters")
        print(f"[DEBUG] First 300 chars:\n{raw_transcript[:300]}")
        print(f"{'='*60}\n")

        if len(raw_transcript) <= MAX_TRANSCRIPT_LENGTH:
            return {**state, "transcript": raw_transcript, "error": None}

        # --- Dynamic Header vs Body Separation ---
        lines = raw_transcript.split('\n')
        header_lines = []
        body_start_index = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if any(k in stripped for k in ['VIDEO TITLE:', 'SPEAKER / CHANNEL:', 'TRANSCRIPT LANGUAGE:', 'VIDEO ID:', 'DESCRIPTION:']):
                header_lines.append(line)
                body_start_index = i + 1
            elif stripped in ['TRANSCRIPT:', 'FULL VERBATIM TRANSCRIPT:']:
                header_lines.append(line)
                body_start_index = i + 1
                break
            elif i >= 10:
                break

        header_str = '\n'.join(header_lines) if header_lines else ""
        transcript_body = '\n'.join(lines[body_start_index:]).strip()

        if not transcript_body:
            transcript_body = raw_transcript
            header_str = ""

        header_len = len(header_str)
        available_body_budget = max(1000, MAX_TRANSCRIPT_LENGTH - header_len - 150)
        truncated_body = transcript_body[:available_body_budget]
        cut_chars = max(0, len(transcript_body) - len(truncated_body))

        print(f"⚠️  [Transcript Node] Truncation Applied:")
        print(f"    - Kept header: {header_len} chars")
        print(f"    - Kept body:   {len(truncated_body)} chars")
        print(f"    - Cut off:     {cut_chars} chars from end")

        final_transcript = (
            (header_str + "\n\n" if header_str else "")
            + truncated_body
            + (f"\n\n[...transcript truncated ({cut_chars} chars cut)...]" if cut_chars > 0 else "")
        )

        return {**state, "transcript": final_transcript, "error": None}
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
