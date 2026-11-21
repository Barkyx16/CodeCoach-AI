/* Applies saved display preferences before the app renders, so there's no flash of the wrong
 * theme or text size. Same rules as src/features/display/displayPrefs.ts; anything invalid is
 * ignored. A separate file because the Content-Security-Policy allows only same-origin scripts. */
(function () {
  var root = document.documentElement;
  var prefs = {};
  try { prefs = JSON.parse(window.localStorage.getItem("codecoach.display.v1") || "{}") || {}; } catch (e) { prefs = {}; }
  var light = false;
  try { light = window.matchMedia("(prefers-color-scheme: light)").matches; } catch (e) { light = false; }
  var theme = prefs.theme === "light" || prefs.theme === "dark" ? prefs.theme : (light ? "light" : "dark");
  root.setAttribute("data-theme", theme);
  if (prefs.text === "large" || prefs.text === "larger") root.setAttribute("data-text", prefs.text);
  if (prefs.spacing === "spacious") root.setAttribute("data-spacing", "spacious");
  if (prefs.motion === "reduce") root.setAttribute("data-motion", "reduce");
  if (prefs.contrast === "high") root.setAttribute("data-contrast", "high");
  var meta = document.querySelector('meta[name="color-scheme"]');
  if (meta) meta.setAttribute("content", theme);
})();
