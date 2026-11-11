import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useKitTemplate, useKitTemplates } from "@/api/queries";
import type { KitTemplateSummary } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/States";
import { timeAgo } from "@/lib/format";
import { useRequestKey } from "@/lib/requestKey";

import { GROUP_LABEL } from "./labels";
import { NOT_KEPT } from "./templateApply";

/**
 * /kit-templates: your kit templates (Volume 11, prompt 7; docs/TEMPLATES.md). Preview, rename or
 * delete. Each is a snapshot of words: renaming or deleting one changes no kit made from it.
 */
export function KitTemplatesPage() {
  const list = useKitTemplates();
  const heading = useRef<HTMLHeadingElement>(null);
  const [said, setSaid] = useState("");
  // After a delete the row (and its focused button) is gone: focus the next one's Preview, or the heading.
  const focusNext = useRef<string | null>(null);
  useEffect(() => {
    const target = focusNext.current;
    if (!target || list.isFetching) return;
    focusNext.current = null;
    const el = target === "heading" ? null : document.querySelector<HTMLElement>(`[data-template="${target}"]`);
    (el ?? heading.current)?.focus();
  });
  return (
    <div className="page kit-templates-page">
      <BackLink fallback={{ to: "/applications", label: "Your applications" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">INTERVIEW DAY · PRIVATE</p>
          <h1 className="page__title" ref={heading} tabIndex={-1}>Your kit templates</h1>
          <p className="page__subtitle">Checklist items and questions you saved from an interview kit, to start another kit from.</p>
        </div>
      </div>
      <div className="stack">
      <p className="banner banner--info" role="note">
        A template is a copy of words, not a link: changing or deleting one changes no kit made from it, and a kit you change
        doesn't change it. {NOT_KEPT.replace("this interview", "the interview it came from")} Only you can see them.
      </p>
      <p className="visually-hidden" role="status">{said}</p>
      {list.isPending ? <LoadingState label="Loading your templates…" />
        : list.isError ? <ErrorState error={list.error} onRetry={() => void list.refetch()} />
        : list.data.length === 0 ? (
          <EmptyState title="No templates yet">Open an interview kit and choose “Save as a template…” to keep its checklist and questions for next time.</EmptyState>
        ) : (
          <ul className="kit-templates-page__list">
            {list.data.map((t, i) => (
              <TemplateRow key={t.id} t={t} onDeleted={(name) => {
                setSaid(`“${name}” deleted. Kits made from it keep their items.`);
                const next = list.data[i + 1] ?? list.data[i - 1];
                focusNext.current = next ? next.id : "heading";
              }} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function TemplateRow({ t, onDeleted }: { t: KitTemplateSummary; onDeleted: (name: string) => void }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(t.name);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [note, setNote] = useState("");
  const full = useKitTemplate(open ? t.id : undefined);
  const key = useRequestKey();

  async function rename(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNote("");
    const body = { name: name.trim(), expected_revision: t.revision };
    try {
      const saved = await api.updateKitTemplate(t.id, { ...body, client_request_id: key.keyFor([t.id, body]) });
      key.done();
      setRenaming(false);
      setNote(saved.save_replay ? "Your earlier rename went through." : "Renamed.");
      void qc.invalidateQueries({ queryKey: ["me", "kit-templates"] });
    } catch (err) {
      if (err instanceof ApiError && err.code === "stale_revision") {
        key.done();
        setNote("It was changed somewhere else since this page loaded. The saved name is shown; rename again if you still want to.");
        setRenaming(false);
        void qc.invalidateQueries({ queryKey: ["me", "kit-templates"] });
      } else {
        setError(err);
      }
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteKitTemplate(t.id);
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 404)) { // already gone is what was asked
        setError(err);
        setBusy(false);
        return;
      }
    }
    await qc.invalidateQueries({ queryKey: ["me", "kit-templates"] });
    onDeleted(t.name);
  }

  return (
    <li className="card stack-sm kit-templates-page__item">
      <div className="kit-templates-page__head">
        <span>
          <strong>{t.name}</strong>
          <span className="subtle"> · {t.checklist_count} checklist item{t.checklist_count === 1 ? "" : "s"} · {t.questions_count} question{t.questions_count === 1 ? "" : "s"} · saved {timeAgo(t.updated_at)}</span>
        </span>
        <span className="row">
          <Button size="sm" variant="ghost" data-template={t.id} aria-expanded={open} aria-label={`${open ? "Hide" : "Preview"}: ${t.name}`} onClick={() => setOpen(!open)}>{open ? "Hide" : "Preview"}</Button>
          <Button size="sm" variant="ghost" aria-label={`Rename: ${t.name}`} onClick={() => { setRenaming(!renaming); setName(t.name); setNote(""); }}>Rename</Button>
          <Button size="sm" variant="ghost" aria-label={`Delete: ${t.name}`} onClick={() => setConfirming(true)}>Delete</Button>
        </span>
      </div>
      {renaming && (
        <form className="row kit-templates-page__rename" onSubmit={(e) => void rename(e)}>
          <label className="field"><span className="field__label">New name</span>
            <input className="input" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </label>
          <Button size="sm" type="submit" variant="primary" loading={busy} disabled={!name.trim() || name.trim() === t.name}>Save name</Button>
          <Button size="sm" variant="ghost" onClick={() => setRenaming(false)}>Cancel</Button>
        </form>
      )}
      {confirming && (
        <div className="banner banner--warning stack-sm" role="group" aria-label={`Delete “${t.name}”`}>
          <p>Delete “{t.name}”? Kits you made from it keep their items. This can't be undone.</p>
          <span className="row">
            <Button size="sm" variant="danger" loading={busy} onClick={() => void remove()}>Delete template</Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>Keep it</Button>
          </span>
        </div>
      )}
      <p className="subtle" role="status">{note}</p>
      {open && (full.isPending ? <LoadingState label="Loading the template…" />
        : full.isError ? <ErrorState error={full.error} onRetry={() => void full.refetch()} />
        : (
          <div className="stack-sm" role="region" aria-label={`Preview: ${t.name}`}>
            {full.data.checklist.length > 0 && <ul className="mini-list">{full.data.checklist.map((c, i) => <li key={i}>{c.text}</li>)}</ul>}
            {full.data.questions.length > 0 && (
              <>
                <p className="field__label">Questions to ask</p>
                <ul className="mini-list">{full.data.questions.map((q, i) => <li key={i}>{q.text} <span className="subtle">· {GROUP_LABEL[q.group ?? "other"]}</span></li>)}</ul>
              </>
            )}
          </div>
        ))}
      <InlineError error={error} />
    </li>
  );
}
