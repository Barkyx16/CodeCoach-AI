/** One function per backend endpoint. See docs/API.md for behavior and error codes. */
import { apiRequest } from "./client";
import type {
  AIHistoryAction,
  Capabilities,
  AIHistoryItem,
  AIUsage,
  Difficulty,
  HintRequest,
  Interview,
  InterviewStart,
  InterviewSummary,
  HintResponse,
  LoginRequest,
  Page,
  ProblemDetail,
  ProblemSummary,
  Progress,
  Recommendation,
  RegisterRequest,
  ExplainFailureResponse,
  ReviewRequest,
  ReviewResponse,
  Submission,
  SubmissionCreate,
  SubmissionListItem,
  SubmissionStatus,
  TokenResponse,
  TopicCount,
  User,
  DifficultyCounts,
  Career,
  QuestionSummary,
  QuestionDetail,
  InterviewAnswer,
  AnswerSource,
  ActivityFacets,
  ActivityItem,
  ActivityStatus,
  ActivityType,
  CareerAnalytics,
  ResumeOut,
  InterviewReview,
  Comparison,
  ReviewQueue,
  Target,
  TargetInput,
  TargetPatch,
  TargetSummary,
  RequirementInput,
  RequirementPatch,
  ExperienceInput,
  Goals,
  GoalsInput,
  Plan,
  PlanItem,
  TrackProgress,
} from "./types";

export interface ProblemFilters {
  difficulty?: Difficulty | "";
  topic?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

export interface QuestionFilters {
  difficulty?: Difficulty | "";
  q?: string;
  page?: number;
  page_size?: number;
}

export interface ActivityFilters {
  career?: string;
  type?: ActivityType | "";
  status?: ActivityStatus | "";
  skill?: string;
  since?: string;
  until?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

export const api = {
  // auth
  register: (body: RegisterRequest) =>
    apiRequest<TokenResponse>("/api/v1/auth/register", { method: "POST", body, auth: false }),
  login: (body: LoginRequest) =>
    apiRequest<TokenResponse>("/api/v1/auth/login", { method: "POST", body, auth: false }),
  guest: (display_name?: string, career_track?: string) =>
    apiRequest<TokenResponse>("/api/v1/auth/guest", {
      method: "POST",
      body: { ...(display_name ? { display_name } : {}), ...(career_track ? { career_track } : {}) },
      auth: false,
    }),
  me: () => apiRequest<User>("/api/v1/auth/me"),
  logout: () => apiRequest<void>("/api/v1/auth/logout", { method: "POST" }),
  logoutAll: () => apiRequest<void>("/api/v1/auth/logout-all", { method: "POST" }),
  verifyEmailLink: (token: string) =>
    apiRequest<User>("/api/v1/auth/verify-email", { method: "POST", body: { token }, auth: false }),
  verifyEmailCode: (code: string) =>
    apiRequest<User>("/api/v1/auth/verify-email/code", { method: "POST", body: { code } }),
  resendVerification: () =>
    apiRequest<{ status: string; message: string }>("/api/v1/auth/verify-email/resend", { method: "POST" }),
  changeEmail: (body: { new_email: string; password: string }) =>
    apiRequest<User>("/api/v1/auth/email", { method: "POST", body }),
  /** Exchange the HttpOnly refresh cookie for a new access token (and a rotated cookie). */
  refresh: () => apiRequest<TokenResponse>("/api/v1/auth/refresh", {
    method: "POST", auth: false, headers: { "X-Requested-With": "codecoach" },
  }),
  updateProfile: (body: { display_name?: string | null; career_track?: string }) =>
    apiRequest<User>("/api/v1/auth/me", { method: "PATCH", body }),
  upgradeGuest: (body: RegisterRequest) =>
    apiRequest<TokenResponse>("/api/v1/auth/upgrade", { method: "POST", body }),
  requestPasswordReset: (email: string) =>
    apiRequest<{ status: string; message: string }>("/api/v1/auth/password-reset", {
      method: "POST", body: { email }, auth: false,
    }),
  confirmPasswordReset: (token: string, newPassword: string) =>
    apiRequest<void>("/api/v1/auth/password-reset/confirm", {
      method: "POST", body: { token, new_password: newPassword }, auth: false,
    }),
  changePassword: (body: { current_password: string; new_password: string }) =>
    apiRequest<TokenResponse>("/api/v1/auth/password", { method: "POST", body }),
  deleteAccount: (body: { password?: string; confirm: string }) =>
    apiRequest<void>("/api/v1/auth/me", { method: "DELETE", body }),
  exportData: () => apiRequest<Record<string, unknown>>("/api/v1/me/export"),

  // problems
  problems: (filters: ProblemFilters = {}, signal?: AbortSignal) =>
    apiRequest<Page<ProblemSummary>>("/api/v1/problems", { query: { ...filters }, signal }),
  problemCounts: (filters: Pick<ProblemFilters, "topic" | "q"> = {}, signal?: AbortSignal) =>
    apiRequest<DifficultyCounts>("/api/v1/problems/counts", { query: { ...filters }, signal }),
  topics: () => apiRequest<TopicCount[]>("/api/v1/topics"),

  // careers and their interview questions
  careers: () => apiRequest<Career[]>("/api/v1/careers"),
  questions: (track: string, filters: QuestionFilters = {}, signal?: AbortSignal) =>
    apiRequest<Page<QuestionSummary>>(`/api/v1/careers/${encodeURIComponent(track)}/questions`, { query: { ...filters }, signal }),
  questionCounts: (track: string, q = "", signal?: AbortSignal) =>
    apiRequest<DifficultyCounts>(`/api/v1/careers/${encodeURIComponent(track)}/questions/counts`, { query: { q }, signal }),
  question: (track: string, id: string, signal?: AbortSignal) =>
    apiRequest<QuestionDetail>(`/api/v1/careers/${encodeURIComponent(track)}/questions/${encodeURIComponent(id)}`, { signal }),
  answerQuestion: (track: string, id: string, answer: string) =>
    apiRequest<InterviewAnswer>(`/api/v1/careers/${encodeURIComponent(track)}/questions/${encodeURIComponent(id)}/answers`, {
      method: "POST", body: { answer },
    }),
  myAnswers: (track: string, id: string) =>
    apiRequest<InterviewAnswer[]>(`/api/v1/careers/${encodeURIComponent(track)}/questions/${encodeURIComponent(id)}/answers`),
  trackProgress: (track: string) =>
    apiRequest<TrackProgress>(`/api/v1/careers/${encodeURIComponent(track)}/progress`),
  problem: (slug: string, signal?: AbortSignal) =>
    apiRequest<ProblemDetail>(`/api/v1/problems/${encodeURIComponent(slug)}`, { signal }),

  capabilities: () => apiRequest<Capabilities>("/api/v1/capabilities"),

  // submissions
  submit: (body: SubmissionCreate) => apiRequest<Submission>("/api/v1/submissions", { method: "POST", body }),
  submission: (id: string, signal?: AbortSignal) =>
    apiRequest<Submission>(`/api/v1/submissions/${encodeURIComponent(id)}`, { signal }),
  mySubmissions: (query: { problem_slug?: string; status?: SubmissionStatus; page?: number; page_size?: number } = {}) =>
    apiRequest<Page<SubmissionListItem>>("/api/v1/me/submissions", { query }),

  // AI coach
  hint: (body: HintRequest) => apiRequest<HintResponse>("/api/v1/ai/hint", { method: "POST", body }),
  review: (body: ReviewRequest) => apiRequest<ReviewResponse>("/api/v1/ai/review", { method: "POST", body }),
  explainFailure: (submissionId: string) =>
    apiRequest<ExplainFailureResponse>("/api/v1/ai/explain-failure", { method: "POST", body: { submission_id: submissionId } }),
  aiUsage: () => apiRequest<AIUsage>("/api/v1/ai/usage"),
  aiHistory: (query: { problem_slug?: string; action?: AIHistoryAction; page?: number; page_size?: number } = {}) =>
    apiRequest<Page<AIHistoryItem>>("/api/v1/me/ai-history", { query }),

  // interview review, retries, review queue
  interviewReview: (id: string) => apiRequest<InterviewReview>(`/api/v1/interviews/${encodeURIComponent(id)}/review`),
  comparison: (id: string, index: number) =>
    apiRequest<Comparison>(`/api/v1/interviews/${encodeURIComponent(id)}/questions/${index}/comparison`),
  retryQuestion: (id: string, index: number, body: { answer: string; source: AnswerSource }) =>
    apiRequest<Comparison>(`/api/v1/interviews/${encodeURIComponent(id)}/questions/${index}/retries`, { method: "POST", body }),
  reviewQueue: () => apiRequest<ReviewQueue>("/api/v1/me/reviews"),
  addReview: (body: { track: string; question_id: string; session_id?: string | null }) =>
    apiRequest<ReviewQueue>("/api/v1/me/reviews", { method: "POST", body }),
  snoozeReview: (id: string, days: 1 | 3 | 7) =>
    apiRequest<ReviewQueue>(`/api/v1/me/reviews/${encodeURIComponent(id)}/snooze`, { method: "POST", body: { days } }),
  removeReview: (id: string) => apiRequest<ReviewQueue>(`/api/v1/me/reviews/${encodeURIComponent(id)}`, { method: "DELETE" }),
  // target roles
  targets: () => apiRequest<TargetSummary[]>("/api/v1/targets"),
  target: (id: string) => apiRequest<Target>(`/api/v1/targets/${encodeURIComponent(id)}`),
  createTarget: (body: TargetInput) => apiRequest<Target>("/api/v1/targets", { method: "POST", body }),
  updateTarget: (id: string, body: TargetPatch) =>
    apiRequest<Target>(`/api/v1/targets/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  deleteTarget: (id: string) => apiRequest<void>(`/api/v1/targets/${encodeURIComponent(id)}`, { method: "DELETE" }),
  reextract: (id: string) => apiRequest<Target>(`/api/v1/targets/${encodeURIComponent(id)}/extract`, { method: "POST" }),
  addRequirement: (id: string, body: RequirementInput) =>
    apiRequest<Target>(`/api/v1/targets/${encodeURIComponent(id)}/requirements`, { method: "POST", body }),
  patchRequirement: (id: string, rid: string, body: RequirementPatch) =>
    apiRequest<Target>(`/api/v1/targets/${encodeURIComponent(id)}/requirements/${encodeURIComponent(rid)}`, { method: "PATCH", body }),
  addExperience: (id: string, body: ExperienceInput) =>
    apiRequest<Target>(`/api/v1/targets/${encodeURIComponent(id)}/experience`, { method: "POST", body }),
  editExperience: (id: string, eid: string, body: ExperienceInput) =>
    apiRequest<Target>(`/api/v1/targets/${encodeURIComponent(id)}/experience/${encodeURIComponent(eid)}`, { method: "PUT", body }),
  deleteExperience: (id: string, eid: string) =>
    apiRequest<Target>(`/api/v1/targets/${encodeURIComponent(id)}/experience/${encodeURIComponent(eid)}`, { method: "DELETE" }),
  // practice plan
  goals: (track?: string) => apiRequest<Goals>("/api/v1/me/goals", { query: { track } }),
  saveGoals: (body: GoalsInput) => apiRequest<Goals>("/api/v1/me/goals", { method: "PUT", body }),
  plan: (track: string | undefined, minutes: number) => apiRequest<Plan>("/api/v1/me/plan", { query: { track, minutes } }),
  planItemAction: (id: string, action: "skip" | "replace" | "reviewed") =>
    apiRequest<PlanItem>(`/api/v1/me/plan/items/${encodeURIComponent(id)}/${action}`, { method: "POST" }),
  // unified progress
  activity: (filters: ActivityFilters, signal?: AbortSignal) =>
    apiRequest<Page<ActivityItem>>("/api/v1/me/activity", { query: { ...filters }, signal }),
  activityFacets: (career?: string) =>
    apiRequest<ActivityFacets>("/api/v1/me/activity/facets", { query: { career } }),
  careerAnalytics: (track: string, since?: string) =>
    apiRequest<CareerAnalytics>(`/api/v1/me/careers/${encodeURIComponent(track)}/analytics`, { query: { since } }),
  resume: () => apiRequest<ResumeOut>("/api/v1/me/resume"),
  aiHistoryItem: (id: string) => apiRequest<AIHistoryItem>(`/api/v1/me/ai-history/${encodeURIComponent(id)}`),
  // mock interviews
  startInterview: (body: InterviewStart) => apiRequest<Interview>("/api/v1/interviews", { method: "POST", body }),
  interview: (id: string, signal?: AbortSignal) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}`, { signal }),
  interviews: (query: { page?: number; page_size?: number } = {}) =>
    apiRequest<Page<InterviewSummary>>("/api/v1/interviews", { query }),
  interviewMessage: (id: string, body: { message: string; code?: string | null; source?: AnswerSource }) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/messages`, { method: "POST", body }),
  finishInterview: (id: string, code?: string | null) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/finish`, { method: "POST", body: { code: code ?? null } }),
  answerRoundQuestion: (id: string, body: { question_index: number; answer: string; source: AnswerSource }) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/answers`, { method: "POST", body }),
  skipRoundQuestion: (id: string, question_index: number) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/skip`, { method: "POST", body: { question_index } }),
  abandonInterview: (id: string) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/abandon`, { method: "POST" }),

  // progress
  progress: () => apiRequest<Progress>("/api/v1/me/progress"),
  recommendations: (limit = 5) => apiRequest<Recommendation[]>("/api/v1/me/recommendations", { query: { limit } }),
};
