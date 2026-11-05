"""Instagram and Facebook, read through a logged-in browser, plus on-screen
text and speech from their images and videos.

Each branch below is one case in CASES.md. When a new kind of post shows
up that this doesn't handle, add a case there first, then handle it here."""

import logging
import os
import re
import time
from urllib.parse import urlparse

from . import biolink, media
from .browser import Browser, BrowserError

log = logging.getLogger(__name__)

IG_POST = re.compile(r"instagram\.com/(?:[\w.]+/)?(p|reels?|tv)/([\w-]+)")
IG_PROFILE = re.compile(r"instagram\.com/([\w.]+)/?$")
# "235 likes, 39 comments - ella_ruth_ on October 11, 2026: "Proof of life"."
IG_DESC = re.compile(r'^(?:(?P<stats>.*?) - )?(?P<author>[\w.]+) on (?P<date>\w+ \d+, \d{4})(?:: "(?P<caption>.*)"\.?)?\s*$',
                     re.S)

_browser: Browser | None = None


def enabled() -> bool:
    return os.environ.get("POSTCONTEXT_BROWSER", "1") == "1"


def browser() -> Browser:
    global _browser
    if _browser is None:
        _browser = Browser()
    return _browser


def host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def handles(url: str) -> bool:
    h = host(url)
    return any(h == d or h.endswith("." + d) for d in ("instagram.com", "facebook.com", "fb.watch"))


def parse_ig_description(desc: str) -> dict:
    m = IG_DESC.match(desc or "")
    if not m:
        return {"caption": desc} if desc else {}
    return {k: v for k, v in m.groupdict().items() if v}


def _src_key(src: str) -> str:
    return src.split("?")[0]


def instagram(url: str, with_media: bool = True, follow_bio: bool = True) -> dict:
    br = browser()
    m = IG_POST.search(url)
    if not m:
        prof = IG_PROFILE.search(url.split("?")[0])
        if not prof:
            return {"method": "browser", "error": "unrecognized instagram url"}
        # Case: profile shared (usually an artist to follow).
        br.open(f"https://www.instagram.com/{prof.group(1)}/")
        d = br.script("instagram_profile.js")
        d.pop("posts", None)
        return {"method": "browser", "site": "instagram", "kind": "profile", "handle": prof.group(1), **d}

    kind = "reel" if m.group(1).startswith("reel") else m.group(1)
    page = f"https://www.instagram.com/{'reel' if kind == 'reel' else 'p'}/{m.group(2)}/"
    br.open(page)
    d = br.script("instagram_post.js")
    if d.get("login_wall"):
        return {"method": "browser", "site": "instagram", "error": "instagram login wall: log in to the shared browser"}

    imgs = list(d.get("imgs", []))
    if d.get("next"):
        # Case: carousel. Click through; slides load lazily.
        seen = {_src_key(i["src"]) for i in imgs}
        for _ in range(media.MAX_IMAGES):
            if not br.script("instagram_next.js"):
                break
            time.sleep(1.0)
            for i in br.script("instagram_post.js").get("imgs", []):
                if _src_key(i["src"]) not in seen:
                    seen.add(_src_key(i["src"]))
                    imgs.append(i)

    out = {"method": "browser", "site": "instagram", "kind": kind, **parse_ig_description(d.get("description", "")),
           "location": d.get("location") or None, "links": d.get("links") or None,
           "page_text": d.get("comments", "")[:2000]}
    if with_media:
        if d.get("video") or kind == "reel":
            out["video"] = media.analyze_video(page)
        if imgs and not (kind == "reel"):
            alts = {_src_key(i["src"]): i["alt"] for i in imgs}
            ocrs = media.ocr_images([i["src"] for i in imgs])
            out["images"] = [{"index": o["index"], "alt": alts.get(_src_key(imgs[o["index"]]["src"])) or None,
                              "text": o["ocr"] or None} for o in ocrs if o["ocr"] or alts.get(_src_key(imgs[o["index"]]["src"]))]
            out["image_count"] = len(imgs)
    caption = out.get("caption", "")
    if follow_bio and out.get("author") and biolink.points_to_bio(caption):
        # Case C8: the details are behind the author's link in bio.
        post_text = " ".join([caption] + [i.get("text") or "" for i in out.get("images", [])])
        try:
            out["bio_link"] = biolink.follow(br, out["author"], post_text, gather=_destination)
        except BrowserError as e:
            out["bio_link"] = {"error": str(e)}
    return {k: v for k, v in out.items() if v not in (None, "", [])}


def _destination(url: str) -> dict:
    """Read a page a bio link points to, without media and without following bios again."""
    from .fetch import YTDLP_HOSTS, fetch_http, fetch_ytdlp, host_matches
    if handles(url) and "instagram.com" in host(url):
        return {"url": url, **instagram(url, with_media=False, follow_bio=False)}
    if host_matches(url, YTDLP_HOSTS):
        return {"url": url, **(fetch_ytdlp(url) or fetch_http(url))}
    return {"url": url, **fetch_http(url)}


def facebook(url: str, with_media: bool = True) -> dict:
    br = browser()
    br.open(url, settle=7.0)
    final = br.url()
    d = br.script("facebook_post.js")
    if d.get("error"):
        return {"method": "browser", "site": "facebook", "final_url": final, **d}
    out = {"method": "browser", "site": "facebook", "final_url": final, "kind": d["kind"], "text": d["text"],
           "links": d.get("links") or None}
    if with_media:
        if d["kind"] == "reel" or d.get("video"):
            out["video"] = media.analyze_video(final)
        if d.get("imgs") and d["kind"] != "reel":
            ocrs = media.ocr_images([i["src"] for i in d["imgs"]])
            out["images"] = [{"index": o["index"], "alt": d["imgs"][o["index"]]["alt"] or None, "text": o["ocr"] or None}
                             for o in ocrs if o["ocr"] or d["imgs"][o["index"]]["alt"]]
    return {k: v for k, v in out.items() if v not in (None, "", [])}


def recent_posts(profile_url: str, limit: int = 12) -> list[str]:
    """Post and reel URLs from an Instagram profile grid (case C10)."""
    prof = IG_PROFILE.search(profile_url.split("?")[0])
    if not prof:
        raise ValueError(f"not an Instagram profile URL: {profile_url}")
    br = browser()
    br.open(f"https://www.instagram.com/{prof.group(1)}/")
    return br.script("instagram_profile.js").get("posts", [])[:limit]


def fetch(url: str, with_media: bool = True) -> dict | None:
    """Returns None when the browser path isn't available, so the caller falls back."""
    if not enabled() or not handles(url):
        return None
    try:
        fn = instagram if "instagram.com" in host(url) else facebook
        return fn(url, with_media=with_media)
    except (BrowserError, OSError) as e:
        log.warning("browser fetch failed for %s: %s", url, e)
        return None
