import { useCallback, useEffect, useRef, useState } from "react";

import { recoveredSave } from "@/lib/conflict";
import { findIntent, fingerprint, forgetIntent, keyForIntent } from "@/lib/pendingIntents";
import { newRequestKey } from "@/lib/requestKey";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import type { Note, NoteInput } from "@/api/types";
import { useAuth } from "@/auth/useAuth";

/**
 * pending: an edit to a saved note couldn't reach the server; it's on this device and is sent
 * once when the connection returns (the revision check turns a clash into a conflict).
 * offline: a new note couldn't be created; it's on this device and waits for "Save now", since
 * a create can't safely be replayed automatically.
 */
export type SaveState = "idle" | "unsaved" | "saving" | "saved" | "error" | "conflict" | "pending" | "offline";
export interface NoteFields { title: string; body: string; reflection: string; tags: string[] }
interface StoredDraft { fields: NoteFields; base: number | null; at: string }

export const EMPTY_FIELDS: NoteFields = { title: "", body: "", reflection: "", tags: [] };
const pick = (n: Note): NoteFields => ({ title: n.title === "Untitled note" ? "" : n.title, body: n.body, reflection: n.reflection, tags: n.tags });
const same = (a: NoteFields, b: NoteFields) =>
  a.title.trim() === b.title.trim() && a.body === b.body && a.reflection === b.reflection && a.tags.join("\n") === b.tags.join("\n");
const empty = (f: NoteFields) => !f.title.trim() && !f.body.trim() && !f.reflection.trim() && f.tags.length === 0;

/**
 * "Keep both" after a conflict: the learner's version saved as a separate note (Volume 8, prompt 4).
 * The exact text chosen is captured when the button is pressed, and that decision gets one key,
 * written to this browser before sending: a double click, a retry after a lost reply, or a retry
 * after a reload sends the same key, and the server returns the copy it made instead of a second.
 * - copying: sent, waiting (the button is disabled);
 * - unknown: no reply: the copy may exist. Check copy (a read) or Retry same copy (same key);
 * - gone: it was made, then deleted: nothing is made again unless the learner asks for a new copy;
 * - failed: refused (not made);
 * - done: made (or found). `newerSince`: the learner typed after pressing it; that text isn't in
 *   the copy and stays in the editor.
 */
export type CopyState =
  | { status: "idle" }
  | { status: "copying"; snapshot: NoteFields }
  | { status: "unknown"; snapshot: NoteFields }
  | { status: "gone"; snapshot: NoteFields }
  | { status: "failed"; snapshot: NoteFields; error: unknown }
  | { status: "done"; id: string; title: string; newerSince: boolean };
const copyTitle = (f: NoteFields) => `${f.title.trim() || "Untitled note"} (my version)`;

function readDraft(key: string): StoredDraft | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as StoredDraft) : null;
  } catch {
    return null;
  }
}
/** False when this browser couldn't keep the copy (private mode, storage full): the page then
 * says so, instead of claiming the text is kept on this device. */
function writeDraft(key: string, d: StoredDraft): boolean {
  try {
    window.localStorage.setItem(key, JSON.stringify(d));
    return true;
  } catch {
    return false;
  }
}
function clearDraft(key: string) {
  try { window.localStorage.removeItem(key); } catch { /* nothing stored */ }
}

/**
 * Autosave for one note. Edits are kept in this browser until the server confirms them (so a
 * failed save or a closed tab can be recovered), saved after a short pause, flushed when the
 * page is left, and never silently overwrite a newer version saved elsewhere: a 409 from the
 * server puts both versions in front of the learner.
 */
export function useNoteAutosave({ initial, createWith, draftKey, onSaved, delayMs = 800 }: {
  initial: Note | null;
  createWith?: Omit<NoteInput, keyof NoteFields>;
  draftKey: string;
  onSaved?: (note: Note) => void;
  delayMs?: number;
}) {
  const [fields, setFields] = useState<NoteFields>(initial ? pick(initial) : EMPTY_FIELDS);
  const [server, setServer] = useState<Note | null>(initial);
  const [state, setState] = useState<SaveState>(initial ? "saved" : "idle");
  const [error, setError] = useState<unknown>(null);
  const [conflict, setConflict] = useState<Note | null>(null);
  const [kept, setKept] = useState(true);
  const [recovery, setRecovery] = useState<StoredDraft | null>(() => {
    const d = readDraft(draftKey);
    if (!d || empty(d.fields)) return null;
    return initial && same(d.fields, pick(initial)) ? null : d;
  });
  const fieldsRef = useRef(fields);
  const serverRef = useRef(server);
  const conflictRef = useRef<Note | null>(null);
  const timer = useRef<number | undefined>(undefined);
  // One key for this editor's create: a retry after a lost response returns the same note.
  const createKey = useRef(newRequestKey());
  // An update sent but not confirmed (its reply was lost: Volume 8, prompt 3). The next save sends
  // exactly it again, with its key, to learn whether it went through, before sending newer text,
  // so the learner's own earlier save is never mistaken for a change made elsewhere.
  const unconfirmed = useRef<{ id: string; base: number; key: string; fields: NoteFields } | null>(null);
  const [earlierSave, setEarlierSave] = useState<number | null>(null);
  const inflight = useRef(false);
  const again = useRef(false);
  const savedCb = useRef(onSaved);
  useEffect(() => { savedCb.current = onSaved; }, [onSaved]);

  const save = useCallback(async (): Promise<void> => {
    window.clearTimeout(timer.current);
    if (inflight.current) {
      again.current = true; // the running save will go round again with the newest text
      return;
    }
    inflight.current = true;
    try {
      for (;;) {
        again.current = false;
        if (conflictRef.current) return;
        const f = fieldsRef.current;
        const s = serverRef.current;
        if (s ? same(f, pick(s)) : empty(f)) {
          setState(s ? "saved" : "idle");
          clearDraft(draftKey);
          return;
        }
        if (typeof navigator !== "undefined" && navigator.onLine === false) {
          // Offline: keep it on this device and say so; don't send a request that can't arrive.
          setState(s ? "pending" : "offline");
          return;
        }
        setState("saving");
        try {
          let result: Note;
          if (s) {
            const u = unconfirmed.current;
            const resend = u && u.id === s.id && u.base === s.revision ? u : null;
            const sent = resend?.fields ?? f;
            const key = resend?.key ?? newRequestKey();
            unconfirmed.current = { id: s.id, base: s.revision, key, fields: sent };
            result = await api.updateNote(s.id, {
              base_revision: s.revision, title: sent.title, body: sent.body, reflection: sent.reflection, tags: sent.tags, client_request_id: key,
            });
            unconfirmed.current = null;
            const recovered = recoveredSave(result);
            if (recovered?.newer) {
              // The earlier save went through, then the note was changed elsewhere: compare.
              conflictRef.current = result;
              setEarlierSave(recovered.accepted);
              setConflict(result);
              setState("conflict");
              return;
            }
          } else {
            result = await api.createNote({ ...createWith, ...f, client_request_id: createKey.current });
          }
          serverRef.current = result;
          setServer(result);
          savedCb.current?.(result);
          setError(null);
          if (!again.current && same(fieldsRef.current, pick(result))) {
            clearDraft(draftKey);
            setState("saved");
            return;
          }
        } catch (e) {
          if (!(e instanceof ApiError && e.code === "network_error")) unconfirmed.current = null; // answered: not lost
          if (e instanceof ApiError && e.code === "note_conflict") {
            setEarlierSave(null);
            const current = (e.details as { current: Note }).current;
            conflictRef.current = current;
            setConflict(current);
            setState("conflict");
          } else if (e instanceof ApiError && e.code === "network_error") {
            setError(null);
            setState(serverRef.current ? "pending" : "offline");
          } else {
            setError(e);
            setState("error");
          }
          return;
        }
      }
    } finally {
      inflight.current = false;
    }
  }, [createWith, draftKey]);

  const change = useCallback((patch: Partial<NoteFields>) => {
    const next = { ...fieldsRef.current, ...patch };
    fieldsRef.current = next;
    setFields(next);
    setKept(writeDraft(draftKey, { fields: next, base: serverRef.current?.revision ?? null, at: new Date().toISOString() }));
    if (conflictRef.current) return;
    setState("unsaved");
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void save(), delayMs);
  }, [delayMs, draftKey, save]);

  // Back online: send a pending edit once. A new note waits for the learner (see SaveState).
  useEffect(() => {
    if (state !== "pending") return;
    const retry = () => void save();
    window.addEventListener("online", retry);
    return () => window.removeEventListener("online", retry);
  }, [state, save]);

  // Leaving the page (in-app navigation or closing the tab): send what's pending with keepalive.
  useEffect(() => {
    const flush = () => {
      window.clearTimeout(timer.current);
      const f = fieldsRef.current;
      const s = serverRef.current;
      if (conflictRef.current || inflight.current) return;
      if (s && !same(f, pick(s))) {
        void api.updateNote(s.id, { base_revision: s.revision, title: f.title, body: f.body, reflection: f.reflection, tags: f.tags }, true)
          .then((n) => { serverRef.current = n; clearDraft(draftKey); })
          .catch(() => { /* the draft stays in this browser for recovery */ });
      } else if (!s && !empty(f)) {
        void api.createNote({ ...createWith, ...f, client_request_id: createKey.current }).then(() => clearDraft(draftKey)).catch(() => {});
      }
    };
    window.addEventListener("pagehide", flush);
    return () => {
      window.removeEventListener("pagehide", flush);
      flush();
    };
  }, [createWith, draftKey]);

  const restore = useCallback(() => {
    if (!recovery) return;
    setRecovery(null);
    fieldsRef.current = recovery.fields;
    setFields(recovery.fields);
    const s = serverRef.current;
    if (s && recovery.base !== s.revision) {
      // The draft started from an older version than the one saved now: let the learner choose.
      conflictRef.current = s;
      setConflict(s);
      setState("conflict");
      return;
    }
    void save();
  }, [recovery, save]);

  const discardRecovery = useCallback(() => { setRecovery(null); clearDraft(draftKey); }, [draftKey]);

  const keepMine = useCallback(() => {
    const c = conflictRef.current;
    if (!c) return;
    serverRef.current = c;
    setServer(c);
    conflictRef.current = null;
    setConflict(null);
    setEarlierSave(null);
    void save();
  }, [save]);

  const takeSaved = useCallback(() => {
    const c = conflictRef.current;
    if (!c) return;
    serverRef.current = c;
    setServer(c);
    fieldsRef.current = pick(c);
    setFields(pick(c));
    conflictRef.current = null;
    setConflict(null);
    setEarlierSave(null);
    clearDraft(draftKey);
    setState("saved");
  }, [draftKey]);

  const { user } = useAuth();
  const [copy, setCopy] = useState<CopyState>({ status: "idle" });
  const copySnap = useRef<NoteFields | null>(null);
  const copyBusy = useRef(false);

  const finishCopy = useCallback((id: string, title: string, snap: NoteFields) => {
    const newerSince = !same(fieldsRef.current, snap);
    setCopy({ status: "done", id, title, newerSince });
    copySnap.current = null;
    // The copy holds exactly what's on the page: this note goes back to the saved version. Text
    // typed after "Keep both" isn't in the copy, so then the editor and the conflict stay as they are.
    if (!newerSince) takeSaved();
  }, [takeSaved]);

  /** Keep both. `again`: retry the same copy (the text captured before, the same key); `fresh`: a
   * deliberate new copy (a new key, even for the same text). Otherwise the text on the page now. */
  const copyMine = useCallback(async (mode: "new" | "again" | "fresh" = "new"): Promise<void> => {
    const sourceId = serverRef.current?.id;
    if (!sourceId || !user || copyBusy.current) return; // one at a time in this tab
    const snap = mode !== "new" && copySnap.current ? copySnap.current : { ...fieldsRef.current };
    copySnap.current = snap;
    if (mode === "fresh") forgetIntent(user.id, "note_copy", sourceId);
    const { key } = keyForIntent(user.id, "note_copy", sourceId, fingerprint(JSON.stringify(snap)));
    copyBusy.current = true;
    setCopy({ status: "copying", snapshot: snap });
    try {
      const made = await api.createNote({ ...snap, title: copyTitle(snap), client_request_id: key, copy_of: sourceId });
      forgetIntent(user.id, "note_copy", sourceId, key);
      finishCopy(made.id, made.title, snap);
    } catch (e) {
      if (e instanceof ApiError && e.code === "network_error") {
        setCopy({ status: "unknown", snapshot: snap }); // the record stays: it may have been made
      } else if (e instanceof ApiError && e.code === "copy_deleted") {
        forgetIntent(user.id, "note_copy", sourceId, key);
        setCopy({ status: "gone", snapshot: snap });
      } else {
        forgetIntent(user.id, "note_copy", sourceId, key);
        setCopy({ status: "failed", snapshot: snap, error: e });
      }
    } finally {
      copyBusy.current = false;
    }
  }, [user, finishCopy]);

  /** Did the copy whose reply was lost arrive? A read: nothing is sent again. */
  const checkCopy = useCallback(async (): Promise<void> => {
    const sourceId = serverRef.current?.id;
    const snap = copySnap.current;
    if (!sourceId || !user || !snap || copyBusy.current) return;
    const intent = findIntent(user.id, "note_copy", sourceId);
    if (!intent) return;
    copyBusy.current = true;
    setCopy({ status: "copying", snapshot: snap });
    try {
      const outcome = await api.requestOutcome(intent.key);
      forgetIntent(user.id, "note_copy", sourceId, intent.key);
      finishCopy(outcome.id, copyTitle(snap), snap);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        // Never made: the same copy can be sent now (same key, so it still can't be made twice).
        setCopy({ status: "failed", snapshot: snap, error: new ApiError(404, "copy_not_made", "The copy never arrived, so nothing was made. Retry it to make it now.") });
      } else {
        setCopy({ status: "unknown", snapshot: snap });
      }
    } finally {
      copyBusy.current = false;
    }
  }, [user, finishCopy]);

  const resetCopy = useCallback(() => { copySnap.current = null; setCopy({ status: "idle" }); }, []);

  /** A change made outside the editor (key points accepted): adopt the server's new revision. */
  const adopt = useCallback((n: Note) => {
    serverRef.current = n;
    setServer(n);
  }, []);

  return { fields, server, state, kept, error, conflict, earlierSave, recovery, change, save, restore, discardRecovery, keepMine, takeSaved, copy, copyMine, checkCopy, resetCopy, adopt };
}
