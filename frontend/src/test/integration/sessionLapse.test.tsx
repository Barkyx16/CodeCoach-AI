/**
 * A session that ends by itself mid-work (Volume 8, prompt 8; RECOVERY.md "When a session ends").
 * The work on screen stays, the banner says what that means and offers a sign-in that comes back
 * here. The same account signing in gets its draft back and its unresolved action checked (a
 * read), never sent again. Another account sees none of it: not the draft, not the earlier
 * action, and nothing is checked, sent or attached as that account. Another tab signing in
 * brings this tab back with one check. A browser that can't keep copies says so.
 */
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { DEVICE_USER_KEY } from "@/auth/deviceUser";

import { executionStatus, queuedSubmission, tokenResponse, user as ada } from "../fixtures";
import { renderApp } from "../render";
import { API, cookieJar, server } from "../server";

const bea = { ...ada, id: "user-bea", email: "bea@example.com", display_name: "Bea" };
const ADA_WORK = "class Solution { /* Ada's work in progress */ }";
const draftKey = (id: string) => `codecoach.draft.v1.${id}.two-sum`;
const pending = (id: string) => localStorage.getItem(`codecoach.pending.v1.${id}`);
const keyOf = async (request: Request) => ((await request.json()) as { client_request_id?: string }).client_request_id;

afterEach(() => localStorage.clear());

/** A server where whoever signed in last is who the cookie restores; a hint ends the session. */
function world() {
  const s = { who: ada as typeof ada, posts: [] as (string | undefined)[], lookups: [] as string[], refreshes: 0, hintPosts: 0 };
  server.use(
    http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({
      execution_enabled: true, ai_provider: "offline", execution: executionStatus("ready"), guest_retention_days: 30 })),
    http.post(`${API}/api/v1/auth/refresh`, () => {
      s.refreshes += 1;
      return cookieJar.hasSession ? HttpResponse.json(tokenResponse({ user: s.who }))
        : HttpResponse.json({ error: { code: "invalid_refresh", message: "Please sign in again.", request_id: "r", details: null } }, { status: 401 });
    }),
    http.post(`${API}/api/v1/auth/login`, async ({ request }) => {
      const body = (await request.json()) as { email: string; password: string };
      if (body.password !== "CorrectHorse42") {
        return HttpResponse.json({ error: { code: "invalid_credentials", message: "Incorrect email or password", request_id: "r", details: null } }, { status: 401 });
      }
      s.who = body.email === bea.email ? bea : ada;
      cookieJar.hasSession = true;
      return HttpResponse.json(tokenResponse({ user: s.who }));
    }),
    // The first submission arrives, but its reply is lost.
    http.post(`${API}/api/v1/submissions`, async ({ request }) => { s.posts.push(await keyOf(request)); return HttpResponse.error(); }),
    http.get(`${API}/api/v1/me/requests/:key`, ({ params }) => {
      s.lookups.push(params.key as string);
      return HttpResponse.json({ kind: "submission", state: "done", id: "sub-earlier", created_at: new Date().toISOString(), problem_slug: "two-sum" });
    }),
    http.get(`${API}/api/v1/submissions/sub-earlier`, () => HttpResponse.json({ ...queuedSubmission, id: "sub-earlier", execution_enabled: true,
      is_terminal: true, status: "PASSED", source_code: ADA_WORK })),
    // Asking for a hint finds the session revoked elsewhere: the refresh is refused too.
    http.post(`${API}/api/v1/ai/hint`, () => {
      s.hintPosts += 1;
      cookieJar.hasSession = false;
      return HttpResponse.json({ error: { code: "invalid_token", message: "Access token has been revoked", request_id: "r", details: null } }, { status: 401 });
    }),
  );
  return s;
}

/** Ada is working: her draft is on screen, a submission's reply is lost, then her session ends. */
async function adaLapsesMidWork(s: ReturnType<typeof world>) {
  localStorage.setItem(draftKey(ada.id), ADA_WORK);
  const app = renderApp("/problems/two-sum", { signedIn: true });
  expect(await screen.findByText(/Ada's work in progress/, {}, { timeout: 3000 })).toBeInTheDocument();
  await app.user.click(screen.getByRole("button", { name: /^Submit/ }));
  expect(await screen.findByText(/We couldn't confirm your submission/)).toBeInTheDocument();
  await app.user.click(screen.getByRole("button", { name: "Get a hint" }));
  expect(await screen.findByText("Your session ended. Please sign in again.")).toBeInTheDocument();
  expect(s.posts).toHaveLength(1);
  return app;
}

async function signIn(user: ReturnType<typeof renderApp>["user"], email: string, password = "CorrectHorse42") {
  const box = await screen.findByLabelText("Email");
  await user.clear(box);
  await user.type(box, email);
  await user.clear(screen.getByLabelText("Password"));
  await user.type(screen.getByLabelText("Password"), password);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

it("the same account signs back in: its draft is there and its earlier submission is checked, not sent again", async () => {
  const s = world();
  const { user, router } = await adaLapsesMidWork(s);
  // The work stays on screen, and the banner says what's kept and offers a way back.
  expect(screen.getByText(/Ada's work in progress/)).toBeInTheDocument();
  expect(screen.getByText(/Until then nothing is saved to an account\. Unsaved work this page keeps on this device stays with the account that was signed in/)).toBeInTheDocument();
  expect(document.querySelector(".session-ended")!.textContent).not.toMatch(/Ada|ada@example\.com/); // names nobody
  await user.click(screen.getByRole("link", { name: "Sign in again" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  // A failed sign-in is just that: the banner stays, nothing loops.
  await signIn(user, ada.email!, "WrongHorse99");
  expect(await screen.findByText("Incorrect email or password")).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/login");
  await signIn(user, ada.email!);
  await waitFor(() => expect(router.state.location.pathname).toBe("/problems/two-sum"));
  expect(await screen.findByText(/Ada's work in progress/)).toBeInTheDocument();
  expect(await screen.findByText(/Your submission from .* arrived\./)).toBeInTheDocument();
  expect(s.lookups).toEqual([s.posts[0]]); // a read of the earlier key
  expect(s.posts).toHaveLength(1); // nothing sent again
  expect(s.hintPosts).toBe(1); // the hint isn't restarted either
  expect(screen.queryByText("Your session ended. Please sign in again.")).not.toBeInTheDocument();
});

it("another account signs in: none of the earlier account's work is shown, checked, sent or attached", async () => {
  const s = world();
  const { user, router } = await adaLapsesMidWork(s);
  await user.click(screen.getByRole("link", { name: "Sign in again" }));
  await signIn(user, bea.email);
  await waitFor(() => expect(router.state.location.pathname).toBe("/problems/two-sum"));
  expect(await screen.findByText(/public int\[\] twoSum/)).toBeInTheDocument(); // Bea's (starter) code
  expect(screen.queryByText(/Ada's work in progress/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Your submission from/)).not.toBeInTheDocument();
  expect(s.lookups).toEqual([]); // Ada's key isn't checked as Bea
  expect(s.posts).toHaveLength(1);
  // Ada's work stays locked to Ada on this device, untouched, for when she signs in again.
  expect(localStorage.getItem(draftKey(ada.id))).toBe(ADA_WORK);
  expect(pending(ada.id)).toContain(s.posts[0]!);
  expect(localStorage.getItem(draftKey(bea.id))).toBeNull();
});

it("another tab signing in brings this tab back with one check, and the work stays", async () => {
  const s = world();
  await adaLapsesMidWork(s);
  const before = s.refreshes;
  // Another tab signs Ada in: the cookie works again, and that tab writes this device's record.
  cookieJar.hasSession = true;
  window.dispatchEvent(new StorageEvent("storage", { key: DEVICE_USER_KEY, newValue: JSON.stringify({ id: ada.id, display_name: "Ada", career_track: null, is_guest: false }) }));
  await waitFor(() => expect(screen.queryByText("Your session ended. Please sign in again.")).not.toBeInTheDocument());
  expect(s.refreshes).toBe(before + 1);
  expect(await screen.findByText(/Ada's work in progress/, {}, { timeout: 3000 })).toBeInTheDocument(); // (fetched again, signed in)
  expect(s.posts).toHaveLength(1);
});

it("a browser that can't keep copies says to copy the work before leaving", async () => {
  const s = world();
  const { user } = await adaLapsesMidWork(s);
  const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
  try {
    // Any re-render of the banner (here: going to the login page) checks again.
    await user.click(screen.getByRole("link", { name: "Sign in again" }));
    expect(await screen.findByText(/this browser can't keep a copy: copy anything you need before leaving this page/)).toBeInTheDocument();
  } finally {
    spy.mockRestore();
  }
});
