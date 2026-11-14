import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useTargetMutation } from "@/api/queries";
import type { Requirement, RequirementSetIn, RevisionPreview, Target } from "@/api/types";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";
import { formatDateTime } from "@/lib/format";

/**
 * Versioned requirements (docs/REQUIREMENT_VERSIONS.md). The whole set is edited, then reviewed
 * ("2 changed, 1 added, 1 removed, 5 unchanged", with the stories each change affects) before it's
 * saved against the revision it was loaded at. Similar wording may be suggested as "the same
 * requirement", but only the learner's answer links them. Nothing is re-scored or re-linked.
 */
type Category = Requirement["category"];
type Row = { id: string | null; category: Category; text: string; removed: boolean };
const STATE: Record<string, string> = {
  changed: "Changed (a new version)",
  cosmetic: "Wording tidied (the same requirement and version)",
  added: "Added",
  removed: "Removed (its history stays)",
  restored: "Restored",
  unchanged: "Unchanged",
};

export function RequirementSetEditor({ t, groups, onDone }: {
  t: Target; groups: { id: Category; label: string }[]; onDone: () => void;
}) {
  const ids = useId();
  const [rows, setRows] = useState<Row[]>(() => t.requirement_list.map((r) => ({ id: r.id, category: r.category, text: r.text, removed: r.removed })));
  const [revision, setRevision] = useState(t.requirements_revision);
  const [preview, setPreview] = useState<RevisionPreview | null>(null);
  const [same, setSame] = useState<Record<number, string>>({}); // new row index -> requirement it is the same as
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [stale, setStale] = useState<Target | null>(null);
  const save = useTargetMutation((body: RequirementSetIn) => api.saveRequirements(t.id, body));
  const body = (): RequirementSetIn => ({
    expected_revision: revision,
    items: rows.map((r) => ({ id: r.id, category: r.category, text: r.text, removed: r.removed })),
    same_as: Object.entries(same).map(([index, requirement_id]) => ({ index: Number(index), requirement_id })),
  });
  const edit = (i: number, change: Partial<Row>) => {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...change } : r)));
    setPreview(null);
  };

  async function review() {
    setChecking(true);
    setError(null);
    try {
      setPreview(await api.previewRequirements(t.id, body()));
    } catch (e) {
      setError(e);
    } finally {
      setChecking(false);
    }
  }

  function submit() {
    save.mutate(body(), {
      onSuccess: () => onDone(),
      onError: (e) => {
        if (e instanceof ApiError && e.code === "stale_revision") {
          setStale((e.details as { current?: Target } | undefined)?.current ?? null);
        }
      },
    });
  }

  return (
    <section className="card stack requirement-set" aria-labelledby={`${ids}-title`}>
      <h3 className="section-title" id={`${ids}-title`}>Edit the requirements</h3>
      <p className="subtle">
        Changing a requirement's meaning makes a new version of it; tidying spacing, capitals or punctuation doesn't. Stories and practice keep the version they were linked to. Nothing is saved until you review the changes.
      </p>
      <ol className="requirement-set__rows">
        {rows.map((r, i) => (
          <li key={r.id ?? `new-${i}`} className="requirement-set__row">
            <label className="field">
              <span className="field__label">Requirement {i + 1}{r.id ? "" : " (new)"}</span>
              <input className="input" value={r.text} maxLength={300} disabled={r.removed} onChange={(e) => edit(i, { text: e.target.value })} />
            </label>
            <label className="field">
              <span className="field__label">Group</span>
              <select className="select" value={r.category} disabled={r.removed} onChange={(e) => edit(i, { category: e.target.value as Category })}>
                {groups.map((g) => <option key={g.id} value={g.id}>{g.label}</option>)}
              </select>
            </label>
            {r.id ? (
              <label className="checkbox">
                <input type="checkbox" checked={r.removed} onChange={(e) => edit(i, { removed: e.target.checked })} />
                Removed
              </label>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => { setRows((rs) => rs.filter((_, j) => j !== i)); setSame({}); setPreview(null); }}>
                Discard
              </Button>
            )}
          </li>
        ))}
      </ol>
      <span className="row">
        <Button size="sm" variant="secondary" onClick={() => { setRows((rs) => [...rs, { id: null, category: "required_skill", text: "", removed: false }]); setPreview(null); }}>
          Add a requirement
        </Button>
        <Button size="sm" variant="primary" loading={checking} disabled={rows.some((r) => !r.removed && r.text.trim().length < 2)} onClick={() => void review()}>
          Review changes
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </span>
      <InlineError error={error} />
      {preview && (
        <div className="stack-sm requirement-set__review" role="region" aria-label="Changes to save">
          <ChangeList preview={preview} />
          {preview.suggestions.map((s) => (
            <fieldset key={s.index} className="stack-sm">
              <legend>{s.question}</legend>
              <label className="checkbox">
                <input type="radio" name={`${ids}-same-${s.index}`} checked={same[s.index] === s.requirement_id}
                  onChange={() => { setSame((m) => ({ ...m, [s.index]: s.requirement_id })); setPreview(null); }} />
                The same requirement: its next version
              </label>
              <label className="checkbox">
                <input type="radio" name={`${ids}-same-${s.index}`} checked={same[s.index] !== s.requirement_id}
                  onChange={() => { setSame((m) => { const n = { ...m }; delete n[s.index]; return n; }); }} />
                A different requirement
              </label>
            </fieldset>
          ))}
          {preview.suggestions.length > 0 && <p className="subtle">Choosing "the same requirement" changes the summary: review again before saving.</p>}
          <Button variant="primary" loading={save.isPending} onClick={submit}>Save these changes</Button>
        </div>
      )}
      {stale && (
        <div className="banner banner--warning stack-sm" role="alert">
          <p><strong>These requirements were changed somewhere else (maybe another tab). Nothing was saved.</strong> Yours are still in the form; the saved ones are:</p>
          <ul className="mini-list">{stale.requirement_list.map((r) => <li key={r.id}>{r.removed ? "(removed) " : ""}{r.text}</li>)}</ul>
          <span className="row">
            <Button size="sm" variant="secondary" onClick={() => { setRevision(stale.requirements_revision); setStale(null); setPreview(null); }}>Keep mine and review again</Button>
            <Button size="sm" variant="ghost" onClick={onDone}>Use the saved ones</Button>
          </span>
        </div>
      )}
      {!stale && <InlineError error={save.error} />}
    </section>
  );
}

/** The change summary and each change with the stories and accepted improvements it affects. */
export function ChangeList({ preview }: { preview: RevisionPreview }) {
  return (
    <>
      <p><strong>{preview.summary}</strong></p>
      <ul className="mini-list">
        {preview.changes.filter((c) => c.state !== "unchanged").map((c) => (
          <li key={`${c.index}-${c.requirement_id ?? "new"}`}>
            <strong>{STATE[c.state]}:</strong> “{c.text}”
            {c.previous_text && c.state === "changed" && <> (was “{c.previous_text}”{c.version_from ? `, version ${c.version_from} → ${c.version_to}` : ""})</>}.
            {c.stories.length > 0 && <span className="subtle"> Stories linked to it: {c.stories.map((s) => s.title).join(", ")}.</span>}
            {(c.actions ?? []).length > 0 && <span className="subtle"> Accepted improvements practising it: {(c.actions ?? []).map((a) => a.title).join(", ")}.</span>}
            {c.state === "changed" && (c.stories.length > 0 || (c.actions ?? []).length > 0) && (
              <span className="subtle"> They stay linked to the earlier wording until you reuse them.</span>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

/** An accepted improvement that practises this requirement, with the version it was accepted against. */
export function ActionLinks({ t, r }: { t: Target; r: Requirement }) {
  const links = (t.action_links ?? []).filter((a) => a.requirement_id === r.id);
  if (!links.length) return null;
  return (
    <ul className="mini-list requirement__actions-linked">
      {links.map((a) => (
        <li key={a.action_id}>
          <span>Accepted improvement “{a.title}”</span>
          <span className="subtle"> · {a.label}</span>
          {a.status === "earlier_wording" && <> <ReuseAction t={t} actionId={a.action_id} requirementId={r.id} /></>}
        </li>
      ))}
    </ul>
  );
}

function ReuseAction({ t, actionId, requirementId }: { t: Target; actionId: string; requirementId: string }) {
  const reuse = useTargetMutation(() => api.reuseAction(t.id, actionId, requirementId));
  return (
    <>
      <Button size="sm" variant="ghost" loading={reuse.isPending} onClick={() => reuse.mutate(undefined)}>Use it for the current wording</Button>
      <InlineError error={reuse.error} />
    </>
  );
}

/** A requirement's recorded versions, removed ones too (loaded when opened). */
export function RequirementHistory({ t, r }: { t: Target; r: Requirement }) {
  const [open, setOpen] = useState(false);
  const history = useQuery({ queryKey: ["me", "target", t.id, "requirement-history", r.id, r.version, r.removed], queryFn: () => api.requirementHistory(t.id, r.id), enabled: open });
  return (
    <details className="requirement__history" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>History{r.version > 1 ? ` (version ${r.version})` : ""}</summary>
      {history.data && (
        <ol className="mini-list">
          {history.data.map((h) => (
            <li key={`${h.version}-${h.state}-${h.at ?? ""}`}>
              {h.state === "original"
                ? <>Version {h.version}, before the first change: “{h.text}”</>
                : <>Version {h.version}, {h.state}: “{h.text}”{h.at ? ` · ${formatDateTime(h.at)}` : ""}</>}
            </li>
          ))}
        </ol>
      )}
      <InlineError error={history.error} />
    </details>
  );
}
