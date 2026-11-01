import { useMemo, useState } from "react";

import { ApiError } from "@/api/client";
import { useAIHistory, useAIUsage, useHint, useReview } from "@/api/queries";
import type { CodeReview, HintLevel, HintResponse, ReviewResponse } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";
import { Tabs } from "@/components/Tabs";

const LEVELS: { level: HintLevel; name: string; blurb: string }[] = [
  { level: 1, name: "Nudge", blurb: "A question that points you in the right direction" },
  { level: 2, name: "Concept", blurb: "The key idea or data structure" },
  { level: 3, name: "Pseudocode", blurb: "Step-by-step outline" },
  { level: 4, name: "Full explanation", blurb: "Complete approach, complexity and edge cases" },
];

interface StoredHint {
  level: number;
  hint: string;
  focus_area?: string;
  encouragement?: string;
}

interface CoachPanelProps {
  problemSlug: string;
  maxLevel: number;
  code: string;
  submissionId: string | null;
  enabled: boolean;
  onSignInRequired(): void;
  onHighlightLine(line: number | null): void;
}

export function CoachPanel({ problemSlug, maxLevel, code, submissionId, enabled, onSignInRequired, onHighlightLine }: CoachPanelProps) {
  const [tab, setTab] = useState<"hints" | "review">("hints");
  const usage = useAIUsage(enabled);

  return (
    <section className="coach" aria-label="AI coach">
      <div className="coach__header">
        <h2 className="section-title">Your coach</h2>
        {usage.data && (
          <span className="subtle" title="AI requests left in the last 24 hours">
            {usage.data.remaining_today}/{usage.data.daily_limit} left
          </span>
        )}
      </div>
      {usage.data && <p className="coach__provider subtle">{usage.data.provider === "offline" ? "Built-in coach · curated hints and static analysis" : `Coach provider: ${usage.data.provider}`}</p>}
      <Tabs label="Coach mode" tabs={[{ id: "hints", label: "Hints" }, { id: "review", label: "Code review" }] as const}
        value={tab} onChange={setTab} panelClassName="coach__tab-panel">
      {!enabled ? (
        <div className="coach__signin stack">
          <p className="muted">The AI coach gives progressive hints and structured reviews of your code.</p>
          <Button variant="primary" onClick={onSignInRequired}>Sign in or continue as guest</Button>
        </div>
      ) : tab === "hints" ? (
        <HintLadder problemSlug={problemSlug} maxLevel={maxLevel} code={code} />
      ) : (
        <ReviewTab problemSlug={problemSlug} code={code} submissionId={submissionId} onHighlightLine={onHighlightLine} />
      )}
      </Tabs>
    </section>
  );
}

function HintLadder({ problemSlug, maxLevel, code }: { problemSlug: string; maxLevel: number; code: string }) {
  // Previously unlocked hints come back from saved history, so the ladder survives reloads.
  const history = useAIHistory({ problem_slug: problemSlug, action: "hint", page_size: 50 });
  const hint = useHint();
  const [fresh, setFresh] = useState<HintResponse[]>([]);

  const hints = useMemo(() => {
    const byLevel = new Map<number, StoredHint>();
    for (const item of [...(history.data?.items ?? [])].reverse()) {
      if (item.hint_level && item.response) byLevel.set(item.hint_level, { level: item.hint_level, ...(item.response as Omit<StoredHint, "level">) });
    }
    for (const h of fresh) byLevel.set(h.level, { level: h.level, ...h.content });
    return [...byLevel.values()].sort((a, b) => a.level - b.level);
  }, [history.data, fresh]);

  const highest = hints.reduce((m, h) => Math.max(m, h.level), 0);
  const next = LEVELS.find((l) => l.level === highest + 1 && l.level <= maxLevel);
  const budgetExhausted = hint.error instanceof ApiError && hint.error.code === "rate_limited";

  async function request(level: HintLevel) {
    const response = await hint.mutateAsync({ problem_slug: problemSlug, level, source_code: code });
    setFresh((f) => [...f.filter((h) => h.level !== response.level), response]);
  }

  return (
    <div className="hints stack">
      {hints.length === 0 && !history.isPending && (
        <p className="muted">Stuck? Hints unlock one level at a time, so you only see as much as you need.</p>
      )}
      <ol className="hint-list">
        {hints.map((h) => (
          <li key={h.level} className="hint">
            <div className="hint__meta">
              <Badge tone="info">Level {h.level} · {LEVELS[h.level - 1]?.name}</Badge>
              {h.focus_area && <span className="subtle">{h.focus_area}</span>}
            </div>
            <p className="hint__text">{h.hint}</p>
            {h.encouragement && <p className="hint__encouragement subtle">{h.encouragement}</p>}
          </li>
        ))}
      </ol>
      {next ? (
        <div className="hint-next">
          <Button variant={highest === 0 ? "primary" : "secondary"} loading={hint.isPending} disabled={budgetExhausted}
            onClick={() => void request(next.level).catch(() => undefined)}>
            {highest === 0 ? "Get a hint" : `Unlock level ${next.level}: ${next.name}`}
          </Button>
          <span className="subtle">{next.blurb}</span>
          {next.level === 4 && <span className="subtle">Heads up: this explains the full solution.</span>}
        </div>
      ) : (
        hints.length > 0 && <p className="subtle">You've unlocked every hint for this problem.</p>
      )}
      <InlineError error={hint.error} />
    </div>
  );
}

const SEVERITY_TONE: Record<string, string> = { high: "danger", medium: "warning", low: "info" };

function ReviewTab({ problemSlug, code, submissionId, onHighlightLine }: {
  problemSlug: string; code: string; submissionId: string | null; onHighlightLine(line: number | null): void;
}) {
  const review = useReview();
  const [result, setResult] = useState<ReviewResponse | null>(null);

  async function run() {
    onHighlightLine(null);
    setResult(await review.mutateAsync({ problem_slug: problemSlug, source_code: code, submission_id: submissionId }));
  }

  return (
    <div className="review stack">
      <div className="row">
        <Button variant="primary" loading={review.isPending} onClick={() => void run().catch(() => undefined)}
          disabled={!code.trim()}>
          {result ? "Review again" : "Review my code"}
        </Button>
        <span className="subtle">Checks correctness risks, edge cases, complexity and readability.</span>
      </div>
      <InlineError error={review.error} />
      {result && <ReviewResult data={result} onHighlightLine={onHighlightLine} />}
    </div>
  );
}

export function ReviewResult({ data, onHighlightLine }: { data: ReviewResponse; onHighlightLine?(line: number | null): void }) {
  const r: CodeReview = data.review;
  const expected = data.expected_complexity;
  const timeMismatch = expected && expected.time !== r.complexity.time;
  return (
    <div className="review-result stack" aria-live="polite">
      <p className="review-result__summary">{r.summary}</p>

      <div className="complexity">
        <div className={`complexity__item${timeMismatch ? " complexity__item--warn" : ""}`}>
          <span className="subtle">Time</span>
          <strong>{r.complexity.time}</strong>
          {expected && <span className="subtle">target {expected.time}</span>}
        </div>
        <div className="complexity__item">
          <span className="subtle">Space</span>
          <strong>{r.complexity.space}</strong>
          {expected && <span className="subtle">target {expected.space}</span>}
        </div>
        <div className="complexity__item">
          <span className="subtle">Confidence</span>
          <strong>{r.confidence}</strong>
        </div>
      </div>

      {r.issues.length > 0 && (
        <ul className="issues">
          {r.issues.map((issue, i) => (
            <li key={i} className={`issue issue--${issue.severity}`}>
              <div className="row">
                <Badge tone={SEVERITY_TONE[issue.severity]}>{issue.severity}</Badge>
                <span className="subtle">{issue.category}</span>
                {issue.line_hint && onHighlightLine && (
                  <button type="button" className="link-button" onClick={() => onHighlightLine(issue.line_hint ?? null)}>
                    line {issue.line_hint}
                  </button>
                )}
              </div>
              <p>{issue.detail}</p>
              <p className="subtle">→ {issue.suggestion}</p>
            </li>
          ))}
        </ul>
      )}

      {r.strengths.length > 0 && (
        <div>
          <h3 className="section-title">What's working</h3>
          <ul className="strengths">{r.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
        </div>
      )}

      <div className="banner banner--success"><strong>Next step:</strong> {r.next_step}</div>
      <p className="subtle">{data.disclaimer}{data.provider.includes("fallback") ? " (Answered by the offline coach.)" : ""}</p>
    </div>
  );
}
