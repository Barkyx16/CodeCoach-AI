/* eslint-disable react-refresh/only-export-components -- route config module, not a component file */
import { lazy, Suspense } from "react";
import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { RequireAuth } from "@/auth/RequireAuth";
import { LoadingState } from "@/components/States";
import { LoginPage, RegisterPage } from "@/features/auth/AuthPages";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { HistoryPage } from "@/features/history/HistoryPage";
import { LandingPage } from "@/features/landing/LandingPage";
import { ProblemListPage } from "@/features/problems/ProblemListPage";

import { Layout } from "./Layout";
import { NotFoundPage } from "./NotFoundPage";

// The workspace pulls in the Monaco editor (~MBs); load it only when a problem is opened.
const WorkspacePage = lazy(() => import("@/features/workspace/WorkspacePage"));

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: "/", element: <LandingPage /> },
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
      { path: "/problems", element: <ProblemListPage /> },
      {
        path: "/problems/:slug",
        element: (
          <Suspense fallback={<LoadingState label="Loading workspace…" />}>
            <WorkspacePage />
          </Suspense>
        ),
      },
      { path: "/dashboard", element: <RequireAuth><DashboardPage /></RequireAuth> },
      { path: "/history", element: <RequireAuth><HistoryPage /></RequireAuth> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const createRouter = () => createBrowserRouter(routes);
