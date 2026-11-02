import { render } from "@testing-library/react";
import { StrictMode } from "react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { AppProviders } from "@/app/providers";
import { makeQueryClient } from "@/app/queryClient";
import { routes } from "@/app/router";
import { cookieJar } from "./server";

/** Render the real app (real routes, providers and API client) at a URL. */
export function renderApp(path: string, { signedIn = false, strict = false }: { signedIn?: boolean; strict?: boolean } = {}) {
  // A signed-in visitor is one whose browser holds a refresh cookie: the app restores the
  // session from it on load, exactly as after a page reload.
  cookieJar.hasSession = signedIn;
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const queryClient = makeQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false } });
  const app = (
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  );
  // strict: render like main.tsx does, where React runs effects twice in development.
  const utils = render(strict ? <StrictMode>{app}</StrictMode> : app);

  return { ...utils, router, queryClient, user: userEvent.setup() };
}
