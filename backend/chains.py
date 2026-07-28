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
import threading
import tempfile
import shutil
from http.cookiejar import MozillaCookieJar
from typing import TypedDict, Optional
import requests
import yt_dlp

# Fix SSL certificate verification on Windows / corporate proxies
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

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

# Rate limiting and cookie management
class RequestRateLimiter:
    """Simple rate limiter to prevent YouTube from blocking requests."""
    def __init__(self, min_delay: float = 2.0):
        self.min_delay = min_delay
        self.last_request_time = 0
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait if the minimum delay hasn't passed since the last request."""
        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_delay:
                sleep_time = self.min_delay - time_since_last
                print(f"[RateLimiter] Sleeping for {sleep_time:.2f}s to avoid rate limiting")
                time.sleep(sleep_time)
            self.last_request_time = time.time()

# Global rate limiter instance - AWS EC2: Increased delay to avoid detection
_rate_limiter = RequestRateLimiter(min_delay=3.0)

# Cookie refresh management
class CookieManager:
    """Manages cookie refresh and rotation to avoid stale cookies."""
    def __init__(self):
        self.cookie_refresh_interval = 1800  # Refresh cookies every 30 minutes (reduced from 1 hour)
        self.last_refresh_time = 0
        self.lock = threading.Lock()
        self.current_cookie_path = None
        self.cookie_validation_cache = {}  # Cache validation results
    
    def validate_cookies(self, cookies_path: str) -> bool:
        """Check if cookies are valid by testing with a simple YouTube request."""
        if cookies_path in self.cookie_validation_cache:
            cached_result, cached_time = self.cookie_validation_cache[cookies_path]
            # Cache validation for 5 minutes
            if time.time() - cached_time < 300:
                return cached_result
        
        try:
            import requests
            session = requests.Session()
            try:
                jar = MozillaCookieJar(cookies_path)
                jar.load(ignore_discard=True, ignore_expires=True)
                session.cookies = jar
            except Exception as e:
                print(f"[CookieManager] Failed to load cookies for validation: {e}")
                self.cookie_validation_cache[cookies_path] = (False, time.time())
                return False
            
            # Test with a simple YouTube page request
            test_url = "https://www.youtube.com"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
            
            try:
                response = session.get(test_url, headers=headers, timeout=10, allow_redirects=True)
                is_valid = response.status_code == 200 and "Sign in" not in response.text
                self.cookie_validation_cache[cookies_path] = (is_valid, time.time())
                print(f"[CookieManager] Cookie validation: {'VALID' if is_valid else 'INVALID'}")
                return is_valid
            except Exception as e:
                print(f"[CookieManager] Cookie validation request failed: {e}")
                self.cookie_validation_cache[cookies_path] = (False, time.time())
                return False
                
        except Exception as e:
            print(f"[CookieManager] Cookie validation error: {e}")
            return False
    
    def get_cookies_path(self) -> Optional[str]:
        """Get a fresh cookie path, refreshing if needed."""
        with self.lock:
            current_time = time.time()
            time_since_refresh = current_time - self.last_refresh_time
            
            # Refresh cookies if interval has passed
            if time_since_refresh > self.cookie_refresh_interval or self.current_cookie_path is None:
                new_cookies_path = _resolve_cookies_path()
                
                # Validate new cookies if available
                if new_cookies_path:
                    if self.validate_cookies(new_cookies_path):
                        self.current_cookie_path = new_cookies_path
                        self.last_refresh_time = current_time
                        print(f"[CookieManager] Refreshed and validated cookies")
                    else:
                        print(f"[CookieManager] Cookies expired or invalid, using without cookies")
                        self.current_cookie_path = None  # Force use of no-cookies strategies
                        self.last_refresh_time = current_time
                else:
                    self.current_cookie_path = None
                    self.last_refresh_time = current_time
            
            return self.current_cookie_path
    
    def force_refresh(self):
        """Force cookie refresh on next request."""
        with self.lock:
            self.current_cookie_path = None
            self.last_refresh_time = 0
            self.cookie_validation_cache = {}  # Clear validation cache
            print("[CookieManager] Forced cookie refresh")

# Global cookie manager instance
_cookie_manager = CookieManager()

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


def _resolve_cookies_path() -> Optional[str]:
    """Locate cookies.txt for YouTube auth (Docker, project root, or env override).

    Returns a *writable* copy under /tmp when the source is read-only
    (docker :ro mounts) — yt-dlp updates the cookie file and fails with Errno 30 otherwise.
    """
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(backend_dir)
    candidates = [
        os.environ.get("YT_COOKIES_PATH"),
        "/app/cookies.txt",
        os.path.join(project_root, "cookies.txt"),
        os.path.join(backend_dir, "cookies.txt"),
    ]
    src = None
    for path in candidates:
        if path and os.path.isfile(path) and os.path.getsize(path) > 10:
            src = path
            break
    if not src:
        return None

    # Always copy to a writable temp file so yt-dlp can refresh cookies.
    # Use a unique temp cookie path per request to avoid concurrent write/race
    # issues and stale shared cookie state when EC2 handles multiple fetches.
    fd, dest = tempfile.mkstemp(prefix="ytnotes_cookies_", suffix=".txt", dir=tempfile.gettempdir())
    os.close(fd)
    try:
        shutil.copy2(src, dest)
        os.chmod(dest, 0o600)
        return dest
    except Exception as e:
        print(f"[Transcript] Could not copy cookies to writable path: {e}")
        try:
            os.unlink(dest)
        except Exception:
            pass
        return src


def _build_youtube_session() -> requests.Session:
    """HTTP session with browser-like headers and optional Netscape cookies."""
    session = requests.Session()
    
    # Rotate user agents to avoid 403 errors
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    
    import random
    session.headers.update({
        "User-Agent": random.choice(user_agents),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    
    try:
        import certifi
        session.verify = certifi.where()
    except ImportError:
        pass
    
    # Use cookie manager for fresh cookies
    cookies_path = _cookie_manager.get_cookies_path()
    if cookies_path:
        try:
            jar = MozillaCookieJar(cookies_path)
            jar.load(ignore_discard=True, ignore_expires=True)
            session.cookies = jar
            print(f"[Transcript] Loaded cookies from {cookies_path}")
        except Exception as e:
            print(f"[Transcript] Could not load cookies ({cookies_path}): {e}")
            # Force refresh on next attempt if current cookies fail
            _cookie_manager.force_refresh()
        finally:
            # Clean up per-request temp cookies files created by _resolve_cookies_path.
            if os.path.basename(cookies_path).startswith("ytnotes_cookies_"):
                try:
                    os.unlink(cookies_path)
                except Exception:
                    pass
    return session


def _extract_json_value(html_text: str, key: str) -> Optional[str]:
    """Extract a JSON object or array value for a given key from embedded page JSON."""
    marker = f'"{key}":'
    idx = html_text.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker)
    while start < len(html_text) and html_text[start] in " \t\n":
        start += 1
    if start >= len(html_text) or html_text[start] not in "[{":
        return None
    open_ch, close_ch = ("[", "]") if html_text[start] == "[" else ("{", "}")
    dept
    h = 0
    for i in range(start, len(html_text)):
        ch = html_text[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return html_text[start : i + 1]
    return None


def _extract_json_array(html_text: str, key: str) -> Optional[str]:
    """Extract a JSON array value for a given key from embedded page JSON."""
    value = _extract_json_value(html_text, key)
    return value if value and value.startswith("[") else None


def _parse_page_metadata(html_text: str) -> tuple[str, str]:
    """Extract video title and channel from watch-page HTML."""
    title = uploader = ""
    player_json = _extract_json_value(html_text, "videoDetails")
    if player_json:
        try:
            vd = json.loads(player_json)
            if isinstance(vd, dict):
                title = vd.get("title", "") or title
                uploader = vd.get("author", "") or uploader
        except Exception:
            pass
    if not title:
        m = re.search(r'<meta\s+name="title"\s+content="([^"]+)"', html_text)
        if m:
            title = html.unescape(m.group(1))
    if not uploader:
        m = re.search(r'<link\s+itemprop="name"\s+content="([^"]+)"', html_text)
        if m:
            uploader = html.unescape(m.group(1))
    return title, uploader


def _parse_json3_captions(content: str) -> str:
    """Turn json3 / vtt caption payloads into plain transcript text."""
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
    return " ".join(snippets).strip()


# ──────────────────────────────────────────────
# 3.  Transcript Strategies
# ──────────────────────────────────────────────

# ── Strategy 1: pytubefix (PO-token-aware client rotation) ────────────────────────
def _fetch_via_pytubefix(video_id: str) -> tuple[Optional[str], str, str, str]:
    """
    Uses pytubefix with clients that avoid PO-token requirements first, then
    falls back to token-capable clients. Returns (transcript, title, uploader, description).
    """
    # Apply rate limiting
    _rate_limiter.wait_if_needed()
    
    title = uploader = description = ""
    url = f"https://www.youtube.com/watch?v={video_id}"

    # PO-token-free clients first, then fallbacks (per yt-dlp wiki).
    for client_type in ["ANDROID_VR", "TV", "TV_EMBED", "WEB_EMBED", "MWEB", "WEB_SAFARI", "IOS", "ANDROID", "WEB"]:
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


# ── Strategy 2: captionTracks scrape (no player API / PO token) ───────────────────
def _fetch_via_caption_tracks(video_id: str) -> tuple[Optional[str], str, str]:
    """
    Scrape captionTracks from the public watch page. Avoids yt-dlp player API and
    PO-token requirements, so it works on datacenter IPs when the page loads.
    Returns (transcript, title, uploader).
    """
    # Apply rate limiting
    _rate_limiter.wait_if_needed()
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    session = _build_youtube_session()
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"[Transcript] Strategy 2 (captionTracks) page fetch failed: {e}")
        return None, "", ""

    title, uploader = _parse_page_metadata(resp.text)
    tracks_json = _extract_json_array(resp.text, "captionTracks")
    if not tracks_json:
        print(f"[Transcript] Strategy 2 (captionTracks): No captionTracks in page for {video_id}")
        return None, title, uploader

    try:
        tracks = json.loads(tracks_json)
    except Exception as e:
        print(f"[Transcript] Strategy 2 (captionTracks): JSON parse error: {e}")
        return None, title, uploader

    preferred_langs = ["en", "en-US", "en-GB", "hi", "hi-IN"]
    chosen = None
    for lang in preferred_langs:
        chosen = next((t for t in tracks if t.get("languageCode") == lang), None)
        if chosen:
            break
    if not chosen and tracks:
        chosen = tracks[0]

    if not chosen or not chosen.get("baseUrl"):
        return None, title, uploader

    cap_url = chosen["baseUrl"]
    if "fmt=" not in cap_url:
        cap_url += "&fmt=json3"

    try:
        cap_resp = session.get(cap_url, timeout=15)
        cap_resp.raise_for_status()
        text = _parse_json3_captions(cap_resp.text)
        if text:
            lang = chosen.get("languageCode", "?")
            print(f"[Transcript] Strategy 2 (captionTracks) SUCCESS: {len(text)} chars, lang={lang}")
            return text, title, uploader
    except Exception as e:
        print(f"[Transcript] Strategy 2 (captionTracks) caption download failed: {e}")

    return None, title, uploader


# ── Strategy 3: youtube-transcript-api v1.x ───────────────────────────────────────
def _fetch_via_transcript_api(video_id: str) -> Optional[str]:
    """
    Uses the v1.x API pattern: YouTubeTranscriptApi().fetch(video_id, languages=[...])
    Returns transcript text joined from .snippets (not the old .get_transcript dict format).
    """
    # Apply rate limiting
    _rate_limiter.wait_if_needed()
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt_api = YouTubeTranscriptApi(http_client=_build_youtube_session())

        for langs in [["en"], ["en-US"], ["en-GB"], ["hi"], ["hi-IN"]]:
            try:
                transcript = ytt_api.fetch(video_id, languages=langs)
                text = " ".join(_clean_text(snippet.text) for snippet in transcript.snippets)
                if text.strip():
                    print(f"[Transcript] Strategy 3 (TranscriptAPI) SUCCESS: {len(text)} chars, lang={langs[0]}")
                    return text
            except Exception:
                continue

        print("[Transcript] Strategy 3 (TranscriptAPI): No transcript found in any language")
    except Exception as e:
        print(f"[Transcript] Strategy 3 (TranscriptAPI) failed: {e}")
    return None


# ── Strategy 4: yt-dlp with cookies + PO-token-free client rotation ───────────────
def _fetch_via_ytdlp(video_id: str) -> Optional[str]:
    import glob
    import shutil
    import tempfile

    # Apply rate limiting before making requests
    _rate_limiter.wait_if_needed()

    url = f"https://www.youtube.com/watch?v={video_id}"
    cookies_path = _cookie_manager.get_cookies_path()
    temp_cookies_path = cookies_path if cookies_path and os.path.basename(cookies_path).startswith("ytnotes_cookies_") else None

    # With cookies, prefer web clients (need account session for subs on DC IPs).
    # Without cookies, prefer PO-token-free clients.
    if cookies_path:
        # AWS EC2: Use TV/MWEB clients first - they work better with cookies on datacenter IPs
        rotations = [["tv_embedded"], ["mweb"], ["mediaconnect"], ["android_creator"], ["ios_music"], ["android_testsuite"]]
        try:
            print(f"[Transcript] Strategy 4 (yt-dlp): Using cookies ({os.path.getsize(cookies_path)} bytes)")
        except OSError:
            print("[Transcript] Strategy 4 (yt-dlp): Using cookies (path exists)")
    else:
        # AWS EC2: YouTube changed player - use only working clients (Jan 2026)
        # Avoid: web, web_safari, ios, android (they trigger player response errors)
        rotations = [["tv_embedded"], ["mweb"], ["mediaconnect"], ["android_testsuite"], ["android_vr"]]
        print("[Transcript] Strategy 4 (yt-dlp): Using working clients only (YouTube Jan 2026 changes)")

    def _read_sub_files(folder: str) -> Optional[str]:
        paths = sorted(glob.glob(os.path.join(folder, "*")))
        for path in paths:
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = _parse_json3_captions(f.read())
                if text and len(text) > 50:
                    return text
            except Exception:
                continue
        return None

    for attempt, clients in enumerate(rotations, start=1):
        # AWS EC2: Increased delay between attempts to avoid aggressive rate limiting
        if attempt > 1:
            delay = min(5 + (attempt * 2), 15)  # Progressive backoff: 5s, 7s, 9s, 11s, 13s, 15s (max)
            print(f"[Transcript] Strategy 4: Waiting {delay}s before attempt {attempt}...")
            time.sleep(delay)
        
        tmp = tempfile.mkdtemp(prefix="ytnm_subs_")
        try:
            ydl_opts = {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                # Only English — wildcards like en.* trigger mass downloads → HTTP 429
                "subtitleslangs": ["en"],
                "subtitlesformat": "vtt",
                "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 45,  # AWS EC2: Increased timeout for slower connections
                "retries": 5,  # AWS EC2: More retries
                "fragment_retries": 5,
                "ignoreerrors": True,
                "ignore_no_formats_error": True,
                "nocheckcertificate": False,  # Keep certificate checks
                "prefer_insecure": False,
                
                # AWS EC2: Critical fix for "Failed to extract any player response" error (Jan 2026)
                "extractor_args": {
                    "youtube": {
                        "player_client": clients,
                        "skip": ["hls", "dash", "translated_subs"],  # Skip video formats completely
                        "player_skip": ["webpage"],  # Only skip webpage, keep configs for player
                        "max_comments": [0],  # Disable comments extraction
                    }
                },
                
                # AWS EC2: Real browser headers - critical for datacenter IPs
                "http_headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Sec-Ch-Ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Cache-Control": "max-age=0",
                },
                
                # AWS EC2: Bypass geo-restrictions
                "geo_bypass": True,
                "geo_bypass_country": "US",
                
                # AWS EC2: Force IPv4 (IPv6 can cause issues on some EC2 configs)
                "source_address": "0.0.0.0",
            }
            if cookies_path:
                ydl_opts["cookiefile"] = cookies_path

            info = None
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
            except Exception as e:
                # Subtitle files may already be on disk before a later language fails
                print(f"[Transcript] Strategy 4 (yt-dlp) attempt {attempt} ({clients}) warning: {e}")
                # If this looks like a cookie issue, force refresh and switch to no-cookies mode
                if "cookies" in str(e).lower() or "login" in str(e).lower() or "sign in" in str(e).lower():
                    print("[Transcript] Cookie authentication failed, switching to no-cookies mode")
                    _cookie_manager.force_refresh()
                    cookies_path = None  # Disable cookies for remaining attempts
                    # Switch to no-cookies client rotation for remaining attempts
                    if attempt < len(rotations):
                        rotations = [["tv_embedded", "tv"], ["mweb", "web_safari"], ["ios", "android"], ["web"]]

            text = _read_sub_files(tmp)
            if text:
                print(
                    f"[Transcript] Strategy 4 (yt-dlp) SUCCESS on attempt {attempt} "
                    f"({clients}) via file: {len(text)} chars"
                )
                return text

            if info:
                all_subs = {**(info.get("subtitles") or {}), **(info.get("automatic_captions") or {})}
                if all_subs:
                    chosen_lang = next(
                        (l for l in ["en", "en-US", "en-GB", "hi"] if l in all_subs),
                        list(all_subs.keys())[0],
                    )
                    formats = all_subs[chosen_lang]
                    sub_url = next(
                        (f.get("url") for f in formats if f.get("ext") in ["json3", "vtt", "srv1", "srv3"]),
                        None,
                    )
                    if not sub_url and formats:
                        sub_url = formats[0].get("url")
                    if sub_url:
                        session = _build_youtube_session()
                        cap_resp = session.get(sub_url, timeout=15)
                        cap_resp.raise_for_status()
                        text = _parse_json3_captions(cap_resp.text)
                        if text:
                            print(
                                f"[Transcript] Strategy 4 (yt-dlp) SUCCESS on attempt {attempt} "
                                f"({clients}) via URL: {len(text)} chars"
                            )
                            return text

            print(
                f"[Transcript] Strategy 4 (yt-dlp) attempt {attempt} ({clients}): "
                f"No subtitles (files in tmp: {os.listdir(tmp)})"
            )
        except Exception as e:
            err = str(e)
            print(f"[Transcript] Strategy 4 (yt-dlp) attempt {attempt} ({clients}) failed: {err}")
            if "bot" in err.lower() or "sign in" in err.lower():
                print("[Transcript] Hint: export browser cookies to cookies.txt (see DEPLOYMENT.md for EC2)")
                # Force cookie refresh on bot detection
                _cookie_manager.force_refresh()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            # Clean up temp cookies if we created them
            if temp_cookies_path and os.path.exists(temp_cookies_path):
                try:
                    os.unlink(temp_cookies_path)
                except Exception:
                    pass
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

    # ── Strategy 2: captionTracks scrape (bypasses yt-dlp player API / PO token) ─
    text, cap_title, cap_uploader = _fetch_via_caption_tracks(video_id)
    if cap_title and not title:
        title = cap_title
    if cap_uploader and not uploader:
        uploader = cap_uploader
    title_header = (
        f"VIDEO TITLE: {title}\nSPEAKER / CHANNEL: {uploader}\n"
        if title else f"VIDEO ID: {video_id}\n"
    )
    if text:
        return f"{title_header}\nTRANSCRIPT:\n{text}"

    # ── Strategy 3: youtube-transcript-api ──────────────────────────────────
    text = _fetch_via_transcript_api(video_id)
    if text:
        return f"{title_header}\nTRANSCRIPT:\n{text}"

    # ── Strategy 4: yt-dlp (PO-token-free client rotation) ─────────────────
    text = _fetch_via_ytdlp(video_id)
    if text:
        return f"{title_header}\nTRANSCRIPT:\n{text}"

    # ── Strategy 5: Metadata fallback ───────────────────────────────────────
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
You are an expert educator and technical note-taker. Your job is to convert a raw YouTube \
transcript into accurate, structured study notes — grounded STRICTLY in what the speaker \
actually said.

═══════════════════════════════
PRIMARY SOURCE OF TRUTH
═══════════════════════════════
The transcript and title under 'INPUT VIDEO CONTENT' below. If the transcript is noisy, \
auto-generated, or code-switches between Hindi/English (Hinglish), still extract the intended \
meaning — do not skip sections just because the phrasing is informal or broken.

═══════════════════════════════
RULES
═══════════════════════════════
1. TITLE: Use the video's exact stated topic/title. If no explicit title is given, infer a \
   precise one from the first 2-3 minutes of content — never a generic placeholder.

2. GROUNDING (STRICT): Every summary line, bullet, and flashcard must trace back to something \
   actually said or shown (explanation, code, example, step, claim). If the transcript doesn't \
   cover a sub-topic, do not fill the gap with generic textbook content.

3. ENRICHMENT (LIMITED): You may add a one-line definition/clarification for a technical term \
   the speaker uses but doesn't define — mark these clearly as "(clarification)" so they're never \
   confused with something the speaker said.

4. HANDLING GAPS: If the transcript is cut off, has missing audio, or a section is unintelligible, \
   note it explicitly (e.g. "[transcript unclear here]") instead of inventing content to bridge it.

5. CODE & STEPS: If the video shows code, commands, or a sequence of steps, preserve them verbatim \
   in order — don't paraphrase code, don't merge or reorder steps.

6. SUMMARY: 150-250 words, covering the video's core argument/goal, method, and outcome — written \
   so someone who hasn't watched it understands what it covers and why it matters.

7. BULLET POINTS: One bullet per major section/step, self-contained (understandable without reading \
   other bullets), action-oriented where the video is instructional.

8. KEY CONCEPTS & FLASHCARDS: Extract only terms the speaker explicitly defines or explains. Each \
   flashcard = {{"question": ..., "answer": ...}}, answer grounded in the video's own explanation, \
   not a textbook definition unless the video's explanation was themselves generic.

9. REASONING (INTERNAL): Before writing final output, silently map out the video's structure \
   (intro → sections → conclusion) so bullets/flashcards follow the video's actual flow. Do NOT \
   include this scratch reasoning in the output — only the final structured notes.

10. LANGUAGE: All output in clean, professional English regardless of spoken language in the video.

11. OUTPUT FORMAT: Return ONLY valid JSON matching this schema, no markdown fences, no preamble:
{{
  "title": "string",
  "summary": "string",
  "key_concepts": [{{"term": "string", "definition": "string"}}],
  "bullet_points": ["string", ...],
  "flashcards": [{{"question": "string", "answer": "string"}}]
}}

INPUT VIDEO CONTENT:
{transcript}
"""

def build_notes_chain(llm=None, instructions: str = ""):
    if llm is None:
        llm = llm_model()

    # Escape braces so user text can't inject PromptTemplate variables
    safe_instructions = (
        instructions.strip().replace("{", "{{").replace("}", "}}")
        if instructions and instructions.strip()
        else ""
    )
    extra = (
        f"\nSPECIAL USER INSTRUCTIONS: {safe_instructions}\n"
        if safe_instructions else ""
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
        from visual_context import temporary_keyframes

        url = state.get("url") or ""
        with temporary_keyframes(url) as frames:
            # Annotate with timestamp captions for the PDF grid
            keyed = [
                {
                    "timestamp": f["timestamp"],
                    "path": f["path"],
                    "caption": f"t = {int(f['timestamp']) // 60:02d}:{int(f['timestamp']) % 60:02d}",
                }
                for f in frames
            ]
            print(f"[PDF] Embedding {len(keyed)} video keyframes into PDFs")
            pdf_paths = generate_all_pdfs(state["notes"], keyframes=keyed)
        return {**state, "pdf_paths": pdf_paths, "error": None}
    except Exception as e:
        # Fallback: notes PDF without frames if extraction blows up mid-flight
        try:
            pdf_paths = generate_all_pdfs(state["notes"])
            return {**state, "pdf_paths": pdf_paths, "error": None}
        except Exception as e2:
            return {**state, "pdf_paths": {}, "error": f"PDF error: {e2} (frames: {e})"}


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
