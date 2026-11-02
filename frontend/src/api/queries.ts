/**
 * TanStack Query hooks: caching, request de-duplication, retries and polling live here,
 * so components only describe *what* data they need.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "./client";
import { api, type ProblemFilters, type QuestionFilters } from "./endpoints";
import type { AIHistoryAction, AnswerSource, HintRequest, Interview, InterviewStart, ReviewRequest, Submission, SubmissionCreate } from "./types";

export const queryKeys = {
  problems: (filters: ProblemFilters) => ["problems", filters] as const,
  problemCounts: (filters: object) => ["problems", "counts", filters] as const,
  topics: ["topics"] as const,
  careers: ["careers"] as const,
  questions: (track: string, filters: object) => ["careers", track, "questions", filters] as const,
  questionCounts: (track: string, q: string) => ["careers", track, "counts", q] as const,
  question: (track: string, id: string) => ["careers", track, "question", id] as const,
  answers: (track: string, id: string) => ["careers", track, "answers", id] as const,
  trackProgress: (track: string) => ["careers", track, "progress"] as const,
  capabilities: ["capabilities"] as const,
  problem: (slug: string) => ["problem", slug] as const,
  submission: (id: string) => ["submission", id] as const,
  mySubmissions: (params: object) => ["me", "submissions", params] as const,
  aiUsage: ["me", "ai-usage"] as const,
  aiHistory: (params: object) => ["me", "ai-history", params] as const,
  progress: ["me", "progress"] as const,
  recommendations: (limit: number) => ["me", "recommendations", limit] as const,
  interview: (id: string) => ["me", "interview", id] as const,
  interviews: (params: object) => ["me", "interviews", params] as const,
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

/** How many problems match the topic and search, per difficulty (the library tab counts). */
export function useProblemCounts(filters: { topic?: string; q?: string }) {
  return useQuery({
    queryKey: queryKeys.problemCounts(filters),
    queryFn: ({ signal }) => api.problemCounts(filters, signal),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  });
}

export function useCareers() {
  return useQuery({ queryKey: queryKeys.careers, queryFn: api.careers, staleTime: Infinity });
}

export function useQuestions(track: string, filters: QuestionFilters) {
  return useQuery({
    queryKey: queryKeys.questions(track, filters),
    queryFn: ({ signal }) => api.questions(track, filters, signal),
    placeholderData: keepPreviousData,
  });
}

export function useQuestionCounts(track: string, q: string) {
  return useQuery({
    queryKey: queryKeys.questionCounts(track, q),
    queryFn: ({ signal }) => api.questionCounts(track, q, signal),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  });
}

export function useQuestion(track: string, id: string) {
  return useQuery({ queryKey: queryKeys.question(track, id), queryFn: ({ signal }) => api.question(track, id, signal) });
}

export function useMyAnswers(track: string, id: string, enabled: boolean) {
  return useQuery({ queryKey: queryKeys.answers(track, id), queryFn: () => api.myAnswers(track, id), enabled });
}

export function useAnswerQuestion(track: string, id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (answer: string) => api.answerQuestion(track, id, answer),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["careers", track] });
    },
  });
}

export function useTrackProgress(track: string, enabled = true) {
  return useQuery({ queryKey: queryKeys.trackProgress(track), queryFn: () => api.trackProgress(track), enabled });
}

export function useTopics() {
  return useQuery({ queryKey: queryKeys.topics, queryFn: api.topics, staleTime: 30 * 60_000 });
}

/** What this deployment supports (e.g. whether code runs). Changes only on redeploy. */
export function useCapabilities() {
  return useQuery({ queryKey: queryKeys.capabilities, queryFn: api.capabilities, staleTime: Infinity });
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

export function useExplainFailure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (submissionId: string) => api.explainFailure(submissionId),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: ["me"] }),
  });
}

export function useAIUsage(enabled = true) {
  return useQuery({ queryKey: queryKeys.aiUsage, queryFn: api.aiUsage, enabled });
}

export function useAIHistory(params: { problem_slug?: string; action?: AIHistoryAction; page?: number; page_size?: number },
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

export function useInterview(id: string) {
  return useQuery({ queryKey: queryKeys.interview(id), queryFn: ({ signal }) => api.interview(id, signal) });
}

export function useInterviews(params: { page?: number; page_size?: number }, enabled = true) {
  return useQuery({
    queryKey: queryKeys.interviews(params),
    queryFn: () => api.interviews(params),
    enabled,
    placeholderData: keepPreviousData,
  });
}

/** All interview mutations return the full, fresh interview; write it straight into the cache. */
function useInterviewMutation<V>(fn: (vars: V) => Promise<Interview>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (interview) => {
      queryClient.setQueryData(queryKeys.interview(interview.id), interview);
      void queryClient.invalidateQueries({ queryKey: ["me", "interviews"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.aiUsage });
      if (interview.status !== "in_progress") void queryClient.invalidateQueries({ queryKey: queryKeys.progress });
    },
  });
}

export const useStartInterview = () => useInterviewMutation((body: InterviewStart) => api.startInterview(body));
export const useInterviewMessage = (id: string) =>
  useInterviewMutation((body: { message: string; code?: string | null; source?: AnswerSource }) => api.interviewMessage(id, body));
export const useAnswerRoundQuestion = (id: string) =>
  useInterviewMutation((body: { question_index: number; answer: string; source: AnswerSource }) => api.answerRoundQuestion(id, body));
export const useSkipRoundQuestion = (id: string) => useInterviewMutation((index: number) => api.skipRoundQuestion(id, index));
export const useFinishInterview = (id: string) =>
  useInterviewMutation((code: string | null) => api.finishInterview(id, code));
export const useAbandonInterview = (id: string) => useInterviewMutation((_: void) => api.abandonInterview(id));
