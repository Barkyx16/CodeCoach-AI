/** One function per backend endpoint. See docs/API.md for behavior and error codes. */
import { apiRequest } from "./client";
import type {
  AIHistoryItem,
  AIUsage,
  Difficulty,
  HintRequest,
  HintResponse,
  LoginRequest,
  Page,
  ProblemDetail,
  ProblemSummary,
  Progress,
  Recommendation,
  RegisterRequest,
  ReviewRequest,
  ReviewResponse,
  Submission,
  SubmissionCreate,
  SubmissionListItem,
  SubmissionStatus,
  TokenResponse,
  TopicCount,
  User,
} from "./types";

export interface ProblemFilters {
  difficulty?: Difficulty | "";
  topic?: string;
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
  guest: (display_name?: string) =>
    apiRequest<TokenResponse>("/api/v1/auth/guest", {
      method: "POST", body: display_name ? { display_name } : {}, auth: false,
    }),
  me: () => apiRequest<User>("/api/v1/auth/me"),
  logout: () => apiRequest<void>("/api/v1/auth/logout", { method: "POST" }),

  // problems
  problems: (filters: ProblemFilters = {}, signal?: AbortSignal) =>
    apiRequest<Page<ProblemSummary>>("/api/v1/problems", { query: { ...filters }, signal }),
  topics: () => apiRequest<TopicCount[]>("/api/v1/topics"),
  problem: (slug: string, signal?: AbortSignal) =>
    apiRequest<ProblemDetail>(`/api/v1/problems/${encodeURIComponent(slug)}`, { signal }),

  // submissions
  submit: (body: SubmissionCreate) => apiRequest<Submission>("/api/v1/submissions", { method: "POST", body }),
  submission: (id: string, signal?: AbortSignal) =>
    apiRequest<Submission>(`/api/v1/submissions/${encodeURIComponent(id)}`, { signal }),
  mySubmissions: (query: { problem_slug?: string; status?: SubmissionStatus; page?: number; page_size?: number } = {}) =>
    apiRequest<Page<SubmissionListItem>>("/api/v1/me/submissions", { query }),

  // AI coach
  hint: (body: HintRequest) => apiRequest<HintResponse>("/api/v1/ai/hint", { method: "POST", body }),
  review: (body: ReviewRequest) => apiRequest<ReviewResponse>("/api/v1/ai/review", { method: "POST", body }),
  aiUsage: () => apiRequest<AIUsage>("/api/v1/ai/usage"),
  aiHistory: (query: { problem_slug?: string; action?: "hint" | "review"; page?: number; page_size?: number } = {}) =>
    apiRequest<Page<AIHistoryItem>>("/api/v1/me/ai-history", { query }),

  // progress
  progress: () => apiRequest<Progress>("/api/v1/me/progress"),
  recommendations: (limit = 5) => apiRequest<Recommendation[]>("/api/v1/me/recommendations", { query: { limit } }),
};
