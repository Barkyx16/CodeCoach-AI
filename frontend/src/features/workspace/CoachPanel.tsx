import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAIHistory, useAIUsage, useHint, useReview } from "@/api/queries";
import { api } from "@/api/endpoints";
import type { CodeReview, HintLevel, HintResponse, ReviewPreview, ReviewResponse } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { ActionError } from "@/components/ActionError";
import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/useAuth";
import { EarlierActionNotice } from "@/features/recovery/EarlierActionNotice";
import { useEarlierAction } from "@/features/recovery/useEarlierAction";
import { useRetryWait } from "@/hooks/useCountdown";
import { fingerprint, forgetIntent, keyForIntent, type IntentKind } from "@/lib/pendingIntents";
import { Tabs } from "@/components/Tabs";
import { FallbackNotice } from "@/components/FallbackNotice";
import { CoachContext } from "@/features/workspace/CoachContext";

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
  // The server's wait (today's budget used up, or another request still running): only the hint
  // button waits, with a countdown; the editor, Run and Submit stay usable.
  const wait = useRetryWait(hint.error);
  const { user } = useAuth();
  // One key per level and code until it's answered, kept in this browser (Volume 8, prompts 1-2):
  // pressing again after a lost response, even after a reload or from another tab, gets the first
  // answer back, without a second AI call or a second use of the budget. Changed code is a new
  // request with a new key (the server refuses an old key with different code).
  const earlier = useEarlierAction("hint", problemSlug);

  async function request(level: HintLevel) {
    if (earlier.status !== "none") earlier.dismiss();
    const response = await keyed(user?.id, "hint", problemSlug, fingerprint(problemSlug, level, code), (key) =>
      hint.mutateAsync({ problem_slug: problemSlug, level, source_code: code, client_request_id: key }));
    setFresh((f) => [...f.filter((h) => h.level !== response.level), response]);
  }

  return (
    <div className="hints stack">
      <EarlierActionNotice earlier={earlier} noun="hint request"
        found={<>{earlier.status === "found" && earlier.outcome.hint_level ? `The level ${earlier.outcome.hint_level} hint is below.` : "It's below."} It wasn't asked for again.</>} />
      {hints.length === 0 && !history.isPending && (
        <p className="muted">Stuck? Hints unlock one level at a time, so you only see as much as you need.</p>
      )}
      <FallbackNotice provider={fresh.find((f) => f.provider.includes("fallback"))?.provider} />
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
          <Button variant={highest === 0 ? "primary" : "secondary"} loading={hint.isPending} disabled={wait > 0}
            onClick={() => void request(next.level).catch(() => undefined)}>
            {highest === 0 ? "Get a hint" : `Unlock level ${next.level}: ${next.name}`}
          </Button>
          <span className="subtle">{next.blurb}</span>
          {next.level === 4 && <span className="subtle">Heads up: this explains the full solution.</span>}
        </div>
      ) : (
        hints.length > 0 && <p className="subtle">You've unlocked every hint for this problem.</p>
      )}
      {!hint.isPending && (
        <ActionError error={hint.error} action="The hint" repeatSafe
          onRetry={next ? () => void request(next.level).catch(() => undefined) : undefined} />
      )}
    </div>
  );
}

const SEVERITY_TONE: Record<string, string> = { high: "danger", medium: "warning", low: "info" };

function ReviewTab({ problemSlug, code, submissionId, onHighlightLine }: {
  problemSlug: string; code: string; submissionId: string | null; onHighlightLine(line: number | null): void;
}) {
  const review = useReview();
  const [result, setResult] = useState<ReviewResponse | null>(null);
  // Check, then send (docs/COACH_CONTEXT.md): the preview shows exactly what the coach would read,
  // and the review is sent bound to it, so it goes only if what's sent is what was shown.
  const [preview, setPreview] = useState<{ data: ReviewPreview; code: string } | null>(null);
  const [share, setShare] = useState(true);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<unknown>(null);
  const [changed, setChanged] = useState<string | null>(null);
  const [cancelled, setCancelled] = useState(false);
  const wait = useRetryWait(review.error);
  const { user } = useAuth();
  // The same approved material, not answered yet (a lost response, even across a reload): the same
  // key, so the server gives back the review it already made. Anything else is a new review.
  const earlier = useEarlierAction("review", problemSlug);

  async function check(withVerdict = share) {
    setChecking(true);
    setCheckError(null);
    setCancelled(false);
    try {
      const data = await api.reviewPreview({ problem_slug: problemSlug, source_code: code, submission_id: submissionId, share_verdict: withVerdict });
      setPreview({ data, code });
      setChanged(null);
    } catch (e) {
      setCheckError(e);
    } finally {
      setChecking(false);
    }
  }

  async function send() {
    if (!preview) return;
    onHighlightLine(null);
    if (earlier.status !== "none") earlier.dismiss();
    const approved = preview.data.context_fingerprint;
    try {
      setResult(await keyed(user?.id, "review", problemSlug, fingerprint(problemSlug, preview.code, submissionId, share ? 1 : 0, approved), (key) =>
        review.mutateAsync({ problem_slug: problemSlug, source_code: preview.code, submission_id: submissionId, share_verdict: share, approved_context: approved, client_request_id: key })));
      setPreview(null);
    } catch (e) {
      if (e instanceof ApiError && e.code === "context_changed") {
        // Nothing was sent: show what would be sent now, to check before sending again.
        const fresh = (e.details as { preview?: ReviewPreview } | undefined)?.preview;
        if (fresh) setPreview({ data: fresh, code: preview.code });
        setChanged("What the coach would read changed since you checked it, so nothing was sent. This is what it would read now.");
        review.reset();
      }
    }
  }

  return (
    <div className="review stack">
      {!preview && (
        <div className="row">
          <Button variant="primary" loading={checking} onClick={() => void check()}
            disabled={!code.trim() || wait > 0}>
            {result ? "Review again" : "Review my code"}
          </Button>
          <span className="subtle">You'll see exactly what the coach will read before anything is sent.</span>
        </div>
      )}
      {cancelled && !preview && <p className="subtle" role="status">Cancelled. Nothing was sent.</p>}
      <ActionError error={checkError} action="Checking what would be sent" onRetry={() => void check()} />
      {preview && (
        <CoachContext preview={preview.data} share={share} stale={preview.code !== code} changed={changed}
          busy={review.isPending || checking}
          onShare={(next) => { setShare(next); void check(next); }}
          onSend={() => void send()}
          onCancel={() => { setPreview(null); setChanged(null); setCancelled(true); }}
          onCheckAgain={() => void check()} />
      )}
      <EarlierActionNotice earlier={earlier} noun="code review"
        found={earlier.status === "found"
          ? <>It wasn't asked for again. <Link to={`/history/coaching/${earlier.outcome.id}`}>Open that review</Link>.</> : null} />
      {!review.isPending && preview && (
        <ActionError error={review.error} action="The code review" repeatSafe onRetry={() => void send()} />
      )}
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
      <FallbackNotice provider={data.provider} />
      <p className="subtle">{data.disclaimer}</p>
    </div>
  );
}

/**
 * Send a keyed AI request whose key is kept in this browser until it's answered: written before
 * sending (so a reload can check it), forgotten once there's a definite answer, kept when no reply
 * came back (the same request again reuses it).
 */
async function keyed<T>(userId: string | undefined, kind: IntentKind, target: string, print: string,
  send: (key: string) => Promise<T>): Promise<T> {
  if (!userId) throw new Error("not signed in");
  const { key } = keyForIntent(userId, kind, target, print);
  try {
    const result = await send(key);
    forgetIntent(userId, kind, target, key);
    return result;
  } catch (e) {
    if (!(e instanceof ApiError && e.code === "network_error")) forgetIntent(userId, kind, target, key);
    throw e;
  }
}
