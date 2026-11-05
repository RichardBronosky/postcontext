// A link-in-bio page (Linktree, Beacons, ...): every outbound entry as {title, url}.
(() => {
  const own = location.hostname;
  const seen = new Set();
  const out = [];
  for (const a of document.querySelectorAll("a[href^='http']")) {
    let h;
    try { h = new URL(a.href); } catch (e) { continue; }
    if (h.hostname === own || /(^|\.)(linktr\.ee|linktree\.com)$/.test(h.hostname)) continue;
    const title = (a.innerText || a.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim();
    if (!title || seen.has(a.href)) continue;
    seen.add(a.href);
    out.push({ title: title.slice(0, 200), url: a.href });
  }
  return JSON.stringify(out);
})()
