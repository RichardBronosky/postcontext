// Links in the open dialog (the bio-links list), unwrapped from l.instagram.com.
(() => {
  const d = [...document.querySelectorAll("[role=dialog]")].pop();
  if (!d) return JSON.stringify([]);
  const out = [...d.querySelectorAll("a[href^='http']")].map(a => {
    try { const u = new URL(a.href); return u.hostname === "l.instagram.com" ? u.searchParams.get("u") : a.href; }
    catch (e) { return null; }
  }).filter(Boolean);
  return JSON.stringify([...new Set(out)]);
})()
