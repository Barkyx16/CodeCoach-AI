import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { WhiteboardAttempt, WhiteboardDraft, WhiteboardPromptList } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const asUser = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: baseUser }))));
const W = `${API}/api/v1/me/whiteboard`;

const prompts: WhiteboardPromptList = {
  note: "System-design prompts for careers that write code.",
  prompts: [{
    id: "sd-url-shortener", version: 1, title: "Design a URL shortener", objective: "Explain how a short link is created and redirected.",
    brief: "Users paste a long URL and get a short one.",
    requirements: [{ id: "store", text: "Where the mapping is stored" }, { id: "failure", text: "What happens when part of it fails" }],
  }],
};
const empty: WhiteboardDraft = {
  prompt_id: "sd-url-shortener", explanation: "", revision: 0, updated_at: null, differs_from_last_attempt: false,
  diagram: { format: "codecoach-whiteboard", version: 1, nodes: [], edges: [], notes: { assumptions: "", requirements: "", capacity: "", tradeoffs: "" } },
};
const EXPLAIN = "I store each mapping in a key-value database because lookups by short code are the only query we need to serve.";

function setup() {
  asUser();
  localStorage.clear();
  server.use(
    http.get(`${W}/prompts`, () => HttpResponse.json(prompts)),
    http.get(`${W}/sd-url-shortener/draft`, () => HttpResponse.json(empty)),
    http.get(`${W}/sd-url-shortener/attempts`, () => HttpResponse.json([])),
  );
}

async function addComponent(user: ReturnType<typeof renderApp>["user"], name: string, kind: string) {
  await user.type(screen.getByLabelText("New component"), name);
  await user.selectOptions(screen.getByRole("combobox", { name: /^Kind(?! of)/ }), kind);
  await user.click(screen.getByRole("button", { name: "Add component" }));
}

describe("whiteboard practice", () => {
  it("builds a diagram from the outline, describes it in words, and asks for an explanation before feedback", async () => {
    setup();
    let sent: Record<string, unknown> | null = null;
    server.use(http.post(`${W}/sd-url-shortener/attempts`, async ({ request }) => {
      sent = (await request.json()) as Record<string, unknown>;
      const attempt: WhiteboardAttempt = {
        id: "a1", prompt_id: "sd-url-shortener", prompt_version: 1, rubric_version: 1, digest: "x", explanation: EXPLAIN, created_at: "2026-11-03T10:00:00Z",
        diagram: sent.diagram as WhiteboardAttempt["diagram"],
        feedback: {
          checks: [{ ok: true, message: "2 components and 1 connections, all named and connected.", refs: [] }],
          rubric: [
            { requirement: "store", text: "Where the mapping is stored", addressed: true, evidence: [{ kind: "component", id: "n2", text: "URL database" }] },
            { requirement: "failure", text: "What happens when part of it fails", addressed: false, evidence: [] },
          ],
          reasoning: [{ ok: true, message: "You explained at least one choice and what it costs or gives up.", refs: [] }],
          limitations: ["It never judges how the diagram looks, and it doesn't certify a design as correct, secure or ready for production."],
        },
      };
      return HttpResponse.json(attempt, { status: 201 });
    }));
    const { user } = renderApp("/whiteboard/sd-url-shortener", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Design a URL shortener" })).toBeInTheDocument();
    expect(screen.getByText(/A good answer addresses: where the mapping is stored/)).toBeInTheDocument();

    await addComponent(user, "Shorten API", "service");
    await addComponent(user, "URL database", "database");
    await user.selectOptions(screen.getByRole("combobox", { name: /^From/ }), "n1");
    await user.selectOptions(screen.getByRole("combobox", { name: /^To/ }), "n2");
    await user.type(screen.getByLabelText("What flows"), "store mapping");
    await user.click(screen.getByRole("button", { name: "Add connection" }));
    const words = screen.getByText("The diagram in words").closest("details")!;
    expect(within(words).getByText("Shorten API → URL database: store mapping (e1)")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Diagram with 2 components and 1 connections/ })).toBeInTheDocument();

    // Delete takes its connection with it; one Undo brings both back.
    await user.click(screen.getByRole("button", { name: "Delete URL database" }));
    expect(within(words).queryByText(/Shorten API → URL database/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(within(words).getByText("Shorten API → URL database: store mapping (e1)")).toBeInTheDocument();

    const ask = screen.getByRole("button", { name: "Get feedback" });
    expect(ask).toBeDisabled(); // explain a decision first
    await user.type(screen.getByLabelText(/Explain one decision/), EXPLAIN);
    expect(ask).toBeEnabled();
    await user.click(ask);
    const fb = await screen.findByRole("region", { name: /Feedback on the attempt/ });
    expect(within(fb).getByText(/Found in: component n2/)).toBeInTheDocument();
    expect(within(fb).getByText("Not found")).toBeInTheDocument();
    expect(within(fb).getByText(/never judges how the diagram looks/)).toBeInTheDocument();
    expect((sent as unknown as { diagram: { nodes: unknown[] } }).diagram.nodes).toHaveLength(2);

    // Editing after the attempt: the feedback says which version it was about.
    await user.click(within(screen.getByRole("group", { name: "Move Shorten API" })).getByRole("button", { name: "Right" }));
    expect(within(fb).getByText(/Your diagram has changed since this attempt/)).toBeInTheDocument();
  });

  it("keeps everything when a save conflicts, and offers to save over the newer copy", async () => {
    setup();
    let saves = 0;
    server.use(http.put(`${W}/sd-url-shortener/draft`, async ({ request }) => {
      saves += 1;
      const body = (await request.json()) as { expected_revision: number; diagram: WhiteboardDraft["diagram"]; explanation: string };
      if (body.expected_revision === 0) {
        return HttpResponse.json({ error: { code: "stale_revision", message: "Saved elsewhere.", details: { current_revision: 3 } } }, { status: 409 });
      }
      return HttpResponse.json({ ...empty, diagram: body.diagram, explanation: body.explanation, revision: 4 });
    }));
    const { user } = renderApp("/whiteboard/sd-url-shortener", { signedIn: true });
    await screen.findByRole("heading", { level: 1, name: "Design a URL shortener" });
    await addComponent(user, "Gateway", "service");
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText(/This diagram was saved somewhere else \(now version 3\)/)).toBeInTheDocument();
    expect(screen.getByLabelText("Name of n1")).toHaveValue("Gateway");
    await user.click(screen.getByRole("button", { name: "Save mine as the newest" }));
    expect(await screen.findByText("Saved to your account.")).toBeInTheDocument();
    expect(saves).toBe(2);
  });

  it("refuses an imported file the server rejects, without touching the diagram", async () => {
    setup();
    server.use(http.post(`${W}/validate`, () => HttpResponse.json({ error: { code: "validation_error", message: "That file doesn't match the diagram format.", details: [] } }, { status: 422 })));
    const { user } = renderApp("/whiteboard/sd-url-shortener", { signedIn: true });
    await screen.findByRole("heading", { level: 1, name: "Design a URL shortener" });
    await addComponent(user, "Gateway", "service");
    const file = new File([JSON.stringify({ nodes: [{ id: "n1", label: "<script>", kind: "iframe", x: 0, y: 0 }] })], "bad.json", { type: "application/json" });
    fireEvent.change(screen.getByLabelText("Import a diagram file"), { target: { files: [file] } });
    await waitFor(() => expect(document.querySelector(".inline-error")).not.toBeNull());
    expect(screen.getByLabelText("Name of n1")).toHaveValue("Gateway");
    const notJson = new File(["{not json"], "broken.json", { type: "application/json" });
    fireEvent.change(screen.getByLabelText("Import a diagram file"), { target: { files: [notJson] } });
    expect(await screen.findByText("That file isn't valid JSON.")).toBeInTheDocument();
  });
});
