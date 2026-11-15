/**
 * Accepted improvements and one interview's kit in the practice packet (Volume 13, prompt 7;
 * docs/PACKET.md): offered beside questions, notes and stories; a kit's meeting link, interviewers
 * and private notes are only sent when chosen; one kit per packet; at most 20 improvements, saying
 * when more exist; the saved file is the preview, so a rename after previewing shows in a new
 * preview but not in the file already saved.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { AcceptedAction, Packet, PacketKitChoice } from "@/api/types";

import { resetExploreStore } from "../explore";
import { renderApp } from "../render";
import { API, server } from "../server";

const SECRET = "CANARY-kit-notes-7f3a9-not-a-real-secret";
const action = (id: string, title: string) => ({ id, title }) as unknown as AcceptedAction;
const kit = (id: string, title: string, privateParts = true): PacketKitChoice => ({
  event_id: id, application_id: `a-${id}`, event_title: title, role_title: "Ward nurse", employer: "Mercy General", on_date: "2026-11-20",
  has_meeting_link: privateParts, has_interviewers: privateParts, has_notes: privateParts,
});

type Body = { title: string; items: { type: string; id: string; parts: string[] }[]; keep_contact_details: boolean };
let sent: Body[] = [];
let actionTitle = "Explain why it matters";

function packetFor(body: Body): Packet {
  return {
    title: body.title, assembled_at: "2026-11-15T08:30:00Z", digest: `d-${actionTitle.length}-${body.items.length}`, redacted: 0, shortened: false, unavailable: [],
    items: body.items.map((i) => i.type === "action"
      ? {
        type: "action", id: i.id, title: actionTitle, notes: [],
        sections: [{ kind: "your_plan", heading: "What you planned", text: actionTitle, provenance: "Accepted improvement, from your practice interview on 12 November 2026 (Registered Nurse interview); read 15 November 2026: weekly, 1 of 3 weeks marked done. A plan you made, not a measure of improvement.", shortened: false }],
      }
      : {
        type: "kit", id: i.id, title: "Kit for Panel interview: Ward nurse at Mercy General",
        notes: i.parts.includes("notes") ? [] : ["Your private kit notes aren't included: choose “Private notes” to add them."],
        sections: [
          { kind: "your_kit", heading: "Checklist", text: "[x] Bring my ID badge", provenance: "Your interview-day kit for Panel interview", shortened: false },
          ...(i.parts.includes("notes") ? [{ kind: "your_kit" as const, heading: "Your private notes", text: SECRET, provenance: "Your interview-day kit", shortened: false }] : []),
        ],
      }),
  };
}

function serve({ actions = [action("act-1", "Explain why it matters")], kits = [kit("ev-1", "Panel interview"), kit("ev-2", "Final interview", false)] } = {}) {
  sent = [];
  actionTitle = "Explain why it matters";
  resetExploreStore();
  server.use(
    http.get(`${API}/api/v1/me/notes`, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50 })),
    http.get(`${API}/api/v1/me/stories`, () => HttpResponse.json([])),
    http.get(`${API}/api/v1/me/actions`, () => HttpResponse.json(actions)),
    http.get(`${API}/api/v1/me/packet/kits`, () => HttpResponse.json(kits)),
    http.post(`${API}/api/v1/me/packet/preview`, async ({ request }) => {
      const body = (await request.json()) as Body;
      sent.push(body);
      return HttpResponse.json(packetFor(body));
    }),
  );
}

async function captureDownload(click: () => Promise<void>): Promise<string> {
  let blob: Blob | null = null;
  Object.assign(URL, { createObjectURL: vi.fn((b: Blob) => { blob = b; return "blob:packet"; }), revokeObjectURL: vi.fn() });
  const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  await click();
  clickSpy.mockRestore();
  return new Promise<string>((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.readAsText(blob!);
  });
}

describe("Improvements and a kit in the packet", () => {
  it("offers both, sends a kit's private parts only when chosen, and holds one kit", async () => {
    serve();
    const { user } = renderApp("/packet", { signedIn: true });
    const kits = await screen.findByRole("group", { name: "One interview's kit" }, { timeout: 3000 });
    await within(kits).findByRole("checkbox", { name: /^Panel interview/ });
    expect(kits).toHaveTextContent("Panel interview: Ward nurse at Mercy General Has a meeting link, interviewers' names and private notes: left out unless you choose them.");
    await user.click(screen.getByRole("checkbox", { name: /^Explain why it matters/ }));
    await user.click(within(kits).getByRole("checkbox", { name: /^Panel interview/ }));
    expect(within(kits).getByRole("checkbox", { name: /^Final interview/ })).toBeDisabled();
    expect(kits).toHaveTextContent("One kit per packet.");
    const parts = screen.getByRole("group", { name: "Parts of Panel interview: Ward nurse at Mercy General" });
    expect(within(parts).getByRole("checkbox", { name: "Checklist" })).toBeChecked();
    expect(within(parts).getByRole("checkbox", { name: "Questions to ask" })).toBeChecked();
    for (const name of ["Meeting link (only if you choose it)", "Interviewers (only if you choose it)", "Private notes (only if you choose it)"]) {
      expect(within(parts).getByRole("checkbox", { name })).not.toBeChecked();
    }
    await user.click(screen.getByRole("button", { name: "Preview packet" }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]!.items).toEqual([
      { type: "action", id: "act-1", parts: ["improvement", "schedule"] },
      { type: "kit", id: "ev-1", parts: ["checklist", "questions"] },
    ]);
    const view = await screen.findByRole("article", { name: "Packet preview" });
    expect(view).not.toHaveTextContent(SECRET);
    expect(view).toHaveTextContent("Note: Your private kit notes aren't included: choose “Private notes” to add them.");
    expect(within(view).getAllByText(/^\[(Your plan|Yours)\]$/).map((x) => x.textContent)).toEqual(["[Your plan]", "[Yours]"]);
    // Choosing the private notes sends them, and only then are they there.
    await user.click(within(parts).getByRole("checkbox", { name: "Private notes (only if you choose it)" }));
    await user.click(screen.getByRole("button", { name: "Preview again" }));
    await waitFor(() => expect(sent).toHaveLength(2));
    expect(sent[1]!.items[1]).toEqual({ type: "kit", id: "ev-1", parts: ["checklist", "questions", "notes"] });
    expect(await screen.findByRole("article", { name: "Packet preview" })).toHaveTextContent(SECRET);
  });

  it("the file is the preview: a rename shows in a new preview, never in the file already saved", async () => {
    serve();
    const { user } = renderApp("/packet", { signedIn: true });
    await user.click(await screen.findByRole("checkbox", { name: /^Explain why it matters/ }, { timeout: 3000 }));
    await user.click(screen.getByRole("button", { name: "Preview packet" }));
    const first = await captureDownload(() => user.click(screen.getByRole("button", { name: "Save as a text file" })));
    expect(first).toContain("1. Explain why it matters (Accepted improvement)");
    expect(first).toContain("## What you planned [Your plan]\n(Accepted improvement, from your practice interview on 12 November 2026");
    expect(first).toContain("A plan you made, not a measure of improvement.");
    actionTitle = "Say why it matters, every time"; // renamed on the plan page
    await user.click(screen.getByRole("button", { name: "Preview again" }));
    await waitFor(() => expect(screen.getByRole("article", { name: "Packet preview" })).toHaveTextContent("Say why it matters, every time"));
    const second = await captureDownload(() => user.click(screen.getByRole("button", { name: "Save as a text file" })));
    expect(second).toContain("Say why it matters, every time");
    expect(first).not.toContain("Say why it matters"); // the saved file keeps what it showed
  });

  it("offers at most 20 improvements and says how many more there are", async () => {
    serve({ actions: Array.from({ length: 23 }, (_, i) => action(`act-${i}`, `Improvement ${i + 1}`)) });
    renderApp("/packet", { signedIn: true });
    const group = await screen.findByRole("group", { name: "Improvements you accepted" }, { timeout: 3000 });
    await waitFor(() => expect(within(group).getAllByRole("checkbox")).toHaveLength(20));
    expect(screen.getByText("3 more aren't listed: a packet holds up to 20 items, so the 20 most recent are offered.")).toBeInTheDocument();
  });
});
