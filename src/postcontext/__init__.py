"""postcontext: turn a social post or web link into the text an LLM needs to
understand it: caption, text on images and video frames, speech, page metadata.

    from postcontext import gather
    ctx = gather("https://www.instagram.com/p/...")

See CASES.md for what each kind of post needs and why."""

from . import social
from .fetch import YTDLP_HOSTS, fetch_http, fetch_ytdlp, host_matches

__all__ = ["gather", "recent_posts"]


def gather(url: str, media: bool = True) -> dict:
    """Everything readable about one URL, as a JSON-serializable dict with a `url` key.
    Instagram/Facebook use the logged-in browser when available, then fall back."""
    result = social.fetch(url, with_media=media)
    if result is None and host_matches(url, YTDLP_HOSTS):
        result = fetch_ytdlp(url)
    if result is None:
        result = fetch_http(url)
    return {"url": url, **result}


def recent_posts(profile_url: str, limit: int = 12) -> list[str]:
    """Post URLs from a profile's grid, newest first after any pinned posts."""
    return social.recent_posts(profile_url, limit)
