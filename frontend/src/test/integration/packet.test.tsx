/**
 * A practice packet (Volume 11, prompt 8; docs/PACKET.md): what's sent is exactly what was chosen,
 * in the order and with the parts chosen; the saved file is made from the preview and holds what it
 * showed; a change after previewing hides saving until it's previewed again; choices that couldn't
 * be included are said, with titles; text from notes is shown as text; nothing is sent without a
 * choice; a failure says so.
 */
import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Bookmark, Packet, StorySummary } from "@/api/types";

import { resetExploreStore, store } from "../explore";
import { renderApp } from "../render";
import { API, server } from "../server";

const now = () => new Date().toISOString();
const NASTY = "<img src=x onerror=alert(1)> <script>alert(2)</script>";
const mark: Bookmark = { item_type: "question", track: "registered-nurse", ref_id: "e-good-0", title: "What good patient assessment looks like", href: "/careers/registered-nurse/questions/e-good-0", available: true, unavailable_reason: null, content_version: 1, created_at: now() };
const story = (id: string, title: string): StorySummary => ({ id, title, track: "registered-nurse", context: "work", competencies: [], tags: [], missing: [], target: null, revision: 1, archived: false, practice_count: 0, preview: "", updated_at: now() });

function packetFor(body: { title: string; items: { type: string; id: string; parts: string[] }[] }): Packet {
  return {
    title: body.title, assembled_at: "2026-11-11T08:30:00Z", digest: "abc123def4567890", redacted: 1, shortened: false,
    unavailable: body.items.filter((i) => i.id === "gone").map((i) => ({ type: i.type as Packet["unavailable"][number]["type"], id: i.id, reason: "Not found: it may have been deleted." })),
    items: body.items.filter((i) => i.id !== "gone").map((i) => ({
      type: i.type as Packet["items"][number]["type"], id: i.id, title: i.type === "story" ? "Two call lights" : i.type === "note" ? "Handover notes" : "What good patient assessment looks like", notes: [],
      sections: i.parts.map((p) => ({
        kind: i.type === "question" ? (p === "feedback" ? "automated_feedback" : p === "your_answer" ? "your_answer" : "question") : i.type === "note" ? "your_note" : "your_story",
        heading: p, text: i.type === "note" ? NASTY : `${p} text`, provenance: `${i.type} ${p} provenance`, shortened: false,
      })) as Packet["items"][number]["sections"],
    })),
  };
}

let sent: { title: string; items: { type: string; id: string; parts: string[] }[]; keep_contact_details: boolean }[] = [];
function serve({ fail = false } = {}) {
  sent = [];
  resetExploreStore();
  store.bookmarks = [mark];
  server.use(
    http.get(`${API}/api/v1/me/notes`, () => HttpResponse.json({ items: [{ id: "n1", title: "Handover notes" }, { id: "gone", title: "A deleted note" }], total: 2, page: 1, page_size: 50 })),
    http.get(`${API}/api/v1/me/stories`, () => HttpResponse.json([story("s1", "Two call lights")])),
    http.post(`${API}/api/v1/me/packet/preview`, async ({ request }) => {
      const body = (await request.json()) as (typeof sent)[number];
      sent.push(body);
      if (fail) return HttpResponse.json({ error: { code: "internal", message: "Something went wrong", request_id: "r" } }, { status: 500 });
      return HttpResponse.json(packetFor(body));
    }),
  );
}

async function captureDownload(click: () => Promise<void>): Promise<{ name: string; text: string }> {
  let blob: Blob | null = null;
  let name = "";
  const create = vi.fn((b: Blob) => { blob = b; return "blob:packet"; });
  Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() });
  const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { name = this.download; });
  await click();
  clickSpy.mockRestore();
  const text = await new Promise<string>((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.readAsText(blob!);
  });
  return { name, text };
}

describe("A practice packet", () => {
  it("sends exactly the choices in order, and the saved file is the preview", async () => {
    serve();
    const { user } = renderApp("/packet", { signedIn: true });
    expect(await screen.findByRole("button", { name: "Preview packet" }, { timeout: 3000 })).toBeDisabled(); // nothing chosen, nothing sent
    await user.click(await screen.findByRole("checkbox", { name: "What good patient assessment looks like" }));
    await user.click(screen.getByRole("checkbox", { name: "Handover notes" }));
    await user.click(screen.getByRole("checkbox", { name: "Two call lights" }));
    // The story first, with its result and without its task; the question with your answer.
    await user.click(screen.getByRole("button", { name: "Move up: Two call lights" }));
    await user.click(screen.getByRole("button", { name: "Move up: Two call lights" }));
    const parts = screen.getByRole("group", { name: "Parts of Two call lights" });
    await user.click(within(parts).getByRole("checkbox", { name: "Task" }));
    await user.click(within(screen.getByRole("group", { name: "Parts of What good patient assessment looks like" })).getByRole("checkbox", { name: "Your latest answer" }));
    await user.clear(screen.getByLabelText("Title"));
    await user.type(screen.getByLabelText("Title"), "Week 1");
    await user.click(screen.getByRole("button", { name: "Preview packet" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Preview" })).toHaveFocus());
    expect(sent).toEqual([{
      title: "Week 1", keep_contact_details: false,
      items: [
        { type: "story", id: "s1", parts: ["situation", "action", "result"] },
        { type: "question", id: "registered-nurse/e-good-0", parts: ["question", "your_answer"] },
        { type: "note", id: "n1", parts: ["note"] },
      ],
    }]);
    const view = screen.getByRole("article", { name: "Packet preview" });
    expect(view.querySelector("img, script")).toBeNull(); // a note's markup is text
    expect(within(view).getByText(NASTY)).toBeInTheDocument();
    expect(within(view).getAllByText(/\[(Yours|From the question library|Automated feedback)\]/).map((x) => x.textContent))
      .toEqual(["[Yours]", "[Yours]", "[Yours]", "[From the question library]", "[Yours]", "[Yours]"]);
    expect(screen.getByText("1 email address or phone number removed from your own text.")).toBeInTheDocument();

    const file = await captureDownload(() => user.click(screen.getByRole("button", { name: "Save as a text file" })));
    expect(file.name).toBe("week-1-2026-11-11.txt");
    expect(file.text.startsWith("Week 1\nPractice packet · assembled 2026-11-11 08:30 UTC · fingerprint abc123def4567890\n")).toBe(true);
    expect(file.text).toContain("It isn't stored in your account, sent or shared.");
    const order = ["1. Two call lights (Your story)", "2. What good patient assessment looks like (Question)", "3. Handover notes (Your note)"];
    expect(order.map((line) => file.text.indexOf(line))).toEqual([...order.map((line) => file.text.indexOf(line))].sort((a, b) => a - b));
    expect(file.text).toContain(`## note [Yours]\n(note note provenance)\n${NASTY}`);
    expect(file.text).toContain("## your_answer [Yours]");
    expect(file.text).not.toContain("task text"); // left out, so not in the file
  });

  it("hides saving after a change until it's previewed again", async () => {
    serve();
    const { user } = renderApp("/packet", { signedIn: true });
    await user.click(await screen.findByRole("checkbox", { name: "Handover notes" }, { timeout: 3000 }));
    await user.click(screen.getByRole("button", { name: "Preview packet" }));
    expect(await screen.findByRole("button", { name: "Save as a text file" })).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Two call lights" }));
    expect(screen.getByText(/Your choices changed since this preview\. Preview again before saving/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save as a text file" })).toBeNull();
    expect(screen.queryByRole("article", { name: "Packet preview" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Preview again" }));
    expect(await screen.findByRole("button", { name: "Save as a text file" })).toBeInTheDocument();
    expect(sent).toHaveLength(2);
  });

  it("names choices that couldn't be included, in the preview and the file", async () => {
    serve();
    const { user } = renderApp("/packet", { signedIn: true });
    await user.click(await screen.findByRole("checkbox", { name: "A deleted note" }, { timeout: 3000 }));
    await user.click(screen.getByRole("checkbox", { name: "Handover notes" }));
    await user.click(screen.getByRole("button", { name: "Preview packet" }));
    expect(await screen.findByText("One of your choices isn't in the packet:")).toBeInTheDocument();
    expect(screen.getAllByText("A deleted note: Not found: it may have been deleted.").length).toBe(2); // the warning and the packet
    const file = await captureDownload(() => user.click(screen.getByRole("button", { name: "Save as a text file" })));
    expect(file.text).toContain("Not included:\n- A deleted note: Not found: it may have been deleted.");
  });

  it("says when the preview can't be made, and shows nothing to save", async () => {
    serve({ fail: true });
    const { user } = renderApp("/packet", { signedIn: true });
    await user.click(await screen.findByRole("checkbox", { name: "Handover notes" }, { timeout: 3000 }));
    await user.click(screen.getByRole("button", { name: "Preview packet" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save as a text file" })).toBeNull();
    await act(async () => {});
  });
});
