// Facebook post or reel in the logged-in shared browser.
// Posts open in a dialog titled "<Page>'s Post"; reels render in [role=main].
// The Messenger dialog holds private chats: never read it.
(() => {
  const dialogs = [...document.querySelectorAll("[role=dialog]")]
    .filter(d => d.getAttribute("aria-label") !== "Messenger" && /'s Post/.test(d.innerText || ""));
  const isReel = /\/reel\//.test(location.pathname);
  const root = (!isReel && dialogs[0]) || document.querySelector("[role=main]");
  if (!root) return JSON.stringify({ error: "no post region found" });
  // Facebook scatters obfuscated one-character lines and "Facebook" placeholders through the text.
  const text = root.innerText.split("\n").map(s => s.replace(/[\u034f\u200b-\u200f\u2060\ufeff]/g, "").trim())
    .filter(s => s.length > 1 && s !== "Facebook" && !/^[\d.,KM]+$/.test(s)).join("\n");
  const imgs = [...root.querySelectorAll("img")].filter(i => i.naturalWidth >= 300)
    .map(i => ({ src: i.currentSrc || i.src, alt: i.alt || "" }));
  const out = [...root.querySelectorAll("a[href*='l.facebook.com/l.php']")].map(a => {
    try { return new URL(a.href).searchParams.get("u"); } catch (e) { return null; }
  }).filter(Boolean);
  return JSON.stringify({
    kind: isReel ? "reel" : "post",
    text: text.slice(0, 4000),
    imgs: imgs.slice(0, 20),
    links: [...new Set(out)],
    video: root.querySelectorAll("video").length,
  });
})()
