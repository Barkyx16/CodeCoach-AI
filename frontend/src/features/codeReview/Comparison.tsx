import { useId } from "react";

import type { ReviewFeedback, ReviewFinding, ReviewReference, ReviewReferenceFinding } from "@/api/types";
import { Badge } from "@/components/Badge";
import { formatArgs, formatValue } from "@/lib/format";

import { where } from "./where";

const count = (n: number, noun: string) => `${n === 1 ? "One" : n} ${noun}${n === 1 ? "" : "s"}`;

/** Everything here renders learner and exercise text as text: React escapes it, nothing is parsed
 * as HTML or Markdown, so a comment like `<img onerror=…>` in the code or a finding is shown as typed. */

/** The code under review, read-only, one numbered line per row. `cited` lines are marked (and
 * said, for screen readers, in the label above). */
export function CodeView({ code, cited, label }: { code: string; cited?: [number, number] | null; label: string }) {
  const lines = code.split("\n");
  if (lines.length > 1 && lines[lines.length - 1] === "") lines.pop();
  const marked = (n: number) => cited != null && n >= cited[0] && n <= cited[1];
  return (
    <pre className="code-block review-code" tabIndex={0} aria-label={label}>
      <code>
        {lines.map((text, i) => (
          <span key={i} className={`review-code__line${marked(i + 1) ? " is-cited" : ""}`}>
            <span className="review-code__no">{i + 1}</span>{text}{"\n"}
          </span>
        ))}
      </code>
    </pre>
  );
}

const LOCATION: Record<ReviewFeedback["findings"][number]["location"], { label: string; tone: string }> = {
  defect: { label: "Points at an authored defect", tone: "success" },
  observation: { label: "Points at an authored observation (a preference)", tone: "info" },
  unsupported: { label: "Not covered by the authored review", tone: "warning" },
  broad: { label: "Too broad to compare", tone: "warning" },
};

function Evidence({ finding }: { finding: ReviewReferenceFinding }) {
  if (!finding.evidence.length) return null;
  return (
    <div className="review-evidence stack-sm">
      <h5 className="review-minor">Test evidence <span className="subtle">(the code was run on the problem's tests when this exercise was written)</span></h5>
      <ul className="mini-list">
        {finding.evidence.map((e) => (
          <li key={e.public_test}>
            Public test {e.public_test}: <code>{formatArgs(e.input)}</code> should give <code>{formatValue(e.expected)}</code>; this code returns <code>{formatValue(e.actual)}</code>.
          </li>
        ))}
      </ul>
    </div>
  );
}

/** One authored finding: its kind first, so a preference is never read as a bug. */
function ReferenceItem({ finding, yours }: { finding: ReviewReferenceFinding; yours?: string[] | null }) {
  const titleId = useId();
  const [start, end] = finding.lines as [number, number];
  return (
    <li className={`card stack-sm review-ref review-ref--${finding.kind}`} aria-labelledby={titleId}>
      <p className="row">
        {finding.kind === "defect"
          ? <Badge tone="danger">Defect · shown by a public test</Badge>
          : <Badge tone="info">Observation · a preference, not a defect</Badge>}
        <span className="subtle">{where(start, end)}</span>
      </p>
      <h4 className="review-ref__title" id={titleId}>{finding.title}</h4>
      <pre className="code-block review-excerpt" aria-label={`The code at ${where(start, end)}`}>{finding.excerpt}</pre>
      <p>{finding.explanation}</p>
      <p><strong>What happens:</strong> {finding.consequence}</p>
      <p><strong>What to change:</strong> {finding.repair}</p>
      {finding.why_preference && <p><strong>Why it's a preference:</strong> {finding.why_preference}</p>}
      <Evidence finding={finding} />
      {yours != null && (
        <p className="subtle">{yours.length ? `In your review: ${yours.map((id) => `finding ${id}`).join(", ")}.` : "Not in your review."}</p>
      )}
    </li>
  );
}

export function ReferenceView({ reference, raisedBy, heading = "The authored review" }: {
  reference: ReviewReference;
  /** reference finding id → the learner's finding numbers that point at it (after a review was sent) */
  raisedBy?: Record<string, string[]>;
  heading?: string;
}) {
  const defects = reference.findings.filter((f) => f.kind === "defect").length;
  const observations = reference.findings.length - defects;
  return (
    <section className="stack-sm review-reference" aria-label={heading}>
      <h3 className="section-title">{heading}</h3>
      <p>{defects === 0 ? "No defect: this code passes every test of the problem. Everything below is a preference."
        : `${count(defects, "defect")} shown by ${defects === 1 ? "a public test" : "public tests"}${observations ? `, and ${count(observations, "observation")} labelled as ${observations === 1 ? "a preference" : "preferences"}` : ""}.`}</p>
      <ul className="stack-sm review-ref-list">
        {reference.findings.map((f) => <ReferenceItem key={f.id} finding={f} yours={raisedBy ? raisedBy[f.id] ?? [] : null} />)}
      </ul>
      <h4 className="review-minor">Debrief</h4>
      <p>{reference.debrief}</p>
      {reference.repaired_code && (
        <details>
          <summary>One correct repair</summary>
          <p className="subtle">Yours doesn't have to look like this.</p>
          <pre className="code-block"><code>{reference.repaired_code}</code></pre>
        </details>
      )}
    </section>
  );
}

/** A sent review next to the authored one. Qualitative notes about the learner's findings are kept
 * apart from the test evidence (which belongs to the authored findings), and there's no score. */
export function ComparisonView({ findings, summary, feedback, reference, afterReveal }: {
  findings: ReviewFinding[];
  summary: string;
  feedback: ReviewFeedback;
  reference: ReviewReference;
  afterReveal: boolean;
}) {
  const number = new Map(findings.map((f, i) => [f.id, String(i + 1)]));
  const notes = new Map(feedback.findings.map((f) => [f.id, f]));
  const raisedBy = Object.fromEntries(feedback.reference.map((r) => [r.id, r.raised_by.map((id) => number.get(id) ?? id)]));
  return (
    <div className="stack review-comparison">
      <section className="card stack-sm" aria-label="How your review compares">
        <h3 className="section-title">How your review compares</h3>
        {feedback.summary.map((line) => <p key={line}>{line}</p>)}
        {afterReveal && <p className="subtle">Written after reading the authored review.</p>}
        <p className="subtle">{feedback.method}</p>
      </section>
      <section className="stack-sm" aria-label="Your findings">
        <h3 className="section-title">Your findings</h3>
        {findings.length === 0 && <p>No findings.</p>}
        {summary && <p><strong>Your summary:</strong> <span className="review-text">{summary}</span></p>}
        <ol className="stack-sm review-your-list">
          {findings.map((f, i) => {
            const fb = notes.get(f.id);
            return (
              <li key={f.id} className="card stack-sm">
                <p className="row"><strong>Finding {i + 1}</strong><span className="subtle">{where(f.start_line, f.end_line)}</span>
                  {fb && <Badge tone={LOCATION[fb.location].tone}>{LOCATION[fb.location].label}</Badge>}</p>
                <pre className="code-block review-excerpt" aria-label={`The code you cited, ${where(f.start_line, f.end_line)}`}>{f.excerpt}</pre>
                <dl className="review-fields">
                  <dt>What's wrong</dt><dd className="review-text">{f.problem || "—"}</dd>
                  <dt>What happens</dt><dd className="review-text">{f.consequence || "—"}</dd>
                  <dt>What to change</dt><dd className="review-text">{f.repair || "—"}</dd>
                </dl>
                {fb && <ul className="mini-list review-notes" aria-label={`Notes on finding ${i + 1}`}>{fb.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
              </li>
            );
          })}
        </ol>
      </section>
      <ReferenceView reference={reference} raisedBy={raisedBy} />
    </div>
  );
}
