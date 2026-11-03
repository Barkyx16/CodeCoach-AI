import type {
  ActivityFacets,
  Goals,
  Plan,
  PlanItem,
  ActivityItem,
  CareerAnalytics,
  Career,
  InterviewAnswer,
  QuestionSummary, HintResponse, Page, ProblemDetail, ProblemSummary, Progress, ReviewResponse, Submission, TokenResponse, User } from "@/api/types";

export const user: User = { id: "u-1", email: "ada@example.com", display_name: "Ada", is_guest: false, created_at: "2026-11-01T08:00:00Z", email_verified: true, career_track: "software-engineer" };

export const tokenResponse = (overrides: Partial<TokenResponse> = {}): TokenResponse => ({
  access_token: "test-token",
  token_type: "bearer",
  expires_at: new Date(Date.now() + 3600_000).toISOString(),
  user,
  ...overrides,
});

export const problems: ProblemSummary[] = [
  { slug: "find-largest-number", title: "Find Largest Number", difficulty: "easy", topics: ["arrays", "iteration"], summary: "Return the largest value." },
  { slug: "two-sum", title: "Two Sum", difficulty: "easy", topics: ["arrays", "hash-maps"], summary: "Find two numbers that add up to a target." },
  { slug: "maximum-subarray", title: "Maximum Subarray Sum", difficulty: "medium", topics: ["arrays", "dynamic-programming"], summary: "Largest contiguous sum." },
];

export const page = <T,>(items: T[]): Page<T> => ({ items, total: items.length, page: 1, page_size: 20 });

export const twoSum: ProblemDetail = {
  ...problems[1]!,
  statement: "Given an integer array `nums` and an integer `target`, return the indices.",
  constraints: ["2 <= nums.length <= 10^4"],
  examples: [{ input: "nums = [2, 7, 11, 15], target = 9", output: "[0, 1]", explanation: "2 + 7 = 9." }],
  starter_code: "class Solution {\n    public int[] twoSum(int[] nums, int target) {\n        return new int[0];\n    }\n}\n",
  signature: { method: "twoSum", params: [{ name: "nums", type: "int[]" }, { name: "target", type: "int" }], returns: "int[]" },
  public_tests: [{ id: 1, input: { nums: [2, 7, 11, 15], target: 9 }, expected_output: [0, 1] }],
  hidden_test_count: 4,
  hint_levels: 4,
};

export const queuedSubmission: Submission = {
  id: "sub-1", problem_slug: "two-sum", problem_title: "Two Sum", language: "java", status: "QUEUED",
  mode: "submit",
  status_detail: "Saved and queued. Automatic judging is turned off until the sandboxed Java runner is approved and deployed, so this submission will not run yet.",
  is_terminal: false, execution_enabled: false, created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
  result: null, source_code: "class Solution {}",
};

export const hint = (level: 1 | 2 | 3 | 4): HintResponse => ({
  level, level_name: ["nudge", "concept", "pseudocode", "full explanation"][level - 1]!,
  content: { hint: `Hint text for level ${level}`, focus_area: "approach", encouragement: "Keep going." },
  max_level: 4, next_level_available: level < 4, provider: "offline", grounded: true,
});

export const review: ReviewResponse = {
  review: {
    summary: "1 thing to look at.",
    complexity: { time: "O(n^2)", space: "O(1)" },
    issues: [{ severity: "medium", category: "complexity", detail: "Nested loops make this roughly O(n^2).", suggestion: "Use a HashMap.", line_hint: 3 }],
    strengths: ["Clear variable names."],
    next_step: "Use a HashMap.",
    confidence: "medium",
  },
  provider: "offline",
  expected_complexity: { time: "O(n)", space: "O(n)" },
  judge_status: null,
  disclaimer: "AI feedback can be wrong. Pass/fail comes only from the test judge, never from the AI.",
};

export const progress: Progress = {
  total_problems: 12, attempted: 2, solved: 1, submissions: 3, accepted_submissions: 1, acceptance_rate: 0.5,
  hints_used: 2, reviews_requested: 1, current_streak_days: 3, longest_streak_days: 5,
  last_active_at: new Date().toISOString(),
  by_topic: [{ topic: "arrays", total_problems: 6, attempted: 2, solved: 1 }],
  by_difficulty: [{ difficulty: "easy", total_problems: 10, solved: 1 }, { difficulty: "medium", total_problems: 2, solved: 0 }],
  problems: [{ slug: "two-sum", status: "solved", last_submission_status: "PASSED", submissions: 2, hints_used: 1 },
    { slug: "find-largest-number", status: "attempted", last_submission_status: "QUEUED", submissions: 1, hints_used: 0 }],
  activity: Array.from({ length: 28 }, (_, i) => ({
    day: new Date(Date.UTC(2026, 9, 5 + i)).toISOString().slice(0, 10),
    events: [0, 1, 3, 7, 12][i % 5]!,
  })),
  weakest_topics: ["arrays"],
  recommended_next: ["find-largest-number"],
};

export const careers: Career[] = [
  { slug: "software-engineer", title: "Software Engineer", category: "Technology", summary: "Build software.", has_coding: true, question_count: 300 },
  { slug: "registered-nurse", title: "Registered Nurse", category: "Healthcare", summary: "Care for patients.", has_coding: false, question_count: 300 },
  { slug: "barista", title: "Barista", category: "Customer Service & Hospitality", summary: "Make coffee.", has_coding: false, question_count: 300 },
];

export const nurseQuestions: QuestionSummary[] = [
  { id: "e-good-0", title: "What good patient assessment looks like", prompt: "What does good patient assessment look like for a registered nurse?", difficulty: "easy", kind: "knowledge", best_score: null },
  { id: "e-time-0", title: "A time patient assessment mattered", prompt: "Tell me about a time patient assessment was an important part of your work.", difficulty: "easy", kind: "behavioral", best_score: 90 },
  { id: "m-pressure-0", title: "Patient assessment under pressure", prompt: "Tell me about a time you had to use patient assessment under pressure.", difficulty: "medium", kind: "behavioral", best_score: null },
];

export const nurseAnswer: InterviewAnswer = {
  id: "a-1", question_id: "m-pressure-0", answer: "Last winter I…", score: 92, rating: "Strong",
  summary: "You covered everything interviewers listen for in this question.",
  points: [
    { label: "Sets the scene: where you were and what was at stake", covered: true, advice: "Open with context." },
    { label: "Shares a result, ideally with a number", covered: false, advice: "Finish with what happened." },
  ],
  notes: ["No numbers yet. A figure (time, %, count) makes your result concrete."],
  outline: ["Situation: what made it high-pressure.", "Result: the outcome."],
  word_count: 140, coach: "built-in (offline)", created_at: "2026-11-01T09:00:00Z",
};

const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

export const activityItems: ActivityItem[] = [
  {
    id: "written_answer:a-1", type: "written_answer", occurred_at: minutesAgo(5), career: "registered-nurse",
    career_title: "Registered Nurse", title: "What good patient assessment looks like", detail: null,
    skills: ["patient assessment"], status: "scored", status_label: "Scored 92/100 (Strong)", score: 92, session_id: null,
    target: { href: "/careers/registered-nurse/questions/e-good-0?answer=a-1", track: "registered-nurse", question_id: "e-good-0", answer_id: "a-1" },
  },
  {
    id: "code_submission:sub-1", type: "code_submission", occurred_at: minutesAgo(30), career: "coding",
    career_title: "Coding problems", title: "Two Sum", detail: null, skills: ["arrays", "hash-maps"],
    status: "saved_not_judged", status_label: "Saved, not judged (the code judge isn't available on this server)", score: null,
    session_id: null, target: { href: "/history/submissions/sub-1", problem_slug: "two-sum", submission_id: "sub-1" },
  },
  {
    id: "interview:round-7", type: "interview", occurred_at: minutesAgo(90), career: "registered-nurse",
    career_title: "Registered Nurse", title: "Registered Nurse question round", detail: "1 of 5 answered, 4 skipped",
    skills: [], status: "completed", status_label: "Completed", score: null, session_id: "round-7",
    target: { href: "/interviews/round-7", interview_id: "round-7", track: "registered-nurse" },
  },
];

export const activityFacets: ActivityFacets = {
  careers: [{ value: "registered-nurse", label: "Registered Nurse", count: 2 }, { value: "coding", label: "Coding problems", count: 1 }],
  types: [
    { value: "problem_opened", label: "Problem opened", count: 0 }, { value: "code_submission", label: "Code submission", count: 1 },
    { value: "coaching", label: "Coaching", count: 0 }, { value: "written_answer", label: "Written answer", count: 1 },
    { value: "interview", label: "Mock interview", count: 1 },
  ],
  statuses: [{ value: "scored", label: "Scored by the rubric", count: 1 }, { value: "saved_not_judged", label: "Saved, not judged", count: 1 }, { value: "completed", label: "Completed", count: 1 }],
  skills: [],
};

const today = new Date().toISOString().slice(0, 10);
export const nurseAnalytics: CareerAnalytics = {
  track: "registered-nurse", career_title: "Registered Nurse", since: null, until: today,
  questions_practiced: 1, answers: 2, strong_questions: 1, total_questions: 300,
  skills: [
    { skill: "patient assessment", total_questions: 26, questions_answered: 1, answers: 2, average_best_score: 92 },
    { skill: "triage", total_questions: 17, questions_answered: 0, answers: 0, average_best_score: null },
  ],
  kinds: [{ value: "knowledge", label: "Knowledge", count: 2 }],
  interviews: { completed: 1, in_progress: 0, expired: 0, abandoned: 1 },
  trends: [{ evaluator: "built-in (offline) · rubric v1", points: [{ week_start: today, answers: 2, average_score: 80 }] }],
  by_day: [{ day: today, answers: 2, interviews: 1 }],
  definitions: { trend: "Weekly average score within one evaluator." },
};

const planItem = (over: Partial<PlanItem>): PlanItem => ({
  id: "item-1", position: 0, kind: "question", skill: "patient assessment", title: "What good patient assessment looks like",
  reason: "You haven't practised patient assessment yet.", completion: "Submit an answer to this question.", minutes: 6,
  status: "pending", evidence: null, href: "/careers/registered-nurse/questions/e-good-0", round: null,
  can_mark_reviewed: false, can_replace: true, created_at: new Date().toISOString(), resolved_at: null, ...over,
});

export const planItems: PlanItem[] = [
  planItem({
    id: "item-base", kind: "assessment", skill: "Baseline", title: "Baseline check: 3 short questions", minutes: 12,
    reason: "There isn't enough evidence to tailor your plan yet (0 answers so far).", completion: "Finish the baseline round.",
    href: null, round: { track: "registered-nurse", purpose: "baseline", duration_minutes: 15, difficulty: null, question_ids: null },
    can_replace: false,
  }),
  planItem({ id: "item-q", position: 1 }),
  planItem({ id: "item-mock", position: 2, kind: "mock", skill: "Interview practice", title: "Registered Nurse mock interview (5 questions)", minutes: 20, href: null,
    round: { track: "registered-nurse", purpose: "practice", duration_minutes: 15, difficulty: "easy", question_ids: null }, can_replace: false }),
];

export function makePlan(minutes: number, items: PlanItem[] = planItems, goalsSaved = false): Plan {
  const pending = items.filter((i) => i.status === "pending");
  const fits = pending.filter((i) => i.minutes <= minutes);
  const primary = fits[0] ?? [...pending].sort((a, b) => a.minutes - b.minutes)[0] ?? null;
  const follow = primary ? pending.find((i) => i !== primary && i.minutes <= minutes - primary.minutes) ?? null : null;
  return {
    track: "registered-nurse", career_title: "Registered Nurse", version: 2, created_at: new Date().toISOString(),
    changes: ["Done: “Patient assessment under pressure” (answered, scored 45/100).", "Added “Retry: Patient assessment under pressure”: Your best score is 45/100."],
    items,
    progress: { done_this_week: 1, minutes_this_week: 6, weekly_minutes: 60, done_in_plan: items.filter((i) => i.status === "done").length, open_in_plan: pending.length },
    today: {
      minutes_available: minutes, primary, follow_up: follow, session_minutes: (primary?.minutes ?? 0) + (follow?.minutes ?? 0),
      note: primary && primary !== pending[0] ? `Your next activity takes about ${pending[0]!.minutes} minutes, so here's one that fits ${minutes}.` : null,
    },
    assessment: {
      state: "building_baseline", note: "Building your baseline: 1 of 3 answers so far. Until then the plan starts broad.",
      self_reported: [{ skill: "triage", rating: 4 }],
      evaluated: [{ skill: "patient assessment", questions: 1, answers: 1, average_best_score: 45 }],
      coding: null,
    },
    goals_saved: goalsSaved, target_date: null, days_to_interview: null,
  };
}

export const nurseGoals: Goals = {
  track: "registered-nurse", career_title: "Registered Nurse", has_coding: false,
  skills: ["patient assessment", "triage", "care planning", "Working with people"], saved: false,
  specialty: null, experience: null, target_date: null, weekly_minutes: null, focus_areas: [], formats: [], confidence: {},
  setup_skipped: false,
};

/** What /capabilities reports for each execution state (see backend app/services/judge/health.py). */
export function executionStatus(state: "ready" | "unavailable" | "not_configured", setupHelp: string | null = null) {
  const now = new Date().toISOString();
  if (state === "ready") {
    return { state, reason: "ok", message: "Run and Submit execute your code in an isolated Linux judge.", run_available: true, submit_mode: "judged", checked_at: now, setup_help: null };
  }
  if (state === "unavailable") {
    return { state, reason: "judge_unreachable", message: "The code judge can't be reached right now. Submissions wait in the queue and are judged when it's back; Run is paused.", run_available: false, submit_mode: "queued_until_available", checked_at: now, setup_help: setupHelp };
  }
  return { state, reason: "not_configured", message: "This server isn't connected to a code judge, so code can't run here. Submitting saves your attempt without a verdict; you can still ask for a code review.", run_available: false, submit_mode: "saved_only", checked_at: now, setup_help: setupHelp };
}
