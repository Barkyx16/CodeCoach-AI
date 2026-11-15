/**
 * Real-interview reflections in the practice packet (Volume 14, prompt 8; docs/PACKET.md): offered
 * with only whether each has private details, and how many more there are; chosen with the usual
 * parts; what was noticed and the interviewers only sent when chosen, one by one; the preview says
 * what was left out; the saved file is the preview.
 */
import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Packet, PacketReflectionChoice } from "@/api/types";

import { resetExploreStore } from "../explore";
import { renderApp } from "../render";
import { API, server } from "../server";

const SECRET = "CANARY-reflection-notes-5e1b2-not-a-real-secret";
const choice = (id: string, title: string, over: Partial<PacketReflectionChoice> = {}): PacketReflectionChoice => ({
  event_id: id, application_id: `a-${id}`, event_title: title, role_title: "Ward nurse", employer: "Mercy General", on_date: "2026-11-12",
  updated_at: "2026-11-13T09:00:00Z", has_observations: true, has_interviewers: true, has_contact_details: false, ...over,
});

type Body = { title: string; items: { type: string; id: string; parts: string[] }[]; keep_contact_details: boolean };
let sent: Body[] = [];
function packetFor(body: Body): Packet {
  return {
    title: body.title, assembled_at: "2026-11-15T08:30:00Z", digest: `d-${body.items[0]?.parts.length}`, redacted: 0, shortened: false, unavailable: [],
    items: body.items.map((i) => ({
      type: "reflection", id: i.id, title: "Reflection on Panel interview: Ward nurse at Mercy General",
      notes: i.parts.includes("observations") ? [] : ["What you noticed isn't included: choose “What you noticed” to add it."],
      sections: [
        { kind: "your_reflection", heading: "What went well", text: "My opening about the ward", provenance: "Your reflection on Panel interview (Ward nurse at Mercy General, 12 November 2026)", shortened: false },
        ...(i.parts.includes("observations") ? [{ kind: "your_reflection" as const, heading: "What you noticed", text: `- What you thought it meant: ${SECRET}`, provenance: "Your reflection", shortened: false }] : []),
      ],
    })),
  };
}

function serve(list = { items: [choice("ev-1", "Panel interview"), choice("ev-2", "Phone screen", { has_observations: false, has_interviewers: false, has_contact_details: true })], total: 5, limit: 2 }) {
  sent = [];
  resetExploreStore();
  server.use(
    http.get(`${API}/api/v1/me/notes`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50 })),
    http.get(`${API}/api/v1/me/stories`, () => HttpResponse.json([])),
    http.get(`${API}/api/v1/me/actions`, () => HttpResponse.json([])),
    http.get(`${API}/api/v1/me/packet/reflections`, () => HttpResponse.json(list)),
    http.post(`${API}/api/v1/me/packet/preview`, async ({ request }) => {
      const body = (await request.json()) as Body;
      sent.push(body);
      return HttpResponse.json(packetFor(body));
    }),
  );
}

describe("Reflections in the packet", () => {
  it("lists them with only whether each has private details, and how many more there are", async () => {
    serve();
    renderApp("/packet", { signedIn: true });
    const list = (await screen.findByText("Your real-interview reflections", undefined, { timeout: 3000 })).closest("fieldset")!;
    const first = await within(list).findByRole("checkbox", { name: /Reflection on Panel interview: Ward nurse at Mercy General \(2026-11-12\)/ }, { timeout: 3000 });
    expect(first.closest("label")).toHaveTextContent("Has what you noticed and interviewers' names (in its kit): left out unless you choose them.");
    const second = within(list).getByRole("checkbox", { name: /Reflection on Phone screen/ });
    expect(second.closest("label")).toHaveTextContent("Looks like it has an email address or phone number: removed unless you keep them.");
    expect(screen.getByText("3 more aren't listed: the 2 most recent interviews are offered.")).toBeInTheDocument();
    expect(list).not.toHaveTextContent(SECRET);
  });

  it("sends the usual parts, what was noticed only when chosen, and says what was left out", async () => {
    serve();
    const { user } = renderApp("/packet", { signedIn: true });
    await user.click(await screen.findByRole("checkbox", { name: /Reflection on Panel interview/ }, { timeout: 3000 }));
    const parts = screen.getByRole("group", { name: /Parts of Reflection on Panel interview/ });
    expect(within(parts).getByRole("checkbox", { name: /What you noticed/ })).not.toBeChecked();
    expect(within(parts).getByRole("checkbox", { name: /What you noticed/ }).closest("label")).toHaveTextContent("(only if you choose it)");
    expect(within(parts).getByRole("checkbox", { name: /Interviewers/ }).closest("label")).toHaveTextContent("(only if you choose it)");
    await user.click(screen.getByRole("button", { name: "Preview packet" }));
    const preview = await screen.findByRole("article", { name: "Packet preview" });
    expect(sent[0]!.items).toEqual([{ type: "reflection", id: "ev-1", parts: ["questions", "went_well", "do_differently", "follow_ups", "stories"] }]);
    expect(preview).toHaveTextContent("Note: What you noticed isn't included: choose “What you noticed” to add it.");
    expect(preview).toHaveTextContent("(Your reflection)");
    expect(preview).not.toHaveTextContent(SECRET);

    await user.click(within(parts).getByRole("checkbox", { name: /What you noticed/ }));
    expect(await screen.findByText(/Your choices changed since this preview/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Preview again" }));
    expect(await screen.findByRole("article", { name: "Packet preview" })).toHaveTextContent(SECRET);
    expect(sent[1]!.items[0]!.parts).toEqual(["questions", "went_well", "do_differently", "follow_ups", "stories", "observations"]);
  });
});
