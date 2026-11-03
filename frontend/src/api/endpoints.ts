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
  Bookmark,
  Collection,
  CollectionSummary,
  ExploreResult,
  ExploreSort,
  MyExploreResult,
  SavedItemRef,
  CheckResult,
  LearnCatalog,
  LearnUnit,
  UnitLink,
  UnitProgress,
  KeyPoints,
  FeedbackInput,
  FeedbackReceipt,
  RecipientView,
  ShareCreate,
  ShareCreated,
  ShareDetail,
  SharePreview,
  ShareSelection,
  ShareSummary,
  Note,
  NoteInput,
  NotePage,
  NotePatch,
  ScenarioAttempt,
  ScenarioAttemptSummary,
  ScenarioCatalog,
  ScenarioDetail,
  InterviewFormat,
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

export interface ExploreFilters {
  q?: string;
  difficulty?: Difficulty;
  kind?: string;
  skill?: string;
  status?: "attempted" | "unattempted" | "bookmarked";
  sort?: ExploreSort;
  page?: number;
  page_size?: number;
}

export interface NoteFilters {
  q?: string;
  career?: string;
  source_type?: "question" | "problem" | "lesson" | "interview";
  source_id?: string;
  tag?: string;
  status?: "active" | "archived" | "all";
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
  interviewFormats: (track: string, difficulty: Difficulty) =>
    apiRequest<InterviewFormat[]>("/api/v1/interviews/formats", { query: { track, difficulty }, auth: false }),
  answerFollowup: (id: string, body: { answer: string; source: AnswerSource }) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/followup`, { method: "POST", body }),
  skipFollowup: (id: string) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/followup/skip`, { method: "POST" }),
  abandonInterview: (id: string) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/abandon`, { method: "POST" }),

  // explorer, bookmarks, collections
  explore: (track: string, filters: ExploreFilters, signal?: AbortSignal) =>
    apiRequest<ExploreResult>(`/api/v1/careers/${encodeURIComponent(track)}/explore`, { query: { ...filters, status: undefined }, signal, auth: false }),
  myExplore: (track: string, filters: ExploreFilters, signal?: AbortSignal) =>
    apiRequest<MyExploreResult>(`/api/v1/me/explore/${encodeURIComponent(track)}`, { query: { ...filters }, signal }),
  bookmarks: () => apiRequest<Bookmark[]>("/api/v1/me/bookmarks"),
  addBookmark: (body: SavedItemRef) => apiRequest<Bookmark[]>("/api/v1/me/bookmarks", { method: "PUT", body }),
  removeBookmark: (ref: SavedItemRef) =>
    apiRequest<Bookmark[]>("/api/v1/me/bookmarks", { method: "DELETE", query: { item_type: ref.item_type, track: ref.track ?? "", ref_id: ref.ref_id } }),
  collections: (ref?: SavedItemRef) =>
    apiRequest<CollectionSummary[]>("/api/v1/me/collections", { query: ref ? { item_type: ref.item_type, track: ref.track ?? "", ref_id: ref.ref_id } : {} }),
  collection: (id: string) => apiRequest<Collection>(`/api/v1/me/collections/${encodeURIComponent(id)}`),
  createCollection: (name: string) => apiRequest<Collection>("/api/v1/me/collections", { method: "POST", body: { name } }),
  renameCollection: (id: string, name: string) =>
    apiRequest<Collection>(`/api/v1/me/collections/${encodeURIComponent(id)}`, { method: "PATCH", body: { name } }),
  deleteCollection: (id: string) => apiRequest<void>(`/api/v1/me/collections/${encodeURIComponent(id)}`, { method: "DELETE" }),
  addToCollection: (id: string, body: SavedItemRef) =>
    apiRequest<Collection>(`/api/v1/me/collections/${encodeURIComponent(id)}/items`, { method: "POST", body }),
  removeFromCollection: (id: string, itemId: string) =>
    apiRequest<Collection>(`/api/v1/me/collections/${encodeURIComponent(id)}/items/${encodeURIComponent(itemId)}`, { method: "DELETE" }),
  reorderCollection: (id: string, itemIds: string[]) =>
    apiRequest<Collection>(`/api/v1/me/collections/${encodeURIComponent(id)}/order`, { method: "PUT", body: { item_ids: itemIds } }),
  setQueuePosition: (id: string, position: number) =>
    apiRequest<Collection>(`/api/v1/me/collections/${encodeURIComponent(id)}/queue`, { method: "PUT", body: { position } }),
  markQueueDone: (id: string, itemId: string, done: boolean) =>
    apiRequest<Collection>(`/api/v1/me/collections/${encodeURIComponent(id)}/items/${encodeURIComponent(itemId)}/done`, { method: "PUT", body: { done } }),

  // learn mode
  learnCatalog: (track: string) => apiRequest<LearnCatalog>("/api/v1/learn", { query: { track }, auth: false }),
  learnUnit: (id: string) => apiRequest<LearnUnit>(`/api/v1/learn/units/${encodeURIComponent(id)}`, { auth: false }),
  relatedUnits: (query: { track?: string; question_id?: string; problem_slug?: string }) =>
    apiRequest<UnitLink[]>("/api/v1/learn/related", { query, auth: false }),
  myLearn: (track: string) => apiRequest<Record<string, UnitProgress>>("/api/v1/me/learn", { query: { track } }),
  unitProgress: (id: string) => apiRequest<UnitProgress>(`/api/v1/me/learn/units/${encodeURIComponent(id)}`),
  learnEvent: (id: string, kind: "started" | "read", version: number) =>
    apiRequest<UnitProgress>(`/api/v1/me/learn/units/${encodeURIComponent(id)}/events`, { method: "POST", body: { kind, version } }),
  learnCheck: (id: string, version: number, answers: Record<string, number>) =>
    apiRequest<CheckResult>(`/api/v1/me/learn/units/${encodeURIComponent(id)}/check`, { method: "POST", body: { version, answers } }),

  // notebook
  notes: (filters: NoteFilters, signal?: AbortSignal) => apiRequest<NotePage>("/api/v1/me/notes", { query: { ...filters }, signal }),
  note: (id: string) => apiRequest<Note>(`/api/v1/me/notes/${encodeURIComponent(id)}`),
  createNote: (body: NoteInput) => apiRequest<Note>("/api/v1/me/notes", { method: "POST", body }),
  updateNote: (id: string, body: NotePatch, keepalive = false) =>
    apiRequest<Note>(`/api/v1/me/notes/${encodeURIComponent(id)}`, { method: "PATCH", body, keepalive }),
  deleteNote: (id: string) => apiRequest<{ id: string; restorable_until: string }>(`/api/v1/me/notes/${encodeURIComponent(id)}`, { method: "DELETE" }),
  restoreNote: (id: string) => apiRequest<Note>(`/api/v1/me/notes/${encodeURIComponent(id)}/restore`, { method: "POST" }),
  keyPoints: (id: string) => apiRequest<KeyPoints>(`/api/v1/me/notes/${encodeURIComponent(id)}/key-points`, { method: "POST" }),

  // sharing an answer for feedback (owner)
  sharePreview: (body: ShareSelection) => apiRequest<SharePreview>("/api/v1/me/shares/preview", { method: "POST", body }),
  createShare: (body: ShareCreate) => apiRequest<ShareCreated>("/api/v1/me/shares", { method: "POST", body }),
  shares: (answerId?: string) => apiRequest<ShareSummary[]>("/api/v1/me/shares", { query: { answer_id: answerId } }),
  share: (id: string) => apiRequest<ShareDetail>(`/api/v1/me/shares/${encodeURIComponent(id)}`),
  shareAction: (id: string, action: "close" | "reopen" | "revoke") =>
    apiRequest<ShareDetail>(`/api/v1/me/shares/${encodeURIComponent(id)}/${action}`, { method: "POST" }),
  newShareLink: (id: string) => apiRequest<ShareCreated>(`/api/v1/me/shares/${encodeURIComponent(id)}/link`, { method: "POST" }),
  deleteShare: (id: string) => apiRequest<void>(`/api/v1/me/shares/${encodeURIComponent(id)}`, { method: "DELETE" }),
  markFeedbackUseful: (id: string, feedbackId: string, useful: boolean) =>
    apiRequest<ShareDetail>(`/api/v1/me/shares/${encodeURIComponent(id)}/feedback/${encodeURIComponent(feedbackId)}/useful`, { method: "PUT", body: { useful } }),
  deleteFeedback: (id: string, feedbackId: string) =>
    apiRequest<ShareDetail>(`/api/v1/me/shares/${encodeURIComponent(id)}/feedback/${encodeURIComponent(feedbackId)}`, { method: "DELETE" }),
  // ...and the reviewer's side: the link secret goes in the body, never in a URL.
  openShared: (token: string) => apiRequest<RecipientView>("/api/v1/shared/open", { method: "POST", body: { token } }),
  sendFeedback: (body: FeedbackInput) => apiRequest<FeedbackReceipt>("/api/v1/shared/feedback", { method: "POST", body }),

  // branching scenarios
  scenarios: (track: string) => apiRequest<ScenarioCatalog>("/api/v1/scenarios", { query: { track }, auth: false }),
  scenario: (id: string) => apiRequest<ScenarioDetail>(`/api/v1/scenarios/${encodeURIComponent(id)}`, { auth: false }),
  startScenario: (id: string, body: { mode: "assessed" | "exploration"; parent_id?: string }) =>
    apiRequest<ScenarioAttempt>(`/api/v1/me/scenarios/${encodeURIComponent(id)}/attempts`, { method: "POST", body }),
  scenarioAttempts: (scenarioId?: string) => apiRequest<ScenarioAttemptSummary[]>("/api/v1/me/scenario-attempts", { query: { scenario_id: scenarioId } }),
  scenarioAttempt: (id: string) => apiRequest<ScenarioAttempt>(`/api/v1/me/scenario-attempts/${encodeURIComponent(id)}`),
  scenarioStep: (id: string, body: { node_id: string; choice_id?: string; text?: string }) =>
    apiRequest<ScenarioAttempt>(`/api/v1/me/scenario-attempts/${encodeURIComponent(id)}/steps`, { method: "POST", body }),

  // progress
  progress: () => apiRequest<Progress>("/api/v1/me/progress"),
  recommendations: (limit = 5) => apiRequest<Recommendation[]>("/api/v1/me/recommendations", { query: { limit } }),
};
