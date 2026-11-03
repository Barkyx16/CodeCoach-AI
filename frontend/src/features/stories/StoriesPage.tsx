import { useId } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useStories } from "@/api/queries";
import type { Competency, StorySummary } from "@/api/types";
import { Badge } from "@/components/Badge";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { timeAgo } from "@/lib/format";

import { COMPETENCIES, COMPETENCY_LABEL, SECTION_LABEL } from "./labels";

/** Your stories: private search and competency filters, kept in the URL. */
export function StoriesPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const competency = (params.get("competency") ?? "") as Competency | "";
  const archived = params.get("archived") === "1";
  // The search runs on the server over everything you wrote; typing doesn't send a request per key.
  const deferredQ = useDebouncedValue(q.trim(), 300);
  const stories = useStories({ archived, q: deferredQ, competency });
  const filtering = !!deferredQ || !!competency;
  const searchId = useId();

  const update = (next: Record<string, string>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    setParams(p, { replace: true });
  };

  return (
    <div className="page stories-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">STORY BANK</p>
          <h1 className="page__title">Your stories</h1>
          <p className="page__subtitle">Real experiences from your work, studies, volunteering or projects, written as Situation, Task, Action and Result. Private to you.</p>
        </div>
        <Link className="btn btn--primary btn--md" to="/stories/new">Write a story</Link>
      </div>

      <form className="stories-filters" role="search" aria-label="Filter stories" onSubmit={(e) => e.preventDefault()}>
        <label className="field" htmlFor={searchId}>
          <span className="field__label">Search your stories</span>
          <input id={searchId} type="search" className="input" value={q} onChange={(e) => update({ q: e.target.value })} placeholder="Words from a title, a section or a tag" />
        </label>
        <label className="field">
          <span className="field__label">Competency</span>
          <select className="select" value={competency} onChange={(e) => update({ competency: e.target.value })}>
            <option value="">Any</option>
            {COMPETENCIES.map((c) => <option key={c} value={c}>{COMPETENCY_LABEL[c]}</option>)}
          </select>
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={archived} onChange={(e) => update({ archived: e.target.checked ? "1" : "" })} />
          Show archived stories
        </label>
      </form>

      {stories.isPending ? <LoadingState label="Loading your stories…" />
        : stories.isError ? <ErrorState error={stories.error} onRetry={() => void stories.refetch()} />
        : stories.data.length === 0 && !filtering ? (
          <EmptyState title={archived ? "No archived stories" : "No stories yet"}>
            {archived ? "Stories you archive appear here." : "Write down one experience you could talk about in an interview. You can add to it any time."}
          </EmptyState>
        ) : (
          <>
            <p className="subtle">{`${stories.data.length} ${stories.data.length === 1 ? "story" : "stories"}${filtering ? " match" : ""}`}</p>
            {stories.data.length === 0 && <p>Nothing matches. Try fewer words or another competency.</p>}
            <ul className="story-list">
              {stories.data.map((s) => <StoryRow key={s.id} s={s} />)}
            </ul>
          </>
        )}
    </div>
  );
}

function StoryRow({ s }: { s: StorySummary }) {
  return (
    <li className="card story-list__item stack-sm">
      <h2 className="section-title"><Link to={`/stories/${s.id}`}>{s.title}</Link></h2>
      {s.preview && <p className="subtle story-list__preview">{s.preview}</p>}
      <p className="row">
        {s.competencies.map((c) => <Badge key={c}>{COMPETENCY_LABEL[c]}</Badge>)}
        {s.tags.map((t) => <Badge key={`t-${t}`} tone="info">{t}</Badge>)}
      </p>
      <p className="subtle">
        {s.missing.length > 0 ? <>Not written yet: {s.missing.map((m) => SECTION_LABEL[m]).join(", ")} · </> : null}
        {s.target ? <>For {s.target.title} · </> : null}
        {s.practice_count > 0 ? `Practised ${s.practice_count} ${s.practice_count === 1 ? "time" : "times"} · ` : ""}
        Updated {timeAgo(s.updated_at)}
      </p>
    </li>
  );
}
