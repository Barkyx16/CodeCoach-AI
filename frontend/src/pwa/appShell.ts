/**
 * The installable-app plumbing: service worker registration, a waiting update, and the
 * browser's install prompt. Kept outside React so it starts before the first render; components
 * read it with useAppShell().
 */
export interface AppShellState {
  /** A service worker controls this page (the app shell can start offline). */
  offlineReady: boolean;
  /** A new version is installed and waiting for the learner to say when. */
  updateWaiting: boolean;
  /** The browser offered to install the app (Chromium's beforeinstallprompt). */
  canInstall: boolean;
  /** Running as an installed app (standalone window). */
  installed: boolean;
  /** Service workers can't run here (unsupported, or a development build). */
  unsupportedReason: string | null;
}

interface InstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

let state: AppShellState = {
  offlineReady: false,
  updateWaiting: false,
  canInstall: false,
  installed: false,
  unsupportedReason: null,
};
const listeners = new Set<() => void>();
let waiting: ServiceWorker | null = null;
let installEvent: InstallPromptEvent | null = null;

function set(patch: Partial<AppShellState>) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

/** For tests: put the shell in a given state (e.g. an update waiting). */
export function setAppShellState(patch: Partial<AppShellState>): void {
  set(patch);
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function snapshot(): AppShellState {
  return state;
}

function standalone(): boolean {
  try {
    return window.matchMedia("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true;
  } catch {
    return false;
  }
}

/** Register the service worker (production builds only) and listen for updates and install offers. */
export function startAppShell(enabled = import.meta.env.PROD): void {
  set({ installed: standalone() });
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault(); // we show our own, restrained button instead of the browser's banner
    installEvent = event as InstallPromptEvent;
    set({ canInstall: true });
  });
  window.addEventListener("appinstalled", () => {
    installEvent = null;
    set({ canInstall: false, installed: true });
  });
  if (!("serviceWorker" in navigator)) {
    set({ unsupportedReason: "This browser doesn't support offline use." });
    return;
  }
  if (!enabled) {
    set({ unsupportedReason: "Offline use is only available in the production build." });
    return;
  }
  let reloading = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    // Only after the learner chose "Update now": the new version takes over and the page reloads
    // (drafts are already on the device). A first install also takes control, but there's no
    // reload then: nothing changed for the page.
    if (reloading) window.location.reload();
    set({ offlineReady: true });
  });
  void navigator.serviceWorker.register("/sw.js", { scope: "/" }).then((registration) => {
    if (registration.active) set({ offlineReady: true }); // an active worker has the shell cached
    const track = (worker: ServiceWorker | null) => {
      if (!worker) return;
      const check = () => {
        if (worker.state === "installed" && navigator.serviceWorker.controller) {
          waiting = worker;
          set({ updateWaiting: true });
        }
        if (worker.state === "activated") set({ offlineReady: true });
      };
      check();
      worker.addEventListener("statechange", check);
    };
    track(registration.waiting);
    track(registration.installing);
    registration.addEventListener("updatefound", () => track(registration.installing));
    // Look for a new version when the learner comes back to the tab (not on a timer).
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") void registration.update().catch(() => undefined);
    });
  }).catch(() => set({ unsupportedReason: "Offline use couldn't be set up in this browser." }));
  applyUpdate = () => {
    if (!waiting) return;
    reloading = true;
    waiting.postMessage({ type: "SKIP_WAITING" });
  };
}

let applyUpdate: () => void = () => undefined;

/** Activate the waiting version now; the page reloads once it takes over. */
export function updateNow(): void {
  applyUpdate();
}

/** Show the browser's install dialog (only after the browser offered it). */
export async function install(): Promise<"accepted" | "dismissed" | "unavailable"> {
  if (!installEvent) return "unavailable";
  const event = installEvent;
  installEvent = null;
  set({ canInstall: false });
  await event.prompt();
  return (await event.userChoice).outcome;
}
