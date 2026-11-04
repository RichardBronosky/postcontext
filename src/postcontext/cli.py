"""postcontext CLI: print what can be read from a URL, as JSON.

    postcontext URL [URL...]            # one JSON object per line
    postcontext --no-media URL          # skip OCR / video / transcription (fast)
    postcontext --recent 6 PROFILE_URL  # gather a profile's 6 most recent posts
"""

import argparse
import json
import logging
import sys

from . import gather, recent_posts


def main() -> None:
    ap = argparse.ArgumentParser(prog="postcontext", description="Turn a post URL into LLM-readable context (JSON).")
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--no-media", action="store_true", help="skip OCR, video frames and transcription")
    ap.add_argument("--recent", type=int, metavar="N", help="treat URLs as profiles; gather their N most recent posts")
    ap.add_argument("--pretty", action="store_true", help="indent the JSON")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, stream=sys.stderr,
                        format="%(levelname)s %(name)s: %(message)s")

    urls = []
    for u in args.urls:
        urls += recent_posts(u, args.recent) if args.recent else [u]
    for u in urls:
        print(json.dumps(gather(u, media=not args.no_media), ensure_ascii=False, indent=2 if args.pretty else None),
              flush=True)


if __name__ == "__main__":
    main()
