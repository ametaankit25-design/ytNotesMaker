"""
Video-context extraction for the ytNotesMaker RAG pipeline.

Pipeline:
  YouTube URL  →  yt-dlp|ffmpeg pipe  →  scene-change keyframes
               →  vision captions     →  timestamp-aligned merge with transcript

No full video file and no raw frame images are retained after the call returns
(or if an exception aborts mid-pipeline).
"""

from __future__ import annotations

import base64
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, Protocol, Sequence, TypedDict

import requests

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Config & types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class VisualContextConfig:
    """All tunables for the visual-context pipeline (no magic numbers elsewhere)."""

    # Video acquisition
    max_height: int = 360                    # 240–480 recommended
    cookies_path: Optional[str] = None       # Netscape cookies.txt for yt-dlp
    ytdlp_format: Optional[str] = None       # override format selector if set
    download_timeout_s: int = 300

    # Keyframe extraction
    scene_threshold: float = 0.4             # ffmpeg scene-change sensitivity (0–1)
    max_frames: int = 40                     # hard cap on vision-model calls
    frame_pattern: str = "kf_%05d.jpg"
    ffmpeg_timeout_s: int = 600

    # Vision captioning
    vision_model_name: str = "llava"
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    vision_timeout_s: int = 120
    vision_max_workers: int = 2              # parallel caption calls (keep low for local GPU)

    # Transcript ↔ visual alignment
    max_time_delta_s: float = 5.0            # max |t_frame − t_transcript| to attach

    # Empty-visual filter (case-insensitive substring match)
    empty_visual_markers: tuple[str, ...] = (
        "no meaningful visual content",
        "no meaningful visual",
        "talking head only",
        "webcam only",
    )


class TranscriptSegment(TypedDict):
    start_time: float
    text: str


class TimelineEntry(TypedDict):
    timestamp: float
    transcript_text: str
    visual_context: Optional[str]


class Keyframe(TypedDict):
    timestamp: float
    path: str


class VisionCaptioner(Protocol):
    """Swappable vision backend — implement `.caption(image_path) -> str`."""

    def caption(self, image_path: str) -> str: ...


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class VisualContextError(Exception):
    """Base error for this module."""


class VideoAcquisitionError(VisualContextError):
    """yt-dlp / stream setup failed (private, geo-block, format missing, etc.)."""


class KeyframeExtractionError(VisualContextError):
    """ffmpeg scene-detection / frame write failed."""


class VisionCaptionError(VisualContextError):
    """Vision model call failed for a frame."""


# ─────────────────────────────────────────────────────────────────────────────
# Vision backends
# ─────────────────────────────────────────────────────────────────────────────

_VISION_PROMPT = """\
You are analyzing a single keyframe from an educational YouTube video.

Instructions:
1. If there is visible source code, terminal output, or UI text: transcribe it VERBATIM.
2. If there is a diagram, slide, whiteboard, chart, or screenshot: describe it concisely
   (labels, arrows, relationships, what it illustrates).
3. If the frame is ONLY a talking-head / webcam / face with no slides, code, diagrams,
   or other instructional visuals, reply EXACTLY with:
   no meaningful visual content
4. Do not invent content that is not visible. Keep the reply under 120 words when describing.
"""


class OllamaVisionCaptioner:
    """Default captioner: Ollama multimodal models (llava / bakllava / etc.)."""

    def __init__(
        self,
        model_name: str = "llava",
        base_url: str = "http://localhost:11434",
        timeout_s: int = 120,
        prompt: str = _VISION_PROMPT,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.prompt = prompt

    def caption(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        payload = {
            "model": self.model_name,
            "prompt": self.prompt,
            "images": [b64],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout_s,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise VisionCaptionError(f"Ollama vision request failed: {e}") from e

        text = (data.get("response") or "").strip()
        if not text:
            raise VisionCaptionError("Ollama returned an empty caption")
        return text


class OpenAICompatibleVisionCaptioner:
    """
    Hosted vision API with an OpenAI-compatible chat/completions endpoint
    (OpenAI, Groq vision, local vLLM, etc.).
    """

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_s: int = 120,
        prompt: str = _VISION_PROMPT,
    ) -> None:
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.prompt = prompt

    def caption(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        ext = Path(image_path).suffix.lstrip(".").lower() or "jpeg"
        mime = "image/png" if ext == "png" else "image/jpeg"

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 400,
        }
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_s,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, IndexError, TypeError) as e:
            raise VisionCaptionError(f"Hosted vision request failed: {e}") from e

        if not text:
            raise VisionCaptionError("Hosted vision API returned an empty caption")
        return text


class CallableVisionCaptioner:
    """Adapter so any `fn(image_path: str) -> str` can be used as the captioner."""

    def __init__(self, fn: Callable[[str], str]) -> None:
        self._fn = fn

    def caption(self, image_path: str) -> str:
        try:
            text = self._fn(image_path)
        except Exception as e:
            raise VisionCaptionError(str(e)) from e
        if not text or not str(text).strip():
            raise VisionCaptionError("Callable captioner returned empty text")
        return str(text).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_SHOWINFO_PTS = re.compile(r"pts_time:([\d.]+)")
_EMPTY_RE_CACHE: dict[tuple[str, ...], re.Pattern[str]] = {}


def _require_binaries() -> None:
    for name in ("ffmpeg", "ffprobe", "yt-dlp"):
        # yt-dlp may be a Python module; prefer CLI if on PATH, else python -m yt_dlp
        if name == "yt-dlp":
            if shutil.which("yt-dlp") or shutil.which("yt_dlp"):
                continue
            try:
                import yt_dlp  # noqa: F401
            except ImportError as e:
                raise VideoAcquisitionError(
                    "yt-dlp is not installed. pip install yt-dlp"
                ) from e
            continue
        if not shutil.which(name):
            raise VisualContextError(
                f"Required binary '{name}' not found on PATH. Install ffmpeg/ffprobe."
            )


def _ytdlp_cmd() -> list[str]:
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    if shutil.which("yt_dlp"):
        return ["yt_dlp"]
    return [os.environ.get("PYTHON", "python"), "-m", "yt_dlp"]


def _format_selector(cfg: VisualContextConfig) -> str:
    if cfg.ytdlp_format:
        return cfg.ytdlp_format
    h = cfg.max_height
    # Prefer progressive mp4 in the 240–480 band; fall back upward then downward.
    return (
        f"best[height<={h}][ext=mp4]/"
        f"best[height<={h}]/"
        f"best[height<=480][ext=mp4]/"
        f"best[height<=480]/"
        f"worst[height>=240]/"
        f"best"
    )


def _resolve_cookies(cfg: VisualContextConfig) -> Optional[str]:
    if cfg.cookies_path and os.path.isfile(cfg.cookies_path):
        return cfg.cookies_path
    # Match chains.py lookup order so EC2 cookies.txt is reused automatically.
    candidates = [
        os.environ.get("YT_COOKIES_PATH"),
        "/app/cookies.txt",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies.txt"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt"),
    ]
    for path in candidates:
        if path and os.path.isfile(path) and os.path.getsize(path) > 10:
            return path
    return None


def _is_empty_visual(text: str, markers: Sequence[str]) -> bool:
    key = tuple(markers)
    if key not in _EMPTY_RE_CACHE:
        escaped = "|".join(re.escape(m) for m in markers)
        _EMPTY_RE_CACHE[key] = re.compile(escaped, re.IGNORECASE)
    return bool(_EMPTY_RE_CACHE[key].search(text))


def _farthest_point_sample(keyframes: list[Keyframe], max_frames: int) -> list[Keyframe]:
    """
    When scene detection yields too many frames, keep `max_frames` that maximize
    temporal spread (1-D farthest-point sampling). Preserves chronological order.
    """
    n = len(keyframes)
    if n <= max_frames:
        return keyframes

    times = [k["timestamp"] for k in keyframes]
    selected: set[int] = {0, n - 1}
    while len(selected) < max_frames:
        best_i, best_dist = -1, -1.0
        for i in range(n):
            if i in selected:
                continue
            dist = min(abs(times[i] - times[j]) for j in selected)
            if dist > best_dist:
                best_dist, best_i = dist, i
        if best_i < 0:
            break
        selected.add(best_i)

    return [keyframes[i] for i in sorted(selected)]


def _safe_unlink(path: str) -> None:
    try:
        if path and os.path.isfile(path):
            os.unlink(path)
    except OSError as e:
        logger.warning("Failed to delete frame %s: %s", path, e)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Video acquisition (stream URL / pipe, no full file on disk)
# ─────────────────────────────────────────────────────────────────────────────

def download_stream(url: str, cfg: VisualContextConfig) -> str:
    """
    Resolve a direct media URL for `url` via yt-dlp (no video file written to disk).

    Returns:
        A direct HTTPS media URL that ffmpeg can read.

    Raises:
        VideoAcquisitionError: private/geo-blocked/unavailable/format issues.
    """
    _require_binaries()
    fmt = _format_selector(cfg)
    cookies = _resolve_cookies(cfg)

    cmd = _ytdlp_cmd() + [
        "--no-playlist",
        "-f", fmt,
        "-g",                # print direct URL only
        "--no-warnings",
        url,
    ]
    if cookies:
        cmd[1:1] = ["--cookies", cookies]
        logger.info("download_stream: using cookies (%s)", cookies)

    logger.info("download_stream: resolving media URL (max_height=%s)", cfg.max_height)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=min(cfg.download_timeout_s, 120),
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise VideoAcquisitionError("yt-dlp timed out resolving the media URL") from e
    except FileNotFoundError as e:
        raise VideoAcquisitionError("yt-dlp executable not found") from e

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        lower = err.lower()
        if "private" in lower:
            raise VideoAcquisitionError(f"Video is private: {err}")
        if "geo" in lower or "not available in your country" in lower:
            raise VideoAcquisitionError(f"Video is geo-blocked: {err}")
        if "sign in" in lower or "bot" in lower:
            raise VideoAcquisitionError(
                f"YouTube bot-check blocked acquisition (upload cookies.txt): {err}"
            )
        raise VideoAcquisitionError(f"yt-dlp failed (code {proc.returncode}): {err}")

    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        raise VideoAcquisitionError("yt-dlp returned no media URL (format unavailable?)")

    # For separate A/V streams yt-dlp -g may print multiple lines; prefer first video URL.
    media_url = lines[0]
    logger.info("download_stream: resolved media URL (%d char)", len(media_url))
    return media_url


def _build_ytdlp_pipe_cmd(url: str, cfg: VisualContextConfig) -> list[str]:
    """yt-dlp command that streams bytes to stdout (no file on disk)."""
    cookies = _resolve_cookies(cfg)
    cmd = _ytdlp_cmd() + [
        "--no-playlist",
        "-f", _format_selector(cfg),
        "-o", "-",
        "--no-warnings",
        url,
    ]
    if cookies:
        # When invoking yt-dlp as a Python module, options must follow the module name.
        if len(cmd) >= 3 and cmd[0].endswith("python") and cmd[1] == "-m":
            cmd[3:3] = ["--cookies", cookies]
        else:
            cmd[1:1] = ["--cookies", cookies]
    return cmd


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Keyframe extraction (scene-change detection)
# ─────────────────────────────────────────────────────────────────────────────

def extract_keyframes(
    url: str,
    frames_dir: str,
    cfg: VisualContextConfig,
    media_url: Optional[str] = None,
) -> list[Keyframe]:
    """
    Extract scene-change keyframes via ffmpeg. Streams video through a yt-dlp → ffmpeg
    pipe so the full video is never written to disk. Frames are written only under
    `frames_dir` (caller must delete them).

    Args:
        url: YouTube watch URL (used for the pipe source).
        frames_dir: Temporary directory for JPEG frames.
        cfg: Pipeline config.
        media_url: Unused reserved arg (kept for API clarity / future direct-URL path).

    Returns:
        List of {timestamp, path} sorted by timestamp (length ≤ cfg.max_frames).

    Raises:
        KeyframeExtractionError: on ffmpeg failure or zero frames.
    """
    os.makedirs(frames_dir, exist_ok=True)
    out_pattern = os.path.join(frames_dir, cfg.frame_pattern)

    # select=scene-change; showinfo prints pts_time on stderr for timestamp capture.
    vf = (
        f"select='gt(scene,{cfg.scene_threshold})',"
        f"showinfo,"
        f"scale=-2:{cfg.max_height}"
    )

    if media_url is None:
        media_url = download_stream(url, cfg)

    ffmpeg = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "info",
        "-i", media_url,
        "-vf", vf,
        "-fps_mode", "vfr",
        "-q:v", "3",
        "-y",
        out_pattern,
    ]

    logger.info(
        "extract_keyframes: scene_threshold=%.2f max_frames=%d height=%d input=%s",
        cfg.scene_threshold, cfg.max_frames, cfg.max_height, media_url,
    )

    timestamps: list[float] = []

    try:
        proc = subprocess.run(
            ffmpeg,
            capture_output=True,
            timeout=cfg.ffmpeg_timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise KeyframeExtractionError(
            f"ffmpeg timed out after {cfg.ffmpeg_timeout_s}s"
        ) from e
    except FileNotFoundError as e:
        raise KeyframeExtractionError(f"Failed to spawn ffmpeg: {e}") from e

    err_text = (proc.stderr or b"").decode("utf-8", errors="replace")
    for m in _SHOWINFO_PTS.finditer(err_text):
        try:
            timestamps.append(float(m.group(1)))
        except ValueError:
            continue

    if proc.returncode not in (0, None) and not timestamps:
        raise KeyframeExtractionError(
            f"ffmpeg failed (code {proc.returncode}). "
            f"ffmpeg: {err_text[-800:]}"
        )

    # Collect written frames in order
    frame_paths = sorted(
        str(p) for p in Path(frames_dir).glob("kf_*.jpg") if p.is_file()
    )
    if not frame_paths:
        # Fallback: some builds write fewer showinfo lines — try fixed fps sampling once.
        logger.warning(
            "extract_keyframes: scene detection produced 0 frames; "
            "falling back to fps=1/30 sampling"
        )
        return _extract_keyframes_fps_fallback(url, frames_dir, cfg)

    # Align timestamps to frames (ffmpeg writes in showinfo order)
    if len(timestamps) < len(frame_paths):
        logger.warning(
            "extract_keyframes: fewer timestamps (%d) than frames (%d); "
            "estimating remaining times",
            len(timestamps), len(frame_paths),
        )
        last = timestamps[-1] if timestamps else 0.0
        while len(timestamps) < len(frame_paths):
            last += 1.0
            timestamps.append(last)
    timestamps = timestamps[: len(frame_paths)]

    keyframes: list[Keyframe] = [
        {"timestamp": t, "path": p}
        for t, p in zip(timestamps, frame_paths)
    ]
    keyframes.sort(key=lambda k: k["timestamp"])

    if len(keyframes) > cfg.max_frames:
        logger.info(
            "extract_keyframes: capping %d → %d via farthest-point sampling",
            len(keyframes), cfg.max_frames,
        )
        kept = _farthest_point_sample(keyframes, cfg.max_frames)
        keep_paths = {k["path"] for k in kept}
        for k in keyframes:
            if k["path"] not in keep_paths:
                _safe_unlink(k["path"])
        keyframes = kept

    logger.info("extract_keyframes: kept %d keyframes", len(keyframes))
    return keyframes


def _extract_keyframes_fps_fallback(
    url: str,
    frames_dir: str,
    cfg: VisualContextConfig,
) -> list[Keyframe]:
    """Sparse fixed-interval fallback when scene detection yields nothing."""
    out_pattern = os.path.join(frames_dir, cfg.frame_pattern)
    # ~1 frame / 30s, still capped later
    vf = f"fps=1/30,scale=-2:{cfg.max_height},showinfo"

    media_url = download_stream(url, cfg)

    ffmpeg = [
        "ffmpeg", "-hide_banner", "-loglevel", "info",
        "-i", media_url, "-vf", vf, "-fps_mode", "vfr", "-q:v", "3", "-y", out_pattern,
    ]

    try:
        proc = subprocess.run(
            ffmpeg,
            capture_output=True,
            timeout=cfg.ffmpeg_timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise KeyframeExtractionError(
            f"ffmpeg timed out after {cfg.ffmpeg_timeout_s}s"
        ) from e
    except FileNotFoundError as e:
        raise KeyframeExtractionError(f"Failed to spawn ffmpeg: {e}") from e

    err_text = (proc.stderr or b"").decode("utf-8", errors="replace")
    timestamps = [float(m.group(1)) for m in _SHOWINFO_PTS.finditer(err_text)]
    frame_paths = sorted(str(p) for p in Path(frames_dir).glob("kf_*.jpg") if p.is_file())
    if not frame_paths:
        raise KeyframeExtractionError(
            "No keyframes extracted (scene detection and fps fallback both empty). "
            f"ffmpeg stderr tail: {err_text[-600:]}"
        )

    while len(timestamps) < len(frame_paths):
        timestamps.append(float(len(timestamps) * 30))
    keyframes: list[Keyframe] = [
        {"timestamp": t, "path": p}
        for t, p in zip(timestamps[: len(frame_paths)], frame_paths)
    ]
    return _farthest_point_sample(keyframes, cfg.max_frames)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — Vision captioning
# ─────────────────────────────────────────────────────────────────────────────

def caption_frame(
    image_path: str,
    captioner: VisionCaptioner,
    cfg: VisualContextConfig,
) -> Optional[str]:
    """
    Caption one keyframe, then delete the image immediately.

    Returns:
        Caption text, or None if the model reports no meaningful visual content.

    Raises:
        VisionCaptionError: if the vision call fails (frame is still deleted).
    """
    try:
        text = captioner.caption(image_path).strip()
    finally:
        _safe_unlink(image_path)

    if _is_empty_visual(text, cfg.empty_visual_markers):
        logger.debug("caption_frame: empty visual discarded (%s)", image_path)
        return None
    return text


def caption_keyframes(
    keyframes: list[Keyframe],
    captioner: VisionCaptioner,
    cfg: VisualContextConfig,
) -> list[dict[str, Any]]:
    """
    Caption all keyframes (optionally in parallel). Each frame file is deleted
    as soon as its caption succeeds or fails.

    Returns:
        [{timestamp, description}, ...] for frames with meaningful visuals only.
    """
    results: list[dict[str, Any]] = []
    workers = max(1, min(cfg.vision_max_workers, len(keyframes) or 1))

    def _one(kf: Keyframe) -> Optional[dict[str, Any]]:
        try:
            desc = caption_frame(kf["path"], captioner, cfg)
        except VisionCaptionError as e:
            logger.warning(
                "caption_keyframes: vision failed @ %.2fs (%s); skipping frame",
                kf["timestamp"], e,
            )
            _safe_unlink(kf["path"])
            return None
        if desc is None:
            return None
        return {"timestamp": kf["timestamp"], "description": desc}

    logger.info("caption_keyframes: captioning %d frames (workers=%d)", len(keyframes), workers)
    if workers == 1:
        for kf in keyframes:
            item = _one(kf)
            if item:
                results.append(item)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_one, kf): kf for kf in keyframes}
            for fut in as_completed(futures):
                item = fut.result()
                if item:
                    results.append(item)

    results.sort(key=lambda x: x["timestamp"])
    logger.info("caption_keyframes: %d meaningful visuals retained", len(results))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — Transcript + visual merge
# ─────────────────────────────────────────────────────────────────────────────

def merge_timeline(
    transcript: Sequence[TranscriptSegment],
    visuals: Sequence[dict[str, Any]],
    cfg: VisualContextConfig,
) -> list[TimelineEntry]:
    """
    Align each meaningful visual to the nearest transcript segment by timestamp.

    Args:
        transcript: [{start_time, text}, ...] (already ordered preferred).
        visuals: [{timestamp, description}, ...] from caption_keyframes.
        cfg: uses max_time_delta_s.

    Returns:
        Ordered list of {timestamp, transcript_text, visual_context} covering
        every transcript segment. visual_context is set when a frame falls within
        max_time_delta_s of that segment (nearest wins; each visual used at most once).
    """
    if not transcript:
        # Still emit visual-only entries so RAG can index slide/code context alone.
        return [
            {
                "timestamp": float(v["timestamp"]),
                "transcript_text": "",
                "visual_context": str(v["description"]),
            }
            for v in sorted(visuals, key=lambda x: x["timestamp"])
        ]

    segs = sorted(transcript, key=lambda s: float(s["start_time"]))
    entries: list[TimelineEntry] = [
        {
            "timestamp": float(s["start_time"]),
            "transcript_text": s["text"],
            "visual_context": None,
        }
        for s in segs
    ]

    used_visuals: set[int] = set()
    for v_idx, vis in enumerate(sorted(visuals, key=lambda x: x["timestamp"])):
        t = float(vis["timestamp"])
        best_i, best_dt = -1, float("inf")
        for i, entry in enumerate(entries):
            dt = abs(entry["timestamp"] - t)
            if dt < best_dt:
                best_dt, best_i = dt, i
        if best_i < 0 or best_dt > cfg.max_time_delta_s:
            logger.debug(
                "merge_timeline: visual @ %.2fs has no transcript within %.1fs; appending",
                t, cfg.max_time_delta_s,
            )
            entries.append(
                {
                    "timestamp": t,
                    "transcript_text": "",
                    "visual_context": str(vis["description"]),
                }
            )
            used_visuals.add(v_idx)
            continue

        # Attach to nearest segment if empty; if occupied, keep closer visual.
        existing = entries[best_i]["visual_context"]
        if existing is None:
            entries[best_i]["visual_context"] = str(vis["description"])
            used_visuals.add(v_idx)
        else:
            # Prefer the visual closer to the segment timestamp.
            # (existing already attached; skip this one)
            logger.debug(
                "merge_timeline: segment @ %.2fs already has visual; skipping @ %.2fs",
                entries[best_i]["timestamp"], t,
            )

    entries.sort(key=lambda e: e["timestamp"])
    with_visual = sum(1 for e in entries if e["visual_context"])
    logger.info(
        "merge_timeline: %d entries (%d with visual_context)",
        len(entries), with_visual,
    )
    return entries


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# PDF helper — extract frames, keep files until caller finishes, then wipe
# ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def temporary_keyframes(
    url: str,
    cfg: Optional[VisualContextConfig] = None,
) -> Iterator[list[Keyframe]]:
    """
    Extract scene-change keyframes for embedding in PDFs.

    Yields a list of {timestamp, path}. Guarantees the temp directory (and all
    frame images) are deleted when the `with` block exits — even on errors.

    On extraction failure, yields an empty list (PDF generation can continue
    without images).
    """
    pdf_cfg = cfg or VisualContextConfig(
        max_height=360,
        scene_threshold=0.35,
        max_frames=int(os.getenv("YTNM_PDF_MAX_FRAMES", "8")),
        ffmpeg_timeout_s=int(os.getenv("YTNM_PDF_FFMPEG_TIMEOUT", "240")),
    )
    # Allow disabling on tiny hosts via env
    if os.getenv("YTNM_PDF_FRAMES", "1").strip() in ("0", "false", "False", "no"):
        yield []
        return

    frames_dir_obj = tempfile.TemporaryDirectory(prefix="ytnm_pdf_kf_")
    frames_dir = frames_dir_obj.name
    keyframes: list[Keyframe] = []
    try:
        try:
            _require_binaries()
            keyframes = extract_keyframes(url, frames_dir, pdf_cfg)
            logger.info("temporary_keyframes: extracted %d frames for PDF", len(keyframes))
        except Exception as e:
            logger.warning("temporary_keyframes: skipped (%s)", e)
            keyframes = []
        yield keyframes
    finally:
        for kf in keyframes:
            _safe_unlink(kf.get("path", ""))
        try:
            for p in Path(frames_dir).glob("*"):
                _safe_unlink(str(p))
        finally:
            frames_dir_obj.cleanup()


def build_visual_context(
    url: str,
    transcript: Sequence[TranscriptSegment],
    cfg: Optional[VisualContextConfig] = None,
    captioner: Optional[VisionCaptioner] = None,
) -> list[TimelineEntry]:
    """
    Run the full pipeline: stream → keyframes → caption → merge.

    Guarantees (via TemporaryDirectory + per-frame deletes) that no video file
    and no frame images survive past return / exception.

    Args:
        url: YouTube URL.
        transcript: list of {start_time, text}.
        cfg: optional config (defaults applied if omitted).
        captioner: optional VisionCaptioner (defaults to Ollama llava).

    Returns:
        Merged timeline ready for chunking / embedding.
    """
    cfg = cfg or VisualContextConfig()
    if captioner is None:
        captioner = OllamaVisionCaptioner(
            model_name=cfg.vision_model_name,
            base_url=cfg.ollama_base_url,
            timeout_s=cfg.vision_timeout_s,
        )

    _require_binaries()
    frames_dir_obj = tempfile.TemporaryDirectory(prefix="ytnm_frames_")
    frames_dir = frames_dir_obj.name

    try:
        # Resolve URL early to fail fast on private/geo videos before ffmpeg work.
        download_stream(url, cfg)

        keyframes = extract_keyframes(url, frames_dir, cfg)
        visuals = caption_keyframes(keyframes, captioner, cfg)
        timeline = merge_timeline(transcript, visuals, cfg)
        return timeline
    finally:
        # Wipe any leftover frames + the temp dir even on failure.
        try:
            for p in Path(frames_dir).glob("*"):
                _safe_unlink(str(p))
        finally:
            frames_dir_obj.cleanup()
            logger.info("build_visual_context: cleanup complete")


def timeline_to_documents(timeline: Sequence[TimelineEntry]) -> list[str]:
    """
    Convenience: turn timeline entries into plain-text chunks for FAISS/Chroma.

    Does not embed — only formats strings for a downstream indexer.
    """
    docs: list[str] = []
    for entry in timeline:
        ts = entry["timestamp"]
        mm, ss = divmod(int(ts), 60)
        header = f"[{mm:02d}:{ss:02d}]"
        parts = [header]
        if entry["transcript_text"]:
            parts.append(f"SPEECH: {entry['transcript_text']}")
        if entry["visual_context"]:
            parts.append(f"VISUAL: {entry['visual_context']}")
        if len(parts) > 1:
            docs.append("\n".join(parts))
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Usage example
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    example_url = "https://www.youtube.com/watch?v=rfscVS0vtbw"
    example_transcript: list[TranscriptSegment] = [
        {"start_time": 0.0, "text": "In this course, I'm going to teach you Python."},
        {"start_time": 12.5, "text": "Let's look at variables and data types."},
        {"start_time": 45.0, "text": "Here is a simple print statement example."},
        {"start_time": 90.0, "text": "Next we cover lists and loops."},
    ]

    config = VisualContextConfig(
        max_height=360,
        scene_threshold=0.4,
        max_frames=20,
        max_time_delta_s=5.0,
        vision_model_name="llava",
    )

    # Default: local Ollama llava. Swap for a hosted API like this:
    # captioner = OpenAICompatibleVisionCaptioner(
    #     model_name="gpt-4o-mini",
    #     api_key=os.environ["OPENAI_API_KEY"],
    # )

    print("Building visual context timeline…")
    t0 = time.time()
    try:
        merged = build_visual_context(
            url=example_url,
            transcript=example_transcript,
            cfg=config,
        )
    except VisualContextError as exc:
        print(f"Pipeline failed: {exc}")
        raise SystemExit(1) from exc

    print(f"Done in {time.time() - t0:.1f}s — {len(merged)} timeline entries\n")
    for row in merged[:8]:
        print(
            f"  t={row['timestamp']:7.2f}s | "
            f"speech={row['transcript_text'][:50]!r} | "
            f"visual={bool(row['visual_context'])}"
        )
    if any(r["visual_context"] for r in merged):
        print("\nSample VISUAL attachment:")
        for row in merged:
            if row["visual_context"]:
                print(f"  @{row['timestamp']:.1f}s → {row['visual_context'][:200]}")
                break

    docs = timeline_to_documents(merged)
    print(f"\nReady for RAG chunking: {len(docs)} text documents")
