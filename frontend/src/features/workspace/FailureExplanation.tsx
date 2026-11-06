import { Fragment, type ReactNode } from "react";

import type { ExplainFailureResponse } from "@/api/types";
import { Badge } from "@/components/Badge";
import { FallbackNotice } from "@/components/FallbackNotice";

const CAUSE_LABEL: Record<ExplainFailureResponse["explanation"]["cause"], string> = {
  "compile-error": "Compile error",
  "index-out-of-bounds": "Index out of bounds",
  "null-reference": "Null reference",
  arithmetic: "Arithmetic",
  "number-format": "Number parsing",
  "recursion-depth": "Recursion depth",
  "time-limit": "Too slow",
  "memory-limit": "Too much memory",
  crash: "Crash",
  "wrong-answer": "Wrong answer",
  "hidden-edge-case": "Hidden edge case",
  overflow: "Integer overflow",
  other: "Other",
};

/** Render `backtick` spans as <code>. Text is plain (never HTML), so this can't inject markup. */
function withInlineCode(text: string): ReactNode {
  return text.split(/(`[^`\n]+`)/g).map((part, i) =>
    part.length > 2 && part.startsWith("`") && part.endsWith("`")
      ? <code key={i}>{part.slice(1, -1)}</code>
      : <Fragment key={i}>{part}</Fragment>,
  );
}

export function FailureExplanationView({ data, onHighlightLine }: {
  data: ExplainFailureResponse;
  onHighlightLine?(line: number | null): void;
}) {
  const e = data.explanation;
  return (
    <div className="explanation stack" aria-live="polite">
      <div className="row">
        <Badge tone="warning">{CAUSE_LABEL[e.cause]}</Badge>
        <span className="subtle">confidence: {e.confidence}</span>
        {e.line_hint && onHighlightLine && (
          <button type="button" className="link-button" onClick={() => onHighlightLine(e.line_hint ?? null)}>
            Go to line {e.line_hint}
          </button>
        )}
      </div>
      <p className="explanation__headline">{withInlineCode(e.headline)}</p>
      <p>{withInlineCode(e.explanation)}</p>
      {e.evidence.trim()
        ? <p className="explanation__evidence"><span className="subtle">Based on:</span> {withInlineCode(e.evidence)}</p>
        : <p className="explanation__evidence subtle">The coach quoted something that isn't in this submission's results, so its evidence isn't shown. Check the explanation against the test results above.</p>}
      {e.next_steps.length > 0 && (
        <div>
          <h3 className="section-title">Try this</h3>
          <ol className="explanation__steps">{e.next_steps.map((s) => <li key={s}>{withInlineCode(s)}</li>)}</ol>
        </div>
      )}
      {e.concept && <p className="subtle">Concept to review: <strong>{e.concept}</strong></p>}
      <FallbackNotice provider={data.provider} />
      <p className="subtle">
        {data.disclaimer}
        {data.cached ? " Saved explanation (didn't use your AI budget)." : ""}
      </p>
    </div>
  );
}
