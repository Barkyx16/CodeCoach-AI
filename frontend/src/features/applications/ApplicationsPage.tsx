import { useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState, type DragEvent, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { isSameSession, sessionMark } from "@/api/client";
import { api } from "@/api/endpoints";
import { useApplications } from "@/api/queries";
import type { ApplicationStage, ApplicationSummary } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { useScrollMemory } from "@/hooks/useScrollMemory";

import { browserTimeZone, dueLabel, formatDay, todayIn } from "./dates";
import { STAGE_HINT, STAGE_LABEL, STAGES } from "./labels";
import { sortApps, type SortKey } from "./sorting";

const SORTS: { key: SortKey; label: string }[] = [
  { key: "role", label: "Role" },
  { key: "employer", label: "Employer" },
  { key: "stage", label: "Stage" },
  { key: "applied", label: "Applied" },
  { key: "due", label: "Next action" },
  { key: "updated", label: "Updated" },
];

/** Your applications as a board (by stage) or a sortable list. View, filters and sort live in the URL. */
export function ApplicationsPage() {
  const [params, setParams] = useSearchParams();
  const view = params.get("view") === "list" ? "list" : "board";
  const stage = (params.get("stage") ?? "") as ApplicationStage | "";
  const q = params.get("q") ?? "";
  const archived = params.get("archived") === "1";
  const sort = (params.get("sort") ?? "updated") as SortKey;
  const dir = params.get("dir") === "asc" ? "asc" : "desc";
  const apps = useApplications(archived);
  const qc = useQueryClient();
  const [moveError, setMoveError] = useState<unknown>(null);
  const [adding, setAdding] = useState(false);
  const searchId = useId();
  const today = todayIn(browserTimeZone());
  useScrollMemory(Boolean(apps.data));

  const update = (next: Record<string, string>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    setParams(p, { replace: true });
  };

  const shown = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    const list = (apps.data ?? []).filter((a) =>
      (!stage || a.stage === stage) && words.every((w) => `${a.role_title} ${a.employer} ${a.next_action}`.toLowerCase().includes(w)));
    return sortApps(list, sort, dir);
  }, [apps.data, q, stage, sort, dir]);

  async function move(a: ApplicationSummary, to: ApplicationStage) {
    if (a.stage === to) return;
    setMoveError(null);
    // Show it in the new column at once; put it back if saving fails.
    const key = ["me", "applications", { archived }];
    const session = sessionMark();
    const prev = qc.getQueryData<ApplicationSummary[]>(key);
    qc.setQueryData<ApplicationSummary[]>(key, (list) => list?.map((x) => (x.id === a.id ? { ...x, stage: to } : x)));
    try {
      await api.setApplicationStage(a.id, { stage: to, note: "", correction: false });
      void qc.invalidateQueries({ queryKey: ["me", "applications"] });
    } catch (e) {
      // Signed out, or in as someone else, while this was saving: nothing of it is put back.
      if (!isSameSession(session)) return;
      qc.setQueryData(key, prev);
      setMoveError(e);
    }
  }

  const upcoming = (apps.data ?? [])
    .filter((a) => a.next_action_due && a.next_action.trim())
    .sort((a, b) => (a.next_action_due! < b.next_action_due! ? -1 : 1))
    .slice(0, 5);

  return (
    <div className="page applications-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">APPLICATIONS</p>
          <h1 className="page__title">Your applications</h1>
          <p className="page__subtitle">What you've applied for and where each one stands, as you record it. Private to you; CodeCoach never contacts employers or submits anything.</p>
          <p className="subtle"><Link to="/reflections">Your interview reflections</Link></p>
        </div>
        <Button variant="primary" aria-expanded={adding} onClick={() => setAdding((v) => !v)}>{adding ? "Close" : "Add an application"}</Button>
      </div>
      {adding && <NewApplication onDone={() => setAdding(false)} />}

      {upcoming.length > 0 && !archived && (
        <Card className="stack-sm">
          <h2 className="section-title">Next actions</h2>
          <p className="subtle">Dates are in your time zone ({browserTimeZone()}).</p>
          <ul className="mini-list">
            {upcoming.map((a) => (
              <li key={a.id}><Link to={`/applications/${a.id}`}>{a.role_title}, {a.employer}</Link>: {a.next_action} <span className="subtle">· {dueLabel(a.next_action_due!, today)} ({formatDay(a.next_action_due!)})</span></li>
            ))}
          </ul>
        </Card>
      )}

      <form className="applications-filters" role="search" aria-label="Filter applications" onSubmit={(e) => e.preventDefault()}>
        <fieldset className="segmented">
          <legend className="visually-hidden">View</legend>
          {(["board", "list"] as const).map((v) => (
            <label key={v} className="segmented__option">
              <input type="radio" name="view" checked={view === v} onChange={() => update({ view: v === "board" ? "" : "list" })} />
              {v === "board" ? "Board" : "List"}
            </label>
          ))}
        </fieldset>
        <label className="field" htmlFor={searchId}>
          <span className="field__label">Search</span>
          <input id={searchId} type="search" className="input" value={q} onChange={(e) => update({ q: e.target.value })} placeholder="Role, employer or next action" />
        </label>
        <label className="field">
          <span className="field__label">Stage</span>
          <select className="select" value={stage} onChange={(e) => update({ stage: e.target.value })}>
            <option value="">All stages</option>
            {STAGES.map((s) => <option key={s} value={s}>{STAGE_LABEL[s]}</option>)}
          </select>
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={archived} onChange={(e) => update({ archived: e.target.checked ? "1" : "" })} />
          Show archived
        </label>
      </form>
      <InlineError error={moveError} />

      {apps.isPending ? <LoadingState label="Loading your applications…" />
        : apps.isError ? <ErrorState error={apps.error} onRetry={() => void apps.refetch()} />
        : apps.data.length === 0 ? (
          <EmptyState title={archived ? "Nothing archived" : "No applications yet"}>
            {archived ? "Applications you archive appear here." : "Add the roles you've applied for, or want to, and keep the next step for each in one place."}
          </EmptyState>
        ) : view === "board"
          ? <Board apps={shown} today={today} onMove={(a, to) => void move(a, to)} />
          : <List apps={shown} today={today} sort={sort} dir={dir} onSort={(k) => update({ sort: k, dir: sort === k && dir === "desc" ? "asc" : "desc" })} onMove={(a, to) => void move(a, to)} />}
    </div>
  );
}

function MoveMenu({ a, onMove }: { a: ApplicationSummary; onMove: (a: ApplicationSummary, to: ApplicationStage) => void }) {
  const id = useId();
  return (
    <span className="move-menu">
      <label className="visually-hidden" htmlFor={id}>Move {a.role_title} at {a.employer} to</label>
      <select id={id} className="select select--sm" value={a.stage} onChange={(e) => onMove(a, e.target.value as ApplicationStage)}>
        {STAGES.map((s) => <option key={s} value={s}>{STAGE_LABEL[s]}</option>)}
      </select>
    </span>
  );
}

function AppCard({ a, today, onMove }: { a: ApplicationSummary; today: string; onMove: (a: ApplicationSummary, to: ApplicationStage) => void }) {
  return (
    <li className="app-card" draggable onDragStart={(e: DragEvent) => { e.dataTransfer.setData("text/plain", a.id); e.dataTransfer.effectAllowed = "move"; }}>
      <Link to={`/applications/${a.id}`} className="app-card__title">{a.role_title}</Link>
      <span className="subtle">{a.employer}</span>
      {a.next_action && <span className="app-card__next">{a.next_action}{a.next_action_due ? <span className="subtle"> · {dueLabel(a.next_action_due, today)}</span> : null}</span>}
      {a.next_event && <span className="subtle">{a.next_event.title}{a.next_event.on_date ? ` · ${formatDay(a.next_event.on_date)}` : ""}</span>}
      <MoveMenu a={a} onMove={onMove} />
    </li>
  );
}

/** Columns by stage. Drag a card, or use its "Move to" menu: the same change either way. */
function Board({ apps, today, onMove }: { apps: ApplicationSummary[]; today: string; onMove: (a: ApplicationSummary, to: ApplicationStage) => void }) {
  const [over, setOver] = useState<ApplicationStage | null>(null);
  return (
    <div className="app-board" role="list" aria-label="Applications by stage">
      {STAGES.map((s) => {
        const items = apps.filter((a) => a.stage === s);
        return (
          <section key={s} role="listitem" aria-labelledby={`col-${s}`} className={`app-board__column${over === s ? " app-board__column--over" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setOver(s); }} onDragLeave={() => setOver(null)}
            onDrop={(e) => {
              e.preventDefault();
              setOver(null);
              const a = apps.find((x) => x.id === e.dataTransfer.getData("text/plain"));
              if (a) onMove(a, s);
            }}>
            <h2 className="section-title" id={`col-${s}`}>{STAGE_LABEL[s]} <span className="subtle">{items.length}</span></h2>
            <p className="subtle app-board__hint">{STAGE_HINT[s]}</p>
            <ul className="app-board__cards">{items.map((a) => <AppCard key={a.id} a={a} today={today} onMove={onMove} />)}</ul>
          </section>
        );
      })}
    </div>
  );
}

function List({ apps, today, sort, dir, onSort, onMove }: {
  apps: ApplicationSummary[]; today: string; sort: SortKey; dir: "asc" | "desc"; onSort: (k: SortKey) => void;
  onMove: (a: ApplicationSummary, to: ApplicationStage) => void;
}) {
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Applications list">
      <table className="app-table">
        <thead>
          <tr>
            {SORTS.map((s) => (
              <th key={s.key} scope="col" aria-sort={sort === s.key ? (dir === "asc" ? "ascending" : "descending") : undefined}>
                <button type="button" className="link-button" onClick={() => onSort(s.key)}>
                  {s.label}{sort === s.key && <span aria-hidden="true">{dir === "asc" ? " ↑" : " ↓"}</span>}
                </button>
              </th>
            ))}
            <th scope="col">Move</th>
          </tr>
        </thead>
        <tbody>
          {apps.map((a) => (
            <tr key={a.id}>
              <td><Link to={`/applications/${a.id}`}>{a.role_title}</Link></td>
              <td>{a.employer}</td>
              <td><Badge>{STAGE_LABEL[a.stage]}</Badge></td>
              <td>{a.applied_on ? formatDay(a.applied_on) : <span className="subtle">Not recorded</span>}</td>
              <td>{a.next_action || <span className="subtle">None</span>}{a.next_action_due ? <span className="subtle"> · {dueLabel(a.next_action_due, today)}</span> : null}</td>
              <td>{new Date(a.updated_at).toLocaleDateString()}</td>
              <td><MoveMenu a={a} onMove={onMove} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NewApplication({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ employer: "", role_title: "", stage: "saved" as ApplicationStage, applied_on: "", link: "", next_action: "", next_action_due: "" });
  // One id per form: a double click or a retry after a dropped connection creates one application.
  const [requestId] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.createApplication({
        employer: form.employer, role_title: form.role_title, stage: form.stage, applied_on: form.applied_on || null,
        link: form.link || null, next_action: form.next_action, next_action_due: form.next_action_due || null, client_request_id: requestId,
      });
      void qc.invalidateQueries({ queryKey: ["me", "applications"] });
      onDone();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }));
  return (
    <form className="card stack-sm" aria-label="New application" onSubmit={(e) => void submit(e)}>
      <div className="app-form__grid">
        <label className="field"><span className="field__label">Role title</span><input className="input" required maxLength={120} value={form.role_title} onChange={(e) => set("role_title", e.target.value)} /></label>
        <label className="field"><span className="field__label">Employer</span><input className="input" required maxLength={120} value={form.employer} onChange={(e) => set("employer", e.target.value)} /></label>
        <label className="field"><span className="field__label">Stage</span>
          <select className="select" value={form.stage} onChange={(e) => set("stage", e.target.value)}>
            {STAGES.map((s) => <option key={s} value={s}>{STAGE_LABEL[s]}</option>)}
          </select>
        </label>
        <label className="field"><span className="field__label">Applied on <span className="subtle">(optional)</span></span><input className="input" type="date" value={form.applied_on} onChange={(e) => set("applied_on", e.target.value)} /></label>
        <label className="field"><span className="field__label">Link to the posting <span className="subtle">(optional)</span></span><input className="input" type="url" inputMode="url" maxLength={500} placeholder="https://" value={form.link} onChange={(e) => set("link", e.target.value)} /></label>
        <label className="field"><span className="field__label">Next action <span className="subtle">(optional)</span></span><input className="input" maxLength={300} value={form.next_action} onChange={(e) => set("next_action", e.target.value)} /></label>
        <label className="field"><span className="field__label">Next action due <span className="subtle">(optional)</span></span><input className="input" type="date" value={form.next_action_due} onChange={(e) => set("next_action_due", e.target.value)} /></label>
      </div>
      <InlineError error={error} />
      <span><Button type="submit" variant="primary" loading={busy} disabled={!form.employer.trim() || !form.role_title.trim()}>Add application</Button></span>
    </form>
  );
}
