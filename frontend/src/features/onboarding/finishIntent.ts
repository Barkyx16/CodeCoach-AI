/**
 * "This account finished the introduction, but the server may not have heard yet." Finish closes
 * the tour at once and saves in the background; a reload in the same instant can cancel that
 * save, and the server would still say the tour is running. This note survives the reload so the
 * next load can send "complete" again (the server applies it only to a running or paused tour,
 * so sending it twice is harmless) and the tour isn't shown in the meantime.
 *
 * It is never a confirmation: only the server's reply clears it as done. It holds an account id
 * and a time, nothing else, and is read only for the signed-in account.
 */
const KEY = "codecoach.tour-finish-pending";

type Notes = Record<string, { at: string }>;

function read(): Notes {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Notes) : {};
  } catch {
    return {}; // storage blocked or the value was damaged: no note
  }
}

function write(notes: Notes) {
  try {
    if (Object.keys(notes).length) localStorage.setItem(KEY, JSON.stringify(notes));
    else localStorage.removeItem(KEY);
  } catch {
    /* storage blocked: the finish still saves normally; it just can't be repeated after a reload */
  }
}

export function markFinishPending(accountId: string | undefined) {
  if (!accountId) return;
  write({ ...read(), [accountId]: { at: new Date().toISOString() } });
}

export function isFinishPending(accountId: string | undefined): boolean {
  return !!accountId && accountId in read();
}

export function clearFinishPending(accountId: string | undefined) {
  if (!accountId) return;
  const notes = read();
  if (!(accountId in notes)) return;
  delete notes[accountId];
  write(notes);
}
