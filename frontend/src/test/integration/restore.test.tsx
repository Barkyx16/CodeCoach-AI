import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { RestoreBatch, RestorePreview } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { failLimits, serveLimits } from "../limits";
import { renderApp } from "../render";
import { API, server } from "../server";

const P = `${API}/api/v1/me/restore`;
const FILE = JSON.stringify({ export_version: 1, notes: [{ title: "Handover tips", body: "SBAR" }] });

const preview: RestorePreview = {
  export_version: 1, exported_at: "2026-11-01T09:00:00Z", file_sha256: "abc", from_other_account: true, ignored_fields: 1, previous: [],
  categories: [
    { key: "notes", label: "Notes", found: 2, new: 1, duplicates: 1, skipped: [], samples: ["Handover tips"] },
    { key: "stories", label: "Stories", found: 0, new: 0, duplicates: 0, skipped: [], samples: [] },
    { key: "bookmarks", label: "Bookmarks", found: 1, new: 0, duplicates: 0, skipped: [{ reason: "The question isn't in the library (it's never swapped for a similar one)", count: 1 }], samples: [] },
    { key: "applications", label: "Applications and their events", found: 0, new: 0, duplicates: 0, skipped: [], samples: [] },
  ],
  not_restored: [{ key: "submissions", count: 3, reason: "Practice results and evaluations aren't restored." }],
};
const batch: RestoreBatch = { id: "b1", status: "applied", categories: ["notes"], counts: { notes: { added: 1, duplicates: 1, skipped: 0 } }, removal: null, created_at: "2026-11-03T10:00:00Z", removed_at: null };

function setup() {
  server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: baseUser }))));
}

describe("restoring from a backup", () => {
  it("previews the file, sends it unchanged, restores only what's chosen, and can remove it later", async () => {
    setup();
    let previewBody = "";
    let applied: { url: string; body: string } | null = null;
    let batches: RestoreBatch[] = [];
    server.use(
      http.post(`${P}/preview`, async ({ request }) => { previewBody = await request.text(); return HttpResponse.json(preview); }),
      http.post(P, async ({ request }) => { applied = { url: request.url, body: await request.text() }; batches = [batch]; return HttpResponse.json(batch, { status: 201 }); }),
      http.get(`${P}/batches`, () => HttpResponse.json(batches)),
      http.post(`${P}/batches/b1/remove`, () => { batches = [{ ...batch, status: "removed", removal: { removed: 0, kept_edited: 1, already_gone: 0 } }]; return HttpResponse.json(batches[0]); }),
    );
    window.confirm = () => true;
    const { user } = renderApp("/settings/restore", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Restore from a backup" })).toBeInTheDocument();
    expect(screen.getByText(/practice results, scores and feedback/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Backup file"), { target: { files: [new File([FILE], "codecoach-data.json", { type: "application/json" })] } });
    const region = await screen.findByRole("region", { name: "2. Check what would be added" });
    expect(previewBody).toBe(FILE); // the file itself, not re-serialized
    expect(within(region).getByText(/came from a different account/)).toBeInTheDocument();
    expect(within(region).getByRole("checkbox", { name: "Notes: 1 new" })).toBeChecked();
    expect(within(region).getByRole("checkbox", { name: "Bookmarks: 0 new" })).toBeDisabled();
    expect(within(region).getByText(/never swapped for a similar one/)).toBeInTheDocument();
    await user.click(within(region).getByRole("button", { name: "Restore notes" }));
    expect(await screen.findByText("Restored: 1 notes.")).toBeInTheDocument();
    expect(applied!.url).toContain("categories=notes");
    expect(applied!.body).toBe(FILE);
    await user.click(await screen.findByRole("button", { name: "Remove what this added" }));
    expect(await screen.findByText(/kept 1 you'd changed since/)).toBeInTheDocument();
  });

  it("restores collections from a version 2 file and names the ones a removal kept (Volume 15, prompt 6)", async () => {
    setup();
    const v2: RestorePreview = {
      ...preview, export_version: 2, from_other_account: false,
      categories: [
        ...preview.categories,
        { key: "collections", label: "Collections, with their items in order (version 2 files)", found: 2, new: 1, duplicates: 1, samples: ["Night shift prep"],
          skipped: [{ reason: "Items kept but shown as unavailable: retired from the library", count: 1 }] },
      ],
    };
    const done: RestoreBatch = { ...batch, categories: ["collections"], counts: { collections: { added: 1, duplicates: 1, skipped: 0 } } };
    let batches: RestoreBatch[] = [];
    let applied = "";
    server.use(
      http.post(`${P}/preview`, () => HttpResponse.json(v2)),
      http.post(P, ({ request }) => { applied = request.url; batches = [done]; return HttpResponse.json(done, { status: 201 }); }),
      http.get(`${P}/batches`, () => HttpResponse.json(batches)),
      http.post(`${P}/batches/b1/remove`, () => {
        batches = [{ ...done, status: "removed", removal: { removed: 0, kept_edited: 1, already_gone: 0, kept_collections: ["Night shift prep"] } }];
        return HttpResponse.json(batches[0]);
      }),
    );
    window.confirm = () => true;
    const { user } = renderApp("/settings/restore", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Restore from a backup" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Backup file"), { target: { files: [new File([FILE], "codecoach-data-v2.json", { type: "application/json" })] } });
    const region = await screen.findByRole("region", { name: "2. Check what would be added" });
    const box = within(region).getByRole("checkbox", { name: "Collections, with their items in order (version 2 files): 1 new" });
    expect(within(region).getByText(/retired from the library/)).toBeInTheDocument();
    await user.click(within(region).getByRole("checkbox", { name: "Notes: 1 new" })); // only the collections
    if (!(box as HTMLInputElement).checked) await user.click(box);
    await user.click(within(region).getByRole("button", { name: /^Restore / }));
    await waitFor(() => expect(applied).toContain("categories=collections"));
    await user.click(await screen.findByRole("button", { name: "Remove what this added" }));
    expect(await screen.findByText(/Collections kept because you changed them: “Night shift prep”\./)).toBeInTheDocument();
  });

  it("offers the questions saved for review with what it doesn't bring back, and restores only them (Volume 20, prompt 1)", async () => {
    setup();
    const NOTE = "Only which questions you saved comes back. Each starts its review ladder afresh, first due 1 day after the restore, as a newly saved question is. Ladders, due dates, scores, review counts and the points each was saved for aren't restored: they come from answers, and a file can't prove those happened here.";
    const withQueue: RestorePreview = {
      ...preview,
      categories: [
        ...preview.categories,
        { key: "review_queue", label: "Questions saved for review, each starting afresh", found: 3, new: 1, duplicates: 1, samples: ["Keeping a family informed"],
          skipped: [{ reason: "Removed from the queue when the file was made: left out", count: 1 }], note: NOTE },
      ],
    };
    const done: RestoreBatch = { ...batch, categories: ["review_queue"], counts: { review_queue: { added: 1, duplicates: 1, skipped: 1 } } };
    let applied = "";
    server.use(
      http.post(`${P}/preview`, () => HttpResponse.json(withQueue)),
      http.post(P, ({ request }) => { applied = request.url; return HttpResponse.json(done, { status: 201 }); }),
      http.get(`${P}/batches`, () => HttpResponse.json([])),
    );
    const { user } = renderApp("/settings/restore", { signedIn: true });
    fireEvent.change(await screen.findByLabelText("Backup file"), { target: { files: [new File([FILE], "codecoach-data.json", { type: "application/json" })] } });
    const region = await screen.findByRole("region", { name: "2. Check what would be added" });
    const box = within(region).getByRole("checkbox", { name: "Questions saved for review, each starting afresh: 1 new" });
    expect(within(region).getByText(NOTE)).toBeInTheDocument(); // what it doesn't bring back, in the server's words
    expect(within(region).getByText(/1 × Removed from the queue when the file was made: left out/)).toBeInTheDocument();
    expect(within(region).queryAllByText(/starts its review ladder afresh/)).toHaveLength(1); // only beside the queue
    await user.click(within(region).getByRole("checkbox", { name: "Notes: 1 new" }));
    if (!(box as HTMLInputElement).checked) await user.click(box);
    await user.click(within(region).getByRole("button", { name: "Restore questions saved for review" }));
    await waitFor(() => expect(applied).toContain("categories=review_queue"));
    expect(applied).not.toContain("categories=notes");
    expect(await screen.findByText("Restored: 1 questions saved for review.")).toBeInTheDocument();
  });

  it("refuses an oversized file before sending it, and shows the server's reason for a bad one", async () => {
    setup();
    let calls = 0;
    server.use(
      http.post(`${P}/preview`, () => { calls += 1; return HttpResponse.json({ error: { code: "unsupported_version", message: "Backups of version 0 can't be read; this version of CodeCoach reads version 1." } }, { status: 400 }); }),
      http.get(`${P}/batches`, () => HttpResponse.json([])),
    );
    serveLimits({ backup_file_bytes: 2 * 1024 * 1024 }); // the server's number, whatever it is
    renderApp("/settings/restore", { signedIn: true });
    const input = await screen.findByLabelText("Backup file");
    expect(await screen.findByText(/^Up to 2 MB\. The file is checked first/)).toBeInTheDocument();
    const big = new File(["x"], "big.json");
    Object.defineProperty(big, "size", { value: 3 * 1024 * 1024 });
    fireEvent.change(input, { target: { files: [big] } });
    expect(await screen.findByText("That file is larger than 2 MB, so it can't be a CodeCoach backup.")).toBeInTheDocument();
    expect(calls).toBe(0);
    fireEvent.change(input, { target: { files: [new File(['{"export_version":0}'], "old.json")] } });
    expect(await screen.findByText(/reads version 1/)).toBeInTheDocument();
    await waitFor(() => expect(calls).toBe(1));
  });

  it("when the limits can't be read, states no size and the server decides", async () => {
    setup();
    const reads = failLimits();
    let sent = 0;
    server.use(
      http.post(`${P}/preview`, () => { sent += 1; return HttpResponse.json({ error: { code: "file_too_large", message: "That file is larger than 5 MB, so it can't be a CodeCoach backup." } }, { status: 400 }); }),
      http.get(`${P}/batches`, () => HttpResponse.json([])),
    );
    renderApp("/settings/restore", { signedIn: true });
    const input = await screen.findByLabelText("Backup file");
    await waitFor(() => expect(reads.n).toBe(2), { timeout: 4000 }); // tried once more, then left
    expect(screen.getByText(/^The file is checked first; nothing changes until you choose to restore\.$/)).toBeInTheDocument();
    expect(screen.queryByText(/Up to \d/)).not.toBeInTheDocument();
    const big = new File(["x"], "big.json");
    Object.defineProperty(big, "size", { value: 6 * 1024 * 1024 });
    fireEvent.change(input, { target: { files: [big] } });
    expect(await screen.findByText(/larger than 5 MB/)).toBeInTheDocument(); // the server's own words
    expect(sent).toBe(1);
  });
});
