import { act, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, cookieJar, server } from "../server";

// What one account's requests bring back belongs to that account. When someone else signs in on
// the same tab, nothing cached or still arriving for the previous account may be shown to them.
// Responses are held with promises and released in a chosen order: no timing sleeps.

const ada = { ...baseUser, career_track: "registered-nurse" };
const bea = { ...ada, id: "user-bea", email: "bea@example.com", display_name: "Bea" };
const QUESTION = "/careers/registered-nurse/questions/e-time-0";
const ANSWERS = `${API}/api/v1/careers/:track/questions/:id/answers`;

function held() {
  let release!: () => void;
  const promise = new Promise<void>((resolve) => { release = resolve; });
  return { promise, release };
}

function signInAsBea() {
  server.use(
    http.post(`${API}/api/v1/auth/login`, () => {
      cookieJar.hasSession = true;
      return HttpResponse.json(tokenResponse({ access_token: "bea-token", user: bea }));
    }),
  );
}

async function login(user: ReturnType<typeof renderApp>["user"], router: ReturnType<typeof renderApp>["router"]) {
  await act(() => router.navigate("/login"));
  await user.type(await screen.findByLabelText("Email"), "bea@example.com");
  await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByRole("link", { name: "Bea, account settings" });
}

beforeEach(() => {
  server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: ada }))));
});

describe("Session isolation", () => {
  it("one account's cached answers are never shown to the account that signs in next", async () => {
    const beas = held();
    server.use(
      http.get(ANSWERS, async ({ request }) => {
        if (request.headers.get("Authorization") === "Bearer bea-token") {
          await beas.promise; // Bea's own answers are still on their way
          return HttpResponse.json([]);
        }
        return HttpResponse.json([nurseAnswer]);
      }),
    );
    signInAsBea();
    const { user, router } = renderApp(QUESTION, { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Your past answers" })).toBeInTheDocument(); // Ada's
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("link", { name: "Sign in" });
    await login(user, router);
    await act(() => router.navigate(QUESTION));
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("heading", { name: "Your past answers" })).not.toBeInTheDocument();
    beas.release();
    await waitFor(() => expect(screen.queryByText("Loading")).not.toBeInTheDocument());
    expect(screen.queryByRole("heading", { name: "Your past answers" })).not.toBeInTheDocument();
  });

  it("a response for one account that arrives after the next account signs in is dropped", async () => {
    window.__ccDiag = [];
    const adas = held();
    let adaSent = false;
    server.use(
      http.get(ANSWERS, async ({ request }) => {
        if (request.headers.get("Authorization") === "Bearer bea-token") return HttpResponse.json([]);
        adaSent = true;
        await adas.promise;
        return HttpResponse.json([nurseAnswer]); // Ada's answers, arriving late
      }),
    );
    signInAsBea();
    const { user, router } = renderApp(QUESTION, { signedIn: true });
    await waitFor(() => expect(adaSent).toBe(true));
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("link", { name: "Sign in" });
    await login(user, router);
    adas.release();
    await waitFor(() =>
      expect(window.__ccDiag?.some((e) => e.kind === "auth" && e.event === "stale_response")).toBe(true),
    );
    await act(() => router.navigate(QUESTION));
    await screen.findByRole("heading", { level: 1 });
    await waitFor(() => expect(screen.queryByText("Loading")).not.toBeInTheDocument());
    expect(screen.queryByRole("heading", { name: "Your past answers" })).not.toBeInTheDocument();
  });

  it("a query still retrying when the learner signs out sends nothing more", async () => {
    const retry = held();
    let sent = 0;
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse())), // the coding dashboard
      http.get(`${API}/api/v1/me/progress`, async () => {
        sent += 1;
        if (sent === 2) await retry.promise; // the first retry is on its way when the learner signs out
        return HttpResponse.json({ error: { code: "unavailable", message: "x", request_id: "r", details: null } }, { status: 503 });
      }),
    );
    // Retries on, with no delay between them: a retry left scheduled would be sent at once.
    const { user, queryClient } = renderApp("/dashboard", { signedIn: true, queries: { retry: 3, retryDelay: 0 } });
    await waitFor(() => expect(sent).toBe(2));
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("link", { name: "Sign in" });
    retry.release();
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); }); // let a due retry run
    expect(queryClient.getQueryCache().find({ queryKey: ["me", "progress"] })).toBeUndefined();
    expect(sent).toBe(2);
    expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
  });
});
