/**
 * Why a browser request waited (Volume 13, prompt 8; docs/NAVIGATION.md, "Requests that never reach
 * the API"). One watch per tab, from Chrome's own network events (a CDP session beside Playwright's),
 * so a single failed CI run says which explanation a waiting request matches:
 *
 *   H1  queued in the browser behind six open requests to the same server (Chrome's HTTP/1.1 limit);
 *   H2  the server closed the connection under it (a keep-alive socket closed as it was reused);
 *   H3  the page's service worker held or answered it;
 *   H5  the page's main thread was blocked, so nothing it asked for was sent or heard back;
 *   H6  it came from a page that has since been replaced: its outcome went with that page, so it
 *       isn't a stall at all (CI run 315's six "waiting" reads were this);
 *   a CORS preflight ends with its request: when the page cancels a request during its preflight,
 *   Chrome reports the cancel on the request and no end for the preflight, so the preflight takes its
 *   request's end (it isn't left "waiting");
 *   or it was sent and never reached the API, or reached it and is still being worked on.
 *
 * Methods, paths (never query strings), timings and connection numbers only: no headers, bodies or
 * cookies. Watching changes nothing the page does.
 */
import { readFileSync } from "node:fs";

import type { CDPSession, Page } from "@playwright/test";

/** A request slower than this is recorded for every test, passed or failed. */
export const SLOW_MS = 5_000;
/** Chrome's connections per server (scheme, host and port) over HTTP/1.1. */
export const PER_SERVER = 6;
/** How long the page gets to answer a probe before its main thread counts as blocked. */
const PROBE_MS = 500;
const SERVER_CLOSED = /ERR_(EMPTY_RESPONSE|CONNECTION_RESET|CONNECTION_CLOSED|CONNECTION_ABORTED|SOCKET_NOT_CONNECTED)/;

export interface Entry {
  id: string;
  method: string;
  path: string;
  origin: string;
  type: string;
  loaderId: string;
  /** Wall-clock ms when the page asked for it. */
  sentAt: number;
  /** Chrome's monotonic seconds when the page asked for it. */
  ts: number;
  /** Handed to the network stack with its headers (requestWillBeSentExtraInfo): it left the queue. */
  onNetwork: boolean;
  /** Requests to the same server already on the network and unfinished when this one was asked for. */
  openSameServer: number;
  endAt?: number;
  status?: number;
  failure?: string;
  canceled?: boolean;
  /** From asking to sending its headers, ms: time in the browser's queue, connecting and stalled. */
  queuedMs?: number;
  reused?: boolean;
  connectionId?: number;
  /** How long its connection had been idle when it was reused, ms. */
  idleMs?: number;
  fromServiceWorker?: boolean;
  /** The API's X-Request-ID on its answer: ties it to the access log exactly. */
  rid?: string;
  /** For a CORS preflight (OPTIONS sent by the browser), the id of the request it was sent for. */
  preflightFor?: string;
}

export interface Probe {
  mainThread: "answered" | "blocked" | "closed";
  serviceWorker: boolean;
}

function split(url: string): { origin: string; path: string } | null {
  try {
    const u = new URL(url);
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    return { origin: u.origin, path: u.pathname };
  } catch {
    return null;
  }
}

const secs = (ms: number) => `${(ms / 1000).toFixed(1)}s`;

export class NetworkWatch {
  readonly entries = new Map<string, Entry>();
  /** The main frame's current document, and when each document replaced the one before. */
  docLoader = "";
  readonly documents: { at: number; loaderId: string }[] = [];
  private mainFrame = "";
  private readonly early = new Set<string>(); // extraInfo seen before its request
  private readonly lastEnd = new Map<number, number>(); // connection id -> Chrome seconds it last finished a response
  setupMs = 0;

  private constructor(private readonly page: Page, readonly started: number) {}

  /** Null where Chrome's protocol isn't available (another browser): the old waiting list stays. */
  static async attach(page: Page, started: number): Promise<NetworkWatch | null> {
    const t0 = Date.now();
    let cdp: CDPSession;
    try {
      cdp = await page.context().newCDPSession(page);
    } catch {
      return null;
    }
    const w = new NetworkWatch(page, started);
    cdp.on("Network.requestWillBeSent", (e) => {
      const where = split(e.request.url);
      if (!where) return;
      const old = w.entries.get(e.requestId); // a redirect keeps its id
      const open = [...w.entries.values()].filter((x) => x.origin === where.origin && x.onNetwork && x.endAt === undefined && x.id !== e.requestId).length;
      w.entries.set(e.requestId, {
        id: e.requestId, method: e.request.method, path: where.path, origin: where.origin, type: e.type ?? "Other",
        loaderId: e.loaderId, sentAt: old?.sentAt ?? Date.now(), ts: old?.ts ?? e.timestamp,
        onNetwork: w.early.delete(e.requestId), openSameServer: old?.openSameServer ?? open,
        preflightFor: e.initiator?.type === "preflight" ? e.initiator.requestId : undefined,
      });
    });
    cdp.on("Network.requestWillBeSentExtraInfo", (e) => {
      const x = w.entries.get(e.requestId);
      if (x) x.onNetwork = true;
      else w.early.add(e.requestId);
    });
    cdp.on("Network.responseReceived", (e) => {
      const x = w.entries.get(e.requestId);
      if (!x) return;
      const r = e.response;
      x.status = r.status;
      x.reused = r.connectionReused;
      x.connectionId = r.connectionId;
      x.fromServiceWorker = r.fromServiceWorker ?? false;
      x.onNetwork = true;
      const rid = Object.entries(r.headers ?? {}).find(([k]) => k.toLowerCase() === "x-request-id")?.[1];
      if (typeof rid === "string") x.rid = rid;
      if (r.timing) {
        x.queuedMs = Math.max(0, Math.round((r.timing.requestTime - x.ts) * 1000 + r.timing.sendStart));
        const last = w.lastEnd.get(r.connectionId);
        if (r.connectionReused && last !== undefined) x.idleMs = Math.max(0, Math.round((r.timing.requestTime - last) * 1000));
      }
    });
    cdp.on("Network.loadingFinished", (e) => {
      const x = w.entries.get(e.requestId);
      if (!x) return;
      x.endAt = Date.now();
      if (x.connectionId !== undefined) w.lastEnd.set(x.connectionId, e.timestamp);
    });
    cdp.on("Network.loadingFailed", (e) => {
      const x = w.entries.get(e.requestId);
      if (!x) return;
      x.endAt = Date.now();
      x.failure = e.errorText;
      x.canceled = e.canceled ?? false;
    });
    cdp.on("Page.frameNavigated", (e) => {
      if (e.frame.parentId || (w.mainFrame && e.frame.id !== w.mainFrame)) return;
      w.mainFrame = e.frame.id;
      w.docLoader = e.frame.loaderId;
      w.documents.push({ at: Date.now(), loaderId: e.frame.loaderId });
    });
    try {
      await cdp.send("Network.enable");
      await cdp.send("Page.enable");
      const tree = await cdp.send("Page.getFrameTree");
      w.mainFrame = tree.frameTree.frame.id;
      w.docLoader ||= tree.frameTree.frame.loaderId;
    } catch {
      return null;
    }
    w.setupMs = Date.now() - t0;
    return w;
  }

  /** Is the page's main thread answering, and does a service worker control it? At most PROBE_MS. */
  async probe(): Promise<Probe> {
    if (this.page.isClosed()) return { mainThread: "closed", serviceWorker: false };
    const answer = this.page
      .evaluate(() => Boolean(navigator.serviceWorker?.controller))
      .then((sw) => ({ mainThread: "answered" as const, serviceWorker: sw }))
      .catch(() => ({ mainThread: "closed" as const, serviceWorker: false }));
    const late = new Promise<Probe>((resolve) => setTimeout(() => resolve({ mainThread: "blocked", serviceWorker: false }), PROBE_MS));
    return Promise.race([answer, late]);
  }

  /** Requests to the same server on the network and unfinished now (what holds its connections). */
  openTo(origin: string, except: string): Entry[] {
    return [...this.entries.values()].filter((x) => x.origin === origin && x.onNetwork && x.endAt === undefined && x.id !== except);
  }

  /** When it ended: its own end, or for a preflight Chrome reported no end for, its request's. */
  endOf(e: Entry): number | undefined {
    if (e.endAt !== undefined || e.preflightFor === undefined) return e.endAt;
    return this.entries.get(e.preflightFor)?.endAt;
  }

  /** The unfinished preflight a request is waiting for, if it is. */
  private preflightOf(e: Entry): Entry | undefined {
    return [...this.entries.values()].find((x) => x.preflightFor === e.id && this.endOf(x) === undefined);
  }

  /** The document that replaced the one this request came from, if one did while it was open. */
  replacedBy(e: Entry): { at: number; loaderId: string } | undefined {
    if (this.endOf(e) !== undefined || e.type === "Document" || e.loaderId === this.docLoader) return undefined;
    return this.documents.find((d) => d.at >= e.sentAt && d.loaderId !== e.loaderId);
  }

  /** Why this one waited, as one line: which explanation it matches, with the numbers that show it. */
  why(e: Entry, probe: Probe, server: ServerLog | null, now = Date.now()): string {
    const replaced = this.replacedBy(e);
    if (e.fromServiceWorker || (e.endAt === undefined && probe.serviceWorker)) {
      return "H3 service worker: the page's service worker handled it";
    }
    if (replaced) {
      return `H6 from an earlier page: asked for ${secs(replaced.at - e.sentAt)} before the page was replaced (+${secs(replaced.at - this.started)}); its outcome went with that page, so this isn't a stall${server?.seen(e) ?? ""}`;
    }
    const main = e.preflightFor === undefined ? undefined : this.entries.get(e.preflightFor);
    if (main && e.endAt === undefined && main.endAt !== undefined) {
      const outcome = main.failure ? `failed (${main.failure}${main.canceled ? ", canceled by the page" : ""})` : `was answered ${main.status ?? ""}`.trimEnd();
      return `a CORS preflight for ${main.method} ${main.path}, which ${outcome} ${secs(main.endAt - e.sentAt)} after the preflight was sent: Chrome reports no end for a preflight whose request ended first, so it ended then and this isn't a stall`;
    }
    if (e.failure && SERVER_CLOSED.test(e.failure)) {
      const idle = this.idleConnectionsTo(e.origin, e.sentAt);
      return `H2 the server closed the connection under it (${e.failure})${idle}`;
    }
    if (e.endAt === undefined && probe.mainThread === "blocked") {
      return `H5 the page's main thread is blocked (it didn't answer in ${PROBE_MS} ms), so what it asked for isn't sent or heard back${e.onNetwork ? " (this one was sent)" : ""}`;
    }
    const preflight = e.endAt === undefined && !e.onNetwork ? this.preflightOf(e) : undefined;
    if (preflight) {
      return `waiting for its CORS preflight (OPTIONS ${preflight.path}, sent +${secs(preflight.sentAt - this.started)}): the browser sends it once the preflight is answered`;
    }
    if (e.endAt === undefined && !e.onNetwork) {
      const open = this.openTo(e.origin, e.id);
      const most = Math.max(open.length, e.openSameServer);
      if (most >= PER_SERVER) {
        return `H1 queued in the browser: ${most} requests to ${e.origin} were already open (Chrome sends at most ${PER_SERVER} at once to one server): ${open.slice(0, PER_SERVER).map((o) => `${o.method} ${o.path} (${secs(now - o.sentAt)})`).join(", ")}`;
      }
      return `not sent by the browser, with ${most} open to ${e.origin} and the page answering: none of H1-H6 fits`;
    }
    if (e.endAt === undefined) {
      const seen = server?.state(e);
      if (seen === "open") return "sent, and the API is still working on it";
      if (seen === "answered") return "sent, and the API answered a request like it, but the browser hasn't had the answer";
      if (seen === "unseen") return "sent by the browser and never reached the API (lost between them)";
      return `sent to ${e.origin}, no answer yet`;
    }
    const took = e.endAt - e.sentAt;
    if (e.failure) return `failed after ${secs(took)}: ${e.failure}${e.canceled ? " (canceled by the page)" : ""}`;
    if ((e.queuedMs ?? 0) >= took / 2) {
      return e.openSameServer >= PER_SERVER
        ? `H1 waited ${secs(e.queuedMs ?? 0)} in the browser behind ${e.openSameServer} open requests to ${e.origin}, then took ${secs(took - (e.queuedMs ?? 0))}`
        : `waited ${secs(e.queuedMs ?? 0)} before being sent (connecting or queued), then took ${secs(took - (e.queuedMs ?? 0))}`;
    }
    return `the server took most of ${secs(took)} (sent after ${secs(e.queuedMs ?? 0)}${e.reused ? `, on a reused connection idle ${secs(e.idleMs ?? 0)}` : ", on a new connection"})`;
  }

  private idleConnectionsTo(origin: string, at: number): string {
    const before = [...this.entries.values()].filter((x) => x.origin === origin && x.endAt !== undefined && x.endAt <= at);
    if (before.length === 0) return "";
    const last = Math.max(...before.map((x) => x.endAt ?? 0));
    return `; the last answer from ${origin} came ${secs(at - last)} earlier (servers here close idle connections after 5 s)`;
  }

  /** Lines for requests still waiting (any age) and for any slower than `slowMs`, each with why. */
  async report(server: ServerLog | null, slowMs = SLOW_MS): Promise<{ waiting: string[]; slow: string[]; ms: number }> {
    const t0 = Date.now();
    const probe = await this.probe();
    const now = Date.now();
    const line = (e: Entry) => {
      const end = this.endOf(e);
      return `${e.method} ${e.path} [${e.type}] ${end === undefined ? `waiting ${secs(now - e.sentAt)}` : `took ${secs(end - e.sentAt)}`} (+${secs(e.sentAt - this.started)}): ${this.why(e, probe, server, now)}`;
    };
    const all = [...this.entries.values()].sort((a, b) => a.sentAt - b.sentAt);
    server?.claim(all.map((e) => e.rid));
    const waiting = all.filter((e) => this.endOf(e) === undefined).map(line);
    // Requests a replaced page left behind never report an end; they aren't slow, so they're counted,
    // not listed, among the slow ones.
    const orphans = all.filter((e) => this.replacedBy(e)).length;
    const slow = all.filter((e) => !this.replacedBy(e) && (this.endOf(e) ?? now) - e.sentAt >= slowMs).map(line);
    if (slow.length && orphans) slow.push(`(and ${orphans} request${orphans === 1 ? "" : "s"} from replaced pages that never reported an end: H6, not slow)`);
    if (probe.mainThread === "blocked") waiting.push(`(the page's main thread didn't answer in ${PROBE_MS} ms)`);
    return { waiting, slow, ms: Date.now() - t0 };
  }
}

/**
 * The suite API's access log (start and finish of each request; ACCESS_LOG_FILE): whether a browser
 * request like this one (method and path, started after the browser asked) reached the API, and
 * whether it was answered. Each log entry is matched to one browser request at most.
 */
export class ServerLog {
  private readonly starts: { rid: string; method: string; path: string; at: number; done: boolean; used: boolean }[] = [];

  constructor(file: string, private readonly apiOrigin: string, private readonly started: number) {
    let text: string;
    try { text = readFileSync(file, "utf8"); } catch { return; }
    const done = new Set<string>();
    const rows: { msg?: string; request_id?: string; method?: string; path?: string; at?: number }[] = [];
    for (const raw of text.split("\n")) {
      try { rows.push(JSON.parse(raw)); } catch { /* a partial line */ }
    }
    for (const r of rows) if (r.msg === "request" && r.request_id) done.add(r.request_id);
    for (const r of rows) {
      if (r.msg === "request_started" && r.request_id && typeof r.at === "number" && r.method && r.path) {
        this.starts.push({ rid: r.request_id, method: r.method, path: r.path, at: r.at * 1000, done: done.has(r.request_id), used: false });
      }
    }
  }

  /** Log entries the browser already has answers for (by their X-Request-ID): never matched again. */
  claim(rids: (string | undefined)[]): void {
    const known = new Set(rids.filter(Boolean));
    for (const s of this.starts) if (known.has(s.rid)) s.used = true;
  }

  private match(e: Entry) {
    if (e.origin !== this.apiOrigin || e.method === "OPTIONS") return null; // preflights aren't in the log
    const hit = this.starts.find((s) => !s.used && s.method === e.method && s.path === e.path && s.at >= e.sentAt - 50);
    if (hit) hit.used = true;
    return hit ?? null;
  }

  state(e: Entry): "open" | "answered" | "unseen" | null {
    if (e.origin !== this.apiOrigin || e.method === "OPTIONS") return null;
    const hit = this.match(e);
    return hit ? (hit.done ? "answered" : "open") : "unseen";
  }

  seen(e: Entry): string {
    if (e.origin !== this.apiOrigin) return "";
    if (e.method === "OPTIONS") return " (a CORS preflight: the API's log doesn't list those)";
    const hit = this.match(e);
    if (!hit) return "; the API never saw it";
    return `; the API got it at +${secs(hit.at - this.started)} and ${hit.done ? "answered it" : "is still working on it"}`;
  }
}

/**
 * Server-side open connections per port, from the kernel's socket table (Linux; elsewhere "not
 * available"): how many connections the dev server and the API hold, to set against the browser's.
 */
export function openConnections(ports: Record<string, number>): string {
  let rows: string[] = [];
  try {
    rows = ["/proc/net/tcp", "/proc/net/tcp6"].flatMap((f) => { try { return readFileSync(f, "utf8").split("\n").slice(1); } catch { return []; } });
  } catch {
    return "(open connections not available here)";
  }
  if (rows.length === 0) return "(open connections not available here)";
  const counts = Object.entries(ports).map(([name, port]) => {
    const hex = port.toString(16).toUpperCase().padStart(4, "0");
    const n = rows.filter((r) => {
      const cols = r.trim().split(/\s+/);
      return cols[1]?.endsWith(`:${hex}`) && cols[3] === "01"; // local port, ESTABLISHED
    }).length;
    return `${name} :${port} ${n}`;
  });
  return `server-side open connections: ${counts.join(", ")}`;
}
