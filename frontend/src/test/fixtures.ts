import type { HintResponse, Page, ProblemDetail, ProblemSummary, Progress, ReviewResponse, Submission, TokenResponse, User } from "@/api/types";

export const user: User = { id: "u-1", email: "ada@example.com", display_name: "Ada", is_guest: false, created_at: "2026-11-01T08:00:00Z", email_verified: true };

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
