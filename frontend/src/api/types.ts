/**
 * Friendly names for the generated OpenAPI types. `schema.d.ts` is generated from
 * docs/openapi.json (`npm run api:types`) and must never be edited by hand, so the frontend's
 * types can't drift from the backend contract.
 */
import type { components } from "./schema";

type S = components["schemas"];

export type ProblemSummary = S["ProblemSummary"];
export type ProblemDetail = S["ProblemDetail"];
export type Difficulty = S["Difficulty"];
export type TopicCount = S["TopicCount"];
export type DifficultyCounts = S["DifficultyCounts"];
export type PublicTestCase = S["PublicTestCase"];
export type Example = S["Example"];

export type TokenResponse = S["TokenResponse"];
export type User = S["UserOut"];
export type RegisterRequest = S["RegisterRequest"];
export type LoginRequest = S["LoginRequest"];

export type SubmissionCreate = S["SubmissionCreate"];
export type Submission = S["SubmissionDetail"];
export type SubmissionListItem = S["SubmissionListItem"];
export type SubmissionStatus = S["SubmissionStatus"];
export type SubmissionMode = S["SubmissionMode"];
export type Capabilities = S["Capabilities"];

export type HintRequest = S["HintRequest"];
export type HintResponse = S["HintResponse"];
export type ReviewRequest = S["ReviewRequest"];
export type ReviewResponse = S["ReviewResponse"];
export type CodeReview = S["CodeReview"];
export type ReviewIssue = S["ReviewIssue"];
export type ExplainFailureResponse = S["ExplainFailureResponse"];
export type FailureExplanation = S["FailureExplanation"];
export type AIUsage = S["AIUsage"];
export type AIHistoryItem = S["AIHistoryItem"];
export type AIHistoryAction = Exclude<S["AIAction"], "mock_interview">;

export type Progress = S["ProgressOut"];
export type Recommendation = S["Recommendation"];

export type Interview = S["InterviewOut"];
export type InterviewSummary = S["InterviewSummary"];
export type InterviewStart = S["InterviewStart"];
export type InterviewPhase = S["InterviewPhase"];
export type InterviewEvaluation = S["InterviewEvaluation"];
export type RubricScore = S["RubricScore"];

export type ErrorEnvelope = S["ErrorEnvelope"];

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type HintLevel = 1 | 2 | 3 | 4;
