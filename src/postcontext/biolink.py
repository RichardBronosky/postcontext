"""Case C8: "link in bio". The post only says where the details are: the
author's bio links, often a Linktree-style list with one entry per post or
event. Read the bio links, open any link list, and pick the entry whose title
matches the post's own text (caption + text on its images)."""

import logging
import re
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

log = logging.getLogger(__name__)

# Captions that send readers to the bio ("Tap the link in our bio", "tickets in bio", "link below").
POINTS_TO_BIO = re.compile(r"\b(link|links|tickets?|rsvp|details|info)\b[^.\n]{0,25}\b(in|on)\s+(our|my|the|their)?\s*bio\b"
                           r"|\blink\s+(in\s+)?bio\b|\blink\s+below\b|\bbio\s+link\b", re.I)

# Hosts that are lists of links rather than a destination. They block plain HTTP, so use the browser.
LINK_LIST_HOSTS = ("linktr.ee", "beacons.ai", "linkin.bio", "lnk.bio", "solo.to", "bio.site", "hoo.be",
                   "tap.bio", "campsite.bio", "linkpop.com", "stan.store", "msha.ke", "komi.io", "snipfeed.co")
MAX_ENTRIES = 25
STOP = set("the and for with your our you are this that from have will just more about into what when where "
           "their them they here there been after before link bio tap head read".split())


def points_to_bio(text: str) -> bool:
    return bool(POINTS_TO_BIO.search(text or ""))


def is_link_list(url: str) -> bool:
    h = (urlparse(url).hostname or "").lower()
    return any(h == d or h.endswith("." + d) for d in LINK_LIST_HOSTS) or "later.com/linkinbio" in url


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9’']{3,}", (text or "").lower().replace("’", "'")) if w not in STOP}


def best_entry(entries: list[dict], post_text: str) -> tuple[dict | None, float]:
    """The entry whose title shares the most words with the post. Score is the share of the
    title's words found in the post; needs at least 3 shared words and half the title."""
    post = words(post_text)
    best, best_score = None, 0.0
    for e in entries:
        t = words(e.get("title", ""))
        if not t:
            continue
        shared = len(t & post)
        score = shared / len(t)
        if shared >= 3 and score > best_score:
            best, best_score = e, score
    return (best, round(best_score, 2)) if best_score >= 0.5 else (None, round(best_score, 2))


def clean_url(url: str) -> str:
    """Drop tracking parameters Instagram adds (utm_*, fbclid, igsh)."""
    u = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
         if not k.startswith("utm_") and k not in ("fbclid", "igsh", "igshid")]
    return urlunparse(u._replace(query=urlencode(q)))


def profile_links(br, handle: str) -> list[str]:
    br.open(f"https://www.instagram.com/{handle}/")
    links = br.script("instagram_profile.js").get("links", [])
    if br.script("instagram_bio_more.js"):
        time.sleep(1.5)
        links = list(dict.fromkeys(links + (br.script("instagram_dialog_links.js") or [])))
        br.press("Escape")
    return list(dict.fromkeys(clean_url(u) for u in links))


def follow(br, handle: str, post_text: str, gather) -> dict:
    """What the bio link says about this post. `gather(url)` reads a destination page."""
    out: dict = {"profile": handle}
    links = profile_links(br, handle)
    out["bio_links"] = links
    if not links:
        out["error"] = "no links in bio"
        return out
    entries: list[dict] = []
    for url in links:
        if is_link_list(url):
            br.open(url, settle=3.0)
            got = br.script("link_list.js") or []
            out.setdefault("lists", []).append(url)
            entries += got
        else:
            entries.append({"title": "", "url": url})
    entries = entries[:MAX_ENTRIES]
    match, score = best_entry(entries, post_text)
    if match is None and len(links) == 1 and not is_link_list(links[0]):
        match, score = {"title": "", "url": links[0]}, None  # a single plain bio link: that's the one
    out["entries"] = [e for e in entries if e.get("title")][:MAX_ENTRIES]
    if match:
        out["matched"] = {**match, "score": score}
        out["page"] = gather(match["url"])
    return out
