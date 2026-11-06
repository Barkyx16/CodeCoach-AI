/** A small in-memory stand-in for the explorer, bookmarks and collections endpoints. */
import { http, HttpResponse } from "msw";

import type { Bookmark, Collection, CollectionItem, ExploreResult, ItemStatus, MyExploreResult, SavedItemRef } from "@/api/types";

import { nurseQuestions } from "./fixtures";

const API = "http://localhost:8000";
const KINDS = { knowledge: "Knowledge", behavioral: "Behavioral", situational: "Scenario", leadership: "Leadership", motivation: "Motivation" } as const;
const LEVELS = { easy: "Easy", medium: "Medium", hard: "Hard" } as const;
const SKILL: Record<string, string> = { "e-good-0": "patient assessment", "e-time-0": "patient assessment", "m-pressure-0": "Judgment under pressure" };

export const store = {
  bookmarks: [] as Bookmark[],
  collections: [] as Collection[],
  failBookmarks: false,
  seq: 0,
};

export function resetExploreStore() {
  store.bookmarks = [];
  store.collections = [];
  store.failBookmarks = false;
  store.seq = 0;
}

const err = (status: number, code: string, message: string) =>
  HttpResponse.json({ error: { code, message, request_id: "r", details: null } }, { status });

function titleOf(ref: SavedItemRef) {
  if (ref.item_type === "problem") return ref.ref_id === "two-sum" ? "Two Sum" : null;
  return nurseQuestions.find((q) => q.id === ref.ref_id)?.title ?? null;
}

function hrefOf(ref: SavedItemRef) {
  return ref.item_type === "problem" ? `/problems/${ref.ref_id}` : `/careers/${ref.track}/questions/${ref.ref_id}`;
}

function status(): Record<string, ItemStatus> {
  const out: Record<string, ItemStatus> = {};
  for (const q of nurseQuestions) {
    const bookmarked = store.bookmarks.some((b) => b.item_type === "question" && b.ref_id === q.id);
    const collection_ids = store.collections.filter((c) => c.item_list.some((i) => i.ref_id === q.id)).map((c) => c.id);
    out[q.id] = {
      best_score: q.best_score ?? null, attempts: q.best_score === null || q.best_score === undefined ? 0 : 1,
      // Fixtures answered with a scoreable answer (the eligibility fields follow best_score).
      best_scored: q.best_scored ?? q.best_score ?? null,
      score_status: q.score_status ?? (q.best_score === null || q.best_score === undefined ? null : "scored"),
      last_practiced_at: q.best_score ? "2026-11-01T09:00:00Z" : null, bookmarked, collection_ids,
    };
  }
  return out;
}

function explore(url: URL, personal: boolean): ExploreResult | MyExploreResult {
  const p = url.searchParams;
  const q = (p.get("q") ?? "").toLowerCase().trim();
  const st = status();
  const words = q.split(/\s+/).filter(Boolean);
  const keep = (x: (typeof nurseQuestions)[number], skip = "") =>
    words.every((w) => `${x.title} ${x.prompt} ${SKILL[x.id]}`.toLowerCase().includes(w))
    && (skip === "difficulty" || !p.get("difficulty") || x.difficulty === p.get("difficulty"))
    && (skip === "kind" || !p.get("kind") || x.kind === p.get("kind"))
    && (skip === "skill" || !p.get("skill") || SKILL[x.id] === p.get("skill"))
    && (!personal || !p.get("status")
      || (p.get("status") === "bookmarked" && st[x.id]!.bookmarked)
      || (p.get("status") === "attempted" && st[x.id]!.attempts > 0)
      || (p.get("status") === "unattempted" && st[x.id]!.attempts === 0));
  const rows = nurseQuestions.filter((x) => keep(x));
  const size = Number(p.get("page_size") ?? 20);
  const items = rows.slice(0, size).map((x) => ({
    id: x.id, title: x.title, prompt: x.prompt, difficulty: x.difficulty, kind: x.kind, skills: [SKILL[x.id]!], tags: [], estimated_minutes: null,
  }));
  const facet = (field: "difficulty" | "kind" | "skill", values: Record<string, string>) =>
    Object.entries(values).map(([value, label]) => ({
      value, label,
      count: nurseQuestions.filter((x) => keep(x, field) && (field === "skill" ? SKILL[x.id] === value : x[field] === value)).length,
    }));
  const explanation = [
    q && `Matching “${q}” in titles, skills, tags and question text`,
    p.get("difficulty") && `Difficulty: ${LEVELS[p.get("difficulty") as keyof typeof LEVELS]}`,
    p.get("kind") && `Format: ${KINDS[p.get("kind") as keyof typeof KINDS]}`,
    p.get("skill") && `Skill: ${p.get("skill")}`,
  ].filter(Boolean) as string[];
  const result: ExploreResult = {
    track: "registered-nurse", career_title: "Registered Nurse", items, total: rows.length, page: 1, page_size: size,
    facets: {
      difficulty: facet("difficulty", LEVELS), kind: facet("kind", KINDS),
      skill: facet("skill", { "patient assessment": "Patient assessment", "Judgment under pressure": "Judgment under pressure" }),
    },
    explanation, suggestions: rows.length ? [] : ["Try fewer or more general words.", "Remove a filter to widen the results."],
    sorts: [...(q ? ["relevance" as const] : []), "library" as const, ...(personal ? ["last_practiced" as const, "lowest_score" as const] : [])],
  };
  return personal ? { ...result, status: Object.fromEntries(items.map((i) => [i.id, st[i.id]!])) } : result;
}

function summary(c: Collection, ref?: SavedItemRef) {
  const { id, name, queue_position, queue_started, updated_at } = c;
  return { id, name, queue_position, queue_started, updated_at, items: c.item_list.length, contains: ref ? c.item_list.some((i) => i.item_type === ref.item_type && i.ref_id === ref.ref_id) : null };
}

function fresh(c: Collection): Collection {
  c.items = c.item_list.length;
  c.queue_done = c.item_list.filter((i) => i.queue_done).length;
  c.item_list.forEach((i, n) => { i.position = n; });
  c.updated_at = new Date().toISOString();
  return structuredClone(c);
}

const find = (id: string) => store.collections.find((c) => c.id === id);

export const exploreHandlers = [
  http.get(`${API}/api/v1/careers/:track/explore`, ({ request }) => HttpResponse.json(explore(new URL(request.url), false))),
  http.get(`${API}/api/v1/me/explore/:track`, ({ request }) => HttpResponse.json(explore(new URL(request.url), true))),
  http.get(`${API}/api/v1/me/bookmarks`, () => HttpResponse.json(store.bookmarks)),
  http.put(`${API}/api/v1/me/bookmarks`, async ({ request }) => {
    if (store.failBookmarks) return err(503, "unavailable", "The service is busy. Try again.");
    const ref = (await request.json()) as SavedItemRef;
    const title = titleOf(ref);
    if (!title) return err(404, "not_found", "That item isn't in the library");
    if (!store.bookmarks.some((b) => b.item_type === ref.item_type && b.ref_id === ref.ref_id)) {
      store.bookmarks.unshift({ item_type: ref.item_type, track: ref.track ?? "", ref_id: ref.ref_id, title, href: hrefOf(ref), available: true, created_at: new Date().toISOString() });
    }
    return HttpResponse.json(store.bookmarks);
  }),
  http.delete(`${API}/api/v1/me/bookmarks`, ({ request }) => {
    if (store.failBookmarks) return err(503, "unavailable", "The service is busy. Try again.");
    const p = new URL(request.url).searchParams;
    store.bookmarks = store.bookmarks.filter((b) => !(b.item_type === p.get("item_type") && b.ref_id === p.get("ref_id")));
    return HttpResponse.json(store.bookmarks);
  }),
  http.get(`${API}/api/v1/me/collections`, ({ request }) => {
    const p = new URL(request.url).searchParams;
    const ref = p.get("ref_id") ? { item_type: p.get("item_type") as "question", track: p.get("track") ?? "", ref_id: p.get("ref_id")! } : undefined;
    return HttpResponse.json(store.collections.map((c) => summary(c, ref)));
  }),
  http.post(`${API}/api/v1/me/collections`, async ({ request }) => {
    const { name } = (await request.json()) as { name: string };
    const c: Collection = {
      id: `c-${++store.seq}`, name: name.trim() || "Untitled", items: 0, queue_position: 0, queue_started: false,
      updated_at: new Date().toISOString(), item_list: [], queue_done: 0, contains: null,
    };
    store.collections.unshift(c);
    return HttpResponse.json(fresh(c), { status: 201 });
  }),
  http.get(`${API}/api/v1/me/collections/:id`, ({ params }) => {
    const c = find(String(params.id));
    return c ? HttpResponse.json(fresh(c)) : err(404, "not_found", "Collection not found");
  }),
  http.patch(`${API}/api/v1/me/collections/:id`, async ({ params, request }) => {
    const c = find(String(params.id));
    if (!c) return err(404, "not_found", "Collection not found");
    c.name = ((await request.json()) as { name: string }).name;
    return HttpResponse.json(fresh(c));
  }),
  http.delete(`${API}/api/v1/me/collections/:id`, ({ params }) => {
    store.collections = store.collections.filter((c) => c.id !== params.id);
    return new HttpResponse(null, { status: 204 });
  }),
  http.post(`${API}/api/v1/me/collections/:id/items`, async ({ params, request }) => {
    const c = find(String(params.id));
    if (!c) return err(404, "not_found", "Collection not found");
    const ref = (await request.json()) as SavedItemRef;
    if (c.item_list.some((i) => i.item_type === ref.item_type && i.ref_id === ref.ref_id)) {
      return err(409, "already_in_collection", `It's already in “${c.name}”.`);
    }
    const title = titleOf(ref);
    if (!title) return err(404, "not_found", "That item isn't in the library");
    const item: CollectionItem = {
      id: `i-${++store.seq}`, item_type: ref.item_type, track: ref.item_type === "question" ? ref.track ?? "" : "", ref_id: ref.ref_id,
      position: c.item_list.length, title, href: hrefOf(ref), available: true, unavailable_reason: null, queue_done: false, practiced_since_added: false,
    };
    c.item_list.push(item);
    return HttpResponse.json(fresh(c));
  }),
  http.delete(`${API}/api/v1/me/collections/:id/items/:item`, ({ params }) => {
    const c = find(String(params.id));
    if (!c) return err(404, "not_found", "Collection not found");
    c.item_list = c.item_list.filter((i) => i.id !== params.item);
    c.queue_position = Math.min(c.queue_position, Math.max(0, c.item_list.length - 1));
    return HttpResponse.json(fresh(c));
  }),
  http.put(`${API}/api/v1/me/collections/:id/order`, async ({ params, request }) => {
    const c = find(String(params.id));
    if (!c) return err(404, "not_found", "Collection not found");
    const { item_ids } = (await request.json()) as { item_ids: string[] };
    c.item_list = item_ids.map((id) => c.item_list.find((i) => i.id === id)!);
    return HttpResponse.json(fresh(c));
  }),
  http.put(`${API}/api/v1/me/collections/:id/queue`, async ({ params, request }) => {
    const c = find(String(params.id));
    if (!c) return err(404, "not_found", "Collection not found");
    c.queue_position = Math.min(((await request.json()) as { position: number }).position, c.item_list.length - 1);
    c.queue_started = true;
    return HttpResponse.json(fresh(c));
  }),
  http.put(`${API}/api/v1/me/collections/:id/items/:item/done`, async ({ params, request }) => {
    const c = find(String(params.id));
    const item = c?.item_list.find((i) => i.id === params.item);
    if (!c || !item) return err(404, "not_found", "Item not found");
    item.queue_done = ((await request.json()) as { done: boolean }).done;
    return HttpResponse.json(fresh(c));
  }),
];
