// Profile header: the "example.com and 2 more" button opens a dialog listing every bio link.
// Clicks it; returns true when there was one.
(() => {
  const header = document.querySelector("main header") || document.querySelector("header") || document;
  const b = [...header.querySelectorAll("button, [role=button]")].find(e => /\band \d+ more\b/i.test(e.innerText || ""));
  if (!b) return false;
  b.click();
  return true;
})()
