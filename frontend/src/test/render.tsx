import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { AppProviders } from "@/app/providers";
import { makeQueryClient } from "@/app/queryClient";
import { routes } from "@/app/router";
import { saveSession } from "@/auth/session";

import { tokenResponse } from "./fixtures";

/** Render the real app (real routes, providers and API client) at a URL. */
export function renderApp(path: string, { signedIn = false }: { signedIn?: boolean } = {}) {
  if (signedIn) {
    const t = tokenResponse();
    saveSession({ token: t.access_token, expiresAt: t.expires_at, user: t.user });
  }
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const queryClient = makeQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false } });
  const utils = render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { ...utils, router, queryClient, user: userEvent.setup() };
}
