"""Get text out of images and videos: OCR (tesseract) on images and video frames,
speech-to-text (faster-whisper, local CPU) on audio. All local, no tokens spent.

See CASES.md for which posts need this and why."""

import difflib
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

FRAME_EVERY_S = 2.0
MAX_FRAMES = 90
MAX_VIDEO_S = 600
MAX_IMAGES = 20
TRANSCRIPT_LIMIT = 6000
OCR_LIMIT = 5000

_whisper = None


def _clean_ocr(text: str) -> str:
    """Drop OCR noise: lines that are mostly symbols or too short to mean anything."""
    keep = []
    for line in text.splitlines():
        line = line.strip()
        alnum = sum(c.isalnum() for c in line)
        if alnum >= 3 and alnum / max(len(line.replace(" ", "")), 1) >= 0.6:
            keep.append(line)
    return "\n".join(keep)


def ocr(path: Path) -> str:
    if not shutil.which("tesseract"):
        return ""
    p = subprocess.run(["tesseract", str(path), "-", "-l", "eng"], capture_output=True, text=True, timeout=60)
    return _clean_ocr(p.stdout)


def _norm(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def dedupe_texts(texts: list[str], threshold: float = 0.8) -> list[str]:
    """Video frames repeat the same overlay for seconds at a time; keep each text once."""
    kept: list[str] = []
    normed: list[str] = []
    for t in texts:
        n = _norm(t)
        if not n or any(difflib.SequenceMatcher(None, n, k).ratio() > threshold for k in normed):
            continue
        kept.append(t)
        normed.append(n)
    return kept


def download(url: str, dest: Path) -> Path | None:
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as c:
            r = c.get(url)
            r.raise_for_status()
    except httpx.HTTPError as e:
        log.info("download failed %s: %s", url[:80], e)
        return None
    dest.write_bytes(r.content)
    return dest


def ocr_images(urls: list[str]) -> list[dict]:
    out = []
    with tempfile.TemporaryDirectory(prefix="postcontext-img-") as d:
        for i, u in enumerate(urls[:MAX_IMAGES]):
            p = download(u, Path(d) / f"{i}.jpg")
            text = ocr(p) if p else ""
            out.append({"index": i, "ocr": text})
    return out


def fetch_video(url: str, workdir: Path) -> Path | None:
    """Download a social video with yt-dlp (≤720p). Returns the mp4 path."""
    if not shutil.which("yt-dlp"):
        return None
    out = workdir / "v.mp4"
    try:
        p = subprocess.run(
            ["yt-dlp", "-q", "--no-warnings", "--no-playlist", "-f", "bv*[height<=720]+ba/b[height<=720]/b",
             "--merge-output-format", "mp4", "--match-filter", f"duration<{MAX_VIDEO_S}", "-o", str(out), url],
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return None
    if p.returncode != 0 or not out.exists():
        log.info("video download failed for %s: %s", url, p.stderr.strip()[-300:])
        return None
    return out


def duration(video: Path) -> float | None:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return None


def frame_texts(video: Path, workdir: Path) -> list[dict]:
    fdir = workdir / "frames"
    fdir.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps=1/{FRAME_EVERY_S},scale=960:-1",
                    "-frames:v", str(MAX_FRAMES), str(fdir / "%03d.png")], check=False, timeout=300)
    out, seen = [], []
    for i, f in enumerate(sorted(fdir.glob("*.png"))):
        text = ocr(f)
        if dedupe_texts(seen + [text]) == seen:  # empty or a repeat of an earlier frame
            continue
        seen.append(text)
        out.append({"t": round(i * FRAME_EVERY_S), "text": text})
    return out


def transcribe(video: Path, model_size: str = "small") -> dict:
    global _whisper
    import numpy as np
    from faster_whisper import WhisperModel

    # Decode with ffmpeg ourselves: faster-whisper's bundled PyAV path breaks on some versions.
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, timeout=300).stdout
    if not raw:
        return {"text": "", "language": None}
    if _whisper is None:
        _whisper = WhisperModel(model_size, device="cpu", compute_type="int8")
    segs, info = _whisper.transcribe(np.frombuffer(raw, np.float32), vad_filter=True)
    text = " ".join(s.text.strip() for s in segs)
    return {"text": text[:TRANSCRIPT_LIMIT], "language": info.language}


def analyze_video(url: str, model_size: str = "small") -> dict:
    """Everything we can read or hear in a video: on-screen text and speech."""
    with tempfile.TemporaryDirectory(prefix="postcontext-vid-") as d:
        work = Path(d)
        v = fetch_video(url, work)
        if not v:
            return {"error": "could not download video"}
        out: dict = {"duration_s": duration(v)}
        texts = frame_texts(v, work)
        joined = "\n".join(f"[{x['t']}s] {x['text']}" for x in texts)
        out["on_screen_text"] = joined[:OCR_LIMIT]
        try:
            out["transcript"] = transcribe(v, model_size)
        except Exception as e:  # noqa: BLE001 - transcription is best effort
            log.exception("transcription failed")
            out["transcript_error"] = repr(e)
        return out
