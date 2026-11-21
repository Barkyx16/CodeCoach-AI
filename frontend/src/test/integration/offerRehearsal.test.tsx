/**
 * Offer-conversation rehearsals (Volume 10, prompt 8; docs/OFFER_REHEARSAL.md): the fictional card
 * with unknown terms in words, goals kept apart, a typed turn and a dictated turn through the shared
 * answer box (the microphone only after a click, released when leaving), a resent or stale turn,
 * the draft kept on this device, stop at any point, the debrief separating the card, the goals, the
 * scripted replies and the coaching, and a different approach that keeps the first.
 */
import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { OfferCard, OfferRehearsal } from "@/api/types";

import { user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";
import { FakeRecognition, installSpeech, spoken, uninstallSpeech } from "../speech";

const card: OfferCard = {
  id: "offer-support-analyst", version: 1, title: "A first offer for a support analyst role", role: "IT support analyst",
  employer: "Northfield Logistics (fictional)", counterpart: "Sam, the recruiter (fictional)", currency: "GBP",
  terms: [{ id: "base", label: "Base salary", value: "£31,000 per year" }, { id: "bonus", label: "Bonus", value: null }],
  phases: [{ id: "clarify", title: "Clarify the terms" }, { id: "request", title: "Make a reasoned request" }, { id: "respond", title: "Respond to the counteroffer" }],
  review_status: "Fictional case. Its numbers aren't market rates.",
};
const base = (over: Partial<OfferRehearsal> = {}): OfferRehearsal => ({
  id: "reh-1", case_id: card.id, case_version: 1, current_version: 1, card, goals: ["A higher base"], status: "in_progress", phase: "clarify",
  turns: [{ seq: 1, speaker: "counterpart", phase: "clarify", text: "Is there anything you'd like me to clarify first?", source: null, at: "2026-11-09T10:00:00Z" }],
  turns_left_in_phase: 3, parent_id: null, mode: "Authored responses (no AI)", debrief: null,
  created_at: "2026-11-09T10:00:00Z", updated_at: "2026-11-09T10:00:00Z", completed_at: null, ...over,
});
const debrief = {
  mode: "Authored responses (no AI)", facts: [], goals: ["A higher base"], pressure: false, outcome: "decline",
  request: { quote: "I'd like £34,000 because I hold the certification.", term: "Base salary", amount: "£34,000 per year", reasons: true, specific: true,
    arithmetic: { offered: "£31,000 per year", requested: "£34,000 per year", difference: "+£3,000 (+9.7%)", per_week: null } },
  counteroffer: { text: "We can offer £32,500.", arithmetic: { from: "£31,000 per year", to: "£32,500 per year", difference: "+£1,500 (+4.8%)" } },
  facts_used: [{ label: "Base salary", value: "£31,000 per year" }], unresolved: [{ label: "Bonus", asked: true }],
  claims: [{ kind: "unsupported", quote: "I have another offer", note: "“another offer” isn't on the card, so it can't be checked here." }],
  criteria: [{ id: "response", label: "A clear answer to the counteroffer", met: true, note: "You declined clearly. Declining is a complete answer." }],
  improvement: "Stick to what the card says.", phases_reached: ["Clarify the terms"], method: "Fixed rules, not AI, the same for typed and spoken answers.",
  disclaimer: "The counterpart is a script. A favourable reply here isn't evidence that a real employer would agree.", no_tax: "Amounts are before tax.",
};

let current: OfferRehearsal;
let sent: { text: string; source: string; after_seq: number; client_request_id: string }[] = [];
let staleNext = false;
function serve(start: OfferRehearsal = base()) {
  current = start;
  sent = [];
  staleNext = false;
  server.use(
    http.get(`${API}/api/v1/offer-rehearsals/cases/${card.id}`, () => HttpResponse.json(card)),
    http.post(`${API}/api/v1/me/offer-rehearsals`, async ({ request }) => {
      const body = (await request.json()) as { parent_id?: string | null };
      current = base({ id: body.parent_id ? "reh-2" : "reh-1", parent_id: body.parent_id ?? null });
      return HttpResponse.json(current, { status: 201 });
    }),
    http.get(`${API}/api/v1/me/offer-rehearsals`, () => HttpResponse.json([])),
    http.get(`${API}/api/v1/me/offer-rehearsals/:id`, () => HttpResponse.json(current)),
    http.post(`${API}/api/v1/me/offer-rehearsals/:id/turns`, async ({ request }) => {
      const body = (await request.json()) as (typeof sent)[number];
      if (staleNext) {
        staleNext = false;
        return HttpResponse.json({ error: { code: "rehearsal_advanced", message: "The conversation moved on in another tab or window. Reload to see where it is." } }, { status: 409 });
      }
      sent.push(body);
      const seq = current.turns.length;
      current = { ...current, turns_left_in_phase: current.turns_left_in_phase - 1, turns: [...current.turns,
        { seq: seq + 1, speaker: "learner", phase: current.phase, text: body.text, source: body.source as "typed", at: "2026-11-09T10:01:00Z" },
        { seq: seq + 2, speaker: "counterpart", phase: current.phase, text: "Bonus: That isn't set out in the offer you have.", source: null, at: "2026-11-09T10:01:00Z" }] };
      return HttpResponse.json(current);
    }),
    http.post(`${API}/api/v1/me/offer-rehearsals/:id/phase`, () => {
      current = { ...current, phase: "request", turns_left_in_phase: 3, turns: [...current.turns, { seq: current.turns.length + 1, speaker: "counterpart", phase: "request", text: "What would you like to discuss?", source: null, at: "2026-11-09T10:02:00Z" }] };
      return HttpResponse.json(current);
    }),
    http.post(`${API}/api/v1/me/offer-rehearsals/:id/finish`, () => {
      current = { ...current, status: "completed", turns_left_in_phase: 0, debrief: debrief as unknown as OfferRehearsal["debrief"], completed_at: "2026-11-09T10:03:00Z" };
      return HttpResponse.json(current);
    }),
  );
}
const DRAFT = (phase: string, id = "reh-1") => `offer-rehearsal-draft:${baseUser.id}:${id}:${phase}`;

afterEach(() => uninstallSpeech());

describe("offer rehearsal", () => {
  it("shows the fictional card with unknown terms in words, keeps goals apart, and starts", async () => {
    serve();
    const { user, router } = renderApp(`/offers/${card.id}`, { signedIn: true });
    const shown = await screen.findByRole("region", { name: "The offer (fictional)" });
    expect(shown).toHaveTextContent("Not stated in the offer (unknown)");
    expect(shown).toHaveTextContent("Amounts are in GBP, before tax.");
    expect(screen.getByText(/kept apart from the card, shown back in the debrief, and never sent anywhere/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Goal 1"), "A higher base");
    await user.click(screen.getByRole("button", { name: "Start the rehearsal" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/offers/rehearsals/reh-1"));
  });

  it("a typed turn, a resend after a stale tab, moving on, the draft kept on this device, and stop at any point", async () => {
    serve();
    const first = renderApp("/offers/rehearsals/reh-1", { signedIn: true });
    expect(await screen.findByText("Authored responses (no AI)")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Parts of the conversation" })).toHaveTextContent("1. Clarify the terms (now)");
    await first.user.type(screen.getByLabelText("What you'd say"), "Is there a bonus?");
    expect(localStorage.getItem(DRAFT("clarify"))).toBe("Is there a bonus?");
    first.unmount();

    const second = renderApp("/offers/rehearsals/reh-1", { signedIn: true });
    const box = await screen.findByLabelText("What you'd say");
    expect(box).toHaveValue("Is there a bonus?");
    staleNext = true;
    await second.user.click(screen.getByRole("button", { name: "Say it" }));
    expect(await screen.findByText("The conversation moved on in another tab or window. Reload to see where it is.")).toBeInTheDocument();
    expect(box).toHaveValue("Is there a bonus?"); // nothing lost
    await second.user.click(screen.getByRole("button", { name: "Say it" }));
    const transcript = await screen.findByRole("list", { name: "Transcript" });
    await waitFor(() => expect(transcript).toHaveTextContent("Bonus: That isn't set out in the offer you have."));
    expect(sent).toEqual([expect.objectContaining({ text: "Is there a bonus?", source: "typed", after_seq: 1 })]);
    expect(localStorage.getItem(DRAFT("clarify"))).toBeNull();
    expect(screen.getByText("2 turns left in this part")).toBeInTheDocument();
    await second.user.click(screen.getByRole("button", { name: "Move on: make a reasoned request" }));
    expect(await screen.findByText("What would you like to discuss?")).toBeInTheDocument();
    expect(screen.getByText(/You can stop at any point; it's practice, and nothing is sent to anyone/)).toBeInTheDocument();
    await second.user.click(screen.getByRole("button", { name: "Stop and see the debrief" }));
    const heading = await screen.findByRole("heading", { name: "Debrief" });
    await waitFor(() => expect(heading).toHaveFocus());
  });

  it("a dictated turn starts the microphone only on a click, is sent as spoken, and leaving releases the microphone", async () => {
    installSpeech();
    serve();
    const { user, router } = renderApp("/offers/rehearsals/reh-1", { signedIn: true });
    await screen.findByLabelText("What you'd say");
    expect(FakeRecognition.instances).toHaveLength(0); // nothing listens on resume
    expect(spoken).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Speak answer" }));
    FakeRecognition.latest.emit(["is there a bonus", true]);
    await user.click(screen.getByRole("button", { name: "Stop listening" }));
    FakeRecognition.latest.end();
    await user.click(screen.getByRole("button", { name: "Say it" }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual(expect.objectContaining({ text: "is there a bonus", source: "voice" }));
    await user.click(await screen.findByRole("button", { name: "Speak answer" }));
    const listening = FakeRecognition.latest;
    await act(() => router.navigate("/dashboard"));
    expect(listening.aborted).toBe(true);
  });

  it("the debrief keeps the card, your goals, the scripted replies and the coaching apart, and a different approach keeps the first", async () => {
    serve(base({ status: "completed", turns_left_in_phase: 0, debrief: debrief as unknown as OfferRehearsal["debrief"], completed_at: "2026-11-09T10:03:00Z" }));
    const { user, router } = renderApp("/offers/rehearsals/reh-1", { signedIn: true });
    const d = await screen.findByRole("region", { name: "Debrief" });
    expect(within(d).getByRole("region", { name: "The request you made" })).toHaveTextContent("£34,000 per year against the card's £31,000 per year: +£3,000 (+9.7%).");
    expect(within(d).getByRole("region", { name: "The request you made" })).toHaveTextContent("The scripted counteroffer: £31,000 per year to £32,500 per year (+£1,500 (+4.8%)).");
    expect(within(d).getByRole("region", { name: "From the card (fictional)" })).toHaveTextContent("Still unknown: Bonus (you asked; get it in writing).");
    expect(within(d).getByRole("region", { name: "From the card (fictional)" })).toHaveTextContent("Your goals (you wrote these): A higher base");
    expect(within(d).getByRole("region", { name: "Things the card doesn't support" })).toHaveTextContent("“another offer” isn't on the card");
    const coaching = within(d).getByRole("region", { name: "Coaching (qualitative)" });
    expect(coaching).toHaveTextContent("Done A clear answer to the counteroffer: You declined clearly. Declining is a complete answer.");
    expect(coaching).toHaveTextContent("One thing to try next: Stick to what the card says.");
    expect(d).toHaveTextContent("isn't evidence that a real employer would agree");
    expect(screen.queryByLabelText("What you'd say")).not.toBeInTheDocument();
    await user.click(within(d).getByRole("button", { name: "Try a different approach" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/offers/rehearsals/reh-2"));
    expect(await screen.findByText("A different approach: your earlier rehearsal is kept")).toBeInTheDocument();
  });

  it("renders what the learner said as text", async () => {
    const hostile = '<img src=x onerror="window.__offerPwned=1"> is there a bonus';
    serve(base({ turns: [...base().turns, { seq: 2, speaker: "learner", phase: "clarify", text: hostile, source: "typed", at: "2026-11-09T10:01:00Z" }] }));
    renderApp("/offers/rehearsals/reh-1", { signedIn: true });
    expect(await screen.findByText(hostile)).toBeInTheDocument();
    expect(document.querySelector("img[src='x']")).toBeNull();
    expect((window as { __offerPwned?: number }).__offerPwned).toBeUndefined();
  });
});
