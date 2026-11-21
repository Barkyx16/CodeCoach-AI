import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import type { AdminReportDetail, ReportStatusValue } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { formatDateTime } from "@/lib/format";

import { CATEGORY_LABEL, STATUS_LABEL, STATUS_TONE } from "@/features/content/labels";

const STATUSES: ReportStatusValue[] = ["open", "investigating", "resolved", "not_actionable"];

/** One report: what the learner said (plain text), the content's state, actions, and the audit trail. */
export function AdminReportPage() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const report = useQuery({ queryKey: ["admin", "report", id], queryFn: () => api.adminReport(id), staleTime: 0 });
  const done = (r: AdminReportDetail) => {
    qc.setQueryData(["admin", "report", id], r);
    void qc.invalidateQueries({ queryKey: ["admin", "reports"] });
    void qc.invalidateQueries({ queryKey: ["content"] });
  };
  const reload = () => {
    void report.refetch();
    void qc.invalidateQueries({ queryKey: ["admin", "reports"] });
    void qc.invalidateQueries({ queryKey: ["content"] });
  };

  if (report.isPending) return <LoadingState label="Loading the report…" />;
  if (report.isError) return <div className="page"><ErrorState error={report.error} onRetry={() => void report.refetch()} /></div>;
  const r = report.data;
  return (
    <div className="page admin-page">
      <BackLink fallback={{ to: "/admin/reports", label: "All reports" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">REPORT · {r.content_type.toUpperCase()}</p>
          <h1 className="page__title">{CATEGORY_LABEL[r.category]}{r.context === "feedback" ? " (about feedback)" : ""}</h1>
          <p className="row">
            <Badge tone={STATUS_TONE[r.status]}>{STATUS_LABEL[r.status]}</Badge>
            <span className="subtle">by {r.reporter} · {formatDateTime(r.created_at)} · on version {r.content_version} (current {r.current_version})</span>
          </p>
        </div>
      </div>
      <div className="admin-report">
        <div className="stack">
          <Card className="stack-sm">
            <h2 className="section-title">What they reported</h2>
            <p>About: {r.content_href ? <Link to={r.content_href}>{r.content_title}</Link> : r.content_title} <span className="subtle">({r.content_id})</span></p>
            {r.details ? <p className="admin-report__text">{r.details}</p> : <p className="subtle">No details given.</p>}
            {r.excerpt && <><h3 className="section-title">Excerpt they chose to attach</h3><blockquote className="admin-report__text">{r.excerpt}</blockquote></>}
            {r.duplicate_of && <p>Likely duplicate of <Link to={`/admin/reports/${r.duplicate_of}`}>an earlier report</Link>.</p>}
            {r.duplicates.length > 0 && <p>{r.duplicates.length} likely {r.duplicates.length === 1 ? "duplicate is" : "duplicates are"} grouped under this report.</p>}
          </Card>
          <StatusForm r={r} onDone={done} />
          <GroupForm r={r} onDone={done} />
          {r.content_type === "question" && r.meta.status === "active" && <CorrectionForm r={r} onDone={reload} />}
          <RetireForm r={r} onDone={reload} />
        </div>
        <aside className="stack">
          <Card className="stack-sm">
            <h2 className="section-title">The content now</h2>
            <p>{r.meta.version_label} · {r.meta.status === "retired" ? `Retired: ${r.meta.retired_reason}` : "Active"}</p>
            <ul className="mini-list">{r.meta.labels.map((l) => <li key={l.key}>{l.text}</li>)}</ul>
            {r.meta.changes.map((c) => <p key={c.version} className="subtle">v{c.version}: {c.note}</p>)}
          </Card>
          <Card className="stack-sm">
            <h2 className="section-title">Audit trail</h2>
            <ol className="admin-audit">
              {r.audit.map((a, i) => (
                <li key={i}>
                  <strong>{a.action.replace("_", " ")}</strong> <span className="subtle">by {a.actor} · {formatDateTime(a.created_at)}</span>
                  {Object.keys(a.detail).length > 0 && <code className="admin-audit__detail">{JSON.stringify(a.detail)}</code>}
                  {a.internal_note && <p className="admin-audit__note">Internal: {a.internal_note}</p>}
                </li>
              ))}
            </ol>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function StatusForm({ r, onDone }: { r: AdminReportDetail; onDone: (r: AdminReportDetail) => void }) {
  const [status, setStatus] = useState<ReportStatusValue>(r.status);
  const [resolution, setResolution] = useState(r.resolution ?? "");
  const [note, setNote] = useState("");
  const save = useMutation({ mutationFn: () => api.adminSetStatus(r.id, { status, resolution: resolution.trim() || undefined, internal_note: note.trim() || undefined }), onSuccess: (x) => { setNote(""); onDone(x); } });
  const needsResolution = status === "resolved" || status === "not_actionable";
  return (
    <form className="card stack-sm" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }} aria-labelledby="status-title">
      <h2 className="section-title" id="status-title">Report status</h2>
      <div className="field">
        <label className="field__label" htmlFor="report-status-select">Status</label>
        <select id="report-status-select" className="select" value={status} onChange={(e) => setStatus(e.target.value as ReportStatusValue)}>
          {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
      </div>
      <label className="field"><span className="field__label">What happened, for the reporter {needsResolution ? "(required)" : "(optional)"}</span>
        <textarea className="input" rows={2} maxLength={1000} value={resolution} onChange={(e) => setResolution(e.target.value)} />
      </label>
      <label className="field"><span className="field__label">Internal note <span className="subtle">(admins only)</span></span>
        <textarea className="input" rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <InlineError error={save.error} />
      <span><Button type="submit" size="sm" variant="primary" loading={save.isPending} disabled={needsResolution && !resolution.trim()}>Save status</Button></span>
    </form>
  );
}

function GroupForm({ r, onDone }: { r: AdminReportDetail; onDone: (r: AdminReportDetail) => void }) {
  const [target, setTarget] = useState("");
  const save = useMutation({ mutationFn: (to: string | null) => api.adminSetDuplicate(r.id, { duplicate_of: to }), onSuccess: onDone });
  return (
    <div className="card stack-sm">
      <h2 className="section-title">Duplicates</h2>
      {r.duplicate_of ? (
        <span><Button size="sm" loading={save.isPending} onClick={() => save.mutate(null)}>Ungroup this report</Button></span>
      ) : (
        <form className="row" onSubmit={(e) => { e.preventDefault(); if (target.trim()) save.mutate(target.trim()); }}>
          <label className="field"><span className="field__label">Group under report id</span>
            <input className="input" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="Another report about the same content" />
          </label>
          <Button type="submit" size="sm" loading={save.isPending} disabled={!target.trim()}>Group</Button>
        </form>
      )}
      <p className="subtle">Grouping never deletes a report; each keeps its own text and reporter.</p>
      <InlineError error={save.error} />
    </div>
  );
}

function CorrectionForm({ r, onDone }: { r: AdminReportDetail; onDone: () => void }) {
  const [track, qid] = r.content_id.split("/") as [string, string];
  const current = useQuery({ queryKey: ["admin", "question", r.content_id], queryFn: () => api.question(track, qid) });
  const [title, setTitle] = useState<string | null>(null);
  const [prompt, setPrompt] = useState<string | null>(null);
  const [changeNote, setChangeNote] = useState("");
  const [significant, setSignificant] = useState(true);
  const [link, setLink] = useState(true);
  const publish = useMutation({
    mutationFn: () => api.adminCorrect(r.content_id, {
      title: title ?? undefined, prompt: prompt ?? undefined, change_note: changeNote.trim(), significant,
      report_ids: link ? [r.id] : [],
    }),
    onSuccess: () => { setTitle(null); setPrompt(null); setChangeNote(""); onDone(); },
  });
  if (!current.data) return null;
  return (
    <form className="card stack-sm" onSubmit={(e) => { e.preventDefault(); publish.mutate(); }} aria-labelledby="correct-title">
      <h2 className="section-title" id="correct-title">Publish a correction</h2>
      <p className="subtle">Creates version {r.meta.version + 1}. Earlier answers keep the version they were written for and their scores.</p>
      <label className="field"><span className="field__label">Title</span>
        <input className="input" maxLength={200} value={title ?? current.data.title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label className="field"><span className="field__label">Prompt</span>
        <textarea className="input" rows={4} maxLength={2000} value={prompt ?? current.data.prompt} onChange={(e) => setPrompt(e.target.value)} />
      </label>
      <label className="field"><span className="field__label">What changed, in plain language (learners see this)</span>
        <textarea className="input" rows={2} maxLength={1000} value={changeNote} onChange={(e) => setChangeNote(e.target.value)} />
      </label>
      <label className="checkbox"><input type="checkbox" checked={significant} onChange={(e) => setSignificant(e.target.checked)} />Significant: tell learners who answered or saved it</label>
      <label className="checkbox"><input type="checkbox" checked={link} onChange={(e) => setLink(e.target.checked)} />Resolve this report with the correction</label>
      <InlineError error={publish.error} />
      <span><Button type="submit" size="sm" variant="primary" loading={publish.isPending} disabled={changeNote.trim().length < 5}>Publish version {r.meta.version + 1}</Button></span>
    </form>
  );
}

function RetireForm({ r, onDone }: { r: AdminReportDetail; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const retire = useMutation({ mutationFn: () => api.adminRetire(r.content_type, r.content_id, { reason: reason.trim(), report_ids: [r.id] }), onSuccess: () => { setReason(""); onDone(); } });
  const restore = useMutation({ mutationFn: () => api.adminRestore(r.content_type, r.content_id), onSuccess: onDone });
  if (r.meta.status === "retired") {
    return (
      <div className="card stack-sm">
        <h2 className="section-title">Retired</h2>
        <p>{r.meta.retired_reason}</p>
        <span><Button size="sm" loading={restore.isPending} onClick={() => restore.mutate()}>Restore for practice</Button></span>
        <InlineError error={restore.error} />
      </div>
    );
  }
  return (
    <form className="card stack-sm" onSubmit={(e) => { e.preventDefault(); if (window.confirm("Retire it? It stops being used for practice and assessment; history keeps it.")) retire.mutate(); }} aria-labelledby="retire-title">
      <h2 className="section-title" id="retire-title">Retire</h2>
      <p className="subtle">For content that's unsuitable for assessment until fixed. It stays readable in learners' history and saved items, with this reason.</p>
      <label className="field"><span className="field__label">Reason (learners see this)</span>
        <textarea className="input" rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      <InlineError error={retire.error} />
      <span><Button type="submit" size="sm" variant="danger" loading={retire.isPending} disabled={reason.trim().length < 5}>Retire</Button></span>
    </form>
  );
}
