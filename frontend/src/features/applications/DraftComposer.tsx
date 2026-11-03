import { useId, useState } from "react";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";

import { draftMessage, type DraftFacts } from "./drafts";

/**
 * A follow-up or thank-you draft from facts the learner types here. Nothing is stored or sent:
 * the learner reviews and edits it, then copies or downloads it. Creating a draft never changes
 * the application's stage.
 */
export function DraftComposer({ role, employer }: { role: string; employer: string }) {
  const id = useId();
  const [facts, setFacts] = useState<Omit<DraftFacts, "role" | "employer">>({ kind: "thank_you", recipient: "", when: "", point: "", sender: "" });
  const [text, setText] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const draft = draftMessage({ ...facts, role, employer });
  const full = `Subject: ${draft.subject}\n\n${draft.body}`;
  const set = (k: keyof typeof facts, v: string) => { setFacts((f) => ({ ...f, [k]: v })); setText(null); setStatus(""); };

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
      <p className="subtle">A draft from what you type below. CodeCoach doesn't send messages, contact employers or keep this text; copy it into your own email if you want to send it.</p>
      <div className="app-form__grid">
        <label className="field"><span className="field__label">Kind</span>
          <select className="select" value={facts.kind} onChange={(e) => set("kind", e.target.value)}>
            <option value="thank_you">Thank you after an interview</option>
            <option value="follow_up">Follow up on an application</option>
          </select>
        </label>
        <label className="field"><span className="field__label">To <span className="subtle">(optional)</span></span><input className="input" maxLength={80} value={facts.recipient} onChange={(e) => set("recipient", e.target.value)} placeholder="Ms Lee" /></label>
        <label className="field"><span className="field__label">When <span className="subtle">(optional)</span></span><input className="input" maxLength={60} value={facts.when} onChange={(e) => set("when", e.target.value)} placeholder="on Tuesday" /></label>
        <label className="field"><span className="field__label">Your name <span className="subtle">(optional)</span></span><input className="input" maxLength={80} value={facts.sender} onChange={(e) => set("sender", e.target.value)} /></label>
      </div>
      <label className="field"><span className="field__label">Something you want to mention <span className="subtle">(optional, in your words)</span></span>
        <textarea className="input" rows={2} maxLength={600} value={facts.point} onChange={(e) => set("point", e.target.value)} />
      </label>
      <label className="field" htmlFor={id}><span className="field__label">Draft (edit it as you like)</span></label>
      <textarea id={id} className="input draft-composer__text" rows={9} value={text ?? full} onChange={(e) => setText(e.target.value)} />
      <span className="row">
        <Button size="sm" onClick={() => void copy()}>Copy</Button>
        <Button size="sm" variant="ghost" onClick={download}>Download as text</Button>
      </span>
      <p className="subtle" role="status">{status}</p>
    </Card>
  );
}
