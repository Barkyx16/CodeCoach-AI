import { Fragment } from "react";

import type { SharedView } from "@/api/types";
import { Badge } from "@/components/Badge";
import { titleCase } from "@/lib/format";

import { KIND_LABEL } from "@/features/careers/kinds";

/**
 * A shared snapshot, exactly as the reviewer sees it. The owner's preview renders this same
 * component from the server's preview, so "what you see" is "what they'll see".
 */
export function SharedSnapshot({ view, idPrefix }: { view: SharedView; idPrefix: string }) {
  const gapBefore = (position: number) => {
    const previous = position === 0 ? -1 : view.excerpt[position - 1]!.index;
    return view.excerpt[position]!.index - previous - 1;
  };
  const trailing = view.total_sentences - 1 - (view.excerpt.at(-1)?.index ?? -1);
  const gap = (n: number) => (
    <li className="shared-excerpt__gap">[…] {n} {n === 1 ? "sentence" : "sentences"} not shared</li>
  );
  return (
    <div className="stack shared-snapshot">
      <section className="stack-sm" aria-labelledby={`${idPrefix}-question`}>
        <p className="eyebrow">{view.career_title.toUpperCase()} · {view.kind === "interview_answer" ? "MOCK INTERVIEW" : "PRACTICE"} QUESTION</p>
        <h2 className="shared-snapshot__title" id={`${idPrefix}-question`}>{view.question.title}</h2>
        <p className="row">
          <Badge>{titleCase(view.question.difficulty)}</Badge>
          <Badge>{KIND_LABEL[view.question.kind] ?? titleCase(view.question.kind)}</Badge>
        </p>
        <p className="shared-snapshot__prompt">{view.question.prompt}</p>
      </section>

      <section className="stack-sm" aria-labelledby={`${idPrefix}-answer`}>
        <h2 className="section-title" id={`${idPrefix}-answer`}>The answer</h2>
        <p className="subtle">
          Written {view.answered_on}.{" "}
          {view.omitted_sentences > 0
            ? `${view.excerpt.length} of ${view.total_sentences} sentences shared; the gaps are marked.`
            : "Shared in full."}{" "}
          Sentences are numbered so comments can point at them.
        </p>
        <ol className="shared-excerpt">
          {view.excerpt.map((s, position) => (
            <Fragment key={s.index}>
              {gapBefore(position) > 0 && gap(gapBefore(position))}
              <li value={s.index + 1} id={`${idPrefix}-s${s.index}`}>{s.text}</li>
            </Fragment>
          ))}
          {trailing > 0 && gap(trailing)}
        </ol>
      </section>

      {view.followup && (
        <section className="stack-sm" aria-labelledby={`${idPrefix}-followup`}>
          <h2 className="section-title" id={`${idPrefix}-followup`}>Follow-up question</h2>
          <p><strong>{view.followup.asked_by} asked:</strong> {view.followup.question}</p>
          <blockquote className="shared-snapshot__reply">{view.followup.answer}</blockquote>
        </section>
      )}

      {view.ai_feedback && (
        <section className="stack-sm shared-ai" aria-labelledby={`${idPrefix}-ai`}>
          <h2 className="section-title" id={`${idPrefix}-ai`}>CodeCoach's automated feedback</h2>
          <p className="subtle">From CodeCoach's rubric (coach: {view.ai_feedback.coach}), not from a person. It checks what the answer covers, not whether it's right.</p>
          <p><strong>{view.ai_feedback.score}/100 · {view.ai_feedback.rating}.</strong> {view.ai_feedback.summary}</p>
          <ul className="rubric-check" aria-label="What the rubric looks for">
            {view.ai_feedback.points.map((p) => (
              <li key={p.label} className={p.covered ? "is-covered" : "is-missing"}>
                <span aria-hidden="true">{p.covered ? "✓" : "○"}</span>
                <div><strong>{p.label}</strong><span className="visually-hidden">{p.covered ? " (covered)" : " (missing)"}</span></div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {view.note && (
        <section className="stack-sm" aria-labelledby={`${idPrefix}-note`}>
          <h2 className="section-title" id={`${idPrefix}-note`}>Note from the learner</h2>
          <p className="shared-snapshot__note">{view.note}</p>
        </section>
      )}
    </div>
  );
}
