/* eslint-disable react-refresh/only-export-components -- route config module, not a component file */
import { lazy, Suspense } from "react";
import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { RequireAuth } from "@/auth/RequireAuth";
import { LoadingState } from "@/components/States";
import { LoginPage, RegisterPage } from "@/features/auth/AuthPages";
import { ForgotPasswordPage, ResetPasswordPage } from "@/features/auth/PasswordResetPages";
import { VerifyEmailPage } from "@/features/auth/VerifyEmailPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { CoachingDetailPage, SubmissionDetailPage } from "@/features/history/ActivityDetailPages";
import { HistoryPage } from "@/features/history/HistoryPage";
import { InterviewsPage } from "@/features/interview/InterviewsPage";
import { QuestionInterviewPage } from "@/features/interview/QuestionInterviewPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { LandingPage } from "@/features/landing/LandingPage";
import { PracticePage } from "@/features/careers/PracticePage";
import { QuestionPage } from "@/features/careers/QuestionPage";

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
      { path: "/analytics", element: <RequireAuth><Suspense fallback={<LoadingState label="Loading analytics…" />}><AnalyticsPage /></Suspense></RequireAuth> },
      { path: "/history", element: <RequireAuth><HistoryPage /></RequireAuth> },
      { path: "/history/submissions/:id", element: <RequireAuth><SubmissionDetailPage /></RequireAuth> },
      { path: "/history/coaching/:id", element: <RequireAuth><CoachingDetailPage /></RequireAuth> },
      { path: "/settings", element: <RequireAuth><SettingsPage /></RequireAuth> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const createRouter = () => createBrowserRouter(routes);
