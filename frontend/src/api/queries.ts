/**
 * TanStack Query hooks: caching, request de-duplication, retries and polling live here,
 * so components only describe *what* data they need.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "./client";
import { api, type ActivityFilters, type ExploreFilters, type ProblemFilters, type QuestionFilters } from "./endpoints";
import type { AIHistoryAction, AnswerSource, Bookmark, Collection, GoalsInput, MyExploreResult, ReviewQueue, SavedItemRef, Target, HintRequest, Interview, InterviewStart, ReviewRequest, Submission, SubmissionCreate } from "./types";

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

export function useProblems(filters: ProblemFilters, enabled = true) {
  return useQuery({
    queryKey: queryKeys.problems(filters),
    queryFn: ({ signal }) => api.problems(filters, signal),
    enabled,
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

export function useQuestion(track: string, id: string, enabled = true) {
  return useQuery({ queryKey: queryKeys.question(track, id), queryFn: ({ signal }) => api.question(track, id, signal), enabled });
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
      void qc.invalidateQueries({ queryKey: ["me"] }); // activity, analytics, resume
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

export function useProblem(slug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.problem(slug),
    queryFn: ({ signal }) => api.problem(slug, signal),
    enabled,
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
      for (const key of ["activity", "activity-facets", "career-analytics", "resume"]) {
        void queryClient.invalidateQueries({ queryKey: ["me", key] });
      }
      if (interview.track) void queryClient.invalidateQueries({ queryKey: ["careers", interview.track] });
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

export function useActivity(filters: ActivityFilters) {
  return useQuery({
    queryKey: ["me", "activity", filters],
    queryFn: ({ signal }) => api.activity(filters, signal),
    placeholderData: keepPreviousData,
  });
}

export function useActivityFacets(career?: string) {
  return useQuery({ queryKey: ["me", "activity-facets", career ?? ""], queryFn: () => api.activityFacets(career) });
}

export function useCareerAnalytics(track: string, since: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["me", "career-analytics", track, since ?? "all"],
    queryFn: () => api.careerAnalytics(track, since),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useResume(enabled = true) {
  return useQuery({ queryKey: ["me", "resume"], queryFn: api.resume, enabled });
}

export function useAIHistoryItem(id: string) {
  return useQuery({ queryKey: ["me", "ai-history-item", id], queryFn: () => api.aiHistoryItem(id) });
}

export function useGoals(track?: string) {
  return useQuery({ queryKey: ["me", "goals", track ?? ""], queryFn: () => api.goals(track) });
}

export function useSaveGoals() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GoalsInput) => api.saveGoals(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["me", "goals"] });
      void qc.invalidateQueries({ queryKey: ["me", "plan"] });
    },
  });
}

export function usePlan(track: string | undefined, minutes: number, enabled = true) {
  return useQuery({
    queryKey: ["me", "plan", track ?? "", minutes],
    queryFn: () => api.plan(track, minutes),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function usePlanItemAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "skip" | "replace" | "reviewed" }) => api.planItemAction(id, action),
    onSettled: () => void qc.invalidateQueries({ queryKey: ["me", "plan"] }),
  });
}

export function useTargets() {
  return useQuery({ queryKey: ["me", "targets"], queryFn: api.targets });
}

export function useTarget(id: string) {
  return useQuery({ queryKey: ["me", "target", id], queryFn: () => api.target(id) });
}

/** Every target edit returns the full, fresh target; write it into the cache. */
export function useTargetMutation<V>(fn: (vars: V) => Promise<Target>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (t) => {
      qc.setQueryData(["me", "target", t.id], t);
      void qc.invalidateQueries({ queryKey: ["me", "targets"] });
    },
  });
}

export function useInterviewReview(id: string, enabled = true) {
  return useQuery({ queryKey: ["me", "interview-review", id], queryFn: () => api.interviewReview(id), enabled });
}

export function useComparison(id: string, index: number) {
  return useQuery({ queryKey: ["me", "comparison", id, index], queryFn: () => api.comparison(id, index) });
}

export function useRetryQuestion(id: string, index: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { answer: string; source: AnswerSource }) => api.retryQuestion(id, index, body),
    onSuccess: (c) => {
      qc.setQueryData(["me", "comparison", id, index], c);
      void qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useReviewQueue(enabled = true) {
  return useQuery({ queryKey: ["me", "review-queue"], queryFn: api.reviewQueue, enabled });
}

export function useReviewQueueMutation<V>(fn: (vars: V) => Promise<ReviewQueue>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (q) => {
      qc.setQueryData(["me", "review-queue"], q);
      void qc.invalidateQueries({ queryKey: ["me", "interview-review"] });
    },
  });
}

// --- explorer, bookmarks, collections -----------------------------------------------------------

/** The question explorer. Signed in: your status, personal filters and sorts; signed out: the public list. */
export function useExplore(track: string, filters: ExploreFilters, signedIn: boolean) {
  return useQuery({
    queryKey: signedIn ? ["me", "explore", track, filters] : ["careers", track, "explore", filters],
    queryFn: ({ signal }) => (signedIn ? api.myExplore(track, filters, signal) : api.explore(track, filters, signal)),
    placeholderData: keepPreviousData,
    enabled: Boolean(track),
  });
}

export function useBookmarks(enabled = true) {
  return useQuery({ queryKey: ["me", "bookmarks"], queryFn: api.bookmarks, enabled });
}

const sameRef = (a: SavedItemRef, b: { item_type: string; track?: string; ref_id: string }) =>
  a.item_type === b.item_type && (a.track ?? "") === (b.track ?? "") && a.ref_id === b.ref_id;

/**
 * Bookmark or un-bookmark with an optimistic update: the star flips at once and flips back (with
 * the error kept on the mutation) if the server refuses, so nothing claims a save that didn't happen.
 */
export function useToggleBookmark() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, on }: { ref: SavedItemRef; on: boolean }) => (on ? api.addBookmark(ref) : api.removeBookmark(ref)),
    onMutate: async ({ ref, on }) => {
      await qc.cancelQueries({ queryKey: ["me", "explore"] });
      await qc.cancelQueries({ queryKey: ["me", "bookmarks"] });
      const explore = qc.getQueriesData<MyExploreResult>({ queryKey: ["me", "explore"] });
      const marks = qc.getQueryData<Bookmark[]>(["me", "bookmarks"]);
      for (const [key, data] of explore) {
        if (!data || ref.item_type !== "question" || data.track !== ref.track) continue;
        const prev = data.status[ref.ref_id] ?? { best_score: null, attempts: 0, last_practiced_at: null, bookmarked: false, collection_ids: [] };
        qc.setQueryData<MyExploreResult>(key, { ...data, status: { ...data.status, [ref.ref_id]: { ...prev, bookmarked: on } } });
      }
      if (marks) {
        qc.setQueryData<Bookmark[]>(["me", "bookmarks"], on
          ? [{ item_type: ref.item_type, track: ref.track ?? "", ref_id: ref.ref_id, title: "", href: null, available: true, created_at: new Date().toISOString() }, ...marks]
          : marks.filter((b) => !sameRef(ref, b)));
      }
      return { explore, marks };
    },
    onError: (_error, _vars, context) => {
      for (const [key, data] of context?.explore ?? []) qc.setQueryData(key, data);
      if (context?.marks) qc.setQueryData(["me", "bookmarks"], context.marks);
    },
    onSuccess: (marks) => qc.setQueryData(["me", "bookmarks"], marks),
    onSettled: () => void qc.invalidateQueries({ queryKey: ["me", "explore"] }),
  });
}

export function useIsBookmarked(ref: SavedItemRef, enabled: boolean): boolean | undefined {
  const marks = useBookmarks(enabled);
  return marks.data ? marks.data.some((b) => sameRef(ref, b)) : undefined;
}

/** Your collections; with `ref`, each says whether it already holds that item. */
export function useCollections(enabled = true, ref?: SavedItemRef) {
  return useQuery({
    queryKey: ref ? ["me", "collections", ref.item_type, ref.track ?? "", ref.ref_id] : ["me", "collections"],
    queryFn: () => api.collections(ref),
    enabled,
  });
}

export function useCollection(id: string, enabled = true) {
  return useQuery({ queryKey: ["me", "collection", id], queryFn: () => api.collection(id), enabled });
}

/** Every collection edit returns the fresh collection; write it into the cache. */
export function useCollectionMutation<V>(fn: (vars: V) => Promise<Collection>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (c) => {
      qc.setQueryData(["me", "collection", c.id], c);
      void qc.invalidateQueries({ queryKey: ["me", "collections"] });
      void qc.invalidateQueries({ queryKey: ["me", "explore"] });
    },
  });
}

export function useDeleteCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteCollection(id),
    onSuccess: (_v, id) => {
      qc.removeQueries({ queryKey: ["me", "collection", id] });
      void qc.invalidateQueries({ queryKey: ["me", "collections"] });
      void qc.invalidateQueries({ queryKey: ["me", "explore"] });
    },
  });
}
