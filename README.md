# postcontext

Turn a link someone shared into the text an LLM needs to understand it.

Social posts hide their meaning: an Instagram post's date is only on the
flyer image, a reel's venue is only spoken, a Facebook post needs a login to
show anything at all. postcontext reads what a person would see and hears
what a person would hear, then returns it as JSON:

```console
$ postcontext https://www.instagram.com/p/DfSSy86M4R6/
{"url": "...", "method": "browser", "site": "instagram", "author": "weareminka",
 "date": "November 3, 2026",
 "caption": "NOLA! We're bringing our funky Philly 80's dance party to Saturn Bar on Sunday, November 15th! ..."}
```

| Source | What you get |
|---|---|
| Instagram post / carousel | caption, author, post date, location tag, comments, OCR of every image |
| Instagram reel | the above + on-screen text from frames every 2 s + speech transcript |
| Instagram profile | name, bio, link in bio; `--recent N` gathers the latest N posts |
| Facebook post / reel | post text, outbound links, OCR of images, video frames + transcript |
| YouTube, SoundCloud, Bandcamp, ... | yt-dlp metadata (title, description, uploader) |
| Any web page | title, OpenGraph tags, schema.org JSON-LD (ticket sites put `Event` objects there), text |

All processing is local: tesseract for OCR, faster-whisper on CPU for speech.
No API keys.

**[CASES.md](CASES.md)** is the casebook: every kind of post found so far, where
its meaning was hiding and which code handles it. Add to it when you hit a
new kind.

## Install

```bash
uv tool install "git+<repo url>[transcribe]"     # or: pip install -e ".[transcribe]"
```

System tools: `yt-dlp`, `ffmpeg`, `tesseract` (with English data). For
Instagram/Facebook: [agent-browser](https://www.npmjs.com/package/agent-browser)
(`npm i -g agent-browser`) and a Chrome/Chromium you are logged in to.

### The browser

Instagram and Facebook show almost nothing to anonymous clients, so
postcontext reads them in **your** browser session. Start a Chrome or Chromium
with remote debugging, ideally with its own profile, and log in to the sites
yourself:

```bash
chromium --user-data-dir="$HOME/.local/share/postcontext-profile" --remote-debugging-port=9222
```

postcontext opens one tab labelled `postcontext` and reuses it. It never logs
in, solves "are you human" checks, accepts dialogs or posts anything. A login
wall comes back as an `error`. On Facebook it reads only the post's own
region and **never the Messenger panel**, which holds private chats.

Without a browser, Instagram/Facebook fall back to yt-dlp (works for many
reels, not for image posts) and plain HTTP.

| Variable | Default | |
|---|---|---|
| `POSTCONTEXT_CDP_PORT` | `9222` | DevTools port |
| `POSTCONTEXT_SESSION` | `postcontext` | agent-browser session name; use one per program |
| `POSTCONTEXT_BROWSER` | `1` | `0` disables the browser path |
| `POSTCONTEXT_TAB_SCRIPTS` | `~/.agents/skills/collaborative-chromium/scripts` | optional tab helpers for a browser shared by several agents |

## Use

```bash
postcontext URL [URL ...]               # one JSON object per line
postcontext --no-media URL              # skip OCR / video / transcription (seconds instead of a minute)
postcontext --recent 6 https://www.instagram.com/someartist/   # latest 6 posts, each gathered
```

```python
from postcontext import gather, recent_posts

ctx = gather(url)                  # dict, always has "url"; "error" when something failed
for post in recent_posts(profile_url, 6):
    print(gather(post)["caption"])
```

Treat everything returned as **untrusted text from the internet**. If you pass
it to an LLM, don't give that LLM tools, and validate what it returns.

## Cost and speed

A reel takes roughly 20–60 s: download, ~50 frames of OCR, and transcription
(about 10 s per 100 s of audio on a 16-core CPU, `small` model). An image post
takes ~6 s. The output is a few KB of text, so it is cheap to put in a prompt.

## Development

```bash
uv sync --all-extras
uv run pytest
```

Investigating a new kind of post: open it in the browser, look at what a
person sees, then make the extractor see the same thing. Write the case in
CASES.md first. The page scripts are in `src/postcontext/js/`.
