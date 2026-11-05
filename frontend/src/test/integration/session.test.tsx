import { act, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { LEGACY_SESSION_KEY } from "@/auth/session";

import { progress, tokenResponse, user as ada } from "../fixtures";
import { renderApp } from "../render";
import { API, cookieJar, server } from "../server";

const expired = { error: { code: "invalid_token", message: "Token expired", request_id: "r", details: null } };

describe("Cookie-backed sessions", () => {
  it("restores the session on load from the refresh cookie, without redirecting to sign-in", async () => {
    const { router } = renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Your interview practice" })).toBeInTheDocument();
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
    expect(await screen.findByRole("heading", { level: 1, name: "Your interview practice" })).toBeInTheDocument();
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

  // A request belongs to the session it was sent in. If that session has ended (signed out) or
  // been replaced (someone else signed in) by the time its 401 comes back, the 401 is not this
  // session's: it must not refresh (which would sign a signed-out user back in, or retry one
  // account's request as another's), and it must not end the session that is open now.
  const staleIgnored = () => window.__ccDiag?.some((e) => e.kind === "auth" && e.event === "stale_401") ?? false;

  it("a request from before sign-out that comes back 401 never signs the user back in", async () => {
    window.__ccDiag = [];
    let release!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    let sent = false;
    let signedOut = false;
    let refreshesAfterSignOut = 0;
    server.use(
      http.get(`${API}/api/v1/me/progress`, async () => {
        sent = true;
        await held;
        return HttpResponse.json(expired, { status: 401 });
      }),
      // The sign-out request never reaches the server, so the refresh cookie is still valid there.
      http.post(`${API}/api/v1/auth/logout`, () => HttpResponse.error()),
      http.post(`${API}/api/v1/auth/refresh`, () => {
        if (signedOut) refreshesAfterSignOut += 1;
        return HttpResponse.json(tokenResponse());
      }),
    );
    const { user } = renderApp("/dashboard", { signedIn: true });
    await waitFor(() => expect(sent).toBe(true));
    signedOut = true;
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("link", { name: "Sign in" });
    release();
    await waitFor(() => expect(staleIgnored()).toBe(true));
    expect(refreshesAfterSignOut).toBe(0);
    expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
  });

  it("a request sent for one account is never retried for the account that signed in next", async () => {
    window.__ccDiag = [];
    const bea = { ...ada, id: "user-bea", email: "bea@example.com", display_name: "Bea" };
    let release!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    let sent = false;
    let switched = false;
    let refreshesAfterSwitch = 0;
    const authHeaders: (string | null)[] = [];
    server.use(
      http.get(`${API}/api/v1/me/progress`, async ({ request }) => {
        const auth = request.headers.get("Authorization");
        authHeaders.push(auth);
        if (auth !== "Bearer test-token") return HttpResponse.json(progress);
        sent = true;
        await held;
        return HttpResponse.json(expired, { status: 401 });
      }),
      http.post(`${API}/api/v1/auth/login`, () => {
        switched = true;
        cookieJar.hasSession = true;
        return HttpResponse.json(tokenResponse({ access_token: "bea-token", user: bea }));
      }),
      http.post(`${API}/api/v1/auth/refresh`, () => {
        if (switched) refreshesAfterSwitch += 1;
        return HttpResponse.json(switched ? tokenResponse({ access_token: "bea-token", user: bea }) : tokenResponse());
      }),
    );
    const { router, user } = renderApp("/dashboard", { signedIn: true });
    await waitFor(() => expect(sent).toBe(true)); // Ada's request is on its way
    await act(() => router.navigate("/login"));
    await user.type(await screen.findByLabelText("Email"), "bea@example.com");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("link", { name: "Bea, account settings" });
    // Bea's own dashboard asks for her progress; wait for that request before the snapshot, so any
    // request with her token after the release can only be Ada's being sent again (CI run 171 hit
    // this race: Bea's own request landed just after the snapshot).
    await waitFor(() => expect(authHeaders).toContain("Bearer bea-token"));
    const beforeRelease = authHeaders.length;
    release();
    await waitFor(() => expect(staleIgnored()).toBe(true));
    expect(refreshesAfterSwitch).toBe(0);
    // Ada's request was not sent again with Bea's token (Bea's own dashboard requests are hers).
    const retried = window.__ccDiag?.filter((e) => e.kind === "http" && e.path === "/api/v1/me/progress" && e.retry === true) ?? [];
    expect(retried).toEqual([]);
    expect(authHeaders.slice(beforeRelease)).not.toContain("Bearer bea-token");
    expect(screen.getByRole("link", { name: "Bea, account settings" })).toBeInTheDocument();
  });

  it("deletes the token that older versions kept in localStorage", async () => {
    window.localStorage.setItem(LEGACY_SESSION_KEY, JSON.stringify({ token: "leaked-token" }));
    renderApp("/");
    await waitFor(() => expect(window.localStorage.getItem(LEGACY_SESSION_KEY)).toBeNull());
  });
});
