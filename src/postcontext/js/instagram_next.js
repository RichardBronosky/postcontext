// Advance an Instagram carousel by one slide. Returns false when there is no next slide.
(() => {
  const b = document.querySelector("main button[aria-label='Next']");
  if (!b) return false;
  b.click();
  return true;
})()
