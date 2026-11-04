# Casebook: where does a post hide its meaning?

Each case is a kind of post that needed a specific way of reading it. When a
link comes back without what a person would see (no date, no caption, a login
page), add a case: what the post looked like, where the answer was, and which
code handles it. Keep going until new posts stop producing new cases.

How to investigate a new one: open it in the logged-in browser and look at
what a person sees. Then make the extractor see the same thing. Examples come
from real shares (message numbers refer to the sharebot import they came from).

Status: ✅ handled · 🟡 partly · ❌ not yet

---

## C1 ✅ Instagram post, details in the caption
*Example: weareminka "funky Philly 80's dance party at Saturn Bar on Sunday, November 15th" (msg 753); margieperezmusic "Friday 10/30 come see us at @bmacsfrenchquarter 6pm-9pm" (msg 744)*

- Not logged in, Instagram shows only "Video by <user>". The caption needs the shared, logged-in browser.
- The caption, author and post date are in `og:description`:
  `235 likes, 39 comments - ella_ruth_ on October 11, 2026: "Proof of life".`
- Comments can correct the details ("I thought it was 7p"), so the first ~2000 chars of page text go in too.
- Code: `social.instagram` + `js/instagram_post.js`, `social.parse_ig_description`.

## C2 ✅ Instagram image post, details only on the image (flyer/poster)
*Example: bmacsfrenchquarter "THIS WEEK!" (msg 686): the caption has only the address; the image is the weekly lineup with dates, acts and times.*

- The page also shows a "More posts from <user>" grid. Only images *before* that heading belong to the post.
- OCR (tesseract, local, free) reads posters well enough: `THURSDAY GABE STILLMAN BAND 9/17 @7PM ...`.
- Instagram's `alt` text on images is sometimes the caption or a description; kept when present.
- Code: `media.ocr_images`.

## C3 ✅ Instagram carousel
*Example: ella_ruth_ "Proof of life" (msg 725, `img_index=19`): a family photo dump, not an event.*

- Only the first 1–2 slides are in the DOM. Click `button[aria-label=Next]` and collect new images until it's gone (max 20).
- Code: `js/instagram_next.js`, loop in `social.instagram`.

## C4 ✅ Instagram reel: details spoken or as on-screen text
*Example: loganinthefuture "How I keep up with AI" (msg 713).*

- `/reels/<code>/` shows a scrolling feed of *other* reels after the shared one. Normalize to `/reel/<code>/`.
- The video in the page is a `blob:` URL, which can't be downloaded. yt-dlp downloads reels without a login.
- Frames every 2 s → OCR → near-duplicate frames dropped (overlays stay up for seconds).
- Audio → faster-whisper `small` int8 on CPU (≈10 s for a 100 s reel). Audio is decoded with ffmpeg first, because faster-whisper's PyAV path crashes with the installed PyAV (`metadata_errors` TypeError).
- Code: `media.analyze_video`.

## C5 ✅ Instagram profile shared
*Example: teddy_lamson (msg 741): "Musician … Drums•Vox•Perc… Swamp gal 🐊 … @shaniatwain", linktr.ee in bio.*

- Almost always an artist to follow. Header text = name, bio, link in bio (the real URL is in `l.instagram.com/?u=`).
- Code: `js/instagram_profile.js`.

## C6 ✅ Facebook post (share link `facebook.com/share/<id>/`)
*Example: Nola Secret Sesh "GARDEN SESH … Saturday, July 18 6PM–10PM Paradigm Gardens … Tickets — link in bio. EVENTBRITE.COM" (msg 649).*

- Open the original `/share/` link: it redirects to `/posts/...?rdid=`. The bare `/posts/` URL without `rdid` lands on the news feed.
- The post is in a `[role=dialog]` whose text contains "'s Post". **Another dialog, `aria-label="Messenger"`, holds the user's private chats. Never read it.**
- The text is laced with one-character lines (`n͏`, char + U+034F) and "Facebook" placeholders. Strip invisible chars, drop 1-char lines.
- Outbound links are `l.facebook.com/l.php?u=<real url>`.
- Code: `social.facebook` + `js/facebook_post.js`.

## C7 ✅ Facebook reel (`facebook.com/share/r/<id>/`)
*Example: Absolute Light "Nothing appearing to be everything" (msg 645).*

- Redirects to `/reel/<id>`; caption is in `[role=main]`. yt-dlp downloads it; same frames + transcript as C4.

## C8 ❌ Ticket/details only behind "link in bio" or an event site
*Example: Nola Secret Sesh (C6) says "Tickets available now — link in bio"; the Eventbrite card is in the post.*

- Next step: follow `links` from the post (or the profile's link in bio) and fetch the ticket page with `fetch_http` (JSON-LD `Event` objects carry exact dates). Not built yet. This case's post already had the date in its text.

## C9 ✅ Non-social links
*Examples: Pitchfork review, donttellcomedy.com/cities/new-orleans-la, Google Maps share, YouTube.*

- Plain HTTP fetch with full browser headers (Wikipedia 403s a bare UA). YouTube via yt-dlp.
- donttellcomedy city page: a *listing*, not one show.

## C10 🟡 Recent posts of an artist's profile ("when is their next show?")
*Example: `postcontext --recent 3 https://www.instagram.com/teddy_lamson/`*

- The profile grid's `/p/` and `/reel/` links, in grid order. **Pinned posts come first** and can be months old: don't assume the first post is the newest; compare `date`s.
- **Collab posts** by other accounts show up in the grid (honest__art's film screening on teddy_lamson's profile). Their `author` is the other account.
- Not yet: scrolling for more than the first rows; skipping pinned posts explicitly.
- Code: `social.recent_posts`, `posts` in `js/instagram_profile.js`.

## C11 ❌ Facebook page Events tab
- An artist's or venue's Facebook page often lists upcoming events at `/<page>/upcoming_hosted_events` or `/events`, with exact dates. Probably the most reliable "next show" source. Not built.

---

## Operational notes
- postcontext keeps one tab labelled `postcontext` per session and reuses it, even across processes (checked via DevTools `/json/list` against `<session>.hub-labels`). With the collaborative-chromium helper scripts, `tab-new` silently fails if the label already exists. That bug made the first full sharebot import fall back to plain fetching for all 22 social links.
- Every page load replays the post's video in the browser. Opening the same post over and over while debugging looks like a loop to anyone watching the browser.

## Sites that block plain fetching
- Songkick: 406/410 to any non-browser client. Use the shared browser if it matters.
- Instagram without login: no captions (C1). Facebook `/share/` posts without login: HTTP 400.
- Rewriting the User-Agent to look like a link-preview crawler was considered and rejected; use the logged-in browser instead.
