/** One function per backend endpoint. See docs/API.md for behavior and error codes. */
import { apiRequest } from "./client";
import type {
  AcceptedAction,
  ActionAccept,
  ActionOccurrencesIn,
  ActionUpdate,
  RequestOutcome,
  ActivityFacets,
  ActivityItem,
  ActivityStatus,
  ActivityType,
  AdminReportDetail,
  AIHistoryAction,
  AIHistoryItem,
  AIUsage,
  AnswerFlagIn,
  AnswerReview,
  AnswerSource,
  Application,
  ApplicationCreate,
  ApplicationEventIn,
  ApplicationStage,
  ApplicationSummary,
  ApplicationUpdate,
  Bookmark,
  Capabilities,
  LabExplanation,
  DemoOut,
  Career,
  CareerAnalytics,
  CheckResult,
  Collection,
  CollectionSummary,
  Comparison,
  ContentKind,
  ContentMeta,
  CorrectionInput,
  Criteria,
  Difficulty,
  DifficultyCounts,
  Drill,
  DrillAttempt,
  DrillAttemptIn,
  ExperienceEdit,
  ExperienceInput,
  ExplainFailureResponse,
  ExploreResult,
  ExploreSort,
  FeedbackInput,
  FeedbackReceipt,
  Goals,
  GoalsInput,
  HintRequest,
  HintResponse,
  Interview,
  InterviewAnswer,
  InterviewFormat,
  InterviewReview,
  InterviewStart,
  InterviewSummary,
  KeyPoints,
  Kit,
  KitTemplate,
  KitTemplateCreate,
  KitTemplateSummary,
  KitTemplateUpdate,
  KitUpdate,
  Packet,
  PacketIn,
  LearnCatalog,
  LearnUnit,
  LoginRequest,
  MyExploreResult,
  MyReport,
  Note,
  NoteInput,
  NotePage,
  NotePatch,
  Onboarding,
  OnboardingUpdate,
  Page,
  Plan,
  PlanItem,
  ProblemDetail,
  ProblemSummary,
  Progress,
  QuestionDetail,
  QuestionSummary,
  QuestionVersion,
  RecipientView,
  Recommendation,
  Reflection,
  ReflectionIn,
  ReflectionSummary,
  RegisterRequest,
  ReportGroup,
  ReportInput,
  ReportStatusValue,
  RequirementInput,
  RequirementPatch,
  RestoreBatch,
  RestorePreview,
  ResumeOut,
  ReviewQueue,
  ReviewPreview,
  ReviewPreviewRequest,
  ReviewRequest,
  ReviewResponse,
  SavedItemRef,
  ScenarioAttempt,
  ScenarioAttemptSummary,
  ScenarioCatalog,
  ScenarioDetail,
  Schedulable,
  ScheduleEntry,
  ScheduleEntryIn,
  ScheduleMove,
  PrepShift,
  PrepShiftResult,
  ScheduleSettings,
  SelfReviewIn,
  ShareCreate,
  ShareCreated,
  ShareDetail,
  SharePreview,
  ShareSelection,
  ShareSummary,
  Story,
  StoryAssist,
  StoryAssistAction,
  StoryCreate,
  StoryRevision,
  StorySummary,
  StoryUpdate,
  StoryUsedIn,
  Submission,
  SubmissionCreate,
  SubmissionListItem,
  SubmissionStatus,
  Target,
  TargetInput,
  TargetPatch,
  TargetSummary,
  TokenResponse,
  TopicCount,
  TraceOut,
  TrackProgress,
  UnitLink,
  UnitProgress,
  User,
  VerificationStatus,
  VerifyLinkResult,
  WhiteboardAttempt,
  ReviewAttempt,
  ReviewAttemptIn,
  ReviewAttemptSummary,
  ReviewDraft,
  ReviewDraftIn,
  ReviewExercise,
  ReviewExerciseSummary,
  ReviewReference,
  TestDesignExercise,
  TestDesignRun,
  TestDesignRunIn,
  TestDesignRunSummary,
  TestDesignSummary,
  TestDesignVariant,
  WorkSampleAttempt,
  ComparisonAttempt,
  ComparisonDoc,
  OfferCard,
  OfferComparison,
  OfferComparisonSummary,
  DataSummary,
  RecentWork,
  WorkspaceSearch,
  CollectionBatchIn,
  CollectionBatchOut,
  WorkspaceSearchBody,
  OfferCaseSummary,
  OfferPhase,
  OfferRehearsal,
  OfferRehearsalSummary,
  ComparisonAttemptSummary,
  ComparisonExplanation,
  ComparisonLesson,
  ComparisonSelectionIn,
  ComparisonSummary,
  WorkSampleAttemptSummary,
  WorkSampleBrief,
  WorkSampleDraft,
  WorkSampleDraftIn,
  WorkSampleSummary,
  WhiteboardAttemptIn,
  WhiteboardAttemptSummary,
  WhiteboardDiagram,
  WhiteboardDraft,
  WhiteboardDraftIn,
  WhiteboardPromptList,
} from "./types";

export interface ProblemFilters {
  /** "debug": the debugging lab's exercises; the coding library otherwise. */
  kind?: "problem" | "debug";
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

const reflectionUrl = (appId: string, eventId: string) =>
  `/api/v1/me/applications/${encodeURIComponent(appId)}/events/${encodeURIComponent(eventId)}/reflection`;

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
  /** Before a guest start or registration: an HttpOnly cookie that lets a retry of it, after a lost
   * reply, find the account it made instead of making another (Volume 8, prompt 6). */
  createAnchor: () => apiRequest<void>("/api/v1/auth/create-anchor", { method: "POST", auth: false }),
  me: () => apiRequest<User>("/api/v1/auth/me"),
  logout: () => apiRequest<void>("/api/v1/auth/logout", { method: "POST" }),
  /** Sign-out with a token that isn't this tab's session (finishing a sign-out the server missed). */
  logoutWith: (accessToken: string) => apiRequest<void>("/api/v1/auth/logout", {
    method: "POST", auth: false, noRefresh: true, headers: { Authorization: `Bearer ${accessToken}` },
  }),
  logoutAll: () => apiRequest<void>("/api/v1/auth/logout-all", { method: "POST" }),
  /** Works signed out. Sent with this tab's session if there is one, so the server can tell the
   * owner's own tab (which gets the account back) from someone signed in as another account (asked
   * first: 409 `verification_link_other_account`, unless `otherAccountOk`). */
  verifyEmailLink: (token: string, otherAccountOk = false) =>
    apiRequest<VerifyLinkResult>("/api/v1/auth/verify-email", {
      method: "POST", body: otherAccountOk ? { token, other_account_ok: true } : { token },
    }),
  /** Where the code went (masked), what became of the email, and when a new one can be sent. */
  verificationStatus: () => apiRequest<VerificationStatus>("/api/v1/auth/verify-email/status"),
  verifyEmailCode: (code: string) =>
    apiRequest<User>("/api/v1/auth/verify-email/code", { method: "POST", body: { code } }),
  resendVerification: () =>
    apiRequest<{ status: string; message: string }>("/api/v1/auth/verify-email/resend", { method: "POST" }),
  /** Asks to change the email. Nothing changes until the new address confirms with its code. */
  changeEmail: (body: { new_email: string; password: string }) =>
    apiRequest<User>("/api/v1/auth/email", { method: "POST", body }),
  cancelEmailChange: () => apiRequest<User>("/api/v1/auth/email/pending", { method: "DELETE" }),
  /**
   * Exchange the HttpOnly refresh cookie for a new access token (and a rotated cookie). The
   * attempt key lets a lost response be recovered (see auth/refreshAttempt.ts).
   */
  refresh: (attemptKey?: string) => apiRequest<TokenResponse>("/api/v1/auth/refresh", {
    method: "POST", auth: false,
    headers: { "X-Requested-With": "codecoach", ...(attemptKey ? { "X-Refresh-Attempt": attemptKey } : {}) },
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
  exportData: (version: 1 | 2 = 1) =>
    // Everything the account holds: allowed longer than an ordinary read.
    apiRequest<Record<string, unknown>>(version === 2 ? "/api/v1/me/export?version=2" : "/api/v1/me/export", { readDeadlineMs: 120_000 }),
  previewRestore: (fileText: string) => apiRequest<RestorePreview>("/api/v1/me/restore/preview", { method: "POST", rawBody: fileText }),
  applyRestore: (fileText: string, categories: string[]) =>
    apiRequest<RestoreBatch>(`/api/v1/me/restore?${categories.map((c) => `categories=${encodeURIComponent(c)}`).join("&")}`, { method: "POST", rawBody: fileText }),
  restoreBatches: () => apiRequest<RestoreBatch[]>("/api/v1/me/restore/batches"),
  removeRestore: (id: string) => apiRequest<RestoreBatch>(`/api/v1/me/restore/batches/${encodeURIComponent(id)}/remove`, { method: "POST" }),

  // problems
  problems: (filters: ProblemFilters = {}, signal?: AbortSignal) =>
    apiRequest<Page<ProblemSummary>>("/api/v1/problems", { query: { ...filters }, signal }),
  problemCounts: (filters: Pick<ProblemFilters, "topic" | "q"> = {}, signal?: AbortSignal) =>
    apiRequest<DifficultyCounts>("/api/v1/problems/counts", { query: { ...filters }, signal }),
  topics: () => apiRequest<TopicCount[]>("/api/v1/topics"),
  labExplanation: (slug: string) => apiRequest<LabExplanation>(`/api/v1/problems/${encodeURIComponent(slug)}/lab/explanation`, { auth: false }),

  // careers and their interview questions
  careers: () => apiRequest<Career[]>("/api/v1/careers"),
  questions: (track: string, filters: QuestionFilters = {}, signal?: AbortSignal) =>
    apiRequest<Page<QuestionSummary>>(`/api/v1/careers/${encodeURIComponent(track)}/questions`, { query: { ...filters }, signal }),
  questionCounts: (track: string, q = "", signal?: AbortSignal) =>
    apiRequest<DifficultyCounts>(`/api/v1/careers/${encodeURIComponent(track)}/questions/counts`, { query: { q }, signal }),
  question: (track: string, id: string, signal?: AbortSignal) =>
    apiRequest<QuestionDetail>(`/api/v1/careers/${encodeURIComponent(track)}/questions/${encodeURIComponent(id)}`, { signal }),
  /** `requestKey`: send only to a server whose capabilities say `answer_request_keys`. A keyed
   * answer goes to the protected route, which a server that ignores keys doesn't have: it refuses
   * the request (404) instead of saving it unprotected. */
  answerQuestion: (track: string, id: string, answer: string, storyId: string | null = null,
    opts: { requestKey?: string | null; revisesAnswerId?: string | null } = {}) =>
    apiRequest<InterviewAnswer>(`/api/v1/careers/${encodeURIComponent(track)}/questions/${encodeURIComponent(id)}/answers${opts.requestKey ? "/keyed" : ""}`, {
      method: "POST",
      body: {
        answer,
        ...(storyId ? { story_id: storyId } : {}),
        ...(opts.requestKey ? { client_request_id: opts.requestKey } : {}),
        ...(opts.revisesAnswerId ? { revises_answer_id: opts.revisesAnswerId } : {}),
      },
    }),
  myAnswers: (track: string, id: string) =>
    apiRequest<InterviewAnswer[]>(`/api/v1/careers/${encodeURIComponent(track)}/questions/${encodeURIComponent(id)}/answers`),
  trackProgress: (track: string) =>
    apiRequest<TrackProgress>(`/api/v1/careers/${encodeURIComponent(track)}/progress`),
  problem: (slug: string, signal?: AbortSignal) =>
    apiRequest<ProblemDetail>(`/api/v1/problems/${encodeURIComponent(slug)}`, { signal }),
  // Public copies (no credentials), for "Save for offline": nothing personal can be included.
  publicQuestion: (track: string, id: string) =>
    apiRequest<QuestionDetail>(`/api/v1/careers/${encodeURIComponent(track)}/questions/${encodeURIComponent(id)}`, { auth: false }),
  publicProblem: (slug: string) => apiRequest<ProblemDetail>(`/api/v1/problems/${encodeURIComponent(slug)}`, { auth: false }),

  capabilities: () => apiRequest<Capabilities>("/api/v1/capabilities"),
  /** The portfolio demo's fictional sample (404 unless the server runs the demo). */
  demo: () => apiRequest<DemoOut>("/api/v1/demo"),

  // submissions
  submit: (body: SubmissionCreate) => apiRequest<Submission>("/api/v1/submissions", { method: "POST", body }),
  submission: (id: string, signal?: AbortSignal) =>
    apiRequest<Submission>(`/api/v1/submissions/${encodeURIComponent(id)}`, { signal }),
  mySubmissions: (query: { problem_slug?: string; status?: SubmissionStatus; page?: number; page_size?: number } = {}) =>
    apiRequest<Page<SubmissionListItem>>("/api/v1/me/submissions", { query }),

  // AI coach
  hint: (body: HintRequest) => apiRequest<HintResponse>("/api/v1/ai/hint", { method: "POST", body }),
  review: (body: ReviewRequest) => apiRequest<ReviewResponse>("/api/v1/ai/review", { method: "POST", body }),
  /** What a review would send, exactly; no provider call and no budget (docs/COACH_CONTEXT.md). */
  reviewPreview: (body: ReviewPreviewRequest) =>
    apiRequest<ReviewPreview>("/api/v1/ai/review/preview", { method: "POST", body }),
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
  editExperience: (id: string, eid: string, body: ExperienceEdit) =>
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
  /** What a request sent with this key made, if anything (read-only; 404: no record). */
  requestOutcome: (key: string) => apiRequest<RequestOutcome>(`/api/v1/me/requests/${encodeURIComponent(key)}`),
  // mock interviews
  startInterview: (body: InterviewStart) => apiRequest<Interview>("/api/v1/interviews", { method: "POST", body }),
  interview: (id: string, signal?: AbortSignal) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}`, { signal }),
  interviews: (query: { page?: number; page_size?: number } = {}) =>
    apiRequest<Page<InterviewSummary>>("/api/v1/interviews", { query }),
  interviewMessage: (id: string, body: { message: string; code?: string | null; source?: AnswerSource; after_seq?: number; client_request_id?: string }) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/messages`, { method: "POST", body }),
  finishInterview: (id: string, code?: string | null) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/finish`, { method: "POST", body: { code: code ?? null } }),
  answerRoundQuestion: (id: string, body: { question_index: number; answer: string; source: AnswerSource }, traceparent?: string) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/answers`, { method: "POST", body, traceparent }),
  skipRoundQuestion: (id: string, question_index: number, traceparent?: string) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/skip`, { method: "POST", body: { question_index }, traceparent }),
  interviewFormats: (track: string, difficulty: Difficulty) =>
    apiRequest<InterviewFormat[]>("/api/v1/interviews/formats", { query: { track, difficulty }, auth: false }),
  answerFollowup: (id: string, body: { answer: string; source: AnswerSource }, traceparent?: string) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/followup`, { method: "POST", body, traceparent }),
  skipFollowup: (id: string, traceparent?: string) =>
    apiRequest<Interview>(`/api/v1/interviews/${encodeURIComponent(id)}/followup/skip`, { method: "POST", traceparent }),
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
  // Several adds or several removals, an outcome for each (docs/BULK_ACTIONS.md).
  batchCollection: (id: string, body: CollectionBatchIn) =>
    apiRequest<CollectionBatchOut>(`/api/v1/me/collections/${encodeURIComponent(id)}/items/batch`, { method: "POST", body }),
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

  // content quality: metadata, reports and (admins) triage
  contentMeta: (type: ContentKind, id: string) =>
    apiRequest<ContentMeta>(`/api/v1/content/${type}/${id.split("/").map(encodeURIComponent).join("/")}/meta`, { auth: false }),
  questionVersion: (track: string, id: string, version: number) =>
    apiRequest<QuestionVersion>(`/api/v1/careers/${encodeURIComponent(track)}/questions/${encodeURIComponent(id)}/versions/${version}`, { auth: false }),
  report: (body: ReportInput) => apiRequest<MyReport>("/api/v1/reports", { method: "POST", body }),
  myReports: () => apiRequest<MyReport[]>("/api/v1/me/reports"),
  adminTrace: (id: string) => apiRequest<TraceOut>(`/api/v1/admin/traces/${encodeURIComponent(id)}`),
  adminReports: (status?: string) => apiRequest<ReportGroup[]>("/api/v1/admin/reports", { query: { status } }),
  adminReport: (id: string) => apiRequest<AdminReportDetail>(`/api/v1/admin/reports/${encodeURIComponent(id)}`),
  adminSetStatus: (id: string, body: { status: ReportStatusValue; resolution?: string; internal_note?: string; include_duplicates?: boolean }) =>
    apiRequest<AdminReportDetail>(`/api/v1/admin/reports/${encodeURIComponent(id)}/status`, { method: "POST", body }),
  adminSetDuplicate: (id: string, body: { duplicate_of: string | null; internal_note?: string }) =>
    apiRequest<AdminReportDetail>(`/api/v1/admin/reports/${encodeURIComponent(id)}/duplicate`, { method: "POST", body }),
  adminCorrect: (contentId: string, body: CorrectionInput) =>
    apiRequest<ContentMeta>(`/api/v1/admin/content/question/${contentId.split("/").map(encodeURIComponent).join("/")}/corrections`, { method: "POST", body }),
  adminRetire: (type: ContentKind, id: string, body: { reason: string; report_ids?: string[]; internal_note?: string }) =>
    apiRequest<ContentMeta>(`/api/v1/admin/content/${type}/${id.split("/").map(encodeURIComponent).join("/")}/retire`, { method: "POST", body }),
  adminRestore: (type: ContentKind, id: string) =>
    apiRequest<ContentMeta>(`/api/v1/admin/content/${type}/${id.split("/").map(encodeURIComponent).join("/")}/restore`, { method: "POST", body: {} }),

  // the optional first-session introduction
  onboarding: () => apiRequest<Onboarding>("/api/v1/me/onboarding"),
  updateOnboarding: (body: OnboardingUpdate) => apiRequest<Onboarding>("/api/v1/me/onboarding", { method: "PATCH", body }),

  // the story bank
  stories: (filters: { archived?: boolean; q?: string; competency?: string } = {}) =>
    apiRequest<StorySummary[]>("/api/v1/me/stories", { query: { archived: filters.archived ? "true" : undefined, q: filters.q || undefined, competency: filters.competency || undefined } }),
  story: (id: string) => apiRequest<Story>(`/api/v1/me/stories/${encodeURIComponent(id)}`),
  createStory: (body: StoryCreate) => apiRequest<Story>("/api/v1/me/stories", { method: "POST", body }),
  updateStory: (id: string, body: StoryUpdate) => apiRequest<Story>(`/api/v1/me/stories/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  archiveStory: (id: string, archived: boolean) =>
    apiRequest<Story>(`/api/v1/me/stories/${encodeURIComponent(id)}/${archived ? "archive" : "unarchive"}`, { method: "POST" }),
  deleteStory: (id: string) => apiRequest<void>(`/api/v1/me/stories/${encodeURIComponent(id)}`, { method: "DELETE" }),
  storyUsedIn: (id: string) => apiRequest<StoryUsedIn>(`/api/v1/me/stories/${encodeURIComponent(id)}/used-in`),
  storyRevisions: (id: string) => apiRequest<StoryRevision[]>(`/api/v1/me/stories/${encodeURIComponent(id)}/revisions`),
  restoreStoryRevision: (id: string, revision: number, expected: number) =>
    apiRequest<Story>(`/api/v1/me/stories/${encodeURIComponent(id)}/revisions/${revision}/restore`, { method: "POST", body: { expected_revision: expected } }),
  assistStory: (id: string, body: { action: StoryAssistAction; situation?: string; task?: string; action_text?: string; result?: string; reflection?: string }) =>
    apiRequest<StoryAssist>(`/api/v1/me/stories/${encodeURIComponent(id)}/assist`, { method: "POST", body }),

  // applications you've made (never sent or submitted anywhere)
  applications: (archived = false) => apiRequest<ApplicationSummary[]>("/api/v1/me/applications", { query: { archived: archived ? "true" : undefined } }),
  application: (id: string) => apiRequest<Application>(`/api/v1/me/applications/${encodeURIComponent(id)}`),
  createApplication: (body: ApplicationCreate) => apiRequest<Application>("/api/v1/me/applications", { method: "POST", body }),
  /** One story at a time, repeat-safe both ways (docs/BACKLINKS.md). */
  linkApplicationStory: (id: string, storyId: string, linked: boolean) =>
    apiRequest<Application>(`/api/v1/me/applications/${encodeURIComponent(id)}/stories/${encodeURIComponent(storyId)}`, { method: linked ? "PUT" : "DELETE" }),
  updateApplication: (id: string, body: ApplicationUpdate) => apiRequest<Application>(`/api/v1/me/applications/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  setApplicationStage: (id: string, body: { stage: ApplicationStage; note: string; correction: boolean }) =>
    apiRequest<Application>(`/api/v1/me/applications/${encodeURIComponent(id)}/stage`, { method: "POST", body }),
  archiveApplication: (id: string, archived: boolean) =>
    apiRequest<Application>(`/api/v1/me/applications/${encodeURIComponent(id)}/${archived ? "archive" : "unarchive"}`, { method: "POST" }),
  deleteApplication: (id: string) => apiRequest<void>(`/api/v1/me/applications/${encodeURIComponent(id)}`, { method: "DELETE" }),
  addApplicationEvent: (id: string, body: ApplicationEventIn) => apiRequest<Application>(`/api/v1/me/applications/${encodeURIComponent(id)}/events`, { method: "POST", body }),
  updateApplicationEvent: (id: string, eventId: string, body: ApplicationEventIn) =>
    apiRequest<Application>(`/api/v1/me/applications/${encodeURIComponent(id)}/events/${encodeURIComponent(eventId)}`, { method: "PUT", body }),
  deleteApplicationEvent: (id: string, eventId: string) =>
    apiRequest<Application>(`/api/v1/me/applications/${encodeURIComponent(id)}/events/${encodeURIComponent(eventId)}`, { method: "DELETE" }),

  // your schedule (nothing is sent; .ics files are downloads)
  schedule: (from: string, to: string, includeCancelled = false) =>
    apiRequest<ScheduleEntry[]>("/api/v1/me/schedule", { query: { from, to, include_cancelled: includeCancelled ? "true" : undefined } }),
  scheduleSettings: () => apiRequest<ScheduleSettings>("/api/v1/me/schedule/settings"),
  saveScheduleSettings: (body: Partial<ScheduleSettings>) => apiRequest<ScheduleSettings>("/api/v1/me/schedule/settings", { method: "PUT", body }),
  schedulable: () => apiRequest<Schedulable[]>("/api/v1/me/schedule/schedulable"),
  createScheduleEntry: (body: ScheduleEntryIn) => apiRequest<ScheduleEntry>("/api/v1/me/schedule", { method: "POST", body }),
  moveScheduleEntry: (id: string, body: ScheduleMove) => apiRequest<ScheduleEntry>(`/api/v1/me/schedule/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  cancelScheduleEntry: (id: string) => apiRequest<ScheduleEntry>(`/api/v1/me/schedule/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  followInterview: (id: string, follows: boolean, expectedSequence: number) =>
    apiRequest<ScheduleEntry>(`/api/v1/me/schedule/${encodeURIComponent(id)}/follows-interview`, { method: "PUT", body: { follows, expected_sequence: expectedSequence } }),
  prepPreview: (appId: string, eventId: string) =>
    apiRequest<PrepShift>(`/api/v1/me/applications/${encodeURIComponent(appId)}/events/${encodeURIComponent(eventId)}/prep`),
  prepShift: (appId: string, eventId: string, eventStartsAt: string | null, entries: { id: string; sequence: number }[]) =>
    apiRequest<PrepShiftResult>(`/api/v1/me/applications/${encodeURIComponent(appId)}/events/${encodeURIComponent(eventId)}/prep/shift`, {
      method: "POST", body: { event_starts_at: eventStartsAt, entries },
    }),
  scheduleIcs: (query: { ids?: string; from?: string; to?: string }) =>
    apiRequest<string>("/api/v1/me/schedule/export.ics", { query, raw: true, headers: { Accept: "text/calendar" } }),

  // rubric transparency and self-review
  criteria: (track: string, id: string) =>
    apiRequest<Criteria>(`/api/v1/careers/${encodeURIComponent(track)}/questions/${encodeURIComponent(id)}/criteria`, { auth: false }),
  answerReview: (id: string) => apiRequest<AnswerReview>(`/api/v1/me/answers/${encodeURIComponent(id)}/review`),
  saveSelfReview: (id: string, body: SelfReviewIn) =>
    apiRequest<AnswerReview>(`/api/v1/me/answers/${encodeURIComponent(id)}/self-review`, { method: "PUT", body }),
  addAnswerFlag: (id: string, body: AnswerFlagIn) =>
    apiRequest<AnswerReview>(`/api/v1/me/answers/${encodeURIComponent(id)}/flags`, { method: "POST", body }),
  removeAnswerFlag: (id: string, flagId: number) =>
    apiRequest<AnswerReview>(`/api/v1/me/answers/${encodeURIComponent(id)}/flags/${flagId}`, { method: "DELETE" }),
  reevaluateAnswer: (id: string, reason: string) =>
    apiRequest<AnswerReview>(`/api/v1/me/answers/${encodeURIComponent(id)}/evaluations`, { method: "POST", body: { reason } }),

  // reflections on real interviews
  reflections: (f: { q?: string; outcome?: string; include_archived?: boolean } = {}) =>
    apiRequest<ReflectionSummary[]>("/api/v1/me/reflections", { query: f }),
  reflection: (appId: string, eventId: string) => apiRequest<Reflection>(reflectionUrl(appId, eventId)),
  saveReflection: (appId: string, eventId: string, body: ReflectionIn) => apiRequest<Reflection>(reflectionUrl(appId, eventId), { method: "PUT", body }),
  suggestReflectionSteps: (appId: string, eventId: string) => apiRequest<Reflection>(`${reflectionUrl(appId, eventId)}/suggestions`, { method: "POST" }),
  editReflectionStep: (appId: string, eventId: string, actionId: string, body: { status?: "suggested" | "dismissed"; title?: string; detail?: string }) =>
    apiRequest<Reflection>(`${reflectionUrl(appId, eventId)}/actions/${encodeURIComponent(actionId)}`, { method: "PATCH", body }),
  acceptReflectionStep: (appId: string, eventId: string, actionId: string, body: { target: "notebook" | "schedule" | "saved"; on_date?: string; timezone?: string }) =>
    apiRequest<Reflection>(`${reflectionUrl(appId, eventId)}/actions/${encodeURIComponent(actionId)}/accept`, { method: "POST", body }),
  setReflectionOutcome: (appId: string, eventId: string, body: { outcome: string; update_application: boolean }) =>
    apiRequest<Reflection>(`${reflectionUrl(appId, eventId)}/outcome`, { method: "PUT", body }),

  // communication drills
  drills: () => apiRequest<Drill[]>("/api/v1/me/drills"),
  drill: (id: string) => apiRequest<Drill>(`/api/v1/me/drills/${encodeURIComponent(id)}`),
  drillAttempts: (id: string) => apiRequest<DrillAttempt[]>(`/api/v1/me/drills/${encodeURIComponent(id)}/attempts`),
  submitDrill: (id: string, body: DrillAttemptIn) =>
    apiRequest<DrillAttempt>(`/api/v1/me/drills/${encodeURIComponent(id)}/attempts`, { method: "POST", body }),

  // whiteboard practice
  whiteboardPrompts: () => apiRequest<WhiteboardPromptList>("/api/v1/me/whiteboard/prompts"),
  whiteboardDraft: (promptId: string) => apiRequest<WhiteboardDraft>(`/api/v1/me/whiteboard/${encodeURIComponent(promptId)}/draft`),
  saveWhiteboardDraft: (promptId: string, body: WhiteboardDraftIn) =>
    apiRequest<WhiteboardDraft>(`/api/v1/me/whiteboard/${encodeURIComponent(promptId)}/draft`, { method: "PUT", body }),
  whiteboardAttempt: (promptId: string, body: WhiteboardAttemptIn) =>
    apiRequest<WhiteboardAttempt>(`/api/v1/me/whiteboard/${encodeURIComponent(promptId)}/attempts`, { method: "POST", body }),
  whiteboardAttempts: (promptId: string) => apiRequest<WhiteboardAttemptSummary[]>(`/api/v1/me/whiteboard/${encodeURIComponent(promptId)}/attempts`),
  whiteboardAttemptById: (id: string) => apiRequest<WhiteboardAttempt>(`/api/v1/me/whiteboard/attempts/${encodeURIComponent(id)}`),
  validateWhiteboard: (body: unknown) => apiRequest<WhiteboardDiagram>("/api/v1/me/whiteboard/validate", { method: "POST", body }),

  // code-review practice (the exercises are public; your review is yours)
  reviewExercises: () => apiRequest<ReviewExerciseSummary[]>("/api/v1/code-reviews", { auth: false }),
  reviewExercise: (slug: string) => apiRequest<ReviewExercise>(`/api/v1/code-reviews/${encodeURIComponent(slug)}`, { auth: false }),
  reviewDraft: (slug: string) => apiRequest<ReviewDraft>(`/api/v1/me/code-reviews/${encodeURIComponent(slug)}/draft`),
  saveReviewDraft: (slug: string, body: ReviewDraftIn) =>
    apiRequest<ReviewDraft>(`/api/v1/me/code-reviews/${encodeURIComponent(slug)}/draft`, { method: "PUT", body }),
  revealReview: (slug: string) => apiRequest<ReviewReference>(`/api/v1/me/code-reviews/${encodeURIComponent(slug)}/reveal`, { method: "POST" }),
  sendReview: (slug: string, body: ReviewAttemptIn) =>
    apiRequest<ReviewAttempt>(`/api/v1/me/code-reviews/${encodeURIComponent(slug)}/attempts`, { method: "POST", body }),
  reviewAttempts: (slug: string) => apiRequest<ReviewAttemptSummary[]>(`/api/v1/me/code-reviews/${encodeURIComponent(slug)}/attempts`),
  reviewAttempt: (id: string) => apiRequest<ReviewAttempt>(`/api/v1/me/code-reviews/attempts/${encodeURIComponent(id)}`),

  // test design (the exercises and their faulty versions are public; your runs are yours)
  testDesigns: () => apiRequest<TestDesignSummary[]>("/api/v1/test-design", { auth: false }),
  testDesign: (slug: string) => apiRequest<TestDesignExercise>(`/api/v1/test-design/${encodeURIComponent(slug)}`, { auth: false }),
  testDesignVariants: (slug: string) => apiRequest<TestDesignVariant[]>(`/api/v1/test-design/${encodeURIComponent(slug)}/variants`, { auth: false }),
  startTestRun: (slug: string, body: TestDesignRunIn) =>
    apiRequest<TestDesignRun>(`/api/v1/me/test-design/${encodeURIComponent(slug)}/runs`, { method: "POST", body }),
  testRuns: (slug: string) => apiRequest<TestDesignRunSummary[]>(`/api/v1/me/test-design/${encodeURIComponent(slug)}/runs`),
  testRun: (id: string) => apiRequest<TestDesignRun>(`/api/v1/me/test-design/runs/${encodeURIComponent(id)}`),

  // work samples (the briefs are public; your drafts and attempts are yours)
  workSamples: () => apiRequest<WorkSampleSummary[]>("/api/v1/work-samples", { auth: false }),
  workSample: (id: string) => apiRequest<WorkSampleBrief>(`/api/v1/work-samples/${encodeURIComponent(id)}`, { auth: false }),
  workSampleDraft: (id: string) => apiRequest<WorkSampleDraft>(`/api/v1/me/work-samples/${encodeURIComponent(id)}/draft`),
  saveWorkSampleDraft: (id: string, body: WorkSampleDraftIn) =>
    apiRequest<WorkSampleDraft>(`/api/v1/me/work-samples/${encodeURIComponent(id)}/draft`, { method: "PUT", body }),
  sendWorkSample: (id: string, body: { sections: Record<string, string>; revision_of?: string | null }) =>
    apiRequest<WorkSampleAttempt>(`/api/v1/me/work-samples/${encodeURIComponent(id)}/attempts`, { method: "POST", body }),
  workSampleAttempts: (id: string) => apiRequest<WorkSampleAttemptSummary[]>(`/api/v1/me/work-samples/${encodeURIComponent(id)}/attempts`),
  workSampleAttempt: (attemptId: string) => apiRequest<WorkSampleAttempt>(`/api/v1/me/work-samples/attempts/${encodeURIComponent(attemptId)}`),

  // sample-answer comparisons (lessons and explanations are public; your readings are yours)
  sampleLessons: () => apiRequest<ComparisonSummary[]>("/api/v1/comparisons", { auth: false }),
  sampleLesson: (id: string) => apiRequest<ComparisonLesson>(`/api/v1/comparisons/${encodeURIComponent(id)}`, { auth: false }),
  sampleLessonExplanation: (id: string) => apiRequest<ComparisonExplanation>(`/api/v1/comparisons/${encodeURIComponent(id)}/explanation`, { auth: false }),
  sendSampleReading: (id: string, body: { selections: ComparisonSelectionIn[]; choice: string | null; revealed_early: boolean }) =>
    apiRequest<ComparisonAttempt>(`/api/v1/me/comparisons/${encodeURIComponent(id)}/attempts`, { method: "POST", body }),
  sampleReadings: (id: string) => apiRequest<ComparisonAttemptSummary[]>(`/api/v1/me/comparisons/${encodeURIComponent(id)}/attempts`),
  sampleReading: (attemptId: string) => apiRequest<ComparisonAttempt>(`/api/v1/me/comparisons/attempts/${encodeURIComponent(attemptId)}`),

  // interview-day kits
  kit: (appId: string, eventId: string) => apiRequest<Kit>(`/api/v1/me/applications/${encodeURIComponent(appId)}/events/${encodeURIComponent(eventId)}/kit`),
  // a practice packet (docs/PACKET.md): assembled for a preview, nothing stored
  previewPacket: (body: PacketIn) => apiRequest<Packet>("/api/v1/me/packet/preview", { method: "POST", body }),
  // your kit templates (docs/TEMPLATES.md)
  kitTemplates: () => apiRequest<KitTemplateSummary[]>("/api/v1/me/kit-templates"),
  kitTemplate: (id: string) => apiRequest<KitTemplate>(`/api/v1/me/kit-templates/${encodeURIComponent(id)}`),
  createKitTemplate: (body: KitTemplateCreate) => apiRequest<KitTemplate>("/api/v1/me/kit-templates", { method: "POST", body }),
  updateKitTemplate: (id: string, body: KitTemplateUpdate) =>
    apiRequest<KitTemplate>(`/api/v1/me/kit-templates/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  deleteKitTemplate: (id: string) => apiRequest<void>(`/api/v1/me/kit-templates/${encodeURIComponent(id)}`, { method: "DELETE" }),
  // improvements you accepted (docs/ACCEPTED_ACTIONS.md): one action each, shown by the plan, schedule and kit
  actions: () => apiRequest<AcceptedAction[]>("/api/v1/me/actions"),
  action: (id: string) => apiRequest<AcceptedAction>(`/api/v1/me/actions/${encodeURIComponent(id)}`),
  acceptAction: (body: ActionAccept) => apiRequest<AcceptedAction>("/api/v1/me/actions", { method: "POST", body }),
  updateAction: (id: string, body: ActionUpdate) =>
    apiRequest<AcceptedAction>(`/api/v1/me/actions/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  setActionDone: (id: string, done: boolean) =>
    apiRequest<AcceptedAction>(`/api/v1/me/actions/${encodeURIComponent(id)}/${done ? "complete" : "reopen"}`, { method: "POST" }),
  scheduleAction: (id: string, body: ActionOccurrencesIn) =>
    apiRequest<AcceptedAction>(`/api/v1/me/actions/${encodeURIComponent(id)}/occurrences`, { method: "POST", body }),
  setOccurrenceDone: (id: string, entryId: string, done: boolean) =>
    apiRequest<AcceptedAction>(
      `/api/v1/me/actions/${encodeURIComponent(id)}/occurrences/${encodeURIComponent(entryId)}/${done ? "complete" : "reopen"}`,
      { method: "POST" },
    ),
  saveKit: (appId: string, eventId: string, body: KitUpdate) =>
    apiRequest<Kit>(`/api/v1/me/applications/${encodeURIComponent(appId)}/events/${encodeURIComponent(eventId)}/kit`, { method: "PUT", body }),

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

  // offer-conversation rehearsals (fictional cards, an authored counterpart; nothing is sent)
  offerCases: () => apiRequest<OfferCaseSummary[]>("/api/v1/offer-rehearsals/cases", { auth: false }),
  offerCase: (id: string) => apiRequest<OfferCard>(`/api/v1/offer-rehearsals/cases/${encodeURIComponent(id)}`, { auth: false }),
  startOfferRehearsal: (body: { case_id: string; goals: string[]; parent_id?: string | null }) =>
    apiRequest<OfferRehearsal>("/api/v1/me/offer-rehearsals", { method: "POST", body }),
  offerRehearsals: () => apiRequest<OfferRehearsalSummary[]>("/api/v1/me/offer-rehearsals"),
  offerRehearsal: (id: string) => apiRequest<OfferRehearsal>(`/api/v1/me/offer-rehearsals/${encodeURIComponent(id)}`),
  offerTurn: (id: string, body: { text: string; source: AnswerSource; after_seq: number; client_request_id: string }) =>
    apiRequest<OfferRehearsal>(`/api/v1/me/offer-rehearsals/${encodeURIComponent(id)}/turns`, { method: "POST", body }),
  offerAdvance: (id: string, fromPhase: OfferPhase) =>
    apiRequest<OfferRehearsal>(`/api/v1/me/offer-rehearsals/${encodeURIComponent(id)}/phase`, { method: "POST", body: { from_phase: fromPhase } }),
  offerFinish: (id: string) => apiRequest<OfferRehearsal>(`/api/v1/me/offer-rehearsals/${encodeURIComponent(id)}/finish`, { method: "POST" }),

  // private offer comparisons (terms entered by hand; nothing is sent)
  offerComparisons: (archived = false) =>
    apiRequest<OfferComparisonSummary[]>("/api/v1/me/offer-comparisons", { query: { archived } }),
  // Out of the active list or back into it; only the flag changes (docs/ARCHIVE.md).
  archiveOfferComparison: (id: string, archived: boolean) =>
    apiRequest<OfferComparison>(`/api/v1/me/offer-comparisons/${encodeURIComponent(id)}/${archived ? "archive" : "unarchive"}`, { method: "POST" }),
  // What's saved to the account, as counts (docs/YOUR_DATA.md)
  dataSummary: () => apiRequest<DataSummary>("/api/v1/me/data-summary"),
  // A few of your own records, newest first: titles and times only (docs/CONTINUE.md)
  recentWork: (limit = 6) => apiRequest<RecentWork>("/api/v1/me/recent-work", { query: { limit } }),
  // Search your own saved work (docs/WORKSPACE_SEARCH.md). A POST: the words stay out of URLs and logs.
  searchWorkspace: (body: WorkspaceSearchBody, signal?: AbortSignal) =>
    apiRequest<WorkspaceSearch>("/api/v1/me/search", { method: "POST", body, signal }),
  createOfferComparison: (body: { title?: string; example?: boolean }) =>
    apiRequest<OfferComparison>("/api/v1/me/offer-comparisons", { method: "POST", body }),
  offerComparison: (id: string) => apiRequest<OfferComparison>(`/api/v1/me/offer-comparisons/${encodeURIComponent(id)}`),
  saveOfferComparison: (id: string, body: { doc: ComparisonDoc; expected_revision: number; client_request_id: string }) =>
    apiRequest<OfferComparison>(`/api/v1/me/offer-comparisons/${encodeURIComponent(id)}`, { method: "PUT", body }),
  deleteOfferComparison: (id: string) => apiRequest<void>(`/api/v1/me/offer-comparisons/${encodeURIComponent(id)}`, { method: "DELETE" }),
  previewOfferComparison: (doc: ComparisonDoc) =>
    apiRequest<{ derived: Record<string, unknown> }>("/api/v1/me/offer-comparisons/preview", { method: "POST", body: doc }),

  // branching scenarios
  scenarios: (track: string) => apiRequest<ScenarioCatalog>("/api/v1/scenarios", { query: { track }, auth: false }),
  scenario: (id: string) => apiRequest<ScenarioDetail>(`/api/v1/scenarios/${encodeURIComponent(id)}`, { auth: false }),
  startScenario: (id: string, body: { mode: "assessed" | "exploration"; parent_id?: string }) =>
    apiRequest<ScenarioAttempt>(`/api/v1/me/scenarios/${encodeURIComponent(id)}/attempts`, { method: "POST", body }),
  scenarioAttempts: (scenarioId?: string) => apiRequest<ScenarioAttemptSummary[]>("/api/v1/me/scenario-attempts", { query: { scenario_id: scenarioId } }),
  scenarioAttempt: (id: string) => apiRequest<ScenarioAttempt>(`/api/v1/me/scenario-attempts/${encodeURIComponent(id)}`),
  scenarioStep: (id: string, body: { node_id: string; choice_id?: string; text?: string; order?: string[] }) =>
    apiRequest<ScenarioAttempt>(`/api/v1/me/scenario-attempts/${encodeURIComponent(id)}/steps`, { method: "POST", body }),

  // progress
  progress: () => apiRequest<Progress>("/api/v1/me/progress"),
  recommendations: (limit = 5) => apiRequest<Recommendation[]>("/api/v1/me/recommendations", { query: { limit } }),
};
