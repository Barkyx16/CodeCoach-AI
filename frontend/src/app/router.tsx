/* eslint-disable react-refresh/only-export-components -- route config module, not a component file */
import { lazy, Suspense } from "react";
import { createBrowserRouter, Outlet, type RouteObject } from "react-router-dom";

import { RequireAuth } from "@/auth/RequireAuth";
import { LoadingState } from "@/components/States";
import { LoginPage, RegisterPage } from "@/features/auth/AuthPages";
import { ForgotPasswordPage, ResetPasswordPage } from "@/features/auth/PasswordResetPages";
import { VerifyEmailPage } from "@/features/auth/VerifyEmailPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { GoalsPage } from "@/features/plan/GoalsPage";
import { PlanPage } from "@/features/plan/PlanPage";
import { RetryPage } from "@/features/review/RetryPage";
import { ReviewQueuePage } from "@/features/review/ReviewQueuePage";
import { CoachingDetailPage, SubmissionDetailPage } from "@/features/history/ActivityDetailPages";
import { HistoryPage } from "@/features/history/HistoryPage";
import { InterviewsPage } from "@/features/interview/InterviewsPage";
import { QuestionInterviewPage } from "@/features/interview/QuestionInterviewPage";
import { LandingPage } from "@/features/landing/LandingPage";
import { PracticePage } from "@/features/careers/PracticePage";
import { QuestionPage } from "@/features/careers/QuestionPage";
import { LearnPage } from "@/features/learn/LearnPage";
import { UnitPage } from "@/features/learn/UnitPage";
import { NotePage } from "@/features/notes/NotePage";
import { NotesPage } from "@/features/notes/NotesPage";
import { OfflinePage } from "@/features/offline/OfflinePage";
import { AdminGuard } from "@/features/admin/AdminGuard";
import { HelpPage } from "@/features/onboarding/HelpPage";
import { SupportReportPage } from "@/features/support/SupportReportPage";
import { WelcomePage } from "@/features/onboarding/WelcomePage";

import { Layout } from "./Layout";
import { NotFoundPage } from "./NotFoundPage";
import { RouteError } from "./RouteError";

// The workspace pulls in the Monaco editor (~MBs); load it only when a problem is opened.
const WorkspacePage = lazy(() => import("@/features/workspace/WorkspacePage"));
const InterviewSessionPage = lazy(() => import("@/features/interview/InterviewSessionPage"));
const AnalyticsPage = lazy(() => import("@/features/analytics/AnalyticsPage"));
// Account, preparation, editing, sharing and admin pages load when first opened, so the first
// download stays small. Pages that must work offline (lessons, questions, notes, Saved for offline,
// history's offline notice) stay in it: a lazy page is only cached once it has been opened online.
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const RestorePage = lazy(() => import("@/features/settings/RestorePage").then((m) => ({ default: m.RestorePage })));
const YourDataPage = lazy(() => import("@/features/privacy/YourDataPage").then((m) => ({ default: m.YourDataPage })));
const WorkspaceSearchPage = lazy(() => import("@/features/search/WorkspaceSearchPage"));
const ShareComposerPage = lazy(() => import("@/features/sharing/ShareComposerPage").then((m) => ({ default: m.ShareComposerPage })));
const ShareDetailPage = lazy(() => import("@/features/sharing/ShareDetailPage").then((m) => ({ default: m.ShareDetailPage })));
const SharedPage = lazy(() => import("@/features/sharing/SharedPage").then((m) => ({ default: m.SharedPage })));
const DemoPage = lazy(() => import("@/features/demo/DemoPage").then((m) => ({ default: m.DemoPage })));
const SharesPage = lazy(() => import("@/features/sharing/SharesPage").then((m) => ({ default: m.SharesPage })));
const AdminReportPage = lazy(() => import("@/features/admin/AdminReportPage").then((m) => ({ default: m.AdminReportPage })));
const AdminReportsPage = lazy(() => import("@/features/admin/AdminReportsPage").then((m) => ({ default: m.AdminReportsPage })));
const AdminTracePage = lazy(() => import("@/features/admin/AdminTracePage").then((m) => ({ default: m.AdminTracePage })));
const MyReportsPage = lazy(() => import("@/features/content/MyReportsPage").then((m) => ({ default: m.MyReportsPage })));
const CollectionPage = lazy(() => import("@/features/saved/CollectionPage").then((m) => ({ default: m.CollectionPage })));
const QueuePage = lazy(() => import("@/features/saved/QueuePage").then((m) => ({ default: m.QueuePage })));
const SavedPage = lazy(() => import("@/features/saved/SavedPage").then((m) => ({ default: m.SavedPage })));
const AttemptPage = lazy(() => import("@/features/scenarios/AttemptPage").then((m) => ({ default: m.AttemptPage })));
const ScenarioBriefing = lazy(() => import("@/features/scenarios/ScenariosPage").then((m) => ({ default: m.ScenarioBriefing })));
const ScenariosPage = lazy(() => import("@/features/scenarios/ScenariosPage").then((m) => ({ default: m.ScenariosPage })));
const StoriesPage = lazy(() => import("@/features/stories/StoriesPage").then((m) => ({ default: m.StoriesPage })));
const StoryEditorPage = lazy(() => import("@/features/stories/StoryEditorPage").then((m) => ({ default: m.StoryEditorPage })));
const ApplicationPage = lazy(() => import("@/features/applications/ApplicationPage").then((m) => ({ default: m.ApplicationPage })));
const ApplicationsPage = lazy(() => import("@/features/applications/ApplicationsPage").then((m) => ({ default: m.ApplicationsPage })));
const SchedulePage = lazy(() => import("@/features/schedule/SchedulePage").then((m) => ({ default: m.SchedulePage })));
const DrillPage = lazy(() => import("@/features/drills/DrillPage").then((m) => ({ default: m.DrillPage })));
const DrillsPage = lazy(() => import("@/features/drills/DrillsPage").then((m) => ({ default: m.DrillsPage })));
const ReflectionPage = lazy(() => import("@/features/reflections/ReflectionPage").then((m) => ({ default: m.ReflectionPage })));
const ReflectionsPage = lazy(() => import("@/features/reflections/ReflectionsPage").then((m) => ({ default: m.ReflectionsPage })));
const OfferCompareList = lazy(() => import("@/features/offerCompare/OfferCompareList").then((m) => ({ default: m.OfferCompareList })));
const KitTemplatesPage = lazy(() => import("@/features/kit/KitTemplatesPage").then((m) => ({ default: m.KitTemplatesPage })));
const OfferComparePage = lazy(() => import("@/features/offerCompare/OfferComparePage").then((m) => ({ default: m.OfferComparePage })));
const OfferList = lazy(() => import("@/features/offers/OfferList").then((m) => ({ default: m.OfferList })));
const OfferStartPage = lazy(() => import("@/features/offers/OfferStartPage").then((m) => ({ default: m.OfferStartPage })));
const RehearsalPage = lazy(() => import("@/features/offers/RehearsalPage").then((m) => ({ default: m.RehearsalPage })));
const SampleLessonList = lazy(() => import("@/features/sampleLessons/SampleLessonList").then((m) => ({ default: m.SampleLessonList })));
const CompareSamplesPage = lazy(() => import("@/features/sampleLessons/CompareSamplesPage").then((m) => ({ default: m.CompareSamplesPage })));
const WorkSampleList = lazy(() => import("@/features/workSamples/WorkSampleList").then((m) => ({ default: m.WorkSampleList })));
const WorkSamplePage = lazy(() => import("@/features/workSamples/WorkSamplePage").then((m) => ({ default: m.WorkSamplePage })));
const TestDesignPage = lazy(() => import("@/features/testDesign/TestDesignPage").then((m) => ({ default: m.TestDesignPage })));
const ReviewPage = lazy(() => import("@/features/codeReview/ReviewPage").then((m) => ({ default: m.ReviewPage })));
const ReviewAttemptPage = lazy(() => import("@/features/codeReview/ReviewAttemptPage").then((m) => ({ default: m.ReviewAttemptPage })));
const WhiteboardEditorPage = lazy(() => import("@/features/whiteboard/WhiteboardEditor").then((m) => ({ default: m.WhiteboardEditorPage })));
const WhiteboardPage = lazy(() => import("@/features/whiteboard/WhiteboardPage").then((m) => ({ default: m.WhiteboardPage })));
const KitPage = lazy(() => import("@/features/kit/KitPage").then((m) => ({ default: m.KitPage })));
const TargetsPage = lazy(() => import("@/features/targets/TargetsPage").then((m) => ({ default: m.TargetsPage })));
const TargetWorkspace = lazy(() => import("@/features/targets/TargetWorkspace").then((m) => ({ default: m.TargetWorkspace })));

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [{
    // One boundary inside the layout: a lazy page shows a loading state, and a page that fails
    // (including code that couldn't be downloaded) shows RouteError with the header still there.
    element: <Suspense fallback={<LoadingState />}><Outlet /></Suspense>,
    errorElement: <RouteError />,
    children: [
      { path: "/", element: <LandingPage /> },
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
      { path: "/forgot-password", element: <ForgotPasswordPage /> },
      { path: "/reset-password", element: <ResetPasswordPage /> },
      { path: "/verify-email", element: <VerifyEmailPage /> },
      { path: "/problems", element: <PracticePage /> },
      { path: "/careers/:track/questions/:id", element: <QuestionPage /> },
      {
        path: "/problems/:slug",
        element: (
          <Suspense fallback={<LoadingState label="Loading workspace…" />}>
            <WorkspacePage />
          </Suspense>
        ),
      },
      { path: "/interviews", element: <RequireAuth><InterviewsPage /></RequireAuth> },
      { path: "/interviews/questions", element: <RequireAuth><QuestionInterviewPage /></RequireAuth> },
      {
        path: "/interviews/:id",
        element: (
          <RequireAuth>
            <Suspense fallback={<LoadingState label="Loading interview…" />}>
              <InterviewSessionPage />
            </Suspense>
          </RequireAuth>
        ),
      },
      { path: "/dashboard", element: <RequireAuth><DashboardPage /></RequireAuth> },
      { path: "/plan", element: <RequireAuth><PlanPage /></RequireAuth> },
      { path: "/reviews", element: <RequireAuth><ReviewQueuePage /></RequireAuth> },
      { path: "/interviews/:id/retry/:index", element: <RequireAuth><RetryPage /></RequireAuth> },
      { path: "/targets", element: <RequireAuth><TargetsPage /></RequireAuth> },
      { path: "/targets/:id", element: <RequireAuth><TargetWorkspace /></RequireAuth> },
      { path: "/plan/goals", element: <RequireAuth><GoalsPage /></RequireAuth> },
      { path: "/analytics", element: <RequireAuth><Suspense fallback={<LoadingState label="Loading analytics…" />}><AnalyticsPage /></Suspense></RequireAuth> },
      { path: "/history", element: <RequireAuth><HistoryPage /></RequireAuth> },
      { path: "/learn", element: <LearnPage /> },
      { path: "/learn/:unitId", element: <UnitPage /> },
      { path: "/scenarios", element: <ScenariosPage /> },
      { path: "/scenarios/:id", element: <ScenarioBriefing /> },
      { path: "/scenarios/attempts/:attemptId", element: <RequireAuth><AttemptPage /></RequireAuth> },
      { path: "/notes", element: <RequireAuth><NotesPage /></RequireAuth> },
      { path: "/notes/:id", element: <RequireAuth><NotePage /></RequireAuth> },
      { path: "/share/new", element: <RequireAuth><ShareComposerPage /></RequireAuth> },
      { path: "/shares", element: <RequireAuth><SharesPage /></RequireAuth> },
      { path: "/shares/:id", element: <RequireAuth><ShareDetailPage /></RequireAuth> },
      // Public: anyone holding a share link (its secret is in the #fragment).
      { path: "/shared", element: <SharedPage /> },
      { path: "/offline", element: <OfflinePage /> },
      { path: "/help", element: <HelpPage /> },
      // Public: the report works signed out, offline and while the server is down.
      { path: "/help/report", element: <SupportReportPage /> },
      // Public: the portfolio demo's entry (it says so when the server isn't a demo server).
      { path: "/demo", element: <Suspense fallback={<LoadingState label="Loading the demo…" />}><DemoPage /></Suspense> },
      { path: "/stories", element: <RequireAuth><StoriesPage /></RequireAuth> },
      { path: "/applications", element: <RequireAuth><ApplicationsPage /></RequireAuth> },
      { path: "/schedule", element: <RequireAuth><SchedulePage /></RequireAuth> },
      { path: "/whiteboard", element: <RequireAuth><WhiteboardPage /></RequireAuth> },
      { path: "/drills", element: <RequireAuth><DrillsPage /></RequireAuth> },
      { path: "/settings/restore", element: <RequireAuth><RestorePage /></RequireAuth> },
      { path: "/settings/data", element: <RequireAuth><YourDataPage /></RequireAuth> },
      { path: "/search", element: <RequireAuth><WorkspaceSearchPage /></RequireAuth> },
      { path: "/reflections", element: <RequireAuth><ReflectionsPage /></RequireAuth> },
      { path: "/applications/:id/events/:eventId/reflection", element: <RequireAuth><ReflectionPage /></RequireAuth> },
      { path: "/drills/:id", element: <RequireAuth><DrillPage /></RequireAuth> },
      { path: "/whiteboard/:promptId", element: <RequireAuth><WhiteboardEditorPage /></RequireAuth> },
      { path: "/code-reviews/attempts/:attemptId", element: <RequireAuth><ReviewAttemptPage /></RequireAuth> },
      { path: "/code-reviews/:slug", element: <RequireAuth><ReviewPage /></RequireAuth> },
      { path: "/test-design/:slug", element: <RequireAuth><TestDesignPage /></RequireAuth> },
      { path: "/work-samples", element: <RequireAuth><WorkSampleList /></RequireAuth> },
      { path: "/work-samples/:briefId", element: <RequireAuth><WorkSamplePage /></RequireAuth> },
      { path: "/offers/compare", element: <RequireAuth><OfferCompareList /></RequireAuth> },
      { path: "/kit-templates", element: <RequireAuth><KitTemplatesPage /></RequireAuth> },
      { path: "/offers/compare/:comparisonId", element: <RequireAuth><OfferComparePage /></RequireAuth> },
      { path: "/offers", element: <RequireAuth><OfferList /></RequireAuth> },
      { path: "/offers/rehearsals/:rehearsalId", element: <RequireAuth><RehearsalPage /></RequireAuth> },
      { path: "/offers/:caseId", element: <RequireAuth><OfferStartPage /></RequireAuth> },
      { path: "/compare", element: <RequireAuth><SampleLessonList /></RequireAuth> },
      { path: "/compare/:lessonId", element: <RequireAuth><CompareSamplesPage /></RequireAuth> },
      { path: "/applications/:id", element: <RequireAuth><ApplicationPage /></RequireAuth> },
      { path: "/applications/:id/events/:eventId/kit", element: <RequireAuth><KitPage /></RequireAuth> },
      { path: "/stories/new", element: <RequireAuth><StoryEditorPage /></RequireAuth> },
      { path: "/stories/:id", element: <RequireAuth><StoryEditorPage /></RequireAuth> },
      { path: "/welcome", element: <RequireAuth><WelcomePage /></RequireAuth> },
      { path: "/reports", element: <RequireAuth><MyReportsPage /></RequireAuth> },
      { path: "/admin/reports", element: <RequireAuth><AdminGuard><AdminReportsPage /></AdminGuard></RequireAuth> },
      { path: "/admin/traces", element: <RequireAuth><AdminGuard><AdminTracePage /></AdminGuard></RequireAuth> },
      { path: "/admin/traces/:id", element: <RequireAuth><AdminGuard><AdminTracePage /></AdminGuard></RequireAuth> },
      { path: "/admin/reports/:id", element: <RequireAuth><AdminGuard><AdminReportPage /></AdminGuard></RequireAuth> },
      { path: "/saved", element: <RequireAuth><SavedPage /></RequireAuth> },
      { path: "/saved/collections/:id", element: <RequireAuth><CollectionPage /></RequireAuth> },
      { path: "/saved/collections/:id/practice", element: <RequireAuth><QueuePage /></RequireAuth> },
      { path: "/history/submissions/:id", element: <RequireAuth><SubmissionDetailPage /></RequireAuth> },
      { path: "/history/coaching/:id", element: <RequireAuth><CoachingDetailPage /></RequireAuth> },
      { path: "/settings", element: <RequireAuth><SettingsPage /></RequireAuth> },
      { path: "*", element: <NotFoundPage /> },
    ],
    }],
  },
];

export const createRouter = () => createBrowserRouter(routes);
