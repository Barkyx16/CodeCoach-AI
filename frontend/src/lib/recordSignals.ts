/**
 * Same-account "this record changed" hints between this browser's tabs (Volume 11, prompt 9;
 * docs/FRESHNESS.md). A tab that saves, archives or deletes a record says so on a BroadcastChannel:
 * which account, which record (type and id), what kind of change and the new revision. Never the
 * record's content. Other tabs treat it as a hint only: they ask the server again, as themselves,
 * through the usual authorised requests. Another account's hint is ignored. Another device gets no
 * hint at all; it catches up when its tab is focused again or comes back online.
 */
export type RecordType = "story";
export type RecordChange = "saved" | "archived" | "unarchived" | "deleted";
export interface RecordSignal {
  v: 1;
  account: string;
  type: RecordType;
  id: string;
  change: RecordChange;
  revision?: number;
}

const CHANNEL = "codecoach-records";
const TYPES: RecordType[] = ["story"];
const CHANGES: RecordChange[] = ["saved", "archived", "unarchived", "deleted"];

let channel: BroadcastChannel | null | undefined;
function getChannel(): BroadcastChannel | null {
  if (channel === undefined) channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(CHANNEL);
  return channel;
}

/** Only the fields a hint may carry, checked: anything else (or a malformed message) is dropped. */
export function parseSignal(data: unknown): RecordSignal | null {
  if (!data || typeof data !== "object") return null;
  const d = data as Record<string, unknown>;
  if (d.v !== 1 || typeof d.account !== "string" || typeof d.id !== "string" || d.id.length > 64) return null;
  if (!TYPES.includes(d.type as RecordType) || !CHANGES.includes(d.change as RecordChange)) return null;
  const revision = typeof d.revision === "number" && Number.isInteger(d.revision) ? d.revision : undefined;
  return { v: 1, account: d.account, type: d.type as RecordType, id: d.id, change: d.change as RecordChange, revision };
}

/** Tell this browser's other tabs (not this one) that a record changed. */
export function announce(signal: Omit<RecordSignal, "v">): void {
  try {
    getChannel()?.postMessage({ v: 1, account: signal.account, type: signal.type, id: signal.id, change: signal.change, revision: signal.revision });
  } catch {
    /* a closed or unavailable channel: other tabs catch up on focus instead */
  }
}

/**
 * Listen for this account's hints; returns the unsubscribe. On the same channel object announce()
 * sends from: a channel object never receives its own messages, so this tab doesn't act on its own
 * hints (a second object in this tab would hear them, and fetch what it just saved).
 */
export function listen(account: string, onSignal: (s: RecordSignal) => void): () => void {
  const ch = getChannel();
  if (!ch) return () => {};
  const onMessage = (event: MessageEvent) => {
    const s = parseSignal(event.data);
    if (s && s.account === account) onSignal(s);
  };
  ch.addEventListener("message", onMessage);
  return () => ch.removeEventListener("message", onMessage);
}
