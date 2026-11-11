import { useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useKitTemplate, useKitTemplates } from "@/api/queries";
import type { Kit, KitTemplate } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/States";
import { useRequestKey } from "@/lib/requestKey";

import { GROUP_LABEL } from "./labels";
import { applyTemplate, NOT_KEPT, SNAPSHOT } from "./templateApply";


/**
 * Templates on an interview kit (Volume 11, prompt 7): start from one of your templates (its items
 * join this kit's form, unsaved, as the kit's own), or save this kit's checklist and questions as a
 * new template after choosing what to keep and seeing it. Optional: the kit works without them.
 */
export function KitTemplatesCard({ kit, fromHere, onApply }: {
  kit: Kit;
  fromHere: { from: string; fromLabel: string };
  onApply: (next: Pick<Kit, "checklist" | "questions">) => void;
}) {
  return (
    <Card className="stack-sm kit-templates">
      <h2 className="section-title">Templates</h2>
      <UseTemplate kit={kit} onApply={onApply} />
      <SaveAsTemplate kit={kit} fromHere={fromHere} />
      <p className="subtle"><Link to="/kit-templates" state={fromHere}>Your kit templates</Link> (rename, preview or delete)</p>
    </Card>
  );
}

function TemplatePreview({ t, label }: { t: Pick<KitTemplate, "checklist" | "questions">; label: string }) {
  return (
    <div className="kit-templates__preview stack-sm" role="region" aria-label={label}>
      {t.checklist.length > 0 && (
        <>
          <p className="field__label">Checklist ({t.checklist.length})</p>
          <ul className="mini-list">{t.checklist.map((c, i) => <li key={i}>{c.text}</li>)}</ul>
        </>
      )}
      {t.questions.length > 0 && (
        <>
          <p className="field__label">Questions to ask ({t.questions.length})</p>
          <ul className="mini-list">{t.questions.map((q, i) => <li key={i}>{q.text} <span className="subtle">· {GROUP_LABEL[q.group ?? "other"]}</span></li>)}</ul>
        </>
      )}
    </div>
  );
}

function UseTemplate({ kit, onApply }: { kit: Kit; onApply: (next: Pick<Kit, "checklist" | "questions">) => void }) {
  const templates = useKitTemplates();
  const [chosen, setChosen] = useState("");
  const [said, setSaid] = useState("");
  const template = useKitTemplate(chosen || undefined);
  const selectId = useId();
  if (!templates.data || templates.data.length === 0) {
    return <p className="subtle">No templates yet. Save this kit's checklist and questions as one below to reuse them for another interview.</p>;
  }
  const gone = template.error instanceof ApiError && template.error.status === 404;
  return (
    <div className="stack-sm">
      <label className="field" htmlFor={selectId}><span className="field__label">Start from one of your templates</span></label>
      <select id={selectId} className="select" value={chosen} onChange={(e) => { setChosen(e.target.value); setSaid(""); }}>
        <option value="">Choose a template</option>
        {templates.data.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.checklist_count + t.questions_count})</option>)}
      </select>
      <p className="subtle" role="status">{gone ? "That template was deleted. Kits made from it keep their items." : said}</p>
      {template.data && chosen && (
        <>
          <TemplatePreview t={template.data} label={`Preview: ${template.data.name}`} />
          <span className="row">
            <Button size="sm" onClick={() => {
              const t = template.data!;
              const next = applyTemplate(kit, t);
              const parts = [
                next.addedChecklist && `${next.addedChecklist} checklist item${next.addedChecklist === 1 ? "" : "s"}`,
                next.addedQuestions && `${next.addedQuestions} question${next.addedQuestions === 1 ? "" : "s"}`,
              ].filter(Boolean);
              onApply({ checklist: next.checklist, questions: next.questions });
              setSaid(parts.length
                ? `Added ${parts.join(" and ")} from “${t.name}”, not ticked. They aren't saved yet: Save kit keeps them.`
                : `Everything in “${t.name}” is already in this kit.`);
              setChosen("");
            }}>Add to this kit</Button>
          </span>
        </>
      )}
    </div>
  );
}

function SaveAsTemplate({ kit, fromHere }: { kit: Kit; fromHere: { from: string; fromLabel: string } }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(`${kit.role_title} interviews`);
  const ticks = kit.checklist.filter((c) => !c.hidden);
  const asks = kit.questions.filter((q) => !q.excluded);
  // Everything is kept unless unticked here (so an item added to the kit meanwhile is kept too).
  const [dropTicks, setDropTicks] = useState<Set<string>>(() => new Set());
  const [dropAsks, setDropAsks] = useState<Set<string>>(() => new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [lost, setLost] = useState(false);
  const [saved, setSaved] = useState<KitTemplate | null>(null);
  const key = useRequestKey();
  const formId = useId();
  const body = {
    name: name.trim(),
    checklist: ticks.filter((c) => !dropTicks.has(c.id)).map((c) => ({ text: c.text })),
    questions: asks.filter((q) => !dropAsks.has(q.id)).map((q) => ({ text: q.text, group: q.group })),
  };
  const empty = body.checklist.length + body.questions.length === 0;

  async function save() {
    setBusy(true);
    setError(null);
    setLost(false);
    try {
      const made = await api.createKitTemplate({ ...body, client_request_id: key.keyFor(body) });
      key.done();
      setSaved(made);
      setOpen(false);
      void qc.invalidateQueries({ queryKey: ["me", "kit-templates"] });
    } catch (e) {
      if (e instanceof ApiError && (e.code === "network_error" || e.status >= 500)) setLost(true);
      else setError(e);
    } finally {
      setBusy(false);
    }
  }

  const toggle = (set: Set<string>, id: string, on: boolean) => { const next = new Set(set); if (on) next.add(id); else next.delete(id); return next; };
  return (
    <div className="stack-sm">
      {saved && !open && (
        <p role="status">Saved as “{saved.name}”. <Link to="/kit-templates" state={fromHere}>See your templates</Link></p>
      )}
      <span className="row">
        <Button size="sm" aria-expanded={open} aria-controls={formId} onClick={() => { setOpen(!open); setSaved(null); }}>
          {open ? "Close" : "Save as a template…"}
        </Button>
      </span>
      {open && (
        <div id={formId} className="stack-sm kit-templates__form">
          <label className="field"><span className="field__label">Template name</span>
            <input className="input" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          {ticks.length > 0 && (
            <fieldset className="stack-sm kit-templates__choose">
              <legend className="field__label">Checklist items to keep</legend>
              {ticks.map((c) => (
                <label key={c.id} className="checkbox"><input type="checkbox" checked={!dropTicks.has(c.id)} onChange={(e) => setDropTicks(toggle(dropTicks, c.id, !e.target.checked))} />{c.text}</label>
              ))}
            </fieldset>
          )}
          {asks.length > 0 && (
            <fieldset className="stack-sm kit-templates__choose">
              <legend className="field__label">Questions to keep</legend>
              {asks.map((q) => (
                <label key={q.id} className="checkbox"><input type="checkbox" checked={!dropAsks.has(q.id)} onChange={(e) => setDropAsks(toggle(dropAsks, q.id, !e.target.checked))} />{q.text}</label>
              ))}
            </fieldset>
          )}
          <p className="field__label">What the template will hold</p>
          {empty ? <p className="subtle">Nothing yet: keep at least one item or question.</p> : <TemplatePreview t={body} label="What the template will hold" />}
          <p className="subtle">{SNAPSHOT} {NOT_KEPT}</p>
          {lost && (
            <div className="banner banner--warning stack-sm" role="alert">
              <p>No reply came, so it isn't known whether the template was saved. Saving again is safe: it makes one template, not two.</p>
            </div>
          )}
          <span className="row">
            <Button size="sm" variant="primary" loading={busy} disabled={empty || !body.name} onClick={() => void save()}>{lost ? "Save again" : "Save template"}</Button>
          </span>
          <InlineError error={error} />
        </div>
      )}
    </div>
  );
}
