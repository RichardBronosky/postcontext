// Instagram profile page: name, bio and link-in-bio.
(() => {
  const meta = n => (document.querySelector(`meta[property="${n}"], meta[name="${n}"]`) || {}).content || "";
  const header = document.querySelector("main header") || document.querySelector("header");
  // Outbound links go through l.instagram.com/?u=<real url>.
  const links = [...(header || document).querySelectorAll("a[href^='http']")].map(a => {
    try { const u = new URL(a.href); return u.hostname === "l.instagram.com" ? u.searchParams.get("u") : a.href; }
    catch (e) { return null; }
  }).filter(h => h && !/(^|\.)(instagram|facebook|meta|threads)\.com/.test(new URL(h).hostname));
  return JSON.stringify({
    description: meta("og:description") || meta("description"),
    title: meta("og:title"),
    header: header ? header.innerText.slice(0, 1500) : "",
    links: [...new Set(links)],
    // Grid order: pinned posts first, then newest.
    posts: [...new Set([...document.querySelectorAll("main a[href*='/p/'], main a[href*='/reel/']")]
      .map(a => a.href.split("?")[0]))],
  });
})()
