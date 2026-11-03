import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";
import { EDITOR_KEY } from "@/features/settings/editorPreferences";

describe("Settings", () => {
  it("persists editor preferences and restores defaults", async () => {
    const { user } = renderApp("/settings", { signedIn: true });
    await user.selectOptions(await screen.findByLabelText("Font size"), "18");
    await user.selectOptions(screen.getByLabelText("Editor theme"), "vs");
    await user.click(screen.getByLabelText("Wrap long lines"));
    expect(JSON.parse(localStorage.getItem(EDITOR_KEY)!)).toMatchObject({ fontSize: 18, theme: "vs", wordWrap: "on" });
    await user.click(screen.getByRole("button", { name: "Restore editor defaults" }));
    expect(screen.getByLabelText("Font size")).toHaveValue("14");
    expect(JSON.parse(localStorage.getItem(EDITOR_KEY)!)).toMatchObject({ fontSize: 14, theme: "codecoach-dark", wordWrap: "off" });
  });

  it("updates the editor preview as each preference changes", async () => {
    const { user } = renderApp("/settings", { signedIn: true });
    const preview = await screen.findByLabelText("Editor appearance preview");
    const code = within(preview).getByRole("region", { name: "Editor code preview" });
    expect(preview).toHaveAttribute("data-theme", "codecoach-dark");
    await user.selectOptions(screen.getByLabelText("Editor theme"), "vs");
    expect(preview).toHaveAttribute("data-theme", "vs");
    await user.selectOptions(screen.getByLabelText("Font size"), "20");
    expect(code).toHaveStyle({ fontSize: "20px" });
    await user.selectOptions(screen.getByLabelText("Indentation"), "2");
    expect(code.textContent).toContain("2  //"); // line 2 is indented by two spaces
    await user.click(screen.getByLabelText("Wrap long lines"));
    expect(code).toHaveStyle({ whiteSpace: "pre-wrap" });
  });

  it("lets a guest keep their progress by creating an account in place", async () => {
    const guestUser = { ...baseUser, email: null, is_guest: true, display_name: "Guest" };
    let body: unknown = null;
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: guestUser }))),
      http.post(`${API}/api/v1/auth/upgrade`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(tokenResponse({ user: { ...baseUser, display_name: "Grace", email: "grace@example.com" } }));
      }),
    );
    const { user } = renderApp("/settings", { signedIn: true });
    const card = within(await screen.findByRole("form", { name: "Keep your progress" }));
    expect(await card.findByText(/deleted after 30 days without activity/)).toBeInTheDocument();
    await user.type(card.getByLabelText(/Name/), "Grace");
    await user.type(card.getByLabelText("Email"), "grace@example.com");
    await user.type(card.getByLabelText("Password"), "CorrectHorse42");
    await user.click(card.getByRole("button", { name: "Create my account" }));
    expect(await screen.findByText(/Your account is ready\. Everything you did as a guest is saved/)).toBeInTheDocument();
    expect(body).toEqual({ email: "grace@example.com", password: "CorrectHorse42", display_name: "Grace" });
    expect(screen.queryByRole("form", { name: "Keep your progress" })).not.toBeInTheDocument();
    expect(within(screen.getByRole("banner")).getByText("Grace")).toBeInTheDocument();
  });

  it("doesn't offer the guest upgrade to full accounts", async () => {
    renderApp("/settings", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Keep your progress" })).not.toBeInTheDocument();
  });

  it("warns when editor preferences cannot be persisted", async () => {
    const { user } = renderApp("/settings", { signedIn: true });
    const field = await screen.findByLabelText("Font size");
    const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota"); });
    await user.selectOptions(field, "18");
    expect(await screen.findByRole("alert")).toHaveTextContent("Settings apply for this visit only");
    expect(field).toHaveValue("18");
    write.mockRestore();
  });
  it("shows a profile save failure and keeps the edited name available for retry", async () => {
    server.use(http.patch(`${API}/api/v1/auth/me`, () => HttpResponse.json({
      error: { code: "unavailable", message: "Profile unavailable. Please try again." },
    }, { status: 503 })));
    const { user } = renderApp("/settings", { signedIn: true });
    const field = await screen.findByLabelText("Display name");
    await user.clear(field);
    await user.type(field, "Grace");
    await user.click(screen.getByRole("button", { name: "Save profile" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Profile unavailable. Please try again.");
    expect(field).toHaveValue("Grace");
    expect(screen.getByRole("button", { name: "Save profile" })).toBeEnabled();
  });
  it("updates the display name everywhere", async () => {
    server.use(http.patch(`${API}/api/v1/auth/me`, async ({ request }) => {
      const body = (await request.json()) as { display_name: string };
      return HttpResponse.json({ ...baseUser, display_name: body.display_name });
    }));
    const { user } = renderApp("/settings", { signedIn: true });
    const field = await screen.findByLabelText("Display name");
    await user.clear(field);
    await user.type(field, "Grace");
    await user.click(screen.getByRole("button", { name: "Save profile" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(within(screen.getByRole("banner")).getByText("Grace")).toBeInTheDocument();
  });

  it("changes the password and adopts the new token", async () => {
    let auth: string | null = null;
    server.use(
      http.post(`${API}/api/v1/auth/password`, () => HttpResponse.json(tokenResponse({ access_token: "rotated-token" }))),
      http.get(`${API}/api/v1/ai/usage`, ({ request }) => {
        auth = request.headers.get("Authorization");
        return HttpResponse.json({ used_today: 0, daily_limit: 50, remaining_today: 50, provider: "offline" });
      }),
    );
    const { user } = renderApp("/settings", { signedIn: true });
    const passwordForm = within(await screen.findByRole("form", { name: "Password" }));
    await user.type(passwordForm.getByLabelText("Current password"), "CorrectHorse42");
    await user.type(passwordForm.getByLabelText("New password"), "BatteryStaple99");
    await user.click(passwordForm.getByRole("button", { name: "Change password" }));
    expect(await screen.findByText(/Other devices were signed out/)).toBeInTheDocument();
    // Requests made after the change use the new token (the old one is revoked server-side).
    await waitFor(() => expect(auth).toBe("Bearer rotated-token"));
  });

  it("deletes the account only after typing DELETE, then signs out", async () => {
    let body: unknown = null;
    server.use(http.delete(`${API}/api/v1/auth/me`, async ({ request }) => {
      body = await request.json();
      return new HttpResponse(null, { status: 204 });
    }));
    const { user, router } = renderApp("/settings", { signedIn: true });
    const button = await screen.findByRole("button", { name: "Delete my account" });
    const danger = within(screen.getByRole("form", { name: "Delete account" }));
    await user.type(danger.getByLabelText("Password"), "CorrectHorse42");
    expect(button).toBeDisabled();
    await user.type(danger.getByLabelText('Type "DELETE" to confirm'), "DELETE");
    await user.click(button);
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(body).toEqual({ password: "CorrectHorse42", confirm: "DELETE" });
    expect(await screen.findByRole("link", { name: "Sign in" })).toBeInTheDocument();
  });

  it("downloads an export of the user's data", async () => {
    server.use(http.get(`${API}/api/v1/me/export`, () => HttpResponse.json({ export_version: 1, submissions: [] })));
    const created: Blob[] = [];
    URL.createObjectURL = vi.fn((blob: Blob) => { created.push(blob); return "blob:x"; });
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const { user } = renderApp("/settings", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Download my data" }));
    expect(await screen.findByText("Downloaded codecoach-data.json")).toBeInTheDocument();
    expect(click).toHaveBeenCalledOnce();
    expect(JSON.parse(await created[0]!.text())).toEqual({ export_version: 1, submissions: [] });
  });

  it("explains what is sent to the AI", async () => {
    renderApp("/settings", { signedIn: true });
    expect(await screen.findByText(/never the prompt that contained your code/)).toBeInTheDocument();
    expect(await screen.findByText(/built-in \(offline\)/)).toBeInTheDocument();
  });

  it("groups settings into sections you can jump to, moving focus to the section", async () => {
    const { user } = renderApp("/settings", { signedIn: true });
    const nav = within(await screen.findByRole("navigation", { name: "Settings sections" }));
    const sections = ["Account", "Sign-in & security", "Display & reading", "Editor", "Privacy & data", "Danger zone"];
    expect(nav.getAllByRole("link").map((a) => a.textContent)).toEqual(sections);
    for (const name of sections) expect(screen.getByRole("region", { name })).toBeInTheDocument();
    // Each form sits in the section you'd look for it in.
    expect(within(screen.getByRole("region", { name: "Account" })).getByRole("form", { name: "Email" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Sign-in & security" })).getByRole("form", { name: "Password" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Danger zone" })).getByRole("form", { name: "Delete account" })).toBeInTheDocument();

    expect(nav.getByRole("link", { name: "Account" })).toHaveAttribute("aria-current", "true");
    await user.click(nav.getByRole("link", { name: "Danger zone" }));
    expect(screen.getByRole("heading", { name: "Danger zone", level: 2 })).toHaveFocus();
    expect(nav.getByRole("link", { name: "Danger zone" })).toHaveAttribute("aria-current", "true");
    expect(nav.getByRole("link", { name: "Account" })).not.toHaveAttribute("aria-current");
  });
});
