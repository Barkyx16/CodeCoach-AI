import { useMemo, useState } from "react";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useAIHistory } from "@/api/queries";
import type { CoachPreview, HintLevel, HintResponse, Interview } from "@/api/types";

type HintContent = HintResponse["content"];
import { ActionError } from "@/components/ActionError";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { CoachContext, REFUSED } from "@/features/workspace/CoachContext";
import { formatDateTime } from "@/lib/format";

const LEVELS: { level: HintLevel; name: string; blurb: string }[] = [
  { level: 1, name: "Nudge", blurb: "A question that points you in the right direction" },
  { level: 2, name: "Concept", blurb: "The key idea or data structure" },
  { level: 3, name: "Pseudocode", blurb: "Step-by-step outline" },
  { level: 4, name: "Full explanation", blurb: "Complete approach, complexity and edge cases" },
];

export const HINTS_CLOSED = "Hints are closed: the interview is over.";

/**
 * Hints inside the coding interview (Volume 17, prompt 4; docs/ATTEMPT_CONDITIONS.md): the problem's
 * own ladder, one level at a time, each checked first (what the coach reads: the code you last sent)
 * and then asked for. The interview records each with its time and the message count, its help says
 * "during the interview", and its feedback is told hints were used. Closed once it's over.
 */
export function InterviewHints({ iv, maxLevel, open, onAsked }: {
  iv: Interview; maxLevel: number; open: boolean; onAsked(): void;
}) {
  const slug = iv.problem?.slug ?? "";
  const recorded = iv.hints ?? [];
  // The hints' words, for the levels this interview recorded (after a reload the panel shows them again).
  const history = useAIHistory({ problem_slug: slug, action: "hint", page_size: 50 }, recorded.length > 0 && Boolean(slug));
  const [fresh, setFresh] = useState<Record<number, HintContent>>({});
  const words = useMemo(() => {
    const out: Record<number, HintContent> = {};
    for (const item of [...(history.data?.items ?? [])].reverse()) {
      if (item.hint_level && item.response) out[item.hint_level] = item.response as unknown as HintContent;
    }
    return { ...out, ...fresh };
  }, [history.data, fresh]);
  const highest = recorded.reduce((m, h) => Math.max(m, h.level), 0);
  const next = LEVELS.find((l) => l.level === highest + 1 && l.level <= maxLevel);
  const [preview, setPreview] = useState<{ data: CoachPreview; level: HintLevel } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [changed, setChanged] = useState<string | null>(null);

  async function check(level: HintLevel) {
    setBusy(true);
    setError(null);
    try {
      setPreview({ data: await api.hintPreview({ problem_slug: slug, source_code: iv.final_code ?? "", level }), level });
      setChanged(null);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function ask() {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api.interviewHint(iv.id, { level: preview.level, approved_context: preview.data.context_fingerprint });
      setFresh((f) => ({ ...f, [out.hint.level]: out.hint.content }));
      setPreview(null);
      onAsked();
    } catch (e) {
      if (e instanceof ApiError && e.code === "context_changed") {
        const now = (e.details as { preview?: CoachPreview } | undefined)?.preview;
        if (now) setPreview({ data: now, level: preview.level });
        setChanged(REFUSED);
      } else {
        setError(e);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="interview-hints card stack-sm" open={recorded.length > 0 || undefined}>
      <summary>Hints{recorded.length ? ` (${recorded.length})` : ""}</summary>
      <p className="subtle">Each hint is recorded with this interview: its help will say it came during the interview, and the feedback is told.</p>
      {recorded.length > 0 && (
        <ol className="hint-list" aria-label="Hints in this interview">
          {recorded.map((h) => (
            <li key={h.level} className="hint">
              <div className="hint__meta">
                <Badge tone="info">Level {h.level} · {h.level_name}</Badge>
                <span className="subtle">at <time dateTime={h.at}>{formatDateTime(h.at)}</time>, after {h.turn} {h.turn === 1 ? "message" : "messages"}</span>
              </div>
              {words[h.level] && <p className="hint__text">{words[h.level]!.hint}</p>}
            </li>
          ))}
        </ol>
      )}
      {!open ? (
        <p className="subtle" role="status">{HINTS_CLOSED}</p>
      ) : preview ? (
        <CoachContext preview={preview.data} choices={{}} onChoose={() => undefined} stale={null} changed={changed}
          busy={busy} blocked={false} sendLabel={`Ask for the level ${preview.level} hint`}
          onSend={() => void ask()} onCancel={() => { setPreview(null); setChanged(null); }}
          onCheckAgain={() => void check(preview.level)} />
      ) : next ? (
        <div className="hint-next">
          <Button size="sm" variant="secondary" loading={busy} onClick={() => void check(next.level)}>
            {highest === 0 ? "Get a hint" : `Unlock level ${next.level}: ${next.name}`}
          </Button>
          <span className="subtle">{next.blurb}. You'll see what the coach will read first: the code you last sent.</span>
        </div>
      ) : (
        recorded.length > 0 && <p className="subtle">You've unlocked every hint for this problem.</p>
      )}
      <ActionError error={error} action="The hint" />
    </details>
  );
}
