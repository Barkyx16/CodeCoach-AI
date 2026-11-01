/**
 * TanStack Query hooks: caching, request de-duplication, retries and polling live here,
 * so components only describe *what* data they need.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "./client";
import { api, type ProblemFilters } from "./endpoints";
import type { HintRequest, ReviewRequest, Submission, SubmissionCreate } from "./types";

export const queryKeys = {
  problems: (filters: ProblemFilters) => ["problems", filters] as const,
  topics: ["topics"] as const,
  problem: (slug: string) => ["problem", slug] as const,
  submission: (id: string) => ["submission", id] as const,
  mySubmissions: (params: object) => ["me", "submissions", params] as const,
  aiUsage: ["me", "ai-usage"] as const,
  aiHistory: (params: object) => ["me", "ai-history", params] as const,
  progress: ["me", "progress"] as const,
  recommendations: (limit: number) => ["me", "recommendations", limit] as const,
};

/** Don't retry client errors (4xx): they won't fix themselves. Retry network/5xx twice. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  return failureCount < 2;
}

export function useProblems(filters: ProblemFilters) {
  return useQuery({
    queryKey: queryKeys.problems(filters),
    queryFn: ({ signal }) => api.problems(filters, signal),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  });
}

export function useTopics() {
  return useQuery({ queryKey: queryKeys.topics, queryFn: api.topics, staleTime: 30 * 60_000 });
}

export function useProblem(slug: string) {
  return useQuery({
    queryKey: queryKeys.problem(slug),
    queryFn: ({ signal }) => api.problem(slug, signal),
    staleTime: 5 * 60_000,
  });
}

export const SUBMISSION_POLL_MS = 1500;

/** Poll while the job is still running AND the backend can actually execute code. */
export function submissionPollInterval(submission: Submission | undefined): number | false {
  if (!submission) return false;
  return !submission.is_terminal && submission.execution_enabled ? SUBMISSION_POLL_MS : false;
}

export function useSubmission(id: string | null) {
  return useQuery({
    queryKey: queryKeys.submission(id ?? "none"),
    queryFn: ({ signal }) => api.submission(id as string, signal),
    enabled: id !== null,
    refetchInterval: (query) => submissionPollInterval(query.state.data),
  });
}

export function useSubmit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SubmissionCreate) => api.submit(body),
    onSuccess: (submission) => {
      queryClient.setQueryData(queryKeys.submission(submission.id), submission);
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useMySubmissions(params: { problem_slug?: string; page?: number; page_size?: number }, enabled = true) {
  return useQuery({
    queryKey: queryKeys.mySubmissions(params),
    queryFn: () => api.mySubmissions(params),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useHint() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: HintRequest) => api.hint(body),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: ["me"] }),
  });
}

export function useReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ReviewRequest) => api.review(body),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: ["me"] }),
  });
}

export function useAIUsage(enabled = true) {
  return useQuery({ queryKey: queryKeys.aiUsage, queryFn: api.aiUsage, enabled });
}

export function useAIHistory(params: { problem_slug?: string; action?: "hint" | "review"; page?: number; page_size?: number },
  enabled = true) {
  return useQuery({
    queryKey: queryKeys.aiHistory(params),
    queryFn: () => api.aiHistory(params),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useProgress(enabled = true) {
  return useQuery({ queryKey: queryKeys.progress, queryFn: api.progress, enabled });
}

export function useRecommendations(limit = 5, enabled = true) {
  return useQuery({ queryKey: queryKeys.recommendations(limit), queryFn: () => api.recommendations(limit), enabled });
}
