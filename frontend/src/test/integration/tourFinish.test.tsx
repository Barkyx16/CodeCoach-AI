import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Onboarding, OnboardingUpdate } from "@/api/types";
import { isFinishPending, markFinishPending } from "@/features/onboarding/finishIntent";

import { tokenResponse, user as baseUser } from "../fixtures";
import { onboardingState } from "../onboarding";
import { renderApp } from "../render";
import { API, server } from "../server";

// Finishing the introduction must survive a reload that cancels the save: the finish is noted on
// this device (account id and time only), the next load asks the server and sends "complete"
// again if the tour is still running there, and the finished tour isn't shown meanwhile.

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const QUESTION = "/careers/registered-nurse/questions/m-pressure-0";
const starter = { kind: "question" as const, track: "registered-nurse", ref: "m-pressure-0", title: "Patient assessment under pressure", difficulty: "easy", href: QUESTION, minutes: 5 };
const leftAtLastStep: Partial<Onboarding> = { tour_status: "in_progress", tour_kind: "written", tour_step: 4, resume_due: true, format: "written", starter };

/** The server's onboarding state; PATCH applies "complete" only to a running or paused tour, as the API does. */
function serverWith(initial: Partial<Onboarding>, patch?: () => Response | undefined) {
  let state = onboardingState(initial);
  const sent: OnboardingUpdate[] = [];
  server.use(
    http.get(`${API}/api/v1/me/onboarding`, () => HttpResponse.json(state)),
    http.patch(`${API}/api/v1/me/onboarding`, async ({ request }) => {
      const body = (await request.json()) as OnboardingUpdate;
      sent.push(body);
      const override = patch?.();
      if (override) return override;
      if (body.tour === "complete" && (state.tour_status === "in_progress" || state.tour_status === "paused")) {
        state = { ...state, tour_status: "completed", resume_due: false };
      }
      return HttpResponse.json(state);
    }),
  );
  return sent;
}

beforeEach(() => {
  vi.spyOn(Element.prototype, "getClientRects").mockReturnValue([{}] as unknown as DOMRectList);
  localStorage.clear();
});
afterEach(() => vi.restoreAllMocks());

describe("A finish that a reload cut off", () => {
  it("is sent again on the next load, and the finished tour isn't offered back meanwhile", async () => {
    asNurse();
    markFinishPending(nurse.id);
    const sent = serverWith(leftAtLastStep);
    renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    await waitFor(() => expect(sent).toEqual([{ tour: "complete" }]));
    await waitFor(() => expect(isFinishPending(nurse.id)).toBe(false)); // the server answered
    expect(screen.queryByText(/You left the introduction/)).not.toBeInTheDocument();
  });

  it("is sent again with React's development double effects too (as main.tsx renders)", async () => {
    asNurse();
    markFinishPending(nurse.id);
    const sent = serverWith(leftAtLastStep);
    renderApp("/dashboard", { signedIn: true, strict: true });
    await waitFor(() => expect(sent).toEqual([{ tour: "complete" }]));
    await waitFor(() => expect(isFinishPending(nurse.id)).toBe(false));
  });

  it("on the question page, the tour panel doesn't come back while it's re-sent", async () => {
    asNurse();
    markFinishPending(nurse.id);
    const sent = serverWith(leftAtLastStep);
    renderApp(QUESTION, { signedIn: true });
    expect(await screen.findByLabelText("Your answer")).toBeInTheDocument();
    expect(screen.queryByText(/Introduction · step/)).toBeNull();
    await waitFor(() => expect(sent).toEqual([{ tour: "complete" }]));
  });

  it("isn't sent when the server already has the tour finished; the note is dropped", async () => {
    asNurse();
    markFinishPending(nurse.id);
    const sent = serverWith({ tour_status: "completed", format: "written", starter });
    renderApp("/dashboard", { signedIn: true });
    await waitFor(() => expect(isFinishPending(nurse.id)).toBe(false));
    expect(sent).toEqual([]);
  });

  it("belongs to its account: another account's note does nothing here", async () => {
    asNurse();
    markFinishPending("someone-else");
    const sent = serverWith(leftAtLastStep);
    renderApp("/dashboard", { signedIn: true });
    expect(await screen.findByText("You left the introduction at step 5 of 5.")).toBeInTheDocument();
    expect(sent).toEqual([]);
    expect(isFinishPending("someone-else")).toBe(true);
  });

  it("is kept when sending it again fails without a reply (it's tried on the next load)", async () => {
    asNurse();
    markFinishPending(nurse.id);
    const sent = serverWith(leftAtLastStep, () => HttpResponse.error());
    renderApp("/dashboard", { signedIn: true });
    await waitFor(() => expect(sent).toEqual([{ tour: "complete" }]));
    await new Promise((r) => setTimeout(r, 50));
    expect(isFinishPending(nurse.id)).toBe(true);
  });

  it("is dropped when the server refuses it outright, and the server's state is shown", async () => {
    asNurse();
    markFinishPending(nurse.id);
    const sent = serverWith(leftAtLastStep, () =>
      HttpResponse.json({ error: { code: "invalid_request", message: "No.", request_id: "r", details: null } }, { status: 409 }));
    renderApp("/dashboard", { signedIn: true });
    await waitFor(() => expect(sent).toEqual([{ tour: "complete" }]));
    await waitFor(() => expect(isFinishPending(nurse.id)).toBe(false));
    expect(await screen.findByText("You left the introduction at step 5 of 5.")).toBeInTheDocument();
  });
});

describe("Finishing the tour", () => {
  it("notes the finish before sending, and the server's reply settles it", async () => {
    asNurse();
    const sent = serverWith(leftAtLastStep);
    const { user } = renderApp(QUESTION, { signedIn: true });
    const finish = await screen.findByRole("button", { name: "Finish" });
    await user.click(finish);
    await waitFor(() => expect(sent).toEqual([{ tour: "complete" }]));
    await waitFor(() => expect(isFinishPending(nurse.id)).toBe(false));
    expect(screen.queryByText(/Introduction · step/)).toBeNull();
  });

  it("keeps the note when the save gets no reply, so the next load can finish it", async () => {
    asNurse();
    const sent = serverWith(leftAtLastStep, () => HttpResponse.error());
    const { user } = renderApp(QUESTION, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Finish" }));
    await waitFor(() => expect(sent).toEqual([{ tour: "complete" }]));
    await new Promise((r) => setTimeout(r, 50));
    expect(isFinishPending(nurse.id)).toBe(true);
    expect(screen.queryByText(/Introduction · step/)).toBeNull();
  });
});
