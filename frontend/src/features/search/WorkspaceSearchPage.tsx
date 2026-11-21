import { useEffect, useId, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { useWorkspaceSearch } from "@/api/queries";
import type { WorkspaceHit, WorkspaceKind, WorkspaceSearch } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { timeAgo } from "@/lib/format";

import { Highlight } from "./Highlight";

/**
 * Search your saved work (Volume 11, prompt 3; docs/WORKSPACE_SEARCH.md): your own notes, stories,
 * interview-day kits and applications, found by the words in them, on the server (a POST, so the
 * words stay out of the address bar and the logs). Not the question bank, not pages (that's Go to…),
 * and not drafts kept only in this browser.
 *
 * Typing waits a moment before searching; an older search's answer is never shown for a newer
 * one, and a superseded request is cancelled. The words and filters are kept in this tab's history
 * entry, for this account only, so Back from a result brings the search back; they're never put in
 * the address, so a copied link doesn't carry them.
 */

const KINDS: { id: WorkspaceKind; label: string; one: string; many: string }[] = [
  { id: "notes", label: "Notes", one: "note", many: "notes" },
  { id: "stories", label: "Stories", one: "story", many: "stories" },
  { id: "kits", label: "Interview-day kits", one: "kit", many: "kits" },
  { id: "applications", label: "Applications", one: "application", many: "applications" },
];
const ALL: WorkspaceKind[] = KINDS.map((k) => k.id);
const TYPE_LABEL: Record<WorkspaceHit["type"], string> = { note: "Note", story: "Story", kit: "Interview-day kit", application: "Application" };
const KIND_NAME: Record<string, string> = { notes: "notes", stories: "stories", kits: "interview-day kits", applications: "applications" };
const MATCHED: Record<string, string> = { title: "title", tags: "tags", text: "text", reflection: "reflection", source: "question", employer: "employer", role: "role", "next step": "next step" };

interface Kept { userId: string; q: string; kinds: WorkspaceKind[]; archived: boolean }

/** What this history entry remembers, if it's this account's and well formed. */
function keptFor(state: unknown, userId: string): Kept | null {
  const kept = (state as { workspaceSearch?: Partial<Kept> } | null)?.workspaceSearch;
  if (!kept || kept.userId !== userId || typeof kept.q !== "string") return null;
  // As kept, even when empty (the page then says to choose a kind): comparing a normalised copy
  // with what's on screen would never match and replace the entry forever.
  const kinds = Array.isArray(kept.kinds) ? kept.kinds.filter((k): k is WorkspaceKind => ALL.includes(k as WorkspaceKind)) : ALL;
  return { userId, q: kept.q.slice(0, 200), kinds, archived: kept.archived === true };
}

const enough = (q: string) => q.replace(/\s+/g, "").length >= 2;

export function WorkspaceSearchPage() {
  const { user } = useAuth();
  if (!user) return null;
  return <Search key={user.id} userId={user.id} />;
}

function pathOf(hit: WorkspaceHit): string {
  const id = encodeURIComponent(hit.id);
  switch (hit.type) {
    case "note": return `/notes/${id}`;
    case "story": return `/stories/${id}`;
    case "application": return `/applications/${id}`;
    case "kit": return `/applications/${encodeURIComponent(hit.parent_id ?? "")}/events/${id}/kit`;
  }
}

function Search({ userId }: { userId: string }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [initial] = useState(() => keptFor(location.state, userId));
  const [q, setQ] = useState(initial?.q ?? "");
  const [kinds, setKinds] = useState<WorkspaceKind[]>(initial?.kinds.length ? initial.kinds : ALL);
  const [archived, setArchived] = useState(initial?.archived ?? false);
  const typed = useDebouncedValue(q.trim(), 300);
  const ids = useId();

  // Remember the search in this history entry (not the address), so Back from a result restores it.
  useEffect(() => {
    const keep: Kept = { userId, q: typed, kinds, archived };
    const current = keptFor(location.state, userId);
    if (current && current.q === keep.q && current.archived === keep.archived && current.kinds.join() === keep.kinds.join()) return;
    navigate(`${location.pathname}${location.search}`, { replace: true, state: { ...(location.state as object | null), workspaceSearch: keep } });
  }, [typed, kinds, archived, userId, location.pathname, location.search, location.state, navigate]);

  const body = useMemo(() => ({ q: typed, kinds, include_archived: archived, limit: 20 }), [typed, kinds, archived]);
  const ready = enough(typed) && kinds.length > 0;
  const search = useWorkspaceSearch(userId, body, ready);
  const waiting = q.trim() !== typed || (ready && search.isFetching && !search.data);

  function toggle(kind: WorkspaceKind, on: boolean) {
    setKinds((now) => (on ? ALL.filter((k) => k === kind || now.includes(k)) : now.filter((k) => k !== kind)));
  }

  return (
    <div className="page workspace-search">
      <div className="page__header">
        <div>
          <h1 className="page__title">Search your saved work</h1>
          <p className="page__subtitle">Your own notes, stories, interview-day kits and applications. Nobody else's are searched or counted.</p>
        </div>
      </div>

      <form className="card stack workspace-search__form" role="search" aria-label="Search your saved work" onSubmit={(e) => e.preventDefault()}>
        <label className="field" htmlFor={`${ids}-q`}>
          <span>Words to find</span>
          <input id={`${ids}-q`} type="search" className="input" value={q} maxLength={200} autoComplete="off" spellCheck={false}
            aria-describedby={`${ids}-hint`} onChange={(e) => setQ(e.target.value)} placeholder="For example: sepsis handover" />
        </label>
        <p id={`${ids}-hint`} className="subtle">
          Every word has to appear. Drafts kept only in this browser aren't searched (they're listed in <Link to="/settings/data">Your data</Link>).
        </p>
        <fieldset className="workspace-search__kinds">
          <legend>Look in</legend>
          {KINDS.map((k) => (
            <label key={k.id} className="checkbox">
              <input type="checkbox" checked={kinds.includes(k.id)} onChange={(e) => toggle(k.id, e.target.checked)} />
              {k.label}
            </label>
          ))}
          <label className="checkbox">
            <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
            Include archived
          </label>
        </fieldset>
      </form>

      <section className="workspace-search__results" aria-labelledby={`${ids}-results`}>
        <h2 id={`${ids}-results`} className="visually-hidden">Results</h2>
        <p className="subtle" role="status">
          {!kinds.length ? "Choose at least one kind of record to look in."
            : !enough(q.trim()) ? (q.trim() ? "Type at least 2 characters." : "")
            : waiting ? "Searching…"
            : search.data ? summary(search.data, kinds)
            : ""}
        </p>
        {search.isError && !waiting && ready && <SearchError error={search.error} onRetry={() => void search.refetch()} />}
        {search.data && ready && !waiting && <Results data={search.data} words={search.data.words} />}
      </section>
    </div>
  );
}

function summary(data: WorkspaceSearch, kinds: WorkspaceKind[]): string {
  const total = Object.values(data.counts).reduce((a, b) => a + b, 0);
  if (!total) return data.unavailable.length ? "Nothing found in what could be searched." : "Nothing saved to your account matches those words.";
  const parts = KINDS.filter((k) => kinds.includes(k.id) && (data.counts[k.id] ?? 0) > 0)
    .map((k) => `${data.counts[k.id]} ${data.counts[k.id] === 1 ? k.one : k.many}`);
  const shown = data.items.length < total ? ` Showing the best ${data.items.length}.` : "";
  return `${total} found: ${parts.join(", ")}.${shown}`;
}

function SearchError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const limited = error instanceof ApiError && error.status === 429;
  return (
    <div className="inline-error" role="alert">
      <p>{limited ? "That's a lot of searches in a minute. Wait a moment, then try again." : "Search isn't working just now. Your saved work isn't affected."}</p>
      <Button size="sm" onClick={onRetry}>Try again</Button>
    </div>
  );
}

function Results({ data, words }: { data: WorkspaceSearch; words: string[] }) {
  return (
    <>
      {data.unavailable.map((k) => <p key={k} className="subtle">Your {KIND_NAME[k] ?? k} couldn't be searched just now; the rest were.</p>)}
      {data.capped.map((k) => <p key={k} className="subtle">Lots of {KIND_NAME[k] ?? k} match; add a word to narrow it down.</p>)}
      {data.items.length > 0 && (
        <ul className="workspace-search__list">
          {data.items.map((hit) => (
            <li key={`${hit.type}:${hit.id}`}>
              <Link to={pathOf(hit)} className="workspace-hit">
                <span className="workspace-hit__meta">
                  {TYPE_LABEL[hit.type]}
                  {hit.state === "archived" && <span className="badge">Archived</span>}
                  {hit.state === "pinned" && <span className="badge">Pinned</span>}
                </span>
                <span className="workspace-hit__title"><Highlight text={hit.title} words={words} /></span>
                {hit.snippet && <span className="workspace-hit__snippet"><Highlight text={hit.snippet} words={words} /></span>}
                <span className="workspace-hit__meta subtle">
                  {[hit.detail, `saved ${timeAgo(hit.at)}`, `found in ${hit.matched.map((m) => MATCHED[m] ?? m).join(", ")}`].filter(Boolean).join(" · ")}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export default WorkspaceSearchPage;
