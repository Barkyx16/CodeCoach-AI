import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { api, type NoteFilters } from "@/api/endpoints";
import { useNotes } from "@/api/queries";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useScrollMemory } from "@/hooks/useScrollMemory";
import { timeAgo } from "@/lib/format";
import { useQueryClient } from "@tanstack/react-query";

const SOURCE_LABEL = { question: "Question", problem: "Coding problem", lesson: "Lesson", interview: "Interview" } as const;
type SourceKind = keyof typeof SOURCE_LABEL;
const isSource = (v: string | null): v is SourceKind => v !== null && v in SOURCE_LABEL;
const isStatus = (v: string | null): v is "active" | "archived" | "all" => v === "active" || v === "archived" || v === "all";
const UNDO_MS = 30_000;

/** The notebook: search, filters (all in the URL), pinned first, and undo for a just-deleted note. */
export function NotesPage() {
  const qc = useQueryClient();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const search = params.get("q") ?? "";
  const q = useDebouncedValue(search.trim(), 300);
  const rawSource = params.get("source");
  const rawStatus = params.get("status");
  const filters: NoteFilters = {
    q: q || undefined,
    career: params.get("career") || undefined,
    source_type: isSource(rawSource) ? rawSource : undefined,
    tag: params.get("tag") || undefined,
    status: isStatus(rawStatus) ? rawStatus : "active",
    page: 1,
    page_size: 100,
  };
  const notes = useNotes(filters);
  useScrollMemory(Boolean(notes.data) && !notes.isPlaceholderData);
  const undo = (location.state as { deleted?: { id: string; title: string } } | null)?.deleted ?? null;
  const [undoOpen, setUndoOpen] = useState(Boolean(undo));
  const [restored, setRestored] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);
  const [undoError, setUndoError] = useState<unknown>(null);

  useEffect(() => {
    if (!undo) return;
    const t = window.setTimeout(() => setUndoOpen(false), UNDO_MS);
    return () => window.clearTimeout(t);
  }, [undo]);

  function update(next: Record<string, string>, replace = false) {
    const merged = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) merged.set(k, v);
      else merged.delete(k);
    }
    setParams(merged, { replace, state: null });
  }

  const data = notes.data;
  const active = Boolean(filters.q || filters.career || filters.source_type || filters.tag || filters.status !== "active");
  return (
    <div className="page notes-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">NOTEBOOK</p>
          <h1 className="page__title" ref={heading} tabIndex={-1}>Your notes</h1>
          <p className="page__subtitle">Private to you. Capture notes from any question, problem, lesson or interview review.</p>
        </div>
        <Link className="btn btn--primary btn--md" to="/notes/new" state={{ from: `${location.pathname}${location.search}`, fromLabel: "Back to your notebook" }}>New note</Link>
      </div>
      <p className="visually-hidden" role="status">{restored}</p>
      {undo && undoOpen && (
        <div className="banner banner--info row notes-undo" role="status">
          <span>Deleted “{undo.title}”. You can undo this for 10 minutes; after that it's gone for good.</span>
          <Button size="sm" onClick={async () => {
            try {
              await api.restoreNote(undo.id);
              setUndoOpen(false);
              setRestored(`Restored “${undo.title}”.`);
              heading.current?.focus(); // the Undo button is gone
              void qc.invalidateQueries({ queryKey: ["me", "notes"] });
            } catch (e) { setUndoError(e); }
          }}>Undo</Button>
          <InlineError error={undoError} />
        </div>
      )}

      <div className="notes-filters" role="search" aria-label="Search notes">
        <label className="field filters__search">
          <span className="visually-hidden">Search notes</span>
          <Icon name="search" size={18} />
          <input className="input" type="search" value={search} placeholder="Search titles, text, reflections and tags"
            onChange={(e) => update({ q: e.target.value }, true)} />
        </label>
        <label className="explore-filter"><span>Career</span>
          <select className="input" value={filters.career ?? ""} onChange={(e) => update({ career: e.target.value })}>
            <option value="">Any career</option>
            {data?.careers.map((c) => <option key={c.tag} value={c.tag}>{c.tag} ({c.count})</option>)}
          </select>
        </label>
        <label className="explore-filter"><span>From</span>
          <select className="input" value={filters.source_type ?? ""} onChange={(e) => update({ source: e.target.value })}>
            <option value="">Anywhere</option>
            {(Object.keys(SOURCE_LABEL) as SourceKind[]).map((k) => <option key={k} value={k}>{SOURCE_LABEL[k]}</option>)}
          </select>
        </label>
        <label className="explore-filter"><span>Tag</span>
          <select className="input" value={filters.tag ?? ""} onChange={(e) => update({ tag: e.target.value })}>
            <option value="">Any tag</option>
            {data?.tags.map((t) => <option key={t.tag} value={t.tag}>{t.tag} ({t.count})</option>)}
          </select>
        </label>
        <label className="explore-filter"><span>Show</span>
          <select className="input" value={filters.status} onChange={(e) => update({ status: e.target.value === "active" ? "" : e.target.value })}>
            <option value="active">Active notes</option>
            <option value="archived">Archived</option>
            <option value="all">All</option>
          </select>
        </label>
      </div>

      {notes.isPending ? <LoadingState label="Loading notes…" />
        : notes.isError ? <ErrorState error={notes.error} onRetry={() => void notes.refetch()} />
        : data!.items.length === 0 ? (
          <EmptyState title={active ? "No notes match" : "No notes yet"}
            action={active ? <Button onClick={() => setParams(new URLSearchParams())}>Clear search and filters</Button> : <Link className="btn btn--secondary btn--md" to="/problems?view=questions">Go practise</Link>}>
            {active ? "Try other words or remove a filter." : "Use “Add a note” on a question, problem, lesson or interview review, or start a blank note."}
          </EmptyState>
        ) : (
          <>
            <p className="subtle" role="status">{data!.total} {data!.total === 1 ? "note" : "notes"}{data!.items.some((n) => n.pinned) ? ` · pinned first (up to ${data!.pinned_limit})` : ""}</p>
            <ul className="notes-list">
              {data!.items.map((n) => (
                <li key={n.id} className="card notes-list__item">
                  <div className="row notes-list__head">
                    <Link to={`/notes/${n.id}`} state={{ from: `${location.pathname}${location.search}`, fromLabel: "Back to your notebook" }} className="notes-list__title">{n.title}</Link>
                    {n.pinned && <Badge tone="info">Pinned</Badge>}
                    {n.archived && <Badge>Archived</Badge>}
                  </div>
                  {n.snippet && <p className="subtle notes-list__snippet">{n.snippet}</p>}
                  <p className="notes-list__meta subtle">
                    {n.source && <>From {SOURCE_LABEL[n.source.type].toLowerCase()}: {n.source.title}{n.source.career_title ? ` (${n.source.career_title})` : ""}{n.source.available ? "" : " · source no longer available"} · </>}
                    updated {timeAgo(n.updated_at)}
                  </p>
                  {n.tags.length > 0 && (
                    <p className="row notes-list__tags">
                      {n.tags.map((t) => <button key={t} type="button" className="filter-chip" aria-label={`Show notes tagged ${t}`} onClick={() => update({ tag: t })}>#{t}</button>)}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
    </div>
  );
}
