/**
 * Search your saved work (Volume 11, prompt 3; docs/WORKSPACE_SEARCH.md): results with their kind,
 * title, snippet and status, opened by the right routes; the words sent in a request body, never in
 * an address; typing debounced; an older answer never shown for a newer search; another account
 * never shown the first one's words or results; markup shown as text; filters and archived opt-in;
 * Back restoring the search; honest empty, failing and limited states.
 */
import { act, screen, waitFor, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";

import type { WorkspaceHit, WorkspaceSearch } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const hour = (n: number) => new Date(Date.now() - n * 3_600_000).toISOString();
const hit = (over: Partial<WorkspaceHit>): WorkspaceHit => ({
  type: "note", id: "n-1", parent_id: null, title: "Sepsis signs", snippet: null, matched: ["title"], state: null, detail: null, tags: [], at: hour(1), ...over,
});
const found = (items: WorkspaceHit[], words: string[], counts?: Record<string, number>): WorkspaceSearch => ({
  items, words, capped: [], unavailable: [],
  counts: counts ?? { notes: items.filter((i) => i.type === "note").length, stories: items.filter((i) => i.type === "story").length, kits: items.filter((i) => i.type === "kit").length, applications: items.filter((i) => i.type === "application").length },
});

let sent: { url: string; body: { q: string; kinds?: string[]; include_archived?: boolean } }[] = [];
let addresses: string[] = [];
function serve(answer: (body: { q: string }) => WorkspaceSearch | Promise<WorkspaceSearch> | Response) {
  sent = [];
  addresses = [];
  server.events.removeAllListeners();
  server.events.on("request:start", ({ request }) => { addresses.push(request.url); });
  server.use(http.post(`${API}/api/v1/me/search`, async ({ request }) => {
    const body = (await request.json()) as { q: string };
    sent.push({ url: request.url, body });
    const out = await answer(body);
    return out instanceof Response ? out : HttpResponse.json(out);
  }));
}
afterEach(() => { server.events.removeAllListeners(); });

const box = () => screen.findByLabelText("Words to find");
const status = () => within(screen.getByRole("region", { name: "Results" })).getByRole("status");

describe("Search your saved work", () => {
  it("finds each kind, links it to its own page, and sends the words only in the request body", async () => {
    serve(() => found([
      hit({ type: "story", id: "s-1", title: "Night shift otter", matched: ["title"], snippet: "A busy ward" }),
      hit({ type: "note", id: "n-1", title: "Sepsis signs", snippet: "the otter mnemonic helps", matched: ["text"], state: "pinned" }),
      hit({ type: "kit", id: "ev-1", parent_id: "app-1", title: "Interview-day kit: Panel interview", detail: "Otter Health · on 2026-12-15", matched: ["employer"] }),
      hit({ type: "application", id: "app-1", title: "Ward nurse at Otter Health", detail: "Stage: Saved", state: "archived" }),
    ], ["otter"]));
    const { user } = renderApp("/search", { signedIn: true });
    await user.type(await box(), "otter");
    const list = await within(screen.getByRole("region", { name: "Results" })).findByRole("list");
    expect(status()).toHaveTextContent("4 found: 1 note, 1 story, 1 kit, 1 application.");
    const links = within(list).getAllByRole("link");
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["/stories/s-1", "/notes/n-1", "/applications/app-1/events/ev-1/kit", "/applications/app-1"]);
    expect(links[1]).toHaveTextContent(/Note\s*Pinned.*Sepsis signs.*the otter mnemonic helps.*saved .* ago · found in text/);
    expect(links[3]).toHaveTextContent("Archived");
    expect(links[0]!.querySelector("mark")).toHaveTextContent("otter"); // the word, marked in the title
    expect(links[1]!.querySelector("mark")).toHaveTextContent("otter"); // and in the snippet
    expect(sent.map((s) => s.body)).toEqual([{ q: "otter", kinds: ["notes", "stories", "kits", "applications"], include_archived: false, limit: 20 }]);
    expect(addresses.some((u) => u.includes("otter"))).toBe(false); // never in an address
    expect(window.location.href).not.toContain("otter");
  });

  it("waits for typing to pause, and shows only the newest search's answer", async () => {
    serve(async ({ q }) => {
      if (q === "ott") await delay(400); // the older search answers last
      return found([hit({ title: q === "ott" ? "Old answer" : "New answer" })], [q]);
    });
    const { user } = renderApp("/search", { signedIn: true });
    await user.type(await box(), "ott");
    await waitFor(() => expect(sent).toHaveLength(1)); // one request for three keystrokes
    await user.type(await box(), "er");
    expect(await screen.findByRole("link", { name: /New answer/ })).toBeInTheDocument();
    await act(() => delay(500)); // the older answer has arrived by now
    expect(screen.queryByText("Old answer")).not.toBeInTheDocument();
    expect(sent.map((s) => s.body.q)).toEqual(["ott", "otter"]);
  });

  it("another account never sees the first one's words or results, even when an answer arrives late", async () => {
    const bea = { ...baseUser, id: "u-bea", email: "bea@example.com", display_name: "Bea" };
    let release: () => void = () => {};
    serve(async ({ q }) => {
      if (q === "adasecret") await new Promise<void>((r) => { release = r; });
      return found([hit({ title: q === "adasecret" ? "Ada's private note" : "Bea's note" })], [q]);
    });
    server.use(http.post(`${API}/api/v1/auth/login`, () => HttpResponse.json(tokenResponse({ user: bea }))));
    const { user, router } = renderApp("/search", { signedIn: true });
    await user.type(await box(), "adasecret");
    await waitFor(() => expect(sent).toHaveLength(1));
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(router.state.location.pathname).not.toBe("/search"));
    await act(() => router.navigate("/login"));
    await user.type(await screen.findByLabelText("Email"), bea.email);
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.state.location.pathname).not.toBe("/login"));
    await act(() => router.navigate("/search"));
    expect(await box()).toHaveValue(""); // Bea's search page starts empty
    release(); // Ada's answer arrives now, after the switch
    await act(() => delay(50));
    expect(screen.queryByText("Ada's private note")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("adasecret")).not.toBeInTheDocument();
  });

  it("shows markup as the characters typed", async () => {
    serve(() => found([hit({ title: "<img src=x onerror=alert(1)> plan", snippet: "<b>bold</b> <script>alert(2)</script>" })], ["plan"]));
    const { user } = renderApp("/search", { signedIn: true });
    await user.type(await box(), "plan");
    const link = await screen.findByRole("link", { name: /onerror/ });
    expect(link).toHaveTextContent("<img src=x onerror=alert(1)> plan");
    expect(link).toHaveTextContent("<b>bold</b> <script>alert(2)</script>");
    expect(link.querySelector("img, b, script")).toBeNull();
  });

  it("searches only the kinds chosen, includes archived only when asked, and needs at least one kind", async () => {
    serve(({ q }) => found([], [q]));
    const { user } = renderApp("/search", { signedIn: true });
    await user.type(await box(), "otter");
    await waitFor(() => expect(sent).toHaveLength(1));
    await user.click(screen.getByRole("checkbox", { name: "Notes" }));
    await user.click(screen.getByRole("checkbox", { name: "Include archived" }));
    await waitFor(() => expect(sent.at(-1)!.body).toMatchObject({ kinds: ["stories", "kits", "applications"], include_archived: true }));
    for (const name of ["Stories", "Interview-day kits"]) await user.click(screen.getByRole("checkbox", { name }));
    await act(() => delay(400));
    const before = sent.length;
    await user.click(screen.getByRole("checkbox", { name: "Applications" })); // the last one
    expect(status()).toHaveTextContent("Choose at least one kind of record to look in.");
    await act(() => delay(400));
    expect(sent).toHaveLength(before); // nothing to search, nothing sent
    await user.click(screen.getByRole("checkbox", { name: "Notes" }));
    expect(await screen.findByText("Nothing saved to your account matches those words.")).toBeInTheDocument();
  });

  it("comes back to the same search after opening a result, without the words in the address", async () => {
    serve(() => found([hit({ type: "story", id: "s-1", title: "Night shift otter" })], ["otter"]));
    server.use(http.get(`${API}/api/v1/me/stories/s-1`, () => HttpResponse.json({ error: { code: "not_found", message: "Story not found", request_id: "r", details: null } }, { status: 404 })));
    const { user, router } = renderApp("/search", { signedIn: true });
    await user.type(await box(), "otter");
    await user.click(screen.getByRole("checkbox", { name: "Include archived" }));
    await user.click(await screen.findByRole("link", { name: /Night shift otter/ }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/stories/s-1"));
    expect(await screen.findByText(/no longer available|isn't available|not found/i, undefined, { timeout: 3000 })).toBeInTheDocument(); // deleted since: the story's own recovery page
    await act(() => router.navigate(-1));
    expect(await box()).toHaveValue("otter");
    expect(screen.getByRole("checkbox", { name: "Include archived" })).toBeChecked();
    expect(await screen.findByRole("link", { name: /Night shift otter/ })).toBeInTheDocument();
    expect(router.state.location.search).toBe("");
  });

  it("doesn't restore a search saved in this tab by another account", async () => {
    serve(({ q }) => found([], [q]));
    const { router } = renderApp("/dashboard", { signedIn: true });
    await screen.findByRole("heading", { level: 1 });
    await act(() => router.navigate("/search", { state: { workspaceSearch: { userId: "someone-else", q: "their words", kinds: ["notes"], archived: true } } }));
    expect(await box()).toHaveValue("");
    expect(screen.getByRole("checkbox", { name: "Include archived" })).not.toBeChecked();
    expect(sent).toEqual([]);
  });

  it("says when the words are too short, a kind couldn't be searched, or there have been too many searches", async () => {
    let mode = "partial";
    serve(({ q }) => (mode === "limited"
      ? HttpResponse.json({ error: { code: "rate_limited", message: "Too many", request_id: "r", details: { retry_after_seconds: 20 } } }, { status: 429, headers: { "Retry-After": "20" } })
      : { ...found([hit({ type: "story", id: "s-2", title: "Otter story" })], [q]), unavailable: ["notes"], capped: ["stories"] }));
    const { user } = renderApp("/search", { signedIn: true });
    await user.type(await box(), "o");
    expect(status()).toHaveTextContent("Type at least 2 characters.");
    await act(() => delay(400));
    expect(sent).toEqual([]);
    await user.type(await box(), "tter");
    expect(await screen.findByText("Your notes couldn't be searched just now; the rest were.")).toBeInTheDocument();
    expect(screen.getByText("Lots of stories match; add a word to narrow it down.")).toBeInTheDocument();
    mode = "limited";
    await user.type(await box(), " x");
    expect(await screen.findByRole("alert")).toHaveTextContent("That's a lot of searches in a minute.");
  });

  it("is in Go to… and the Library menu", async () => {
    const { user } = renderApp("/dashboard", { signedIn: true });
    await screen.findByRole("heading", { level: 1 });
    await user.click(screen.getByRole("button", { name: "Library" }));
    expect(await screen.findByRole("link", { name: /Search/ })).toHaveAttribute("href", "/search");
  });
});
