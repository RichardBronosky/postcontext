"""Plain fetching for links that don't need a logged-in browser.

YouTube, SoundCloud, Bandcamp and friends go through yt-dlp, which returns
descriptions the HTML often hides. Everything else is fetched directly; the
OpenGraph tags and schema.org JSON-LD (ticket sites usually publish Event
objects) are the most useful parts."""

import json
import logging
import shutil
import subprocess
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

YTDLP_HOSTS = ("instagram.com", "tiktok.com", "youtube.com", "youtu.be", "x.com", "twitter.com",
               "facebook.com", "fb.watch", "threads.net", "threads.com", "soundcloud.com", "bandcamp.com")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TEXT_LIMIT = 6000
JSONLD_LIMIT = 6000


def host_matches(url: str, hosts) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in hosts)


def fetch_ytdlp(url: str) -> dict | None:
    if not shutil.which("yt-dlp"):
        return None
    try:
        p = subprocess.run(
            ["yt-dlp", "--dump-single-json", "--skip-download", "--no-warnings", "--no-playlist", url],
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        log.warning("yt-dlp timed out for %s", url)
        return None
    if p.returncode != 0:
        log.info("yt-dlp failed for %s: %s", url, p.stderr.strip()[-300:])
        return None
    d = json.loads(p.stdout)
    keep = ("title", "description", "uploader", "uploader_id", "channel", "creator", "artist", "track",
            "upload_date", "location", "tags", "webpage_url", "extractor")
    out = {k: d[k] for k in keep if d.get(k)}
    out["method"] = "yt-dlp"
    return out


def _jsonld(soup: BeautifulSoup) -> list:
    found = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for obj in data if isinstance(data, list) else [data]:
            if isinstance(obj, dict) and "@graph" in obj:
                found.extend(obj["@graph"])
            else:
                found.append(obj)
    return found


def fetch_http(url: str) -> dict:
    out: dict = {"method": "http"}
    try:
        with httpx.Client(follow_redirects=True, timeout=20, headers=HEADERS) as c:
            r = c.get(url)
    except httpx.HTTPError as e:
        return {**out, "error": f"{type(e).__name__}: {e}"}
    out["status"] = r.status_code
    out["final_url"] = str(r.url)
    if "html" not in r.headers.get("content-type", ""):
        out["content_type"] = r.headers.get("content-type")
        return out
    soup = BeautifulSoup(r.text[:2_000_000], "html.parser")
    if soup.title and soup.title.string:
        out["title"] = soup.title.string.strip()
    meta = {}
    for m in soup.find_all("meta"):
        key = m.get("property") or m.get("name")
        if key and m.get("content") and (key.startswith(("og:", "twitter:", "event:", "music:"))
                                         or key == "description"):
            meta[key] = m["content"].strip()
    if meta:
        out["meta"] = meta
    ld = _jsonld(soup)
    if ld:
        out["json_ld"] = json.dumps(ld, ensure_ascii=False)[:JSONLD_LIMIT]
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    text = " ".join(soup.get_text(" ").split())
    if text:
        out["text"] = text[:TEXT_LIMIT]
    return out
