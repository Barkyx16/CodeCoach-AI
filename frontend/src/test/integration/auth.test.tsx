import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { chooseCareer } from "../careerPicker";
import { renderApp } from "../render";
import { API, server } from "../server";
import { progress, tokenResponse } from "../fixtures";

describe("Authentication", () => {
  it("authenticates the first request when opening a protected page with a saved session", async () => {
    const headers: (string | null)[] = [];
    server.use(http.get(`${API}/api/v1/me/progress`, ({ request }) => {
      const header = request.headers.get("Authorization");
      headers.push(header);
      return header === `Bearer ${tokenResponse().access_token}`
        ? HttpResponse.json(progress)
        : HttpResponse.json({ error: { code: "unauthorized", message: "Missing token" } }, { status: 401 });
    }));
    renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Your interview practice" })).toBeInTheDocument();
    expect(headers.length).toBeGreaterThan(0);
    expect(headers.every((value) => value === `Bearer ${tokenResponse().access_token}`)).toBe(true);
    expect(screen.queryByText("Missing token")).not.toBeInTheDocument();
  });
  it("redirects protected pages to login and returns afterwards", async () => {
    const { user, router } = renderApp("/dashboard");
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/dashboard"));
    expect(await screen.findByRole("heading", { level: 1, name: "Your interview practice" })).toBeInTheDocument();
  });

  it("opens the dashboard after signing in from the login page", async () => {
    const { user, router } = renderApp("/login");
    await user.type(await screen.findByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/dashboard"));
    expect(await screen.findByRole("heading", { level: 1, name: "Your interview practice" })).toBeInTheDocument();
  });

  it("offers the optional welcome after continuing as a guest", async () => {
    const { user, router } = renderApp("/login");
    await user.click(await screen.findByRole("button", { name: "Continue as guest" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/welcome"));
  });

  it("shows the generic login error", async () => {
    server.use(http.post(`${API}/api/v1/auth/login`, () => HttpResponse.json(
      { error: { code: "invalid_credentials", message: "Incorrect email or password", request_id: null, details: null } }, { status: 401 })));
    const { user } = renderApp("/login");
    await user.type(await screen.findByLabelText("Email"), "a@example.com");
    await user.type(screen.getByLabelText("Password"), "nope");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
  });

  it("maps backend validation errors onto register fields", async () => {
    server.use(http.post(`${API}/api/v1/auth/register`, () => HttpResponse.json({
      error: { code: "validation_error", message: "Request validation failed", request_id: null,
        details: [{ loc: ["body", "password"], msg: "Value error, password needs upper- and lower-case letters and at least one digit", type: "value_error" }] },
    }, { status: 422 })));
    const { user } = renderApp("/register");
    await user.type(await screen.findByLabelText("Email"), "a@example.com");
    await user.type(screen.getByLabelText("Password"), "alllowercase");
    await chooseCareer(user, screen.getByLabelText("Job you're preparing for"), "registered-nurse");
    await user.click(within(screen.getByRole("form", { name: "Create your account" })).getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("password needs upper- and lower-case letters and at least one digit")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveAttribute("aria-invalid", "true");
  });

  it("starts a guest session from the landing page", async () => {
    const { user, router } = renderApp("/");
    await user.click(await screen.findByRole("button", { name: /try it now/i }));
    // A deliberate demo: the guest chooses how to start on the optional welcome.
    await waitFor(() => expect(router.state.location.pathname).toBe("/welcome"));
    expect(await screen.findByText("Guest")).toBeInTheDocument();
  });

  it("signs out when the server revokes the token", async () => {
    server.use(http.get(`${API}/api/v1/me/progress`, () => HttpResponse.json(
      { error: { code: "invalid_token", message: "Access token has been revoked", request_id: null, details: null } }, { status: 401 })));
    renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByText("Your session ended. Please sign in again.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });

  it("logs out and revokes server-side", async () => {
    let revoked = false;
    server.use(http.post(`${API}/api/v1/auth/logout`, () => { revoked = true; return new HttpResponse(null, { status: 204 }); }));
    const { user } = renderApp("/problems", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(revoked).toBe(true));
    expect(await screen.findByRole("link", { name: "Sign in" })).toBeInTheDocument();
  });

  it("sends a deliberate sign-out from a protected page home, not to login", async () => {
    const { user, router } = renderApp("/dashboard", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(screen.queryByText(/Your session/)).not.toBeInTheDocument();
  });
});
