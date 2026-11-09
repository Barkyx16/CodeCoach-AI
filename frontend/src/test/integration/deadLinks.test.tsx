/**
 * Links that lead nowhere (Volume 9, prompt 5; NAVIGATION.md "Links that lead nowhere"). A
 * private record the server won't show (deleted, mistyped, another account's: one 404 for all)
 * gets the same generic words and the learner's own list; public content that's gone leads to its
 * library; a temporary failure keeps Try again, which works; signing in again rechecks access.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { contentMeta } from "../content";
import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const notFound = (message: string) => HttpResponse.json({ error: { code: "not_found", message, request_id: "r-1" } }, { status: 404 });
const busy = () => HttpResponse.json({ error: { code: "server_busy", message: "The server is very busy right now.", request_id: "r-2" } }, { status: 503 });

describe("a bookmarked private record that isn't there", () => {
  it("an interview: the generic words, All your interviews and the dashboard; no retry, no id, no server wording", async () => {
    asNurse();
    server.use(http.get(`${API}/api/v1/interviews/:id`, () => notFound("Interview not found")));
    renderApp("/interviews/iv-0f3a", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "This interview isn't available" })).toBeInTheDocument();
    expect(screen.getByText("It may have been deleted, the link may be mistyped, or it may belong to a different account. Nothing was changed.")).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(within(main).getByRole("link", { name: "All your interviews" })).toHaveAttribute("href", "/history?type=interview");
    expect(within(main).getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("iv-0f3a");
    expect(document.body).not.toHaveTextContent("Interview not found");
  });

  it("deleted, never there, and another account's look exactly the same (the server answers 404 for each; a 403 is treated alike)", async () => {
    asNurse();
    const seen: string[] = [];
    for (const reply of [() => notFound("Note not found"), () => notFound("Not found"),
      () => HttpResponse.json({ error: { code: "forbidden", message: "Not allowed", request_id: "r" } }, { status: 403 })]) {
      server.use(http.get(`${API}/api/v1/me/notes/:id`, () => reply()));
      const r = renderApp("/notes/n-77", { signedIn: true });
      await screen.findByRole("heading", { level: 1, name: "This note isn't available" });
      seen.push(document.querySelector(".page")!.textContent ?? "");
      r.unmount();
    }
    expect(new Set(seen).size).toBe(1);
  });

  it("each kind leads to its own list", async () => {
    asNurse();
    server.use(
      http.get(`${API}/api/v1/me/applications/:id`, () => notFound("x")),
      http.get(`${API}/api/v1/me/stories/:id`, () => notFound("x")),
      http.get(`${API}/api/v1/me/applications/:id/events/:eventId/reflection`, () => notFound("x")),
    );
    for (const [path, heading, link, href] of [
      ["/applications/a-9", "This application isn't available", "Your applications", "/applications"],
      ["/stories/s-9", "This story isn't available", "Your stories", "/stories"],
      ["/applications/a-9/events/e-9/reflection", "This reflection isn't available", "Your reflections", "/reflections"],
    ] as const) {
      const r = renderApp(path, { signedIn: true });
      expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: link })).toHaveAttribute("href", href);
      r.unmount();
    }
  });
});

describe("a temporary failure", () => {
  it("isn't called missing: Try again, which loads the record once the server answers", async () => {
    asNurse();
    let fail = true;
    server.use(http.get(`${API}/api/v1/me/notes/:id`, ({ params }) => (fail ? busy() : HttpResponse.json({
      id: params.id, title: "Shift handover", body: "SBAR first.", tags: [], links: [], pinned: false, archived: false,
      created_at: "2026-11-01T09:00:00Z", updated_at: "2026-11-01T09:00:00Z", revision: 1, career: null,
    }))));
    const { user } = renderApp("/notes/n-1", { signedIn: true });
    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.queryByText(/isn't available/)).not.toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByDisplayValue("Shift handover")).toBeInTheDocument());
  });
});

describe("public content that's gone, or retired", () => {
  it("a removed scenario or lesson leads to its library, and says there's no direct replacement for a lesson", async () => {
    server.use(
      http.get(`${API}/api/v1/scenarios/:id`, () => notFound("Scenario not found")),
      http.get(`${API}/api/v1/learn/units/:id`, () => notFound("Unit not found")),
    );
    const first = renderApp("/scenarios/old-one");
    expect(await screen.findByRole("heading", { level: 1, name: "This scenario isn't available" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse scenarios" })).toHaveAttribute("href", "/scenarios");
    expect(screen.getByText(/Attempts you made at it stay in your history/)).toBeInTheDocument();
    first.unmount();
    renderApp("/learn/old-unit");
    expect(await screen.findByRole("heading", { level: 1, name: "This lesson isn't available" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse lessons" })).toHaveAttribute("href", "/learn");
    expect(screen.getByText(/There's no direct replacement for it/)).toBeInTheDocument();
  });

  it("a retired question stays readable, says why, isn't graded, and leads to its career's questions", async () => {
    asNurse();
    server.use(http.get(`${API}/api/v1/content/question/*`, () => HttpResponse.json(contentMeta({ status: "retired", retired_reason: "The scenario was misleading." }))));
    renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    expect(await screen.findByText(/The scenario was misleading\./)).toBeInTheDocument();
    expect(screen.getByText(/This question is retired, so it isn't graded any more/)).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent("Registered Nurse questions");
  });
});

describe("signing in from a direct link", () => {
  it("a signed-out visitor goes to sign in, and the link is rechecked for whoever signs in (no loop)", async () => {
    server.use(http.get(`${API}/api/v1/me/notes/:id`, () => notFound("Note not found")));
    const { router, user } = renderApp("/notes/n-5");
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    asNurse();
    server.use(http.post(`${API}/api/v1/auth/login`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
    await user.type(await screen.findByLabelText("Email"), "nurse@example.com");
    await user.type(screen.getByLabelText("Password", { exact: true }), "CorrectHorse42");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { level: 1, name: "This note isn't available" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/notes/n-5");
  });
});
