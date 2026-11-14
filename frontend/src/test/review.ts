import type { Interview, InterviewReview, ReviewEntry } from "@/api/types";

const LABEL: Record<Interview["status"], string> = {
  completed: "Completed", abandoned: "Ended early", expired: "Time ran out", in_progress: "In progress",
};

/** A review shaped like the backend's, derived from a mocked interview (for UI tests only). */
export function reviewFor(iv: Interview): InterviewReview {
  const isRound = iv.kind === "questions";
  const candidate = new Map(iv.turns.filter((t) => t.role === "candidate").map((t) => [t.question_index, t]));
  const items: ReviewEntry[] = isRound
    ? iv.questions.map((q) => {
      const t = candidate.get(q.index);
      return {
        key: `q${q.index}`, index: q.index, title: q.title, prompt: q.prompt, kind: q.kind, role: "question",
        status: q.status === "answered" ? "answered" : q.status === "skipped" ? "skipped" : "not_reached",
        asked_at: iv.started_at, answer_text: q.answer?.answer ?? null, answered_at: q.answer ? t?.created_at ?? null : null,
        source: t?.source ?? null, transcription_note: null, engagement: t?.engagement ?? null, feedback: q.answer ?? null,
        dimensions: [], retries: 0, in_review_queue: false, question_id: q.id,
      };
    })
    : iv.turns.map((t) => ({
      key: `turn-${t.seq}`, index: t.seq, title: t.role === "interviewer" ? "Interviewer" : "You", prompt: t.content,
      kind: t.phase ?? "", role: t.role, status: "said", asked_at: t.created_at, answer_text: null, answered_at: null,
      source: t.source ?? null, transcription_note: null, engagement: t.engagement ?? null, feedback: null,
      dimensions: [], retries: 0, in_review_queue: false,
    }));
  const improvements = isRound ? [] : (iv.evaluation?.improvements ?? []).slice(0, 1).map((why) => ({
    key: "next-time", title: "Next time", why, evidence: [], practice: { label: "Practise this problem", href: `/problems/${iv.problem?.slug ?? ""}` },
  }));
  return {
    id: iv.id, kind: iv.kind, track: iv.track ?? null, career_title: iv.career_title ?? null, problem: iv.problem,
    status: iv.status, status_label: LABEL[iv.status], completed: iv.status === "completed",
    started_at: iv.started_at, ended_at: iv.ended_at, elapsed_seconds: 300, time_limit_seconds: iv.duration_seconds,
    notices: iv.status === "abandoned" ? ["Ended early."] : [], items,
    overall: [{ name: "Answer content", status: "evaluated", summary: "Summary", points: [], evidence: [] }],
    improvements, evaluation_available: true, evaluator: iv.provider ?? null,
    disclaimer: "Pass/fail only ever comes from the judge.", final_code: iv.final_code,
  };
}
