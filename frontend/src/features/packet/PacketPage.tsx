import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useBookmarks, useNotes, useStories } from "@/api/queries";
import type { Packet } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/States";

import { LOCAL_FILE, packetFilename, packetText, SOURCE_LABEL, TYPE_LABEL } from "./packetText";

/** At most this many items, the server's limit (docs/PACKET.md). */
const MAX_ITEMS = 20;
type Kind = "question" | "note" | "story";
const PART_LABEL: Record<Kind, [string, string][]> = {
  question: [["question", "The question and tips"], ["your_answer", "Your latest answer"], ["feedback", "Automated feedback on it"]],
  note: [["note", "Note"], ["reflection", "Reflection"], ["excerpt", "The excerpt it quotes"]],
  story: [["situation", "Situation"], ["task", "Task"], ["action", "Action"], ["result", "Result"], ["reflection", "Reflection"], ["short_version", "Short version"], ["long_version", "Longer version"]],
};
const DEFAULT_PARTS: Record<Kind, string[]> = { question: ["question"], note: ["note"], story: ["situation", "task", "action", "result"] };

interface Chosen { type: Kind; id: string; title: string; parts: string[] }

/**
 * /packet: a private practice packet (Volume 11, prompt 8; docs/PACKET.md). Choose questions you
 * bookmarked, notes and stories, which parts and in what order; preview; then download a text file
 * or print / save as PDF from that preview. The file is made on this device from the preview shown:
 * nothing is stored in the account, sent, shared or emailed. Changing a choice after previewing
 * hides the download until the packet is previewed again.
 */
export function PacketPage() {
  const marks = useBookmarks();
  const notes = useNotes({ status: "active", page_size: 50 });
  const stories = useStories({});
  const [chosen, setChosen] = useState<Chosen[]>([]);
  const [title, setTitle] = useState("My practice packet");
  const [keepContact, setKeepContact] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [preview, setPreview] = useState<{ packet: Packet; forRequest: string } | null>(null);
  const previewHeading = useRef<HTMLHeadingElement>(null);
  const focusPreview = useRef(false);

  const request = useMemo(() => ({
    title: title.trim() || "My practice packet",
    keep_contact_details: keepContact,
    items: chosen.map((c) => ({ type: c.type, id: c.id, parts: c.parts })),
  }), [title, keepContact, chosen]);
  const requestKey = JSON.stringify(request);
  const stale = preview !== null && preview.forRequest !== requestKey;

  useEffect(() => {
    if (focusPreview.current && preview) {
      focusPreview.current = false;
      previewHeading.current?.focus();
    }
  }, [preview]);

  const isChosen = (type: Kind, id: string) => chosen.some((c) => c.type === type && c.id === id);
  const toggle = (type: Kind, id: string, itemTitle: string, on: boolean) => setChosen((now) => on
    ? (now.length >= MAX_ITEMS || now.some((c) => c.type === type && c.id === id) ? now : [...now, { type, id, title: itemTitle, parts: DEFAULT_PARTS[type] }])
    : now.filter((c) => !(c.type === type && c.id === id)));
  const move = (i: number, by: -1 | 1) => setChosen((now) => {
    const next = [...now];
    const [c] = next.splice(i, 1);
    next.splice(i + by, 0, c!);
    return next;
  });
  const setParts = (i: number, part: string, on: boolean) => setChosen((now) => now.map((c, j) => (j !== i ? c : {
    ...c, parts: on ? PART_LABEL[c.type].map(([p]) => p).filter((p) => p === part || c.parts.includes(p)) : c.parts.filter((p) => p !== part),
  })));
  const titleOf = (type: string, id: string) => chosen.find((c) => c.type === type && c.id === id)?.title ?? `A ${type} you chose`;

  async function makePreview() {
    setBusy(true);
    setError(null);
    try {
      const packet = await api.previewPacket(request);
      focusPreview.current = true;
      setPreview({ packet, forRequest: requestKey });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  function download(p: Packet) {
    const blob = new Blob([packetText(p, titleOf)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = packetFilename(p);
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  const questions = (marks.data ?? []).filter((b) => b.item_type === "question" && b.available);
  const full = chosen.length >= MAX_ITEMS;
  const emptyParts = chosen.some((c) => c.parts.length === 0);
  return (
    <div className="page packet-page">
      <div className="page__header no-print">
        <div>
          <p className="eyebrow">PRIVATE · MADE ON YOUR DEVICE</p>
          <h1 className="page__title">Practice packet</h1>
          <p className="page__subtitle">Choose questions, notes and stories, and their order. Preview the packet, then save it as a text file or print it (or save it as a PDF).</p>
        </div>
      </div>
      <div className="stack">
        <p className="banner banner--info no-print" role="note">
          The file is made on this device from the preview you see: it isn't stored in your account, sent, emailed or shared. It isn't a
          backup either (that's <Link to="/settings/data">Your data</Link>). Never in a packet: meeting links, interview kits, applications,
          offer terms, recordings, account details, or a coding problem's tests.
        </p>
        <div className="packet-page__layout no-print">
          <Card className="stack-sm">
            <h2 className="section-title">Choose</h2>
            <p className="subtle" aria-live="polite">{chosen.length} of up to {MAX_ITEMS} chosen.</p>
            <ChooseList legend="Questions you bookmarked" empty={<>None yet. <Link to="/problems?view=questions">Bookmark questions</Link> to add them here.</>}
              rows={questions.map((b) => ({ type: "question" as const, id: `${b.track}/${b.ref_id}`, title: b.title }))} isChosen={isChosen} full={full} onToggle={toggle} />
            <ChooseList legend="Your notes" empty={<>No notes yet.</>}
              rows={(notes.data?.items ?? []).map((n) => ({ type: "note" as const, id: n.id, title: n.title || "Untitled note" }))} isChosen={isChosen} full={full} onToggle={toggle} />
            <ChooseList legend="Your stories" empty={<>No stories yet.</>}
              rows={(stories.data ?? []).map((s) => ({ type: "story" as const, id: s.id, title: s.title }))} isChosen={isChosen} full={full} onToggle={toggle} />
            {full && <p className="subtle">Up to {MAX_ITEMS} in one packet.</p>}
          </Card>
          <Card className="stack-sm">
            <h2 className="section-title">Your packet</h2>
            <label className="field"><span className="field__label">Title</span>
              <input className="input" maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} />
            </label>
            {chosen.length === 0 ? <p className="subtle">Nothing chosen yet. A packet holds only what you choose.</p> : (
              <ol className="packet-page__order">
                {chosen.map((c, i) => (
                  <li key={`${c.type}:${c.id}`} className="stack-sm">
                    <div className="packet-page__row">
                      <span><strong>{c.title}</strong> <span className="subtle">· {TYPE_LABEL[c.type]}</span></span>
                      <span className="row">
                        <Button size="sm" variant="ghost" aria-label={`Move up: ${c.title}`} disabled={i === 0} onClick={() => move(i, -1)}>↑</Button>
                        <Button size="sm" variant="ghost" aria-label={`Move down: ${c.title}`} disabled={i === chosen.length - 1} onClick={() => move(i, 1)}>↓</Button>
                        <Button size="sm" variant="ghost" aria-label={`Remove: ${c.title}`} onClick={() => toggle(c.type, c.id, c.title, false)}>Remove</Button>
                      </span>
                    </div>
                    <fieldset className="packet-page__parts">
                      <legend className="visually-hidden">Parts of {c.title}</legend>
                      {PART_LABEL[c.type].map(([part, label]) => (
                        <label key={part} className="checkbox"><input type="checkbox" checked={c.parts.includes(part)} onChange={(e) => setParts(i, part, e.target.checked)} />{label}</label>
                      ))}
                    </fieldset>
                    {c.parts.length === 0 && <p className="subtle">Choose at least one part, or remove it.</p>}
                  </li>
                ))}
              </ol>
            )}
            <label className="checkbox"><input type="checkbox" checked={keepContact} onChange={(e) => setKeepContact(e.target.checked)} />
              Keep email addresses and phone numbers in my own text (they're removed otherwise)</label>
            <span className="row">
              <Button variant="primary" loading={busy} disabled={chosen.length === 0 || emptyParts} onClick={() => void makePreview()}>
                {preview ? "Preview again" : "Preview packet"}
              </Button>
            </span>
            <InlineError error={error} action="Making the preview" />
          </Card>
        </div>

        {preview && (
          <section className="stack" aria-labelledby="packet-preview-title">
            <div className="no-print stack-sm">
              <h2 className="section-title" id="packet-preview-title" ref={previewHeading} tabIndex={-1}>Preview</h2>
              {stale ? (
                <p className="banner banner--warning" role="status">Your choices changed since this preview. Preview again before saving, so the file is what you see.</p>
              ) : (
                <>
                  <p className="subtle" role="status">This is exactly what the file will hold. {LOCAL_FILE}</p>
                  <span className="row">
                    <Button onClick={() => download(preview.packet)}>Save as a text file</Button>
                    <Button variant="ghost" onClick={() => window.print()}>Print or save as PDF…</Button>
                  </span>
                </>
              )}
              {preview.packet.unavailable.length > 0 && (
                <div className="banner banner--warning" role="note">
                  <p>{preview.packet.unavailable.length === 1 ? "One of your choices isn't" : `${preview.packet.unavailable.length} of your choices aren't`} in the packet:</p>
                  <ul className="mini-list">{preview.packet.unavailable.map((u) => <li key={`${u.type}:${u.id}`}>{titleOf(u.type, u.id)}: {u.reason}</li>)}</ul>
                </div>
              )}
              {preview.packet.redacted > 0 && <p className="subtle">{preview.packet.redacted} email address{preview.packet.redacted === 1 ? "" : "es"} or phone number{preview.packet.redacted === 1 ? "" : "s"} removed from your own text.</p>}
            </div>
            {!stale && <PacketView packet={preview.packet} titleOf={titleOf} />}
          </section>
        )}
      </div>
    </div>
  );
}

function ChooseList({ legend, rows, empty, isChosen, full, onToggle }: {
  legend: string;
  rows: { type: Kind; id: string; title: string }[];
  empty: React.ReactNode;
  isChosen: (type: Kind, id: string) => boolean;
  full: boolean;
  onToggle: (type: Kind, id: string, title: string, on: boolean) => void;
}) {
  return (
    <fieldset className="stack-sm packet-page__choose">
      <legend className="field__label">{legend}</legend>
      {rows.length === 0 ? <p className="subtle">{empty}</p> : rows.map((r) => {
        const on = isChosen(r.type, r.id);
        return (
          <label key={r.id} className="checkbox">
            <input type="checkbox" checked={on} disabled={!on && full} onChange={(e) => onToggle(r.type, r.id, r.title, e.target.checked)} />{r.title}
          </label>
        );
      })}
    </fieldset>
  );
}

/** The packet as it will print: the same content as the text file. */
function PacketView({ packet, titleOf }: { packet: Packet; titleOf: (type: string, id: string) => string }) {
  return (
    <article className="card stack print-packet" aria-label="Packet preview">
      <header className="stack-sm">
        <h2 className="print-packet__title">{packet.title}</h2>
        <p className="subtle">Practice packet · assembled {packet.assembled_at.slice(0, 10)} {packet.assembled_at.slice(11, 16)} UTC · fingerprint {packet.digest}</p>
        <p className="subtle">{LOCAL_FILE}</p>
      </header>
      <ol className="print-packet__items">
        {packet.items.map((item) => (
          <li key={`${item.type}:${item.id}`} className="stack-sm print-packet__item">
            <h3>{item.title} <span className="subtle">({TYPE_LABEL[item.type]})</span></h3>
            {(item.notes ?? []).map((n) => <p key={n} className="subtle">Note: {n}</p>)}
            {item.sections.map((s, j) => (
              <section key={j} className={`print-packet__section print-packet__section--${s.kind}`}>
                <h4>{s.heading} <span className="print-packet__source">[{SOURCE_LABEL[s.kind]}]</span></h4>
                <p className="subtle print-packet__provenance">{s.provenance}</p>
                <div className="print-packet__text">{s.text}</div>
              </section>
            ))}
          </li>
        ))}
      </ol>
      {packet.unavailable.length > 0 && (
        <div>
          <p><strong>Not included:</strong></p>
          <ul className="mini-list">{packet.unavailable.map((u) => <li key={`${u.type}:${u.id}`}>{titleOf(u.type, u.id)}: {u.reason}</li>)}</ul>
        </div>
      )}
      {packet.shortened && <p className="subtle">Some text was shortened: a packet holds a bounded amount.</p>}
    </article>
  );
}
