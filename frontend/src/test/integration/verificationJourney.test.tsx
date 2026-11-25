import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { rememberVerifyNext, VERIFIED_KEY } from "@/auth/emailVerified";
import { safeReturnPath } from "@/lib/links";

import { tokenResponse, user as baseUser, verificationStatus } from "../fixtures";
import { chooseCareer } from "../careerPicker";
import { renderApp } from "../render";
import { API, cookieJar, server } from "../server";

/**
 * Email verification as a recovery journey: the "Check your email" page says what the server can
 * back up (where the code went, masked; what became of the email; how long the code works; when
 * a new one can be sent), resend can't be pressed twice and never claims success it didn't get, a
 * link that doesn't work says why and offers the way on, and the learner ends up where they were
 * going, whichever tab the link was opened in.
 */
const unverified = { ...baseUser, email_verified: false };
const err = (code: string, message: string, details: unknown = null) =>
  ({ error: { code, message, request_id: "r", details } });
const signedInUnverified = () =>
  server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: unverified }))));
const openLink = (token: string) => window.history.replaceState(null, "", `/verify-email#token=${token}`);
const TOKEN = "t".repeat(43);

afterEach(() => {
  window.history.replaceState(null, "", "/");
  localStorage.clear();
});

describe("Check your email: what the server can back up", () => {
  it("says it's sending, then what happened, without claiming the email arrived", async () => {
    signedInUnverified();
    let calls = 0;
    server.use(http.get(`${API}/api/v1/auth/verify-email/status`, () => {
      calls += 1;
      return HttpResponse.json(calls === 1
        ? verificationStatus({ delivery: { state: "queued", requested_at: new Date().toISOString(), updated_at: null, next_try_at: null } })
        : verificationStatus());
    }));
    renderApp("/verify-email", { signedIn: true });
    const line = await screen.findByTestId("delivery-status");
    expect(line).toHaveTextContent(/Sending it now/);
    expect(line).toHaveAttribute("role", "status");
    // While it's queued the page looks again by itself.
    await waitFor(() => expect(screen.getByTestId("delivery-status")).toHaveTextContent(/handed it to your email provider/), { timeout: 6000 });
    expect(screen.getByTestId("delivery-status")).toHaveTextContent("We can't see whether it has reached your inbox.");
    expect(screen.queryByText(/delivered/i)).not.toBeInTheDocument();
    expect(screen.getByText(/The newest code and link work until/)).toBeInTheDocument();
  }, 10_000);

  it.each([
    ["retrying", /first try didn't go through. It's tried again automatically/],
    ["failed", /We couldn't send it.*Send a new code/],
    ["unknown", /no record of the latest email/],
  ] as const)("explains a %s email and what to do", async (state, text) => {
    signedInUnverified();
    server.use(http.get(`${API}/api/v1/auth/verify-email/status`, () => HttpResponse.json(verificationStatus({
      delivery: { state, requested_at: new Date().toISOString(), updated_at: new Date().toISOString(),
        next_try_at: state === "retrying" ? new Date(Date.now() + 120_000).toISOString() : null },
    }))));
    renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByTestId("delivery-status")).toHaveTextContent(text);
    expect(screen.getByRole("button", { name: "Send a new code" })).toBeEnabled();
  });

  it.each([
    ["console", /printed in the terminal window.*\.\/dev\.sh/],
    ["file", /saved as a file on the server.*EMAIL_FILE_DIR/],
  ] as const)("on a development server (%s) says the email stayed on that computer", async (transport, text) => {
    signedInUnverified();
    server.use(http.get(`${API}/api/v1/auth/verify-email/status`, () => HttpResponse.json(verificationStatus({
      transport, delivery: { state: "kept_locally", requested_at: null, updated_at: null, next_try_at: null },
    }))));
    renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByTestId("delivery-status")).toHaveTextContent(/Not emailed/);
    expect(await screen.findByRole("note")).toHaveTextContent(text);
    expect(screen.queryByText(/\b\d{6}\b/)).not.toBeInTheDocument(); // the page never shows a code
  });

  it("says when the last code no longer works", async () => {
    signedInUnverified();
    server.use(http.get(`${API}/api/v1/auth/verify-email/status`, () =>
      HttpResponse.json(verificationStatus({ code_expires_at: null, code_tries_left: null }))));
    renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByText("Your last code no longer works. Send a new one below.")).toBeInTheDocument();
  });

  it("offers help that doesn't guess: spam, the address, a new code, Settings, or sign out", async () => {
    signedInUnverified();
    const { user } = renderApp("/verify-email", { signedIn: true });
    await user.click(await screen.findByText("Not in your inbox?"));
    const help = screen.getByText("Not in your inbox?").closest("details")!;
    expect(help).toHaveTextContent(/spam or junk/);
    expect(help).toHaveTextContent(/only the newest email's code and link work/);
    expect(within(help).getByRole("link", { name: "Change it in Settings" })).toHaveAttribute("href", "/settings");
    await user.click(within(help).getByRole("button", { name: "sign out" }));
    await waitFor(() => expect(cookieJar.hasSession).toBe(false));
  });
});

describe("Send a new code", () => {
  it("waits as long as the server says, from the moment the page opens", async () => {
    signedInUnverified();
    server.use(http.get(`${API}/api/v1/auth/verify-email/status`, () =>
      HttpResponse.json(verificationStatus({ resend_available_in_seconds: 37 }))));
    renderApp("/verify-email", { signedIn: true });
    const waiting = await screen.findByRole("button", { name: /Send a new code \(in \d+ s\)/ });
    expect(waiting).toBeDisabled();
    expect(Number(/in (\d+) s/.exec(waiting.textContent ?? "")![1])).toBeGreaterThan(30);
  });

  it("sends one request however often it's pressed, and announces the masked address", async () => {
    signedInUnverified();
    let sent = 0;
    server.use(http.post(`${API}/api/v1/auth/verify-email/resend`, async () => {
      sent += 1;
      await new Promise((r) => setTimeout(r, 150));
      return HttpResponse.json({ status: "accepted",
        message: "A new code is on its way to a•••@example.com. It replaces the one before: only the newest email's code and link work." },
      { status: 202 });
    }));
    const { user } = renderApp("/verify-email", { signedIn: true });
    const button = await screen.findByRole("button", { name: "Send a new code" });
    await user.click(button);
    await user.click(screen.getByRole("button", { name: "Sending a new code…" }));
    await user.click(screen.getByRole("button", { name: "Sending a new code…" }));
    expect(await screen.findByText(/A new code is on its way to a•••@example.com/)).toHaveAttribute("role", "status");
    expect(sent).toBe(1);
    expect(screen.getByRole("button", { name: /Send a new code \(in \d+ s\)/ })).toBeDisabled();
  });

  it("never says it was sent when it wasn't, and the button comes back", async () => {
    signedInUnverified();
    server.use(http.post(`${API}/api/v1/auth/verify-email/resend`, () =>
      HttpResponse.json(err("internal_error", "Something went wrong on our side."), { status: 500 })));
    const { user } = renderApp("/verify-email", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Send a new code" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/went wrong/);
    expect(screen.queryByText(/on its way/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send a new code" })).toBeEnabled();
  });
});

describe("The emailed link", () => {
  it.each([
    ["expired", "This link has expired", "Get a new code"],
    ["superseded", "A newer email replaced this link", "Get a new code"],
    ["stopped", "This link no longer works", "Get a new code"],
    ["address_changed", "This link is for an earlier request", "Get a new code"],
    ["unknown", "We don't recognise this link", "Get a new code"],
  ])("signed in: a %s link says so and leads to a new code", async (reason, title, action) => {
    signedInUnverified();
    server.use(http.post(`${API}/api/v1/auth/verify-email`, () =>
      HttpResponse.json(err("invalid_verification_token", `Server says: ${reason}.`, { reason, account: "this" }), { status: 400 })));
    openLink(TOKEN);
    renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(`Server says: ${reason}.`);
    expect(screen.getByRole("link", { name: action })).toHaveAttribute("href", "/verify-email");
  });

  it("signed out: an expired link leads to signing in, and back here afterwards", async () => {
    server.use(http.post(`${API}/api/v1/auth/verify-email`, () =>
      HttpResponse.json(err("invalid_verification_token", "This link has expired: links work for 48 hours.", { reason: "expired", account: "signed_out" }), { status: 400 })));
    openLink(TOKEN);
    const { user, router } = renderApp("/verify-email");
    await user.click(await screen.findByRole("link", { name: "Sign in to get a new code" }));
    expect(router.state.location.pathname).toBe("/login");
    expect(router.state.location.state).toEqual({ from: "/verify-email" });
  });

  it("a link that was cut short is caught without sending it", async () => {
    let sent = false;
    server.use(http.post(`${API}/api/v1/auth/verify-email`, () => { sent = true; return HttpResponse.json({}); }));
    signedInUnverified();
    openLink("abc123");
    renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "This link is incomplete" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Enter the code instead" })).toHaveAttribute("href", "/verify-email");
    expect(sent).toBe(false);
  });

  it("already used: says it's done and continues", async () => {
    server.use(http.post(`${API}/api/v1/auth/verify-email`, () =>
      HttpResponse.json(err("invalid_verification_token", "This email is already confirmed. There's nothing more to do.", { reason: "already_verified", account: "this" }), { status: 400 })));
    openLink(TOKEN);
    renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "This email is already confirmed" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Continue" })).toHaveAttribute("href", "/dashboard");
  });

  it("another account's link asks first, and confirming it leaves this session alone", async () => {
    const bodies: unknown[] = [];
    server.use(http.post(`${API}/api/v1/auth/verify-email`, async ({ request }) => {
      const body = await request.json() as { other_account_ok?: boolean };
      bodies.push(body);
      expect(request.headers.get("Authorization")).toBe("Bearer test-token"); // sent as this session
      return body.other_account_ok
        ? HttpResponse.json({ status: "verified", account: "other", email_masked: "j•••@e•••.com", changed_email: false, user: null })
        : HttpResponse.json(err("verification_link_other_account", "This link is for a different account.", { account: "other", link_for: "j•••@e•••.com" }), { status: 409 });
    }));
    openLink(TOKEN);
    const { user } = renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "This link is for a different account" })).toBeInTheDocument();
    expect(screen.getByText(/You're signed in as/)).toHaveTextContent("ada@example.com");
    expect(screen.getByText(/You're signed in as/)).toHaveTextContent("(j•••@e•••.com). Nothing has changed yet.");
    expect(screen.getByRole("link", { name: "Don't use it" })).toHaveAttribute("href", "/dashboard");
    await user.click(screen.getByRole("button", { name: "Confirm that account's email" }));
    expect(await screen.findByText("Confirmed j•••@e•••.com for the other account.")).toBeInTheDocument();
    expect(screen.getByText(/You're still signed in as/)).toHaveTextContent("ada@example.com");
    expect(screen.getByRole("link", { name: "Continue as ada@example.com" })).toBeInTheDocument();
    expect(bodies).toEqual([{ token: TOKEN }, { token: TOKEN, other_account_ok: true }]);
  });

  it("a lost answer can be tried again (a used link then says it's already done)", async () => {
    let calls = 0;
    server.use(http.post(`${API}/api/v1/auth/verify-email`, () => {
      calls += 1;
      return calls === 1
        ? HttpResponse.error()
        : HttpResponse.json(err("invalid_verification_token", "This email is already confirmed. There's nothing more to do.", { reason: "already_verified", account: "signed_out" }), { status: 400 });
    }));
    openLink(TOKEN);
    const { user } = renderApp("/verify-email");
    await user.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "This email is already confirmed" })).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
  });

  it("a link pasted into a tab already on Check your email is used (and checked again if pasted twice)", async () => {
    signedInUnverified();
    let posts = 0;
    server.use(http.post(`${API}/api/v1/auth/verify-email`, () => {
      posts += 1;
      return posts === 1
        ? HttpResponse.json({ status: "verified", account: "this", email_masked: "a•••@example.com", changed_email: false, user: baseUser })
        : HttpResponse.json(err("invalid_verification_token", "This email is already confirmed. There's nothing more to do.", { reason: "already_verified", account: "this" }), { status: 400 });
    }));
    renderApp("/verify-email", { signedIn: true });
    await screen.findByRole("heading", { name: "Check your email" });
    const paste = () => act(() => {
      window.history.replaceState(null, "", `/verify-email#token=${TOKEN}`);
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    paste();
    expect(await screen.findByText("a•••@example.com is confirmed. Thanks!")).toBeInTheDocument();
    expect(window.location.hash).toBe("");
    paste();
    expect(await screen.findByRole("heading", { name: "This email is already confirmed" })).toBeInTheDocument();
    expect(posts).toBe(2);
  });

  it("confirmed without the session (its token had just expired): reads the account again", async () => {
    signedInUnverified();
    let looked = 0;
    server.use(
      http.post(`${API}/api/v1/auth/verify-email`, () =>
        HttpResponse.json({ status: "verified", account: "signed_out", email_masked: "a•••@e•••.com", changed_email: false, user: null })),
      http.get(`${API}/api/v1/auth/me`, () => { looked += 1; return HttpResponse.json(baseUser); }),
    );
    openLink(TOKEN);
    renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByText("a•••@e•••.com is confirmed. Thanks!")).toBeInTheDocument();
    await waitFor(() => expect(looked).toBe(1));
    expect(screen.getByRole("link", { name: "Continue" })).toBeInTheDocument();
  });

  it("in a new tab of the same browser, continues to where the learner was going", async () => {
    rememberVerifyNext(baseUser.id, "/problems/two-sum?tab=notes");
    server.use(http.post(`${API}/api/v1/auth/verify-email`, () =>
      HttpResponse.json({ status: "verified", account: "this", email_masked: "a•••@example.com", changed_email: false, user: baseUser })));
    const announced: string[] = [];
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (this: Storage, key: string, value: string) {
      if (key === VERIFIED_KEY) announced.push(value);
    });
    openLink(TOKEN);
    renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByText("a•••@example.com is confirmed. Thanks!")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Continue" })).toHaveAttribute("href", "/problems/two-sum?tab=notes");
    expect(announced.map((v) => JSON.parse(v).userId)).toEqual([baseUser.id]); // the other tabs are told
    spy.mockRestore();
  });
});

describe("The tab that's still waiting", () => {
  it("moves on when another tab confirms, and says so", async () => {
    signedInUnverified();
    server.use(http.get(`${API}/api/v1/auth/me`, () => HttpResponse.json(baseUser)));
    renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: VERIFIED_KEY, newValue: JSON.stringify({ userId: baseUser.id, at: Date.now() }) }));
    });
    expect(await screen.findByRole("heading", { name: "Your email is confirmed" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("You confirmed it in another tab or on another device.");
  });

  it("ignores a signal about a different account", async () => {
    signedInUnverified();
    let looked = false;
    server.use(http.get(`${API}/api/v1/auth/me`, () => { looked = true; return HttpResponse.json(baseUser); }));
    renderApp("/verify-email", { signedIn: true });
    await screen.findByRole("heading", { name: "Check your email" });
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: VERIFIED_KEY, newValue: JSON.stringify({ userId: "someone-else", at: Date.now() }) }));
    });
    await new Promise((r) => setTimeout(r, 50));
    expect(looked).toBe(false);
    expect(screen.getByRole("heading", { name: "Check your email" })).toBeInTheDocument();
  });

  it("confirmed on another device: the status on focus says so", async () => {
    signedInUnverified();
    let verified = false;
    server.use(
      http.get(`${API}/api/v1/auth/verify-email/status`, () =>
        HttpResponse.json(verified ? verificationStatus({ state: "verified", delivery: null }) : verificationStatus())),
      http.get(`${API}/api/v1/auth/me`, () => HttpResponse.json(baseUser)),
    );
    renderApp("/verify-email", { signedIn: true });
    await screen.findByTestId("delivery-status");
    verified = true;
    act(() => {
      window.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("focus"));
    });
    expect(await screen.findByRole("heading", { name: "Your email is confirmed" })).toBeInTheDocument();
  });
});

describe("Getting back to where the learner was going", () => {
  it("survives Sign in → Create account → Check your email", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/register`, () => {
        cookieJar.hasSession = true;
        return HttpResponse.json(tokenResponse({ user: unverified }), { status: 201 });
      }),
      http.post(`${API}/api/v1/auth/verify-email/code`, () => HttpResponse.json(baseUser)),
    );
    const { user, router } = renderApp("/history");
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    await user.click(await screen.findByRole("link", { name: "Create an account" }));
    await user.type(await screen.findByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await chooseCareer(user, await screen.findByLabelText("Job you're preparing for"), "registered-nurse");
    await user.click(within(screen.getByRole("main")).getByRole("button", { name: "Create account" }));
    await user.type(await screen.findByLabelText("Verification code"), "123456");
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/history"));
  });

  it("refuses a destination outside the app, or one that loops", async () => {
    const { user, router } = renderApp("/login");
    await act(() => router.navigate("/login", { state: { from: "//evil.example/steal" } }));
    await user.type(await screen.findByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await user.click(within(screen.getByRole("main")).getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/dashboard"));
  });

  it.each([
    ["//evil.example", "/fallback"],
    ["/\\evil.example", "/fallback"],
    ["https://evil.example/x", "/fallback"],
    ["/\t/evil.example", "/fallback"],
    ["javascript:alert(1)", "/fallback"],
    ["/login", "/fallback"],
    ["/register?x=1", "/fallback"],
    [42, "/fallback"],
    ["/problems/two-sum?tab=notes#top", "/problems/two-sum?tab=notes#top"],
    ["/interviews/abc", "/interviews/abc"],
  ])("safeReturnPath(%j) → %s", (raw, expected) => {
    expect(safeReturnPath(raw, "/fallback")).toBe(expected);
  });
});
