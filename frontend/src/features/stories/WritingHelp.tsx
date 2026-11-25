import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/api/endpoints";
import type { StoryAssist, StoryAssistAction, StorySection } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/States";

import { SECTION_LABEL } from "./labels";

const ACTIONS: { id: StoryAssistAction; label: string }[] = [
  { id: "check", label: "Check for missing parts" },
  { id: "shorten", label: "Suggest a shorter version" },
  { id: "clarity", label: "Suggest clearer wording" },
];

/**
 * The built-in writing check. It works on what's in the form now (saved or not), only proposes,
 * and changes nothing until the learner accepts a proposal (and then saves). Questions are for
 * things only the learner knows; nothing is filled in for them.
 */
export function WritingHelp({ storyId, sections, onAccept }: {
  storyId: string;
  sections: Record<StorySection, string>;
  onAccept: (field: StorySection, text: string) => void;
}) {
  const [result, setResult] = useState<StoryAssist | null>(null);
  const [done, setDone] = useState<Record<string, "accepted" | "kept">>({});
  const run = useMutation({
    mutationFn: (action: StoryAssistAction) => api.assistStory(storyId, {
      action, situation: sections.situation, task: sections.task, action_text: sections.action, result: sections.result, reflection: sections.reflection,
    }),
    onSuccess: (r) => { setResult(r); setDone({}); },
  });
  return (
    <Card className="stack-sm writing-help">
      <h2 className="section-title">Writing check</h2>
      <p className="subtle">Fixed rules, not AI: your story isn't sent anywhere. It never adds facts, numbers or achievements.</p>
      <div className="row">
        {ACTIONS.map((a) => (
          <Button key={a.id} size="sm" loading={run.isPending && run.variables === a.id} onClick={() => run.mutate(a.id)}>{a.label}</Button>
        ))}
      </div>
      <InlineError error={run.error} />
      {result && (
        <div className="stack-sm" aria-live="polite">
          {result.questions.length > 0 && (
            <>
              <h3 className="section-title">Questions for you</h3>
              <ul className="mini-list">{result.questions.map((q) => <li key={q}>{q}</li>)}</ul>
            </>
          )}
          {result.proposals.map((p, i) => {
            const key = `${p.field}-${i}`;
            return (
              <section key={key} className="proposal" aria-label={`Suggestion for ${SECTION_LABEL[p.field]}`}>
                <h3 className="section-title">{SECTION_LABEL[p.field]}</h3>
                <div className="proposal__compare">
                  <div><p className="eyebrow">YOURS</p><p className="proposal__text">{p.original}</p></div>
                  <div><p className="eyebrow">SUGGESTED</p><p className="proposal__text">{p.proposed}</p></div>
                </div>
                <ul className="mini-list subtle">{p.changes.map((c) => <li key={c}>{c}</li>)}</ul>
                {done[key] ? (
                  <p className="subtle" role="status">{done[key] === "accepted" ? "Used in the form. Save to keep it." : "Kept yours."}</p>
                ) : (
                  <span className="row">
                    <Button size="sm" variant="primary" onClick={() => { onAccept(p.field, p.proposed); setDone((d) => ({ ...d, [key]: "accepted" })); }}>Use this version</Button>
                    <Button size="sm" variant="ghost" onClick={() => setDone((d) => ({ ...d, [key]: "kept" }))}>Keep mine</Button>
                  </span>
                )}
              </section>
            );
          })}
        </div>
      )}
    </Card>
  );
}
