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

export type Career = S["CareerSummary"];
export type QuestionSummary = S["QuestionSummary"];
export type QuestionDetail = S["QuestionDetail"];
export type InterviewAnswer = S["AnswerOut"];
export type TrackProgress = S["TrackProgress"];
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
/** `format` defaults to "mixed" on the server. */
export type InterviewStart = Omit<S["InterviewStart"], "format"> & { format?: S["InterviewStart"]["format"] };
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
export type AnswerSource = S["RoundAnswer"]["source"];
export type Engagement = S["Engagement"];
export type RoundQuestion = S["RoundQuestion"];
export type InterviewTurn = S["TurnOut"];
export type ActivityItem = S["ActivityItem"];
export type ActivityType = S["ActivityItem"]["type"];
export type ActivityStatus = S["ActivityItem"]["status"];
export type ActivityFacets = S["ActivityFacets"];
export type CareerAnalytics = S["CareerAnalytics"];
export type ResumeOut = S["ResumeOut"];
export type Goals = S["GoalsOut"];
export type GoalsInput = S["GoalsIn"];
export type Plan = S["PlanOut"];
export type PlanItem = S["PlanItemOut"];
export type RoundStart = S["RoundStart"];
export type TargetSummary = S["TargetSummary"];
export type Target = S["TargetOut"];
export type TargetInput = S["TargetIn"];
export type TargetPatch = S["TargetPatch"];
export type Requirement = S["RequirementOut"];
export type RequirementInput = S["RequirementIn"];
export type RequirementPatch = S["RequirementPatch"];
export type ExperienceInput = S["ExperienceIn"];
export type Experience = S["ExperienceOut"];
export type InterviewReview = S["InterviewReview"];
export type ReviewEntry = S["ReviewItem"];
export type Comparison = S["Comparison"];
export type ReviewQueue = S["ReviewQueue"];
export type ReviewQueueItem = S["ReviewQueueItem"];

export type ExploreResult = S["ExploreResult"];
export type MyExploreResult = S["MyExploreResult"];
export type ExploreItem = S["ExploreItem"];
export type ExploreSort = S["MyExploreResult"]["sorts"][number];
export type ItemStatus = S["ItemStatus"];
export type Facet = S["Facet"];
export type Bookmark = S["BookmarkOut"];
export type SavedItemRef = S["CollectionItemIn"];
export type CollectionSummary = S["CollectionSummary"];
export type Collection = S["CollectionOut"];
export type CollectionItem = S["CollectionItemOut"];

export type LearnCatalog = S["LearnCatalog"];
export type LearnUnitSummary = S["UnitSummary"];
export type LearnUnit = S["UnitOut"];
export type UnitLink = S["UnitLink"];
export type UnitProgress = S["UnitProgress"];
export type CheckResult = S["CheckResult"];

export type Note = S["NoteOut"];
export type NoteSummary = S["NoteSummary"];
export type NotePage = S["NotePage"];
export type NoteInput = S["NoteIn"];
export type NotePatch = S["NotePatch"];
export type NoteSource = S["SourceIn"];
export type KeyPoints = S["KeyPoints"];

export type ContentMeta = S["ContentMeta"];
export type ContentKind = S["ContentMeta"]["content_type"];
export type ReportInput = S["ReportIn"];
export type ReportCategory = S["ReportIn"]["category"];
export type MyReport = S["MyReport"];
export type AdminReport = S["AdminReport"];
export type AdminReportDetail = S["AdminReportDetail"];
export type ReportGroup = S["ReportGroup"];
export type ReportStatusValue = S["MyReport"]["status"];
export type QuestionVersion = S["QuestionVersionOut"];
export type CorrectionInput = S["CorrectionIn"];

export type ShareSelection = S["ShareSelection"];
export type ShareCreate = S["ShareCreate"];
export type SharePreview = S["SharePreview"];
export type SharedView = S["SharedView"];
export type SharedSentence = S["SharedSentence"];
export type ShareCreated = S["ShareCreated"];
export type ShareSummary = S["ShareSummary"];
export type ShareDetail = S["ShareDetail"];
export type ShareFeedback = S["FeedbackOut"];
export type FeedbackInput = S["FeedbackIn"];
export type FeedbackReceipt = S["FeedbackReceipt"];
export type RecipientView = S["RecipientView"];

export type ScenarioCatalog = S["ScenarioCatalog"];
export type ScenarioSummary = S["ScenarioSummary"];
export type ScenarioDetail = S["ScenarioDetail"];
export type ScenarioAttempt = S["ScenarioAttemptOut"];
export type ScenarioAttemptSummary = S["ScenarioAttemptSummary"];
export type ScenarioStep = S["StepOut"];

export type InterviewFormat = S["FormatOption"];
export type InterviewFormatId = S["FormatOption"]["id"];
export type RoundFormat = S["RoundFormatOut"];

export type Onboarding = S["OnboardingOut"];
export type OnboardingUpdate = S["OnboardingUpdate"];
export type TourKind = S["OnboardingOut"]["format"];
export type StarterActivity = S["StarterActivity"];

export type StorySummary = S["StorySummary"];
export type Story = S["StoryOut"];
export type StoryCreate = S["StoryCreate"];
export type StoryUpdate = S["StoryUpdate"];
export type StoryRevision = S["StoryRevisionOut"];
export type StoryAssist = S["StoryAssistOut"];
export type StoryAssistAction = S["StoryAssistIn"]["action"];
export type Competency = S["StoryCreate"]["competencies"] extends (infer C)[] | null | undefined ? C : never;
export type StoryContext = NonNullable<S["StoryCreate"]["context"]>;
export type StorySection = S["StoryProposal"]["field"];

export type ApplicationSummary = S["ApplicationSummary"];
export type Application = S["ApplicationOut"];
export type ApplicationEvent = S["ApplicationEventOut"];
export type ApplicationStage = S["ApplicationOut"]["stage"];
export type EventKind = S["ApplicationEventOut"]["kind"];
export type ApplicationCreate = S["ApplicationCreate"];
export type ApplicationUpdate = S["ApplicationUpdate"];
export type ApplicationEventIn = S["ApplicationEventIn"];

export type ScheduleEntry = S["EntryOut"];
export type ScheduleSettings = S["ScheduleSettingsOut"];
export type ScheduleKind = S["EntryOut"]["kind"];
export type ScheduleEntryIn = S["EntryIn"];
export type ScheduleMove = S["EntryMove"];
export type Schedulable = S["SchedulableOut"];

export type Kit = S["KitOut"];
export type KitQuestion = S["AskQuestion"];
export type KitChecklistItem = S["ChecklistItem"];
export type KitUpdate = S["KitUpdate"];

export type WhiteboardDiagram = S["WhiteboardDiagram"];
export type WhiteboardPrompt = S["WhiteboardPrompt"];
export type WhiteboardPromptList = S["WhiteboardPromptList"];
export type WhiteboardDraft = S["WhiteboardDraftOut"];
export type WhiteboardDraftIn = S["WhiteboardDraftIn"];
export type WhiteboardAttemptIn = S["WhiteboardAttemptIn"];
export type WhiteboardAttempt = S["WhiteboardAttemptOut"];
export type WhiteboardAttemptSummary = S["WhiteboardAttemptSummary"];

export type Criteria = S["CriteriaOut"];
export type AnswerReview = S["AnswerReviewOut"];
export type SelfReviewIn = S["SelfReviewIn"];
export type SelfRating = NonNullable<S["AnswerPerspective"]["yours"]>;
export type AnswerFlagIn = S["FlagIn"];

export type Reflection = S["ReflectionOut"];
export type ReflectionIn = S["ReflectionIn"];
export type ReflectionAction = S["ReflectionActionOut"];
export type ReflectionSummary = S["ReflectionSummary"];
export type ReflectionOutcome = S["ReflectionOutcomeIn"]["outcome"];

export type Drill = S["DrillOut"];
export type DrillAttempt = S["DrillAttemptOut"];
export type DrillAttemptIn = S["DrillAttemptIn"];
