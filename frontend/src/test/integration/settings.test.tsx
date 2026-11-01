import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { loadSession } from "@/auth/session";

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
    expect(loadSession()?.user.display_name).toBe("Grace");
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
    await user.type(await screen.findByLabelText("Current password"), "CorrectHorse42");
    await user.type(screen.getByLabelText("New password"), "BatteryStaple99");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByText(/Other devices were signed out/)).toBeInTheDocument();
    expect(loadSession()?.token).toBe("rotated-token");
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
    expect(loadSession()).toBeNull();
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
});
