/* If the app's code doesn't start (a content blocker stopped a file, the browser is too old, a
 * download failed), say so instead of leaving a blank page, with what failed and what to try.
 * Plain ES5 so it runs in browsers the app itself can't. A separate file because the
 * Content-Security-Policy allows only same-origin scripts. Nothing is sent anywhere. */
(function () {
  var problems = [];
  var shown = null;

  function note(text) {
    if (text && problems.length < 6 && problems.indexOf(text) < 0) problems.push(String(text).slice(0, 300));
  }
  window.addEventListener("error", function (e) {
    var t = e.target;
    if (t && t !== window && (t.src || t.href)) note("Couldn't load " + (t.src || t.href));
    else if (e.message) note(e.message + (e.filename ? " (" + e.filename + ":" + e.lineno + ")" : ""));
  }, true);
  window.addEventListener("unhandledrejection", function (e) {
    var r = e.reason;
    note(r && r.message ? r.message : String(r));
  });

  function started() {
    var root = document.getElementById("root");
    return !!root && root.childNodes.length > 0;
  }

  function line(parent, tag, text) {
    var el = document.createElement(tag);
    el.textContent = text;
    parent.appendChild(el);
    return el;
  }

  function show() {
    if (shown || started()) return;
    shown = document.createElement("div");
    shown.setAttribute("role", "alert");
    shown.id = "boot-problem";
    var s = shown.style;
    s.maxWidth = "40rem";
    s.margin = "3rem auto";
    s.padding = "0 1rem";
    s.font = "16px/1.5 -apple-system, system-ui, sans-serif";
    s.color = "CanvasText";
    line(shown, "h1", "CodeCoach couldn't start in this browser").style.fontSize = "1.5rem";
    line(shown, "p", "Something stopped the app's code from loading or running. A content blocker or ad blocker is the usual cause.");
    var steps = document.createElement("ol");
    line(steps, "li", "Turn content blockers off for this site. In Safari: Safari menu → Settings for This Website (or “Settings for localhost”) → untick “Enable content blockers”. Other browsers: the blocker's own button.");
    line(steps, "li", "Reload the page.");
    line(steps, "li", "Still blank? Try another browser, such as Chrome or Firefox.");
    shown.appendChild(steps);
    var button = line(shown, "button", "Reload");
    button.type = "button";
    button.style.font = "inherit";
    button.style.padding = "0.4rem 1rem";
    button.addEventListener("click", function () { window.location.reload(); });
    line(shown, "p", "Details, if you ask someone for help:").style.marginTop = "1.5rem";
    var details = document.createElement("ul");
    details.style.fontSize = "0.85rem";
    details.style.wordBreak = "break-word";
    for (var i = 0; i < problems.length; i++) line(details, "li", problems[i]);
    if (!problems.length) line(details, "li", "No error was reported: the app's code may not have been allowed to run.");
    line(details, "li", "Browser: " + navigator.userAgent);
    shown.appendChild(details);
    document.body.appendChild(shown);
    // If the app starts after all, the message goes away.
    var root = document.getElementById("root");
    if (root && window.MutationObserver) {
      var watch = new MutationObserver(function () {
        if (!started()) return;
        watch.disconnect();
        if (shown && shown.parentNode) shown.parentNode.removeChild(shown);
        shown = null;
      });
      watch.observe(root, { childList: true });
    }
  }

  // The app normally shows something within a moment of loading.
  function later() {
    setTimeout(show, 5000);
  }
  if (document.readyState === "complete") later();
  else window.addEventListener("load", later);
  setTimeout(show, 20000); // in case the page never finishes loading
})();
