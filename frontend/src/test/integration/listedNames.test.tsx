/**
 * Names kept in (Volume 15, prompt 7; docs/PRIVACY.md, "Names you listed"): Settings lists the names,
 * adds, changes and removes them with the account; the coach's and the interviewer's check says how
 * many were replaced; a share's preview says it before anything is created.
 */
import { render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { ListedNames } from "@/api/types";
import { CoachContext } from "@/features/workspace/CoachContext";

import { reviewPreview } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const URL = `${API}/api/v1/me/listed-names`;
const at = "2026-11-15T09:00:00Z";
const list = (names: { id: string; name: string }[]): ListedNames => ({
  items: names.map((n) => ({ ...n, created_at: at, updated_at: at })), max: 100, placeholder: "[name]",
  note: "Each of these is replaced with [name] in what leaves CodeCoach.",
});

describe("Names kept in", () => {
  it("adds, changes and removes names in Settings, kept with the account", async () => {
    let names = [{ id: "n1", name: "Mr Okafor" }];
    const sent: unknown[] = [];
    server.use(
      http.get(URL, () => HttpResponse.json(list(names))),
      http.post(URL, async ({ request }) => {
        const body = (await request.json()) as { name: string };
        sent.push({ add: body.name });
        names = [...names, { id: "n2", name: body.name.trim() }];
        return HttpResponse.json(list(names));
      }),
      http.patch(`${URL}/:id`, async ({ params, request }) => {
        const body = (await request.json()) as { name: string };
        sent.push({ change: params.id, name: body.name });
        names = names.map((n) => (n.id === params.id ? { ...n, name: body.name } : n));
        return HttpResponse.json(list(names));
      }),
      http.delete(`${URL}/:id`, ({ params }) => {
        sent.push({ remove: params.id });
        names = names.filter((n) => n.id !== params.id);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user } = renderApp("/settings", { signedIn: true });
    const row = await screen.findByRole("group", { name: "Names kept in" });
    expect(within(row).getByText(/Only the names listed here are found/)).toBeInTheDocument();
    expect(await within(row).findByText("Mr Okafor")).toBeInTheDocument();
    await user.type(within(row).getByLabelText("Add a name"), "Priya Raman");
    await user.click(within(row).getByRole("button", { name: "Add" }));
    expect(await within(row).findByText("Priya Raman")).toBeInTheDocument();
    await user.click(within(row).getByRole("button", { name: "Change: Mr Okafor" }));
    const input = within(row).getByLabelText("Change Mr Okafor");
    await user.clear(input);
    await user.type(input, "Dr Okafor");
    await user.click(within(row).getByRole("button", { name: "Save" }));
    expect(await within(row).findByText("Dr Okafor")).toBeInTheDocument();
    await user.click(within(row).getByRole("button", { name: "Remove: Priya Raman" }));
    await within(row).findByText("Dr Okafor");
    expect(await within(row).findByRole("status")).toHaveTextContent("Removed “Priya Raman”.");
    expect(sent).toEqual([{ add: "Priya Raman" }, { change: "n1", name: "Dr Okafor" }, { remove: "n2" }]);
  });

  it("the coach's check says how many listed names were replaced in what it shows", () => {
    const preview = { ...reviewPreview(), names_replaced: 2, names_note: "2 names you listed were replaced with [name]." };
    render(
      <CoachContext preview={preview} choices={{}} onChoose={() => {}} stale={null} changed={null} busy={false}
        sendLabel="Send" onSend={() => {}} onCancel={() => {}} onCheckAgain={() => {}} />,
    );
    expect(screen.getByText("2 names you listed were replaced with [name].")).toBeInTheDocument();
  });

  it("with nothing replaced, the check doesn't mention names", () => {
    render(
      <CoachContext preview={reviewPreview()} choices={{}} onChoose={() => {}} stale={null} changed={null} busy={false}
        sendLabel="Send" onSend={() => {}} onCancel={() => {}} onCheckAgain={() => {}} />,
    );
    expect(screen.queryByText(/names you listed/)).toBeNull();
  });

  it("a share's preview says how many names were replaced before the link is created", async () => {
    const sentences = [{ index: 0, text: "When Priya Raman asked me to cover two bays I checked both." }];
    server.use(http.post(`${API}/api/v1/me/shares/preview`, () => HttpResponse.json({
      source_sentences: sentences, has_followup: false,
      names: { replaced: 1, listed: 2, as_of: at, text: "1 name you listed was replaced with [name]." },
      view: {
        kind: "practice_answer", career_title: "Registered Nurse",
        question: { title: "Patient assessment under pressure", prompt: "Tell me about a time…", kind: "behavioral", difficulty: "medium" },
        excerpt: [{ index: 0, text: "When [name] asked me to cover two bays I checked both." }], total_sentences: 1, omitted_sentences: 0,
        followup: null, note: "", answered_on: "2026-11-03", ai_feedback: null, prompts: ["What was clear?"],
      },
    })));
    renderApp("/share/new?answer=a-1", { signedIn: true });
    const region = await screen.findByRole("region", { name: "Preview: what your reviewer sees" });
    expect(await within(region).findByText("1 name you listed was replaced with [name].")).toBeInTheDocument();
    expect(within(region).getByText("When [name] asked me to cover two bays I checked both.")).toBeInTheDocument();
    expect(within(region).queryByText(/Priya/)).toBeNull();
  });
});
