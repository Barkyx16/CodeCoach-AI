import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { tokenResponse, user as baseUser, verificationStatus } from "../fixtures";
import { chooseCareer } from "../careerPicker";
import { renderApp } from "../render";
import { API, cookieJar, server } from "../server";

const unverified = { ...baseUser, email_verified: false };
const err = (code: string, message: string, details: unknown = null) =>
  ({ error: { code, message, request_id: "r", details } });

describe("Password fields", () => {
  it("have an eye button that shows and hides the password", async () => {
    const { user } = renderApp("/login");
    const input = await screen.findByLabelText("Password");
    await user.type(input, "CorrectHorse42");
    expect(input).toHaveAttribute("type", "password");
    const eye = screen.getByRole("button", { name: "Show password" });
    expect(eye).toHaveAttribute("aria-pressed", "false");
    await user.click(eye);
    expect(input).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Hide password" }));
    expect(input).toHaveAttribute("type", "password");
  });

  it("tick off the password rules as you type", async () => {
    const { user } = renderApp("/register");
    const rules = await screen.findByRole("list", { name: "Password requirements" });
    expect(within(rules).getAllByText(/not met yet/)).toHaveLength(4);
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    expect(within(rules).queryAllByText(/not met yet/)).toHaveLength(0);
  });
});

describe("Email verification", () => {
  it("sends you to enter the emailed code after creating an account", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/register`, () => {
        cookieJar.hasSession = true;
        return HttpResponse.json(tokenResponse({ user: unverified }), { status: 201 });
      }),
      http.post(`${API}/api/v1/auth/verify-email/code`, async ({ request }) => {
        const { code } = (await request.json()) as { code: string };
        return code === "123456" ? HttpResponse.json(baseUser)
          : HttpResponse.json(err("invalid_verification_code", "That code isn't right.", { attempts_left: 4 }), { status: 400 });
      }),
    );
    const { user, router } = renderApp("/register");
    await user.type(await screen.findByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await chooseCareer(user, await screen.findByLabelText("Job you're preparing for"), "registered-nurse");
    await user.click(within(screen.getByRole("main")).getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    // Masked on screen (the domain shows, to spot a typo there); the whole address on request.
    await waitFor(() => expect(screen.getByTestId("verify-destination")).toHaveTextContent("a•••@example.com"));
    await user.click(screen.getByRole("button", { name: "Show full address" }));
    expect(screen.getByTestId("verify-destination")).toHaveTextContent("ada@example.com");
    const code = screen.getByLabelText("Verification code");
    expect(code).toHaveAttribute("autocomplete", "one-time-code");
    await user.type(code, "65ab4321"); // letters are dropped, length capped at 6
    expect(code).toHaveValue("654321");
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    expect(await screen.findByText("That code isn't right. 4 tries left.")).toBeInTheDocument();

    await user.clear(code);
    await user.type(code, "123456");
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/welcome")); // new accounts are welcomed
  });

  it("can send a new code", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: unverified }))),
      http.post(`${API}/api/v1/auth/verify-email/resend`, () =>
        HttpResponse.json({ status: "accepted", message: "We've sent a new verification link to ada@example.com." }, { status: 202 })),
    );
    const { user } = renderApp("/verify-email", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Send a new code" }));
    expect(await screen.findByText(/We've sent a new verification link/)).toBeInTheDocument();
  });

  it.each([
    [false, true],
    [true, false],
  ])("says where the code went when the server can't send email (emails_delivered: %s)", async (delivered, shown) => {
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: unverified }))),
      http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({
        execution_enabled: false, ai_provider: "offline", guest_retention_days: 30, emails_delivered: delivered,
        execution: { state: "not_configured", reason: "not_configured", message: "", run_available: false,
          submit_mode: "saved_only", checked_at: new Date().toISOString(), setup_help: null },
      })),
    );
    renderApp("/verify-email", { signedIn: true });
    await screen.findByRole("heading", { name: "Check your email" });
    if (shown) {
      expect(await screen.findByRole("note")).toHaveTextContent(/isn't set up to send email.*printed in the terminal/);
    } else {
      await new Promise((r) => setTimeout(r, 50));
      expect(screen.queryByText(/isn't set up to send email/)).not.toBeInTheDocument();
    }
  });

  it("shows the server's cooldown on Send a new code, and says why", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: unverified }))),
      http.post(`${API}/api/v1/auth/verify-email/resend`, () => HttpResponse.json({ error: {
        code: "resend_cooldown", message: "A code was sent less than a minute ago. You can ask for another in 42 seconds.",
        request_id: "r", details: { retry_after_seconds: 42 } } }, { status: 429, headers: { "Retry-After": "42" } })),
    );
    const { user } = renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByText(/We send a 6-digit code to/)).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Send a new code" }));
    expect(await screen.findByText(/less than a minute ago/)).toBeInTheDocument();
    const waiting = screen.getByRole("button", { name: /Send a new code \(in \d+ s\)/ });
    expect(waiting).toBeDisabled();
    expect(Number(/in (\d+) s/.exec(waiting.textContent ?? "")![1])).toBeGreaterThan(40);
    expect(screen.getByRole("link", { name: "Change it in Settings" })).toHaveAttribute("href", "/settings");
  });

  it("says when a code was replaced by a newer one", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: unverified }))),
      http.post(`${API}/api/v1/auth/verify-email/code`, () => HttpResponse.json({ error: {
        code: "superseded_verification_code", message: "That code was replaced by a newer one. Use the code in the newest email.",
        request_id: "r", details: { attempts_left: 4 } } }, { status: 400 })),
    );
    const { user } = renderApp("/verify-email", { signedIn: true });
    await user.type(await screen.findByLabelText(/Verification code/), "123456");
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    expect(await screen.findByText("That code was replaced by a newer one. Use the code in the newest email. 4 tries left.")).toBeInTheDocument();
  });

  it("verifies from the emailed link even when signed out, and removes the token from the URL", async () => {
    let body: unknown = null;
    server.use(http.post(`${API}/api/v1/auth/verify-email`, async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({ status: "verified", account: "signed_out", email_masked: "a•••@e•••.com", changed_email: false, user: null });
    }));
    window.history.replaceState(null, "", `/verify-email#token=${"v".repeat(43)}`);
    renderApp("/verify-email");
    expect(await screen.findByText("a•••@e•••.com is confirmed. Thanks!")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in to continue" })).toHaveAttribute("href", "/login");
    expect(body).toEqual({ token: "v".repeat(43) });
    expect(window.location.hash).toBe("");
  });
});

describe("Confirming a new email", () => {
  it("asks for the code sent to the new address and says the old one still applies", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () =>
        HttpResponse.json(tokenResponse({ user: { ...baseUser, pending_email: "new@example.com" } }))),
      http.get(`${API}/api/v1/auth/verify-email/status`, () =>
        HttpResponse.json(verificationStatus({ changing_email: true, address_masked: "n•••@example.com" }))),
    );
    renderApp("/verify-email", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Confirm your new email" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("verify-destination")).toHaveTextContent("n•••@example.com"));
    expect(screen.getByTestId("pending-email-note")).toHaveTextContent("keeps using ada@example.com");
    expect(screen.queryByText(/is verified/)).not.toBeInTheDocument(); // not "done" while a change waits
    expect(screen.getByRole("link", { name: "Change or cancel it in Settings" })).toHaveAttribute("href", "/settings");
  });
});

describe("Settings: email and signing out", () => {
  it("shows the verification status and changes the email with the password", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: unverified }))),
      http.post(`${API}/api/v1/auth/email`, async ({ request }) => {
        body = await request.json();
        // The server keeps the current email until the new address confirms.
        return HttpResponse.json({ ...unverified, pending_email: "new@example.com" });
      }),
    );
    const { user } = renderApp("/settings", { signedIn: true });
    const card = within(await screen.findByRole("form", { name: "Email" }));
    expect(card.getByText("Not verified")).toBeInTheDocument();
    expect(card.getByRole("link", { name: "Enter the verification code" })).toHaveAttribute("href", "/verify-email");
    await user.type(card.getByLabelText("New email"), "new@example.com");
    await user.type(card.getByLabelText("Current password"), "CorrectHorse42");
    await user.click(card.getByRole("button", { name: "Change email" }));
    expect(await card.findByText(/Code sent to the new address. Nothing changes until you enter it/)).toBeInTheDocument();
    expect(body).toEqual({ new_email: "new@example.com", password: "CorrectHorse42" });
    const pending = within(card.getByTestId("pending-email"));
    expect(pending.getByText("new@example.com")).toBeInTheDocument();
    expect(pending.getByText(/you sign in with ada@example.com/)).toBeInTheDocument();
    expect(card.getByText("ada@example.com")).toBeInTheDocument(); // still the account's email
  });

  it("cancels a pending change", async () => {
    const waiting = { ...baseUser, pending_email: "new@example.com" };
    let cancelled = 0;
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: waiting }))),
      http.delete(`${API}/api/v1/auth/email/pending`, () => {
        cancelled += 1;
        return HttpResponse.json({ ...waiting, pending_email: null });
      }),
    );
    const { user } = renderApp("/settings", { signedIn: true });
    const card = within(await screen.findByRole("form", { name: "Email" }));
    expect(within(card.getByTestId("pending-email")).getByRole("link", { name: "Enter the code" }))
      .toHaveAttribute("href", "/verify-email");
    await user.click(card.getByRole("button", { name: "Cancel this change" }));
    expect(await card.findByText(/Change cancelled/)).toBeInTheDocument();
    expect(cancelled).toBe(1);
    expect(card.queryByTestId("pending-email")).not.toBeInTheDocument();
    expect(card.getByText("Verified")).toBeInTheDocument();
  });

  it("signs out of this device", async () => {
    let calls = 0;
    server.use(http.post(`${API}/api/v1/auth/logout`, () => { calls += 1; cookieJar.hasSession = false; return new HttpResponse(null, { status: 204 }); }));
    const { user, router } = renderApp("/settings", { signedIn: true });
    const card = within(await screen.findByRole("region", { name: "Sign out" }));
    await user.click(card.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(calls).toBe(1);
    expect(await screen.findByRole("link", { name: "Sign in" })).toBeInTheDocument();
  });

  it("signs out of every device only after confirming", async () => {
    let calls = 0;
    server.use(http.post(`${API}/api/v1/auth/logout-all`, () => { calls += 1; cookieJar.hasSession = false; return new HttpResponse(null, { status: 204 }); }));
    const confirm = vi.spyOn(window, "confirm");
    const { user, router } = renderApp("/settings", { signedIn: true });
    const button = await screen.findByRole("button", { name: "Sign out of all devices" });
    confirm.mockReturnValueOnce(false);
    await user.click(button);
    expect(calls).toBe(0);
    confirm.mockReturnValueOnce(true);
    await user.click(button);
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(calls).toBe(1);
    confirm.mockRestore();
  });

  it("says what's kept and for how long, including what deletion can't reach", async () => {
    renderApp("/settings", { signedIn: true });
    const row = within(await screen.findByRole("group", { name: "What we keep, and for how long" }));
    expect(row.getByText(/removes it and everything in it at once/)).toBeInTheDocument();
    expect(row.getByText(/Older server backups keep a copy until they expire/)).toBeInTheDocument();
    expect(row.getByText(/cleared when you sign out here/)).toBeInTheDocument();
  });

  it("still offers account deletion", async () => {
    renderApp("/settings", { signedIn: true });
    expect(await screen.findByRole("button", { name: "Delete my account" })).toBeDisabled(); // until confirmed
  });
});
