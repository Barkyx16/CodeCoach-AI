import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

// The learner journey from choosing practice to what comes after feedback (Learner Experience
// pack). Synthetic accounts and answers only.

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));

describe("A link to a question that isn't there", () => {
  it("says the question isn't available and leads back to that career's questions, without a retry that can't help", async () => {
    asNurse();
    renderApp("/careers/registered-nurse/questions/no-such-question", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "This question isn't available" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Browse Registered Nurse questions" })).toHaveAttribute("href", "/problems?view=questions");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("for another career, the way back keeps that career", async () => {
    asNurse();
    renderApp("/careers/barista/questions/no-such-question", { signedIn: true });
    expect(await screen.findByRole("link", { name: "Browse Barista questions" })).toHaveAttribute("href", "/problems?career=barista&view=questions");
  });

  it("an unknown career leads to the question library", async () => {
    server.use(http.get(`${API}/api/v1/careers/:track/questions/:id`, () =>
      HttpResponse.json({ error: { code: "not_found", message: "Career 'x' not found", request_id: "r", details: null } }, { status: 404 })));
    asNurse();
    renderApp("/careers/no-such-career/questions/e-good-0", { signedIn: true });
    expect(await screen.findByRole("link", { name: "Browse interview questions" })).toHaveAttribute("href", "/problems?view=questions");
  });

  it("a server failure is still offered a retry (it may be temporary)", async () => {
    server.use(http.get(`${API}/api/v1/careers/:track/questions/:id`, () =>
      HttpResponse.json({ error: { code: "internal_error", message: "Something went wrong.", request_id: "r", details: null } }, { status: 500 })));
    asNurse();
    renderApp("/careers/registered-nurse/questions/e-good-0", { signedIn: true });
    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("a coding problem that isn't there leads back to the problems, without a retry", async () => {
    server.use(http.get(`${API}/api/v1/problems/:slug`, () =>
      HttpResponse.json({ error: { code: "not_found", message: "Problem not found", request_id: "r", details: null } }, { status: 404 })));
    renderApp("/problems/no-such-problem", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "This problem isn't available" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse coding problems" })).toHaveAttribute("href", "/problems");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });
});
