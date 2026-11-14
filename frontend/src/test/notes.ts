/** In-memory notes API for tests: revisions, 409 conflicts, undo, and switchable failures. */
import { http, HttpResponse } from "msw";

import type { Note } from "@/api/types";

const API = "http://localhost:8000";
export const noteStore = {
  notes: [] as Note[], deleted: [] as Note[], failSaves: 0, seq: 0, requests: [] as string[],
  /** Keyed creates, as the server keeps them: key → the note it made. */
  keys: new Map<string, string>(),
  /** Make the next create, then lose its reply (the server did it; the page never hears). */
  dropNextCreateReply: false,
  bodies: [] as Record<string, unknown>[],
};
export function resetNoteStore() {
  noteStore.notes = [];
  noteStore.deleted = [];
  noteStore.failSaves = 0;
  noteStore.seq = 0;
  noteStore.requests = [];
  noteStore.keys = new Map();
  noteStore.dropNextCreateReply = false;
  noteStore.bodies = [];
}

export function makeNote(over: Partial<Note> = {}): Note {
  const now = new Date().toISOString();
  return {
    id: `n-${++noteStore.seq}`, title: "Untitled note", snippet: "", tags: [], source: null, pinned: false, archived: false,
    revision: 1, created_at: now, updated_at: now, body: "", reflection: "", excerpt: null, excerpt_kind: null, key_points: null, ...over,
  };
}

const err = (status: number, code: string, message: string, details: unknown = null) =>
  HttpResponse.json({ error: { code, message, request_id: "r", details } }, { status });

export const noteHandlers = [
  http.get(`${API}/api/v1/me/notes`, ({ request }) => {
    const p = new URL(request.url).searchParams;
    const words = (p.get("q") ?? "").toLowerCase().split(/\s+/).filter(Boolean);
    const status = p.get("status") ?? "active";
    const items = noteStore.notes
      .filter((n) => status === "all" || n.archived === (status === "archived"))
      .filter((n) => words.every((w) => `${n.title} ${n.body} ${n.reflection} ${n.tags.join(" ")}`.toLowerCase().includes(w)))
      .filter((n) => !p.get("tag") || n.tags.includes(p.get("tag")!))
      .filter((n) => !p.get("source_id") || n.source?.id === p.get("source_id"));
    const tags = new Map<string, number>();
    for (const n of noteStore.notes) for (const t of n.tags) tags.set(t, (tags.get(t) ?? 0) + 1);
    return HttpResponse.json({
      items: [...items].sort((a, b) => Number(b.pinned) - Number(a.pinned)), total: items.length, page: 1, page_size: 100,
      tags: [...tags].map(([tag, count]) => ({ tag, count })), careers: [], pinned_limit: 5,
    });
  }),
  http.post(`${API}/api/v1/me/notes`, async ({ request }) => {
    noteStore.requests.push("POST");
    if (noteStore.failSaves > 0) { noteStore.failSaves--; return err(503, "unavailable", "The server is busy."); }
    const body = (await request.json()) as Partial<Note> & { source?: { type: "question"; id: string; track?: string }; client_request_id?: string };
    noteStore.bodies.push(body as Record<string, unknown>);
    const key = body.client_request_id;
    if (key && noteStore.keys.has(key)) {
      const made = noteStore.notes.find((x) => x.id === noteStore.keys.get(key));
      return made ? HttpResponse.json(made) : err(410, "copy_deleted", "That copy was made, then deleted. Nothing was made again.");
    }
    const n = makeNote({
      title: body.title || "Untitled note", body: body.body ?? "", reflection: body.reflection ?? "", tags: body.tags ?? [],
      excerpt: body.excerpt ?? null, excerpt_kind: body.excerpt_kind ?? null,
      source: body.source ? { type: body.source.type, id: body.source.id, track: body.source.track ?? null, version: null, title: "A time patient assessment mattered", href: `/careers/${body.source.track}/questions/${body.source.id}`, available: true, career_title: "Registered Nurse" } : null,
    });
    noteStore.notes.unshift(n);
    if (key) noteStore.keys.set(key, n.id);
    if (noteStore.dropNextCreateReply) {
      noteStore.dropNextCreateReply = false;
      return HttpResponse.error();
    }
    return HttpResponse.json(n, { status: 201 });
  }),
  http.get(`${API}/api/v1/me/notes/:id`, ({ params }) => {
    const n = noteStore.notes.find((x) => x.id === params.id);
    return n ? HttpResponse.json(n) : err(404, "not_found", "Note not found");
  }),
  http.patch(`${API}/api/v1/me/notes/:id`, async ({ params, request }) => {
    noteStore.requests.push("PATCH");
    const n = noteStore.notes.find((x) => x.id === params.id);
    if (!n) return err(404, "not_found", "Note not found");
    if (noteStore.failSaves > 0) { noteStore.failSaves--; return err(503, "unavailable", "The server is busy."); }
    const body = (await request.json()) as Partial<Note> & { base_revision?: number };
    const text = ["title", "body", "reflection", "tags", "key_points"].some((k) => k in body);
    if (text && body.base_revision !== n.revision) return err(409, "note_conflict", "This note was changed somewhere else.", { current: n });
    const rest: Partial<Note> & { base_revision?: number } = { ...body };
    delete rest.base_revision;
    Object.assign(n, rest, { title: rest.title === undefined ? n.title : rest.title || "Untitled note", updated_at: new Date().toISOString() });
    if (text) n.revision += 1;
    return HttpResponse.json(n);
  }),
  http.delete(`${API}/api/v1/me/notes/:id`, ({ params }) => {
    const n = noteStore.notes.find((x) => x.id === params.id);
    if (!n) return err(404, "not_found", "Note not found");
    noteStore.notes = noteStore.notes.filter((x) => x !== n);
    noteStore.deleted.push(n);
    return HttpResponse.json({ id: n.id, restorable_until: new Date(Date.now() + 600_000).toISOString() });
  }),
  http.post(`${API}/api/v1/me/notes/:id/restore`, ({ params }) => {
    const n = noteStore.deleted.find((x) => x.id === params.id);
    if (!n) return err(404, "not_found", "Nothing to restore");
    noteStore.deleted = noteStore.deleted.filter((x) => x !== n);
    noteStore.notes.unshift(n);
    return HttpResponse.json(n);
  }),
  http.post(`${API}/api/v1/me/notes/:id/key-points`, () =>
    HttpResponse.json({ points: ["Next time I should escalate earlier."], method: "Built in, no AI model." })),
];
