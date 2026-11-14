/* CodeCoach service worker: a small, public app shell and nothing else. See docs/OFFLINE.md.
 *
 * - It never handles API requests (cross-origin, or /api/ on the same origin) or anything that
 *   isn't a GET, so account data, answers, transcripts and other private responses can't enter
 *   a cache here. There is deliberately no catch-all handler.
 * - Page loads: network first; when offline, the cached shell (index.html) so the app can start
 *   and show what's available.
 * - Built files: the shell's own files are precached at install; this build's other hashed
 *   /assets/ files (e.g. the code editor) are cached the first time they're loaded. They never
 *   change in place, so cache-first is safe. Only files listed for this build are ever cached,
 *   and on update the ones the new build still uses are carried over; the rest are deleted.
 * - "Saved for offline" copies of public lessons, questions and problems are written by the
 *   page into their own cache; this worker doesn't touch it.
 * - A new version waits. The page asks the learner, then sends SKIP_WAITING, so an update never
 *   reloads away an answer being written.
 *
 * The placeholders are filled in at build time (vite.config.ts, offlineShell plugin).
 */
const VERSION = /*__SHELL_VERSION__*/ "dev";
const SHELL_FILES = /*__SHELL_FILES__*/ [];
const BUILD_ASSETS = /*__BUILD_ASSETS__*/ [];
const SHELL = `codecoach-shell-${VERSION}`;
const ASSETS = `codecoach-assets-${VERSION}`;

async function carryOverAssets() {
  const keep = new Set(BUILD_ASSETS);
  const next = await caches.open(ASSETS);
  for (const name of await caches.keys()) {
    if (!name.startsWith("codecoach-assets-") || name === ASSETS) continue;
    const old = await caches.open(name);
    for (const request of await old.keys()) {
      const path = new URL(request.url).pathname;
      if (keep.has(path)) {
        const response = await old.match(request);
        if (response) await next.put(path, response);
      }
    }
    await caches.delete(name);
  }
}

self.addEventListener("install", (event) => {
  // Where supported (Chromium's static routing), API requests skip this worker entirely: they go
  // straight to the network without waking it, so it can't delay, duplicate or see them.
  if (typeof event.addRoutes === "function" && typeof URLPattern === "function") {
    try {
      event.addRoutes([{ condition: { urlPattern: new URLPattern({ pathname: "/api/*" }) }, source: "network" }]);
    } catch (_) {
      /* not supported for this pattern: the fetch handler below still ignores API requests */
    }
  }
  event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll(SHELL_FILES)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    carryOverAssets()
      .then(() => caches.keys())
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("codecoach-shell-") && k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
  if (event.data && event.data.type === "VERSION" && event.ports[0]) event.ports[0].postMessage(VERSION);
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // the API and every other origin: untouched
  if (url.pathname.startsWith("/api/")) return; // an API behind the same origin: untouched

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() =>
        caches.open(SHELL).then((cache) => cache.match("/index.html")).then((shell) => shell || Response.error()),
      ),
    );
    return;
  }
  if (SHELL_FILES.includes(url.pathname)) {
    event.respondWith(caches.open(SHELL).then((cache) => cache.match(url.pathname)).then((hit) => hit || fetch(request)));
    return;
  }
  if (BUILD_ASSETS.includes(url.pathname)) {
    event.respondWith(
      caches.open(ASSETS).then(async (cache) => {
        const hit = await cache.match(url.pathname);
        if (hit) return hit;
        const response = await fetch(request);
        if (response.ok && response.type === "basic") await cache.put(url.pathname, response.clone());
        return response;
      }),
    );
  }
});
