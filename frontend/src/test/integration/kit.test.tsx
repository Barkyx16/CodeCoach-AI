import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Kit } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const asUser = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "registered-nurse" } }))));
const URL = "/applications/a1/events/e1/kit";

function kit(over: Partial<Kit> = {}): Kit {
  return {
    event_id: "e1", application_id: "a1", role_title: "Ward nurse", employer: "Mercy General", event_title: "Panel interview", event_kind: "interview",
    on_date: "2026-11-12", local_time: "10:00", timezone: "Europe/London", starts_at: "2026-11-12T10:00:00Z", format: "remote", location: "",
    meeting_link: "https://meet.example.com/secret", interviewers: [{ name: "Ms Lee", role: "Ward manager" }], notes: "Ask about parking.",
    checklist: [
      { id: "s-0", text: "Confirm the date, time and time zone", origin: "suggested", done: false, hidden: false },
      { id: "s-1", text: "Check your microphone and camera", origin: "suggested", done: false, hidden: false },
    ],
    questions: [
      { id: "s-q0", text: "What would you want the person in this role to achieve in the first three months?", group: "role", origin: "suggested", excluded: false, note: null },
      { id: "s-q2", text: "What training or onboarding is there for someone new?", group: "training", origin: "suggested", excluded: false, note: "The job description mentions “induction”: check whether it already answers this." },
    ],
    stories: [], target_title: null, saved: false, ...over,
  };
}

describe("the interview-day kit", () => {
  it("labels suggestions, says a tick is only yours, and saves the order and choices you make", async () => {
    asUser();
    let body: Record<string, unknown> | null = null;
    server.use(
      http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json(kit())),
      http.put(`${API}/api/v1/me/applications/a1/events/e1/kit`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(kit({ ...(body as Partial<Kit>), saved: true, stories: [] }));
      }),
    );
    const { user } = renderApp(URL, { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Panel interview" })).toBeInTheDocument();
    expect(screen.getAllByText("Suggested").length).toBeGreaterThan(0);
    expect(screen.getByText(/CodeCoach doesn't check your camera, connection, documents or travel/)).toBeInTheDocument();
    expect(screen.getByText(/mentions “induction”/)).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Confirm the date, time and time zone" }));
    await user.click(screen.getByRole("button", { name: /Move “What training or onboarding.*” up/ }));
    const second = screen.getAllByRole("checkbox", { name: "Ask this" })[1]!;
    await user.click(second);
    await user.type(screen.getByLabelText("Add your own question"), "How is feedback given to new nurses?");
    await user.click(screen.getAllByRole("button", { name: "Add" })[1]!);
    await user.click(screen.getByRole("button", { name: "Save kit" }));
    await waitFor(() => expect(body).not.toBeNull());
    const b = body as unknown as { checklist: { done: boolean }[]; questions: { id: string; excluded: boolean; origin: string }[] };
    expect(b.checklist[0]!.done).toBe(true);
    expect(b.questions.map((q) => q.id).slice(0, 2)).toEqual(["s-q2", "s-q0"]);
    expect(b.questions[1]!.excluded).toBe(true);
    expect(b.questions[2]!.origin).toBe("yours");
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("keeps private details out of the printout until chosen, and the preview is what prints", async () => {
    asUser();
    server.use(http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json(kit({ saved: true }))));
    const { user } = renderApp(URL, { signedIn: true });
    const pack = await screen.findByRole("article", { name: "Your interview pack" });
    expect(within(pack).getByText(/Not sent to anyone/)).toBeInTheDocument();
    expect(within(pack).queryByText(/meet\.example\.com/)).toBeNull();
    expect(within(pack).queryByText(/Ms Lee/)).toBeNull();
    expect(within(pack).queryByText(/Ask about parking/)).toBeNull();
    expect(within(pack).getByText(/What training or onboarding/)).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Meeting link (private)" }));
    await user.click(screen.getByRole("checkbox", { name: "Your notes (private)" }));
    expect(within(pack).getByText(/meet\.example\.com\/secret/)).toBeInTheDocument();
    expect(within(pack).getByText("Ask about parking.")).toBeInTheDocument();
    const printSpy = vi.spyOn(window, "print").mockImplementation(() => {});
    await user.click(screen.getByRole("button", { name: "Print…" }));
    expect(printSpy).toHaveBeenCalled();
  });

  it("is a plain not-found for someone else's interview", async () => {
    asUser();
    server.use(http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json({ error: { code: "not_found", message: "Interview not found", request_id: "r" } }, { status: 404 })));
    renderApp(URL, { signedIn: true });
    expect(await screen.findByText(/Interview not found/)).toBeInTheDocument();
  });
});
