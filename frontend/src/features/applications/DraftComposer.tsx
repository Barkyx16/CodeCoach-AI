import { useId, useState } from "react";

import type { ApplicationEvent } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";

import { formatDay } from "./dates";
import { draftMessage, type DraftFacts } from "./drafts";

type Typed = Omit<DraftFacts, "role" | "employer">;

/** What the chosen interview adds to the draft, from the recorded event (nothing else). */
function interviewPhrase(e: ApplicationEvent, withTime: boolean): string {
  const day = e.on_date ? `on ${formatDay(e.on_date)}` : "";
  const time = withTime && e.local_time ? ` at ${e.local_time}${e.timezone ? ` (${e.timezone.replace(/_/g, " ")})` : ""}` : "";
  return `${day}${time}`;
}

/**
 * A follow-up or thank-you draft from facts the learner types or explicitly picks here. Nothing is
 * stored or sent: the learner reviews and edits it, then copies or downloads it. Creating a draft
 * never changes the application's stage.
 *
 * Context is opt-in: role and employer come from the application; a recorded interview's date (and,
 * separately, its time) is used only when chosen. Once the learner edits the draft, it's never
 * replaced silently: if the details behind it change, they choose to update it or keep their text.
 */
export function DraftComposer({ role, employer, events = [] }: { role: string; employer: string; events?: ApplicationEvent[] }) {
  const id = useId();
  const [facts, setFacts] = useState<Typed>({ kind: "thank_you", recipient: "", when: "", point: "", sender: "" });
  const [eventId, setEventId] = useState(""); // no interview mentioned unless chosen
  const [withTime, setWithTime] = useState(false);
  const [text, setText] = useState<string | null>(null); // null: the draft follows the details
  const [editedFrom, setEditedFrom] = useState<string | null>(null); // the draft the edits started from
  const [status, setStatus] = useState("");
  const dated = events.filter((e) => e.on_date);
  const chosen = dated.find((e) => e.id === eventId) ?? null; // a removed or undated event is just not chosen
  const when = chosen ? interviewPhrase(chosen, withTime) : facts.when;
  const draft = draftMessage({ ...facts, when, role, employer });
  const full = `Subject: ${draft.subject}\n\n${draft.body}`;
  const stale = text !== null && editedFrom !== null && editedFrom !== full;
  const set = (k: keyof Typed, v: string) => { setFacts((f) => ({ ...f, [k]: v })); setStatus(""); };

  async function copy() {
    try {
      await navigator.clipboard.writeText(text ?? full);
      setStatus("Copied. Paste it into your own email to send it.");
    } catch {
      setStatus("Couldn't copy here: select the text and copy it yourself.");
    }
  }
  function download() {
    const blob = new Blob([text ?? full], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${facts.kind === "thank_you" ? "thank-you" : "follow-up"}-${employer.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "draft"}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    setStatus("Downloaded as a text file.");
  }

  return (
    <Card className="stack-sm draft-composer">
      <h2 className="section-title">Write a message</h2>
      <p className="subtle">A draft from what you type or choose below. CodeCoach doesn't send messages, contact employers or keep this text; copy it into your own email if you want to send it.</p>
      <div className="app-form__grid">
        <label className="field"><span className="field__label">Kind</span>
          <select className="select" value={facts.kind} onChange={(e) => set("kind", e.target.value)}>
            <option value="thank_you">Thank you after an interview</option>
            <option value="follow_up">Follow up on an application</option>
          </select>
        </label>
        <label className="field"><span className="field__label">To <span className="subtle">(optional)</span></span><input className="input" maxLength={80} value={facts.recipient} onChange={(e) => set("recipient", e.target.value)} placeholder="Ms Lee" /></label>
        <label className="field"><span className="field__label">When <span className="subtle">(optional)</span></span>
          <input className="input" maxLength={60} value={chosen ? when : facts.when} disabled={chosen !== null}
            onChange={(e) => set("when", e.target.value)} placeholder="on Tuesday" />
        </label>
        <label className="field"><span className="field__label">Your name <span className="subtle">(optional)</span></span><input className="input" maxLength={80} value={facts.sender} onChange={(e) => set("sender", e.target.value)} /></label>
      </div>
      {dated.length > 0 && (
        <fieldset className="stack-sm draft-composer__context">
          <legend className="field__label">Mention a recorded interview <span className="subtle">(optional)</span></legend>
          <label className="field"><span className="visually-hidden">Interview</span>
            <select className="select" value={chosen?.id ?? ""} onChange={(e) => { setEventId(e.target.value); setStatus(""); }}>
              <option value="">Don't mention one</option>
              {dated.map((e) => <option key={e.id} value={e.id}>{e.title} · {formatDay(e.on_date!)}</option>)}
            </select>
          </label>
          {chosen?.local_time && (
            <label className="checkbox"><input type="checkbox" checked={withTime} onChange={(e) => setWithTime(e.target.checked)} />Include the time</label>
          )}
          {chosen && (
            <p className="subtle">From your recorded event “{chosen.title}”. A recorded time doesn't mean it happened as planned: mention it only if it did.</p>
          )}
        </fieldset>
      )}
      <label className="field"><span className="field__label">Something you want to mention <span className="subtle">(optional, in your words)</span></span>
        <textarea className="input" rows={2} maxLength={600} value={facts.point} onChange={(e) => set("point", e.target.value)} />
      </label>
      <label className="field" htmlFor={id}><span className="field__label">Draft (edit it as you like)</span></label>
      <textarea id={id} className="input draft-composer__text" rows={9} value={text ?? full}
        onChange={(e) => { if (text === null) setEditedFrom(full); setText(e.target.value); setStatus(""); }} />
      {stale && (
        <div className="banner banner--info stack-sm" role="status">
          <span>The details behind this draft changed since you edited it. Your text is unchanged.</span>
          <span className="row">
            <Button size="sm" onClick={() => { setText(null); setEditedFrom(null); }}>Update the draft (replaces your edits)</Button>
            <Button size="sm" variant="ghost" onClick={() => setEditedFrom(full)}>Keep my text</Button>
          </span>
        </div>
      )}
      <span className="row">
        <Button size="sm" onClick={() => void copy()}>Copy</Button>
        <Button size="sm" variant="ghost" onClick={download}>Download as text</Button>
      </span>
      <p className="subtle" role="status">{status}</p>
    </Card>
  );
}
