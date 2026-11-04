// Runs inside an Instagram /p/ or /reel/ page in the logged-in shared browser.
// Returns the post's own media and text, ignoring the "More posts from" grid.
(() => {
  const meta = n => (document.querySelector(`meta[property="${n}"], meta[name="${n}"]`) || {}).content || "";
  const root = document.querySelector("main") || document.body;
  const stop = [...root.querySelectorAll("h2, span, div")].find(e => /^More posts from/.test(e.innerText || ""));
  const before = el => !stop || (el.compareDocumentPosition(stop) & Node.DOCUMENT_POSITION_FOLLOWING);
  const imgs = [...root.querySelectorAll("img")]
    .filter(i => i.naturalWidth >= 300 && before(i))
    .map(i => ({ src: i.currentSrc || i.src, alt: i.alt || "" }));
  const location = [...root.querySelectorAll("a[href*='/explore/locations/']")].map(a => a.textContent.trim())[0] || "";
  const links = [...root.querySelectorAll("a[href^='http']")].filter(before)
    .map(a => a.href).filter(h => !/instagram\.com|facebook\.com|meta\.com/.test(h));
  return JSON.stringify({
    description: meta("og:description") || meta("description"),
    title: meta("og:title"),
    canonical: meta("og:url"),
    location,
    links: [...new Set(links)],
    imgs,
    video: [...root.querySelectorAll("video")].filter(before).length,
    next: !!root.querySelector("button[aria-label='Next']"),
    login_wall: !!document.querySelector("a[href*='/accounts/login']") && !meta("og:description"),
    comments: (stop ? root.innerText.split("More posts from")[0] : root.innerText).slice(0, 3000),
  });
})()
