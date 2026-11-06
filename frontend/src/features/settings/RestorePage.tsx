import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { api } from "@/api/endpoints";
import { useRestoreBatches } from "@/api/queries";
import type { RestoreBatch, RestorePreview } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/States";
import { formatDateTime } from "@/lib/format";

const MAX_BYTES = 5 * 1024 * 1024;
const LABEL: Record<string, string> = { notes: "Notes", stories: "Stories", bookmarks: "Bookmarks", applications: "Applications" };

/**
 * Restore your own notes, stories, bookmarks and applications from a CodeCoach backup into this
 * account: check the file first, choose what to add, and undo a restore later (keeping edits).
 */
export function RestorePage() {
  const qc = useQueryClient();
  const batches = useRestoreBatches();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<{ name: string; text: string } | null>(null);
  const [preview, setPreview] = useState<RestorePreview | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<{ batch: RestoreBatch; again: boolean } | null>(null);

  async function check(f: File) {
    setError(null);
    setPreview(null);
    setResult(null);
    if (f.size > MAX_BYTES) {
      setError(new Error("That file is larger than 5 MB, so it can't be a CodeCoach backup."));
      return;
    }
    setBusy("preview");
    try {
      const text = await f.text();
      const p = await api.previewRestore(text);
      setFile({ name: f.name, text });
      setPreview(p);
      setChosen(p.categories.filter((c) => c.new > 0).map((c) => c.key));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function restore() {
    if (!file || !chosen.length) return;
    setBusy("restore");
    setError(null);
    try {
      const batch = await api.applyRestore(file.text, chosen);
      // The same file and choices again return the earlier restore instead of adding anything.
      setResult({ batch, again: preview?.previous.some((p) => p.id === batch.id) ?? false });
      void qc.invalidateQueries({ queryKey: ["me"] });
    } catch (e) {
      setError(e); // nothing was changed; the file and choices stay here
    } finally {
      setBusy(null);
    }
  }

  async function remove(b: RestoreBatch) {
    if (!window.confirm("Remove what this restore added? Anything you've changed since stays.")) return;
    setBusy(`remove-${b.id}`);
    setError(null);
    try {
      await api.removeRestore(b.id);
      void qc.invalidateQueries({ queryKey: ["me"] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="page restore-page">
      <BackLink fallback={{ to: "/settings", label: "Settings" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">YOUR DATA</p>
          <h1 className="page__title">Restore from a backup</h1>
          <p className="page__subtitle">Bring your notes, stories, bookmarks and applications from a CodeCoach backup (the file “Download my data” gives you) into this account. Nothing is replaced; only new records are added.</p>
        </div>
      </div>

      <Card className="stack-sm">
        <h2 className="section-title">What can and can't be restored</h2>
        <ul className="mini-list">
          <li><strong>Restored:</strong> notes, stories, bookmarks, and applications with their interview events.</li>
          <li><strong>Never restored:</strong> account details, sign-in and roles; practice results, scores and feedback (a file can't prove they happened); shared links, sessions and your schedule.</li>
          <li>Records already in your account are skipped, so restoring the same file twice adds nothing. A question that's no longer in the library is never swapped for a similar one.</li>
        </ul>
      </Card>

      <Card className="stack-sm">
        <h2 className="section-title">1. Choose the file</h2>
        <span className="row">
          <Button variant="primary" loading={busy === "preview"} onClick={() => fileRef.current?.click()}>Choose a backup file…</Button>
          {file && <span className="subtle">{file.name}</span>}
        </span>
        <input ref={fileRef} type="file" accept="application/json,.json" className="visually-hidden" aria-label="Backup file" tabIndex={-1}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void check(f); e.target.value = ""; }} />
        <p className="subtle">Up to 5 MB. The file is checked first; nothing changes until you choose to restore.</p>
      </Card>

      {preview && (
        <section className="card stack-sm restore-preview" aria-labelledby="restore-preview-title">
          <h2 className="section-title" id="restore-preview-title">2. Check what would be added</h2>
          <p className="subtle">Backup version {preview.export_version}{preview.exported_at ? `, made ${formatDateTime(preview.exported_at)}` : ""}.
            {preview.from_other_account ? " It came from a different account: only its content can come into yours, as yours." : ""}</p>
          {preview.previous.some((b) => b.status === "applied") && <p className="banner banner--info">You've restored from this file before. Records already here will be skipped.</p>}
          <fieldset className="stack-sm restore-choices">
            <legend className="field__label">Restore these</legend>
            {preview.categories.map((c) => (
              <div key={c.key} className="restore-choice">
                <label className="checkbox">
                  <input type="checkbox" disabled={c.new === 0} checked={chosen.includes(c.key)}
                    onChange={(e) => setChosen((x) => (e.target.checked ? [...x, c.key] : x.filter((k) => k !== c.key)))} />
                  {c.label}: {c.new} new
                </label>
                <p className="subtle">
                  {c.found} in the file{c.duplicates ? ` · ${c.duplicates} already here (skipped)` : ""}
                  {c.samples.length > 0 && <> · for example {c.samples.slice(0, 3).map((s) => `“${s}”`).join(", ")}</>}
                </p>
                {c.skipped.length > 0 && <ul className="mini-list subtle">{c.skipped.map((s) => <li key={s.reason}>{s.count} × {s.reason}</li>)}</ul>}
              </div>
            ))}
          </fieldset>
          {preview.not_restored.length > 0 && (
            <details>
              <summary>Not restored from this file ({preview.not_restored.length})</summary>
              <ul className="mini-list">{preview.not_restored.map((u) => <li key={u.key}><code>{u.key}</code> ({u.count}): {u.reason}</li>)}</ul>
            </details>
          )}
          {preview.ignored_fields > 0 && <p className="subtle">{preview.ignored_fields} unrecognised fields inside records were ignored.</p>}
          <span className="row">
            <Button variant="primary" loading={busy === "restore"} disabled={!chosen.length} onClick={() => void restore()}>
              Restore {chosen.length ? chosen.map((k) => LABEL[k]!.toLowerCase()).join(", ") : "nothing yet"}
            </Button>
          </span>
        </section>
      )}

      {result && (
        <p className="banner banner--success" role="status">
          {result.again ? "This file was already restored with these choices, so nothing new was added." : `Restored: ${Object.entries(result.batch.counts).map(([k, v]) => `${(v as { added: number }).added} ${LABEL[k]!.toLowerCase()}`).join(", ")}.`}
        </p>
      )}
      <InlineError error={error} />

      <Card className="stack-sm">
        <h2 className="section-title">Your restores</h2>
        {(batches.data ?? []).length === 0 ? <p className="subtle">None yet.</p> : (
          <ul className="restore-batches">
            {batches.data!.map((b) => (
              <li key={b.id}>
                <span className="row">
                  <strong>{formatDateTime(b.created_at)}</strong>
                  <Badge tone={b.status === "applied" ? "success" : b.status === "failed" ? "warning" : "neutral"}>{b.status === "applied" ? "Added" : b.status === "failed" ? "Stopped, nothing changed" : "Removed"}</Badge>
                  <span className="subtle">{b.categories.map((k) => LABEL[k] ?? k).join(", ")}</span>
                </span>
                {b.removal && <p className="subtle">Removed {(b.removal as { removed: number }).removed}; kept {(b.removal as { kept_edited: number }).kept_edited} you'd changed since; {(b.removal as { already_gone: number }).already_gone} were already gone.</p>}
                {b.status === "applied" && <Button size="sm" variant="ghost" loading={busy === `remove-${b.id}`} onClick={() => void remove(b)}>Remove what this added</Button>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
