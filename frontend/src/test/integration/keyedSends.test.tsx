import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { InterviewAnswer } from "@/api/types";

import { comparisonWith, nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

// Send keys and revision links on the question page (Durable Saves briefs 05 and 10). Synthetic
// accounts and answers only.

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asNurse = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))));
const QUESTION = "/careers/registered-nurse/questions/e-good-0";
const TEXT = "Last winter I noticed a patient's breathing change and called the doctor.";
type Body = { answer: string; client_request_id?: string; revises_answer_id?: string; story_id?: string; route?: "keyed" | "plain" };

function capabilities(keys: boolean | undefined) {
  server.use(http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({
    execution_enabled: false, ai_provider: "offline", guest_retention_days: 30,
    execution: { state: "not_configured", reason: "not_configured", message: "", run_available: false, submit_mode: "saved_only", checked_at: null, setup_help: null },
    ...(keys === undefined ? {} : { answer_request_keys: keys }),
  })));
}

/** Records every answer POST (and which route it used); `replies` decides each one in turn
 * (default: saved, 201; "no_route": the 404 of a server without the protected route). */
function answers(listed: InterviewAnswer[] = [], replies: Array<"lost" | "saved" | "no_route"> = []) {
  const bodies: Body[] = [];
  const reply = (route: "keyed" | "plain") => async ({ request }: { request: Request }) => {
    const body = (await request.json()) as Body;
    bodies.push({ ...body, route });
    const what = replies[bodies.length - 1];
    if (what === "lost") return HttpResponse.error();
    if (what === "no_route") return HttpResponse.json({ error: { code: "not_found", message: "Not Found", request_id: "r", details: null } }, { status: 404 });
    return HttpResponse.json({ ...nurseAnswer, id: `a-${bodies.length}`, question_id: "e-good-0", answer: body.answer,
      created_at: new Date().toISOString(), revises_answer_id: body.revises_answer_id ?? null }, { status: 201 });
  };
  server.use(
    http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json(listed)),
    http.post(`${API}/api/v1/careers/:track/questions/:id/answers/keyed`, reply("keyed")),
    http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, reply("plain")),
  );
  return bodies;
}

async function send(user: ReturnType<typeof renderApp>["user"], text?: string) {
  const box = screen.getByRole("textbox", { name: "Your answer" });
  if (text !== undefined) { await user.clear(box); await user.type(box, text); }
  await user.click(screen.getByRole("button", { name: "Get feedback" }));
}

describe("Send keys", () => {
  it("are sent to a server that keeps one answer per key; a resend after no reply keeps its key", async () => {
    asNurse();
    capabilities(true);
    const bodies = answers([], ["lost"]);
    const { user } = renderApp(QUESTION, { signedIn: true });
    await screen.findByRole("textbox", { name: "Your answer" });
    await send(user, TEXT);
    expect(await screen.findByText(/Sending it again unchanged is safe/)).toBeInTheDocument();
    await send(user); // the same text, resent
    expect(await screen.findByRole("region", { name: "Feedback" })).toBeInTheDocument();
    expect(bodies).toHaveLength(2);
    expect(bodies[0]!.client_request_id).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(bodies[1]!.client_request_id).toBe(bodies[0]!.client_request_id);
    expect(bodies.map((b) => b.route)).toEqual(["keyed", "keyed"]); // keyed sends use the protected route
    // Release Readiness brief 06: the key lives in memory only, never in browser storage or the URL.
    const key = bodies[0]!.client_request_id!;
    const stored = [localStorage, sessionStorage].flatMap((st) => Object.keys(st).map((k) => `${k}=${st.getItem(k)}`));
    expect(stored.join("\n")).not.toContain(key);
    expect(window.location.href).not.toContain(key);
  });

  it("change when the text changes, and a new try after a saved one gets a new key", async () => {
    asNurse();
    capabilities(true);
    const bodies = answers([], ["lost"]);
    const { user } = renderApp(QUESTION, { signedIn: true });
    await screen.findByRole("textbox", { name: "Your answer" });
    await send(user, TEXT);
    await screen.findByText(/isn't certain whether this answer was saved/);
    await send(user, TEXT + " Then I documented it."); // edited: a different send
    await screen.findByRole("region", { name: "Feedback" });
    await send(user, TEXT); // a deliberate new try, same words as the first
    await waitFor(() => expect(bodies).toHaveLength(3));
    expect(new Set(bodies.map((b) => b.client_request_id)).size).toBe(3);
  });

  it("aren't sent to a server that doesn't say it keeps them, and no protection is claimed", async () => {
    for (const keys of [undefined, false]) {
      asNurse();
      capabilities(keys);
      const bodies = answers([], ["lost"]);
      const { user, unmount } = renderApp(QUESTION, { signedIn: true });
      await screen.findByRole("textbox", { name: "Your answer" });
      await send(user, TEXT);
      expect(await screen.findByText(/look under “Your past answers” before sending it again/)).toBeInTheDocument();
      expect(screen.queryByText(/Sending it again unchanged is safe/)).not.toBeInTheDocument();
      expect(bodies[0]).not.toHaveProperty("client_request_id");
      expect(bodies[0]!.route).toBe("plain");
      unmount();
    }
  });

  it("are refused, not saved, by a server without the protected route, and the next send is the learner's choice", async () => {
    // Verification brief 04: capabilities came from a server that keeps keys, the POST reached one
    // that doesn't (it has no /answers/keyed: 404, nothing saved).
    asNurse();
    let asked = 0;
    server.use(http.get(`${API}/api/v1/capabilities`, () => {
      asked += 1;
      return HttpResponse.json({
        execution_enabled: false, ai_provider: "offline", guest_retention_days: 30,
        execution: { state: "not_configured", reason: "not_configured", message: "", run_available: false, submit_mode: "saved_only", checked_at: null, setup_help: null },
        ...(asked === 1 ? { answer_request_keys: true } : {}),
      });
    }));
    const bodies = answers([], ["no_route", "saved"]);
    const { user } = renderApp(QUESTION, { signedIn: true });
    await screen.findByRole("textbox", { name: "Your answer" });
    await send(user, TEXT);
    expect(await screen.findByText(/so your answer wasn't saved/)).toBeInTheDocument();
    expect(screen.queryByText(/Sending it again unchanged is safe/)).not.toBeInTheDocument();
    expect(bodies).toHaveLength(1); // no automatic resend
    expect(bodies[0]!.route).toBe("keyed");
    await send(user); // the learner sends it again
    expect(await screen.findByRole("region", { name: "Feedback" })).toBeInTheDocument();
    expect(bodies[1]!.route).toBe("plain");
    expect(bodies[1]).not.toHaveProperty("client_request_id");
  });

  it("claim nothing when the server stopped saying it keeps them since the page loaded, or can't be asked", async () => {
    // Release Readiness brief 03: a server replaced by an older one ignores the key it was sent.
    for (const later of ["older", "unreachable"] as const) {
      asNurse();
      let asked = 0;
      server.use(http.get(`${API}/api/v1/capabilities`, () => {
        asked += 1;
        if (asked > 1 && later === "unreachable") return HttpResponse.error();
        return HttpResponse.json({
          execution_enabled: false, ai_provider: "offline", guest_retention_days: 30,
          execution: { state: "not_configured", reason: "not_configured", message: "", run_available: false, submit_mode: "saved_only", checked_at: null, setup_help: null },
          ...(asked === 1 ? { answer_request_keys: true } : {}),
        });
      }));
      const bodies = answers([], ["lost", "saved"]);
      const { user, unmount } = renderApp(QUESTION, { signedIn: true });
      await screen.findByRole("textbox", { name: "Your answer" });
      await send(user, TEXT);
      expect(await screen.findByText(/look under “Your past answers” before sending it again/)).toBeInTheDocument();
      expect(screen.queryByText(/Sending it again unchanged is safe/)).not.toBeInTheDocument();
      expect(bodies[0]!.client_request_id).toBeTruthy(); // it was sent while the server said it kept them
      expect(asked).toBe(2); // asked again once, at the lost reply: a read, never a speculative write
      unmount();
    }
  });
});

const first: InterviewAnswer = { ...nurseAnswer, id: "t1", question_id: "e-good-0", answer: TEXT, created_at: "2026-11-01T09:00:00Z", score: 58 };

describe("Revision links", () => {
  it("are sent only from an explicit revision", async () => {
    asNurse();
    capabilities(true);
    const bodies = answers([first]);
    const { user } = renderApp(`${QUESTION}?answer=t1`, { signedIn: true });
    await user.click(within(await screen.findByRole("region", { name: "What next" })).getByRole("button", { name: /Revise this answer|Add to this answer/ }));
    await send(user); // the box holds try 1's text
    await screen.findByRole("region", { name: "Feedback" });
    // A plain new try afterwards isn't a revision, even though try 1 was the last one viewed.
    await send(user, "A fresh answer from scratch about a different shift.");
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[0]!.revises_answer_id).toBe("t1");
    expect(bodies[1]).not.toHaveProperty("revises_answer_id");
  });

  it("aren't sent once the revision note is hidden", async () => {
    asNurse();
    capabilities(true);
    const bodies = answers([first]);
    const { user } = renderApp(`${QUESTION}?answer=t1`, { signedIn: true });
    await user.click(within(await screen.findByRole("region", { name: "What next" })).getByRole("button", { name: /Revise this answer|Add to this answer/ }));
    await user.click(screen.getByRole("button", { name: "Hide this note" }));
    await send(user);
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).not.toHaveProperty("revises_answer_id");
  });

  it("are shown from the stored link: in the list, and in the recap with the comparison", async () => {
    asNurse();
    capabilities(true);
    const second: InterviewAnswer = { ...first, id: "t2", created_at: "2026-11-02T09:00:00Z", score: 81, revises_answer_id: "t1", comparison: comparisonWith("t1", "comparable") };
    answers([second, first]);
    renderApp(`${QUESTION}?answer=t2`, { signedIn: true });
    const recap = await screen.findByRole("region", { name: "What next" });
    expect(recap).toHaveTextContent("Try 2 revises try 1.");
    expect(recap).toHaveTextContent(/Compared with try 1, which it revises\. Comparable: the same question and version/);
    const list = screen.getByRole("heading", { name: "Your past answers" }).closest(".card") as HTMLElement;
    expect(within(list).getByRole("button", { name: /Try 2/ })).toHaveTextContent("revised from try 1");
    expect(within(list).getByRole("button", { name: /Try 1/ })).not.toHaveTextContent("revised from");
  });

  it("say so when the revised answer isn't listed, without guessing which it was", async () => {
    asNurse();
    capabilities(true);
    const orphan: InterviewAnswer = { ...first, id: "t9", revises_answer_id: "gone-or-older" };
    answers([orphan]);
    renderApp(`${QUESTION}?answer=t9`, { signedIn: true });
    const recap = await screen.findByRole("region", { name: "What next" });
    expect(recap).toHaveTextContent("Try 1 revises an earlier answer that isn't in this list.");
    expect(recap).not.toHaveTextContent(/Compared with/);
  });
});

describe("Sending an answer: exact save state", () => {
  it("words typed while it's sending stay in the box; only what was sent is cleared", async () => {
    asNurse();
    capabilities(true);
    let release!: () => void;
    const answered = new Promise<void>((r) => { release = r; });
    server.use(
      http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json([])),
      http.post(`${API}/api/v1/careers/:track/questions/:id/answers/keyed`, async ({ request }) => {
        const body = (await request.json()) as Body;
        await answered; // slow
        return HttpResponse.json({ ...nurseAnswer, id: "a-1", question_id: "e-good-0", answer: body.answer, created_at: new Date().toISOString(), revises_answer_id: null }, { status: 201 });
      }),
    );
    const { user } = renderApp(QUESTION, { signedIn: true });
    await screen.findByRole("textbox", { name: "Your answer" });
    await send(user, TEXT);
    const box = screen.getByRole("textbox", { name: "Your answer" });
    expect(box).toBeEnabled(); // the box stays editable while the answer is on its way
    await user.type(box, " Then I stayed with him.");
    release();
    expect(await screen.findByRole("region", { name: "Feedback" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Your answer" })).toHaveValue(`${TEXT} Then I stayed with him.`);
  });
});
