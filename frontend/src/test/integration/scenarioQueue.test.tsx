/**
 * Work queues in scenarios (Volume 10, prompt 7; docs/SCENARIOS.md, "Work queues"): every fact on
 * the page, reordering by keyboard (Move up / Move down, a position list) with focus kept on the
 * moved task, reasoning required, the order and reasoning kept on this device through a reload, an
 * optional timer that's labelled and never sent, and a debrief that judges each plan on what was
 * known then, names the broken constraint in words and shows other reasonable strategies.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ScenarioAttempt, ScenarioNode } from "@/api/types";

import { user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { scenarioSummary } from "../scenarios";
import { API, server } from "../server";

const node: ScenarioNode = {
  id: "plan", kind: "prioritize", title: "08:00: plan the morning", text: "Put the tasks in order.", options: [], clock: "08:00",
  tasks: [
    { id: "pick", title: "Make the pick list", facts: ["Six pickers are waiting."], minutes: 15, due: null, due_is_hard: false, consequence: null },
    { id: "labels", title: "Print the shipping labels", facts: ["The label system reads the box count from the pick list."], minutes: 10, due: null, due_is_hard: false, consequence: null },
    { id: "truck", title: "Confirm the 11:00 truck", facts: ["The slot is held until 09:00."], minutes: 5, due: "09:00", due_is_hard: true, consequence: "After 09:00 nothing ships today." },
  ],
};
const summary = { ...scenarioSummary, id: "logistics-dispatch-queue", title: "Dispatch before the 11:00 truck", regulated: false, queue: true };
const base = {
  id: "att-q", scenario: summary, version: 1, mode: "assessed", parent_id: null, retired: false,
  created_at: "2026-11-09T08:00:00Z", updated_at: "2026-11-09T08:00:00Z",
} as const;
const open: ScenarioAttempt = { ...base, status: "in_progress", current: node, steps: [], debrief: null, completed_at: null };
const plan = (order: string[]) => {
  let at = 8 * 60;
  return order.map((id) => {
    const t = node.tasks!.find((x) => x.id === id)!;
    const start = at; at += t.minutes;
    const hhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
    return { id, title: t.title, start: hhmm(start), finish: hhmm(at), due: t.due ?? null, late: t.due ? at > 9 * 60 : false };
  });
};

let sent: { node_id: string; order?: string[]; text?: string }[] = [];
function serve() {
  sent = [];
  server.use(
    http.get(`${API}/api/v1/me/scenario-attempts/att-q`, () => HttpResponse.json(open)),
    http.post(`${API}/api/v1/me/scenario-attempts/att-q/steps`, async ({ request }) => {
      const body = (await request.json()) as (typeof sent)[number];
      sent.push(body);
      const order = body.order ?? [];
      const broken = order.indexOf("labels") < order.indexOf("pick");
      const violations = broken ? [{ kind: "dependency" as const, text: "Print the shipping labels comes before Make the pick list, but it needs it first: the label system reads the box count from the pick list." }] : [];
      const step = {
        node_id: "plan", kind: "prioritize" as const, title: node.title, text: node.text, plan: plan(order), violations, response: body.text ?? null,
        follows: broken ? [] : [{ label: "Get the pickers moving first", explanation: "Six people are waiting on one list." }],
        others: [{ label: "Secure the truck first", explanation: "Five minutes protects the only truck." }],
        covered: ["Impact: who waits, and what's lost if it slips"], missing: ["Communication: who you call or update"], at: "2026-11-09T08:01:00Z",
      };
      const done: ScenarioAttempt = {
        ...base, status: "completed", current: null, steps: [step], completed_at: "2026-11-09T08:01:00Z",
        debrief: {
          outcome: broken ? "A hard constraint was broken (simulated)" : "Everything ships (simulated)", ending_title: "End", ending_text: "Done.",
          summary: "Several orders work.", path: [node.title], decisions: [], strengths: [], written: [], references: [],
          feedback_source: "All feedback here is the scenario's authored decision rules and rubric points. No AI commentary was generated.",
          disclaimer: "Outcomes are simulated consequences of a fictional case.",
          plans: [{
            step_index: 0, title: node.title, clock: "08:00", known: node.tasks!, learned_before: [], plan: step.plan, violations, follows: step.follows,
            others: step.others, response: body.text ?? "", covered: step.covered, missing: step.missing,
          }],
        },
      };
      return HttpResponse.json(done);
    }),
  );
}
const KEY = `scenario-queue-draft:${baseUser.id}:att-q:plan`;
const titles = () => within(screen.getByRole("list", { name: "Your order" })).getAllByRole("heading", { level: 3 }).map((h) => h.textContent);

describe("work queues", () => {
  it("shows every fact and reorders from the keyboard, keeping focus on the moved task", async () => {
    serve();
    const { user } = renderApp("/scenarios/attempts/att-q", { signedIn: true });
    await screen.findByRole("list", { name: "Your order" });
    expect(titles()).toEqual(["Make the pick list", "Print the shipping labels", "Confirm the 11:00 truck"]);
    expect(screen.getByText("The label system reads the box count from the pick list.")).toBeInTheDocument();
    expect(screen.getByText("must be done by 09:00")).toBeInTheDocument();
    expect(screen.getByText("After 09:00 nothing ships today.")).toBeInTheDocument();
    const up = screen.getByRole("button", { name: "Move up: Confirm the 11:00 truck" });
    up.focus();
    await user.keyboard("{Enter}");
    expect(titles()).toEqual(["Make the pick list", "Confirm the 11:00 truck", "Print the shipping labels"]);
    await waitFor(() => expect(screen.getByRole("button", { name: "Move up: Confirm the 11:00 truck" })).toHaveFocus());
    await user.keyboard("{Enter}"); // to the top: Move up is now disabled, so focus goes to Move down
    expect(titles()[0]).toBe("Confirm the 11:00 truck");
    await waitFor(() => expect(screen.getByRole("button", { name: "Move down: Confirm the 11:00 truck" })).toHaveFocus());
    expect(screen.getByText("“Confirm the 11:00 truck” is now 1 of 3.")).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Position of “Make the pick list”" }), "3");
    expect(titles()).toEqual(["Confirm the 11:00 truck", "Print the shipping labels", "Make the pick list"]);
    await waitFor(() => expect(screen.getByRole("combobox", { name: "Position of “Make the pick list”" })).toHaveFocus());
  });

  it("needs reasoning, keeps the order and reasoning through a reload, and the timer is labelled and never sent", async () => {
    serve();
    const first = renderApp("/scenarios/attempts/att-q", { signedIn: true });
    await first.user.click(await screen.findByRole("button", { name: "Move up: Confirm the 11:00 truck" }));
    await first.user.type(screen.getByLabelText("What you'd do first, and why"), "truck first");
    await first.user.click(screen.getByRole("button", { name: "Submit this order" }));
    expect(screen.getByText("Say what you'd do first and why, in a sentence or two.")).toBeInTheDocument();
    expect(sent).toHaveLength(0);
    expect(JSON.parse(localStorage.getItem(KEY)!)).toEqual({ order: ["pick", "truck", "labels"], text: "truck first" });
    first.unmount();

    serve();
    const second = renderApp("/scenarios/attempts/att-q", { signedIn: true });
    expect(await screen.findByText("Your order and reasoning were restored from this device.")).toBeInTheDocument();
    expect(titles()).toEqual(["Make the pick list", "Confirm the 11:00 truck", "Print the shipping labels"]);
    expect(screen.getByLabelText("What you'd do first, and why")).toHaveValue("truck first");
    await second.user.click(screen.getByRole("checkbox", { name: "Show a practice timer" }));
    expect(screen.getByText(/^Practice timer: 0:0\d$/)).toBeInTheDocument();
    expect(screen.getByText("The timer is optional and just for you: it isn't saved or sent, and nothing here is judged on speed.")).toBeInTheDocument();
    await second.user.type(screen.getByLabelText("What you'd do first, and why"), " because six pickers are waiting and the slot goes at 09:00");
    await second.user.click(screen.getByRole("button", { name: "Submit this order" }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual({ node_id: "plan", order: ["pick", "truck", "labels"], text: "truck first because six pickers are waiting and the slot goes at 09:00" });
    expect(JSON.stringify(sent[0])).not.toMatch(/timer|elapsed|seconds/);
    await screen.findByRole("heading", { name: "Debrief" });
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it("the debrief judges the plan on what was known, names a broken dependency in words and shows other strategies", async () => {
    serve();
    const { user } = renderApp("/scenarios/attempts/att-q", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Move up: Print the shipping labels" }));
    const hostile = '<img src=x onerror="window.__queuePwned=1"> labels first because they are quick';
    await user.type(screen.getByLabelText("What you'd do first, and why"), hostile);
    await user.click(screen.getByRole("button", { name: "Submit this order" }));
    const debrief = await screen.findByRole("region", { name: "Debrief" });
    const plans = within(debrief).getByRole("region", { name: "Your plans" });
    expect(plans).toHaveTextContent("Judged on what you knew at 08:00, before any new information. Later news doesn't count against it.");
    expect(plans).toHaveTextContent("This order breaks a hard constraint:");
    expect(plans).toHaveTextContent("Needs another task first: Print the shipping labels comes before Make the pick list");
    expect(plans).toHaveTextContent("08:00–08:10 Print the shipping labels");
    expect(plans).toHaveTextContent("Other reasonable strategies");
    expect(plans).toHaveTextContent("Secure the truck first: Five minutes protects the only truck.");
    expect(plans).toHaveTextContent("More than one order can be right here");
    expect(plans).toHaveTextContent(hostile);
    expect(document.querySelector("img[src='x']")).toBeNull();
    expect((window as { __queuePwned?: number }).__queuePwned).toBeUndefined();
    const history = screen.getByRole("list", { name: "What has happened so far" });
    expect(history).toHaveTextContent("This order breaks a hard constraint");
  });
});
