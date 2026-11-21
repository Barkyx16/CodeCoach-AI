/**
 * Keeping a lost refresh response from signing the user out.
 *
 * A refresh rotates the HttpOnly refresh cookie on the server. If the response never arrives (a
 * reload, a closed tab, a dropped connection), the browser still holds the old cookie, which the
 * server has already used. The server accepts that same cookie again for a short time if it comes
 * with the same attempt key, and hands back the same new session (backend:
 * app/services/refresh.py). So a key is made before a refresh is sent and kept until its outcome is
 * known, and the next attempt reuses it:
 *  - in this tab, across a reload: sessionStorage (one tab only, gone when the tab closes);
 *  - in this app's other tabs: announced over a BroadcastChannel, and kept by each tab in its own
 *    sessionStorage, so a tab (even after it reloads) can finish a refresh that another tab
 *    started and never heard back from, for example because that tab was closed.
 * The key is useless without the HttpOnly cookie and only works inside the server's window. It is
 * never written to localStorage and never logged.
 *
 * Refreshes are also serialised across tabs with the Web Locks API where available, so two tabs
 * don't present the same cookie at the same moment.
 */

const STORAGE_KEY = "codecoach.refresh-attempt"; // this tab's own unfinished attempt
const OTHER_KEY = "codecoach.refresh-attempt.other"; // another tab's, as last announced
const CHANNEL_NAME = "codecoach-auth";
const LOCK_NAME = "codecoach-refresh";
/** A little under the server's two-minute recovery window: older keys can't recover anything. */
export const ATTEMPT_TTL_MS = 110_000;
/**
 * Waits before retrying a refresh the server answered with `refresh_race` (another tab, or a
 * request this page sent before a reload, is using the same cookie right now). Bounded: after the
 * last one the refresh gives up instead of looping.
 */
export const RACE_RETRY_MS = [300, 800, 1600] as const;

interface Attempt {
  key: string;
  at: number; // when the attempt this key belongs to was first sent
}

type Message = { type: "attempt"; attempt: Attempt } | { type: "settled"; key: string };

let shared: Attempt | null = null; // the latest unfinished attempt another tab told us about (memory copy)
let channel: BroadcastChannel | null | undefined;

function getChannel(): BroadcastChannel | null {
  if (channel !== undefined) return channel;
  channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(CHANNEL_NAME);
  (channel as { unref?: () => void } | null)?.unref?.(); // Node (tests): don't keep the process alive
  channel?.addEventListener("message", (event: MessageEvent<Message>) => {
    const message = event.data;
    if (message?.type === "attempt" && isAttempt(message.attempt)) {
      shared = message.attempt;
      write(OTHER_KEY, message.attempt);
    }
    // Another tab got the answer for this key: the cookie in this browser is up to date.
    if (message?.type === "settled") forget(message.key);
  });
  return channel;
}

function isAttempt(value: unknown): value is Attempt {
  const a = value as Attempt | null;
  return typeof a?.key === "string" && /^[A-Za-z0-9_-]{22,64}$/.test(a.key) && typeof a.at === "number";
}

const fresh = (a: Attempt | null, now = Date.now()): a is Attempt => a !== null && now - a.at < ATTEMPT_TTL_MS && a.at <= now + 1000;

function read(name: string): Attempt | null {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(name) ?? "null");
    return isAttempt(value) ? value : null;
  } catch {
    return null;
  }
}

function write(name: string, attempt: Attempt): void {
  try {
    sessionStorage.setItem(name, JSON.stringify(attempt));
  } catch {
    /* storage unavailable: recovery after a reload won't be possible, the refresh still works */
  }
}

function remove(name: string): void {
  try {
    sessionStorage.removeItem(name);
  } catch {
    /* nothing to clean up */
  }
}

/** This key's outcome is known (or it's no use any more): stop offering it. */
function forget(key: string): void {
  if (read(STORAGE_KEY)?.key === key) remove(STORAGE_KEY);
  if (read(OTHER_KEY)?.key === key) remove(OTHER_KEY);
  if (shared?.key === key) shared = null;
}

function newKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(24));
  let text = "";
  for (const b of bytes) text += String.fromCharCode(b);
  return btoa(text).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function pending(now: number): Attempt | null {
  const own = read(STORAGE_KEY);
  if (fresh(own, now)) return own;
  const other = fresh(shared, now) ? shared : read(OTHER_KEY);
  return fresh(other, now) ? other : null;
}

/** The unfinished attempt's key the next refresh would reuse, if any (no side effects). */
export function pendingAttemptKey(now = Date.now()): string | null {
  getChannel();
  return pending(now)?.key ?? null;
}

/**
 * The key to send with the next refresh: this tab's unfinished attempt if there is one (a reload
 * or a retry after a lost response), else another tab's unfinished attempt, else a new key. It is
 * stored and announced before the request goes out, so it survives whatever happens to the reply.
 */
export function beginAttempt(now = Date.now()): string {
  getChannel();
  const attempt = pending(now) ?? { key: newKey(), at: now };
  write(STORAGE_KEY, attempt);
  getChannel()?.postMessage({ type: "attempt", attempt } satisfies Message);
  return attempt.key;
}

/** The outcome for this key is known (it worked, or the server definitively refused it). */
export function settleAttempt(key: string): void {
  forget(key);
  getChannel()?.postMessage({ type: "settled", key } satisfies Message);
}

/**
 * This tab's key didn't rotate anything (the server said another attempt used the cookie): don't
 * reuse it, but don't tell other tabs either. Their attempts are unaffected.
 */
export function dropAttempt(key: string): void {
  forget(key);
}

/** Forget any unfinished attempt (signing out): nothing should try to recover it. */
export function forgetAttempts(): void {
  const own = read(STORAGE_KEY);
  remove(STORAGE_KEY);
  remove(OTHER_KEY);
  shared = null;
  if (own) getChannel()?.postMessage({ type: "settled", key: own.key } satisfies Message);
}

/** How long a refresh waits for another tab's refresh before going ahead anyway. */
export const LOCK_WAIT_MS = 4000;

/**
 * Run `fn` while no other tab of this app is refreshing (Web Locks), or directly without them.
 * The wait is bounded: if another tab's refresh is stuck (a stalled connection), this one goes
 * ahead after LOCK_WAIT_MS rather than leaving the page restoring forever. Going ahead is safe:
 * the server's race handling and the attempt keys cover two refreshes at once.
 */
export async function withRefreshLock<T>(fn: () => Promise<T>, waitMs = LOCK_WAIT_MS): Promise<T> {
  const locks = typeof navigator !== "undefined" ? (navigator as Navigator & { locks?: LockManager }).locks : undefined;
  if (!locks?.request || typeof AbortSignal === "undefined" || !("timeout" in AbortSignal)) return fn();
  const signal = AbortSignal.timeout(waitMs);
  try {
    return (await locks.request(LOCK_NAME, { signal }, fn)) as T;
  } catch (error) {
    // Not granted in time: the lock request was withdrawn with our signal's reason, so go ahead
    // without it. Anything fn itself throws (even its own abort) is passed on unchanged.
    if (signal.aborted && error === signal.reason) return fn();
    throw error;
  }
}

/** For tests: reset module state. */
export function resetRefreshAttemptsForTests(): void {
  shared = null;
  channel?.close();
  channel = undefined;
  remove(STORAGE_KEY);
  remove(OTHER_KEY);
}
