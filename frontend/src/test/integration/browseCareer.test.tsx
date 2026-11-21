/**
 * Viewing a career without changing the account (Volume 9, prompt 4; NAVIGATION.md "Browsing a
 * career"). A known `?career=` decides what public pages show, for anyone; a signed-in learner
 * browsing another career is told so once, with the way back and where to change their own
 * career; browsing never saves to the profile or the goals; links within the browse context keep
 * it; unknown, differently cased and malformed values are handled the same way everywhere.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { careerSlug } from "@/features/careers/practiceTrack";

import { chooseCareer } from "../careerPicker";
import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const engineer = { ...baseUser, career_track: "software-engineer" };

/** Signs in as `who`; records every change to the account and the goals (none is expected). */
function signedIn(who: typeof baseUser) {
  const writes: string[] = [];
  server.use(
    http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: who }))),
    http.patch(`${API}/api/v1/auth/me`, () => { writes.push("profile"); return HttpResponse.json(who); }),
    http.put(`${API}/api/v1/me/goals`, () => { writes.push("goals"); return HttpResponse.json({}); }),
  );
  return writes;
}
const note = () => document.querySelector(".browse-note");

describe("the career in a link", () => {
  it("is read the same way everywhere: trimmed and lower-cased, and anything that can't be a career is none", () => {
    expect(careerSlug("registered-nurse")).toBe("registered-nurse");
    expect(careerSlug(" Registered-Nurse ")).toBe("registered-nurse");
    expect(careerSlug("../admin")).toBeNull();
    expect(careerSlug("a".repeat(65))).toBeNull();
    expect(careerSlug("")).toBeNull();
    expect(careerSlug(null)).toBeNull();
  });
});

describe("a nurse browsing coding", () => {
  it("sees coding problems, told once that their plan follows nursing, with the way back and where to change it; nothing is saved", async () => {
    const writes = signedIn(nurse);
    const { user, router } = renderApp("/problems?career=software-engineer", { signedIn: true });
    expect(await screen.findByText("Two Sum")).toBeInTheDocument();
    const line = await waitFor(() => { const n = note(); if (!n) throw new Error("no note"); return n as HTMLElement; });
    expect(line).toHaveTextContent("Viewing Software Engineer coding problems. Your plan and progress follow your own career, Registered Nurse.");
    expect(within(line).getByRole("link", { name: "Change my career" })).toHaveAttribute("href", "/settings#account");
    // Links within the browse context keep it.
    const switcher = screen.getByRole("navigation", { name: "Practice type" });
    expect(within(switcher).getByRole("link", { name: "Interview questions" })).toHaveAttribute("href", "/problems?career=software-engineer&view=questions");
    expect(screen.getByRole("link", { name: /Try a mock interview/ })).toHaveAttribute("href", "/interviews?career=software-engineer");
    // Back to their own career's practice: their questions.
    await user.click(within(line).getByRole("link", { name: "Back to Registered Nurse interview questions" }));
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
    expect(router.state.location.search).toBe("");
    expect(note()).toBeNull(); // their own career: nothing to say
    expect(writes).toEqual([]);
  });

  it("choosing another career in the library browses it: the URL changes, the account doesn't; choosing their own goes back", async () => {
    const writes = signedIn(nurse);
    const { user, router } = renderApp("/problems", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
    await chooseCareer(user, screen.getByLabelText("Show practice for"), "barista");
    expect(await screen.findByRole("heading", { name: "Barista interview questions" })).toBeInTheDocument();
    expect(router.state.location.search).toBe("?career=barista");
    expect(note()).toHaveTextContent("Viewing Barista interview questions. Your plan and progress follow your own career, Registered Nurse.");
    await chooseCareer(user, screen.getByLabelText("Show practice for"), "registered-nurse");
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
    expect(router.state.location.search).toBe("");
    expect(note()).toBeNull();
    expect(writes).toEqual([]); // never the profile, never the goals
  });

  it("an unknown career falls back to their own and says so; a differently cased one is that career; a malformed one is unknown", async () => {
    signedIn(nurse);
    const first = renderApp("/problems?career=not-a-job", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
    await waitFor(() => expect(note()).toHaveTextContent("There's no career called “not-a-job” here, so these are Registered Nurse interview questions."));
    first.unmount();

    const second = renderApp("/problems?career=Barista", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Barista interview questions" })).toBeInTheDocument();
    second.unmount();

    renderApp("/problems?career=..%2Fadmin", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
    await waitFor(() => expect(note()).toHaveTextContent("There's no career called “../admin” here"));
  });
});

describe("signed out", () => {
  it("a copied link opens that career; no 'your career' line; an unknown one says what's shown instead", async () => {
    const first = renderApp("/problems?career=registered-nurse");
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview questions" })).toBeInTheDocument();
    expect(note()).toBeNull();
    first.unmount();
    renderApp("/problems?career=nope&view=questions");
    expect(await screen.findByRole("heading", { name: "Software Engineer interview questions" })).toBeInTheDocument();
    await waitFor(() => expect(note()).toHaveTextContent("There's no career called “nope” here, so these are Software Engineer interview questions."));
  });
});

describe("lessons, scenarios and mock interviews", () => {
  it("lessons for another career say so, and their scenario link keeps that career; an unknown career shows their own lessons, not an error", async () => {
    signedIn(engineer);
    const asked: string[] = [];
    server.events.on("request:start", ({ request }) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/learn") asked.push(url.searchParams.get("track") ?? "");
    });
    const first = renderApp("/learn?career=registered-nurse", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Registered Nurse lessons" })).toBeInTheDocument();
    expect(note()).toHaveTextContent("Viewing Registered Nurse lessons. Your plan and progress follow your own career, Software Engineer.");
    expect(screen.getByRole("link", { name: "branching scenario" })).toHaveAttribute("href", "/scenarios?career=registered-nurse");
    expect(within(note() as HTMLElement).getByRole("link", { name: "Back to Software Engineer lessons" })).toHaveAttribute("href", "/learn");
    first.unmount();

    asked.length = 0;
    renderApp("/learn?career=not-a-job", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Software Engineer lessons" })).toBeInTheDocument();
    expect(note()).toHaveTextContent("There's no career called “not-a-job” here, so these are Software Engineer lessons.");
    expect(asked).not.toContain("not-a-job"); // never asked the server for a career that isn't there
    server.events.removeAllListeners();
  });

  it("a mock interview for another career says what a round started there is saved as, and its links keep that career", async () => {
    signedIn(engineer);
    renderApp("/interviews?career=registered-nurse", { signedIn: true });
    expect(await screen.findByRole("heading", { name: "Registered Nurse interview" })).toBeInTheDocument();
    expect(note()).toHaveTextContent("A round you start here is saved to your history as a Registered Nurse interview.");
    expect(screen.getByRole("link", { name: "Browse all Registered Nurse questions" })).toHaveAttribute("href", "/problems?view=questions&career=registered-nurse");
    expect(screen.getByRole("link", { name: "branching scenario" })).toHaveAttribute("href", "/scenarios?career=registered-nurse");
  });
});

describe("a deliberate change", () => {
  it("is made in Settings; afterwards the library follows the new career, with nothing to explain", async () => {
    let current = { ...nurse };
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: current }))),
      http.patch(`${API}/api/v1/auth/me`, async ({ request }) => {
        current = { ...current, ...((await request.json()) as Partial<typeof nurse>) };
        return HttpResponse.json(current);
      }),
    );
    const { user, router } = renderApp("/settings", { signedIn: true });
    const row = (await screen.findByRole("form", { name: "Career" }));
    await chooseCareer(user, within(row).getByRole("combobox"), "barista");
    await user.click(within(row).getByRole("button", { name: "Save career" }));
    expect(await within(row).findByText("Saved. Your practice questions now match this job.")).toBeInTheDocument();
    await router.navigate("/problems");
    expect(await screen.findByRole("heading", { name: "Barista interview questions" })).toBeInTheDocument();
    expect(note()).toBeNull();
  });
});
