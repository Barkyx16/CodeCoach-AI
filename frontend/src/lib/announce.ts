/**
 * Say something to screen readers without moving focus: one polite live region for the app,
 * created on first use. The text is set a moment after clearing it, so the same message said twice
 * is still read.
 */
export function announce(message: string): void {
  let region = document.getElementById("app-announcer");
  if (!region) {
    region = document.createElement("div");
    region.id = "app-announcer";
    region.className = "visually-hidden";
    region.setAttribute("role", "status");
    region.setAttribute("aria-live", "polite");
    document.body.appendChild(region);
  }
  region.textContent = "";
  const target = region;
  window.setTimeout(() => { target.textContent = message; }, 50);
}
