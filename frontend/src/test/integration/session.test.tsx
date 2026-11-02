import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { LEGACY_SESSION_KEY } from "@/auth/session";

import { progress, tokenResponse } from "../fixtures";
import { renderApp } from "../render";
import { API, cookieJar, server } from "../server";

const expired = { error: { code: "invalid_token", message: "Token expired", request_id: "r", details: null } };

describe("Cookie-backed sessions", () => {
  it("restores the session on load from the refresh cookie, without redirecting to sign-in", async () => {
    const { router } = renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: /progress/i })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/dashboard");
  });

  it("restores with one refresh even when React runs startup effects twice (StrictMode)", async () => {
    // Two refreshes with one cookie would rotate it and then hit a race: a real reload bug.
    let refreshes = 0;
    server.use(http.post(`${API}/api/v1/auth/refresh`, () => {
      refreshes += 1;
      return refreshes === 1
        ? HttpResponse.json(tokenResponse())
        : HttpResponse.json({ error: { code: "refresh_race", message: "retry", request_id: "r", details: null } }, { status: 401 });
    }));
    const { router } = renderApp("/dashboard", { signedIn: true, strict: true });
    expect(await screen.findByRole("heading", { level: 1, name: /progress/i })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/dashboard");
    expect(refreshes).toBe(1);
  });

  it("sends a signed-out visitor to sign in once the cookie check says there's no session", async () => {
    const { router } = renderApp("/dashboard");
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });

  it("never writes the access token to browser storage", async () => {
    const { user } = renderApp("/login");
    await user.type(await screen.findByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("button", { name: "Sign out" });
    const stored = Object.values({ ...window.localStorage, ...window.sessionStorage }).join(" ");
    expect(stored).not.toContain("test-token");
  });

  it("refreshes an expired access token and retries the request transparently", async () => {
    const seen: (string | null)[] = [];
    let refreshes = 0;
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => {
        refreshes += 1;
        // First call restores the session; later calls rotate to a new access token.
        return HttpResponse.json(tokenResponse({ access_token: refreshes === 1 ? "old-token" : "fresh-token" }));
      }),
      http.get(`${API}/api/v1/me/progress`, ({ request }) => {
        const auth = request.headers.get("Authorization");
        seen.push(auth);
        return auth === "Bearer fresh-token" ? HttpResponse.json(progress) : HttpResponse.json(expired, { status: 401 });
      }),
    );
    renderApp("/dashboard", { signedIn: true });
    const summary = await screen.findByRole("region", { name: "Summary" }); // the dashboard loaded after all
    expect(summary).toHaveTextContent("Solved");
    expect(seen).toContain("Bearer old-token");
    expect(seen.at(-1)).toBe("Bearer fresh-token");
    expect(screen.queryByText(/Your session ended/)).not.toBeInTheDocument();
  });

  it("signs out with an explanation when the session can't be refreshed", async () => {
    server.use(http.get(`${API}/api/v1/me/progress`, () => {
      cookieJar.hasSession = false; // e.g. signed out on another device
      return HttpResponse.json(expired, { status: 401 });
    }));
    const { router } = renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByText(/Your session ended\. Please sign in again\./)).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });

  it("deletes the token that older versions kept in localStorage", async () => {
    window.localStorage.setItem(LEGACY_SESSION_KEY, JSON.stringify({ token: "leaked-token" }));
    renderApp("/");
    await waitFor(() => expect(window.localStorage.getItem(LEGACY_SESSION_KEY)).toBeNull());
  });
});
