import { useCallback, useEffect, useRef, useState } from "react";

import { recoveredSave } from "@/lib/conflict";
import { newRequestKey } from "@/lib/requestKey";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import type { Note, NoteInput } from "@/api/types";

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

  const saveMineAsNew = useCallback(async (): Promise<Note | null> => {
    const mine = fieldsRef.current;
    try {
      const copy = await api.createNote({ ...mine, title: `${mine.title.trim() || "Untitled note"} (my version)` });
      takeSaved();
      return copy;
    } catch (e) {
      setError(e);
      return null;
    }
  }, [takeSaved]);

  /** A change made outside the editor (key points accepted): adopt the server's new revision. */
  const adopt = useCallback((n: Note) => {
    serverRef.current = n;
    setServer(n);
  }, []);

  return { fields, server, state, kept, error, conflict, earlierSave, recovery, change, save, restore, discardRecovery, keepMine, takeSaved, saveMineAsNew, adopt };
}
