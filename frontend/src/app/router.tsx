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
import { CollectionPage } from "@/features/saved/CollectionPage";
import { QueuePage } from "@/features/saved/QueuePage";
import { SavedPage } from "@/features/saved/SavedPage";

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
