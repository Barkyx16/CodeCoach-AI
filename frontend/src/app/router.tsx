/* eslint-disable react-refresh/only-export-components -- route config module, not a component file */
import { lazy, Suspense } from "react";
import { createBrowserRouter, type RouteObject } from "react-router-dom";

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
import { TargetsPage } from "@/features/targets/TargetsPage";
import { TargetWorkspace } from "@/features/targets/TargetWorkspace";
import { CoachingDetailPage, SubmissionDetailPage } from "@/features/history/ActivityDetailPages";
import { HistoryPage } from "@/features/history/HistoryPage";
import { InterviewsPage } from "@/features/interview/InterviewsPage";
import { QuestionInterviewPage } from "@/features/interview/QuestionInterviewPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { LandingPage } from "@/features/landing/LandingPage";
import { PracticePage } from "@/features/careers/PracticePage";
import { QuestionPage } from "@/features/careers/QuestionPage";
import { LearnPage } from "@/features/learn/LearnPage";
import { UnitPage } from "@/features/learn/UnitPage";
import { NotePage } from "@/features/notes/NotePage";
import { NotesPage } from "@/features/notes/NotesPage";
import { ShareComposerPage } from "@/features/sharing/ShareComposerPage";
import { ShareDetailPage } from "@/features/sharing/ShareDetailPage";
import { SharedPage } from "@/features/sharing/SharedPage";
import { SharesPage } from "@/features/sharing/SharesPage";
import { OfflinePage } from "@/features/offline/OfflinePage";
import { MyReportsPage } from "@/features/content/MyReportsPage";
import { AdminGuard } from "@/features/admin/AdminGuard";
import { AdminReportPage } from "@/features/admin/AdminReportPage";
import { AdminReportsPage } from "@/features/admin/AdminReportsPage";
import { CollectionPage } from "@/features/saved/CollectionPage";
import { AttemptPage } from "@/features/scenarios/AttemptPage";
import { ScenarioBriefing, ScenariosPage } from "@/features/scenarios/ScenariosPage";
import { QueuePage } from "@/features/saved/QueuePage";
import { SavedPage } from "@/features/saved/SavedPage";
import { HelpPage } from "@/features/onboarding/HelpPage";
import { WelcomePage } from "@/features/onboarding/WelcomePage";
import { StoriesPage } from "@/features/stories/StoriesPage";
import { ApplicationPage } from "@/features/applications/ApplicationPage";
import { ApplicationsPage } from "@/features/applications/ApplicationsPage";
import { StoryEditorPage } from "@/features/stories/StoryEditorPage";

import { Layout } from "./Layout";
import { NotFoundPage } from "./NotFoundPage";

// The workspace pulls in the Monaco editor (~MBs); load it only when a problem is opened.
const WorkspacePage = lazy(() => import("@/features/workspace/WorkspacePage"));
const InterviewSessionPage = lazy(() => import("@/features/interview/InterviewSessionPage"));
const AnalyticsPage = lazy(() => import("@/features/analytics/AnalyticsPage"));

export const routes: RouteObject[] = [
  {
    element: <Layout />,
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
      { path: "/stories", element: <RequireAuth><StoriesPage /></RequireAuth> },
      { path: "/applications", element: <RequireAuth><ApplicationsPage /></RequireAuth> },
      { path: "/applications/:id", element: <RequireAuth><ApplicationPage /></RequireAuth> },
      { path: "/stories/new", element: <RequireAuth><StoryEditorPage /></RequireAuth> },
      { path: "/stories/:id", element: <RequireAuth><StoryEditorPage /></RequireAuth> },
      { path: "/welcome", element: <RequireAuth><WelcomePage /></RequireAuth> },
      { path: "/reports", element: <RequireAuth><MyReportsPage /></RequireAuth> },
      { path: "/admin/reports", element: <RequireAuth><AdminGuard><AdminReportsPage /></AdminGuard></RequireAuth> },
      { path: "/admin/reports/:id", element: <RequireAuth><AdminGuard><AdminReportPage /></AdminGuard></RequireAuth> },
      { path: "/saved", element: <RequireAuth><SavedPage /></RequireAuth> },
      { path: "/saved/collections/:id", element: <RequireAuth><CollectionPage /></RequireAuth> },
      { path: "/saved/collections/:id/practice", element: <RequireAuth><QueuePage /></RequireAuth> },
      { path: "/history/submissions/:id", element: <RequireAuth><SubmissionDetailPage /></RequireAuth> },
      { path: "/history/coaching/:id", element: <RequireAuth><CoachingDetailPage /></RequireAuth> },
      { path: "/settings", element: <RequireAuth><SettingsPage /></RequireAuth> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const createRouter = () => createBrowserRouter(routes);
