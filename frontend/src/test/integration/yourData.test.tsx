/**
 * "Your data" (Volume 10, prompt 10; docs/YOUR_DATA.md): a device copy told apart from an account
 * save; one chosen copy removed while the account, the sign-in, other accounts' copies and device
 * settings stay; interview drafts listed only for this account's interviews; pending actions
 * removed with their consequence said; storage that refuses; counts without content; processing
 * described truthfully, including what isn't known; export and deletion through their own flows.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { vi } from "vitest";

import type { DataSummary } from "@/api/types";
import { DEVICE_USER_KEY } from "@/auth/deviceUser";
import { DISPLAY_KEY } from "@/features/display/displayPrefs";
import { storyDraftKey } from "@/features/stories/storyForm";
import { answerDraftKey } from "@/features/dashboard/savedWork";
import { keyForIntent, listIntents } from "@/lib/pendingIntents";

import { user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const ME = baseUser.id;
const ANSWER = answerDraftKey(ME, "registered-nurse", "m-walk-0");
const STORY = storyDraftKey(ME, "story-1");
const OTHER = answerDraftKey("someone-else", "registered-nurse", "m-walk-0");
const MINE_IV = "codecoach.round.iv-mine.0";
const THEIR_IV = "codecoach.round.iv-theirs.0";
const SECRET = "PRIVATE-HERON-4410";

const summary: DataSummary = {
  categories: [
    { key: "account", group: "account", label: "Your account: email, name and career, and a hash of your password (never the password)", count: 1, note: null },
    { key: "answers", group: "work", label: "Written and dictated answers, with their feedback and retries", count: 4, note: "A dictated answer is kept as the text you sent. No audio reaches CodeCoach." },
    { key: "stories", group: "work", label: "Stories, with their earlier versions", count: 2, note: null },
    { key: "notes", group: "work", label: "Notes", count: 0, note: null },
    { key: "shares", group: "sharing", label: "Answers you shared through a link, with the feedback they received", count: 0, note: null },
  ],
};

let requests: string[] = [];
function serve(provider = "offline") {
  requests = [];
  server.events.removeAllListeners();
  server.events.on("request:start", ({ request }) => { requests.push(`${request.method} ${new URL(request.url).pathname}`); });
  server.use(
    http.get(`${API}/api/v1/me/data-summary`, () => HttpResponse.json(summary)),
    http.get(`${API}/api/v1/ai/usage`, () => HttpResponse.json({ used_today: 0, daily_limit: 50, remaining_today: 50, provider })),
    http.get(`${API}/api/v1/interviews`, () => HttpResponse.json({ items: [{ id: "iv-mine", status: "finished" }], total: 1, page: 1, page_size: 100 })),
  );
}

function seed() {
  localStorage.setItem(ANSWER, `I checked the patient's observations first ${SECRET}`);
  localStorage.setItem(STORY, JSON.stringify({ form: { title: "Night shift", situation: SECRET }, base: 3, at: "2026-11-09T10:00:00Z" }));
  localStorage.setItem(OTHER, "Another account's unsent answer");
  localStorage.setItem(MINE_IV, "My unsent interview answer");
  localStorage.setItem(THEIR_IV, "Someone else's interview answer");
  localStorage.setItem(DISPLAY_KEY, JSON.stringify({ theme: "dark" }));
}

afterEach(() => { vi.restoreAllMocks(); server.events.removeAllListeners(); });

describe("Your data", () => {
  it("tells a device copy from an account save and removes only the one chosen, leaving the account and sign-in", async () => {
    serve();
    seed();
    const { user } = renderApp("/settings/data", { signedIn: true });
    const device = await screen.findByRole("region", { name: "On this device" });
    const unsent = within(device).getByRole("heading", { name: "Not sent yet: only on this device" }).parentElement!;
    expect(unsent).toHaveTextContent("Written answer, not sent");
    expect(within(unsent).getByRole("link", { name: "Open: Written answer, not sent" })).toHaveAttribute("href", "/careers/registered-nurse/questions/m-walk-0");
    const edits = within(device).getByRole("heading", { name: "Unsaved changes: your account keeps the last saved version" }).parentElement!;
    expect(edits).toHaveTextContent("Story changes, not saved yet");
    // Only this account's interview, and nothing's content.
    await waitFor(() => expect(device).toHaveTextContent("Interview answer, not sent"));
    expect(within(device).getAllByText("Interview answer, not sent")).toHaveLength(1);
    expect(device).not.toHaveTextContent(SECRET);
    expect(document.body).not.toHaveTextContent(SECRET);
    const account = screen.getByRole("region", { name: "Saved to your account" });
    expect(await within(account).findByText(/Stories, with their earlier versions/)).toBeInTheDocument();
    expect(account).toHaveTextContent("No audio reaches CodeCoach.");

    await user.click(within(device).getByRole("checkbox", { name: /Written answer, not sent/ }));
    await user.click(within(device).getByRole("button", { name: "Review removal (1)" }));
    const review = screen.getByRole("region", { name: "Before you remove this" });
    expect(review).toHaveTextContent("What stays: Nothing: it was never sent, so removing it deletes this text.");
    await user.click(within(review).getByRole("button", { name: "Remove it from this device" }));
    expect(await screen.findByText("Removed 1 item from this browser. Everything saved to your account is unchanged.")).toHaveFocus();

    expect(localStorage.getItem(ANSWER)).toBeNull();
    for (const kept of [STORY, OTHER, MINE_IV, THEIR_IV, DISPLAY_KEY, DEVICE_USER_KEY]) expect(localStorage.getItem(kept), kept).not.toBeNull();
    expect(within(device).queryByText("Written answer, not sent")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Your data" })).toBeInTheDocument(); // still signed in, still here
    // Nothing on the server was touched (restoring the session on load is the only other request).
    expect(requests.filter((r) => !r.startsWith("GET") && r !== "POST /api/v1/auth/refresh")).toEqual([]);
    // Counts, never content: no list of notes, stories, answers or applications was fetched to show them.
    expect(requests.some((r) => /\/me\/(notes|stories|applications)|\/answers/.test(r))).toBe(false);
  });

  it("lists a pending action with what removing it means, and removes it without touching drafts", async () => {
    serve();
    localStorage.setItem(ANSWER, "Unsent");
    keyForIntent(ME, "submission", "two-sum", "print-1");
    keyForIntent(ME, "hint", "valid-anagram", "print-2"); // not chosen: stays
    const { user } = renderApp("/settings/data", { signedIn: true });
    const device = await screen.findByRole("region", { name: "On this device" });
    const box = within(device).getByRole("checkbox", { name: /Code submission · two-sum, sent/ });
    await user.click(box);
    await user.click(screen.getByRole("button", { name: "Review removal (1)" }));
    expect(screen.getByRole("region", { name: "Before you remove this" })).toHaveTextContent("sending again may save it twice");
    await user.click(screen.getByRole("button", { name: "Remove it from this device" }));
    expect(await screen.findByText(/Removed 1 item from this browser/)).toBeInTheDocument();
    expect(listIntents(ME).map((i) => `${i.kind}:${i.target}`)).toEqual(["hint:valid-anagram"]);
    expect(localStorage.getItem(ANSWER)).toBe("Unsent");
  });

  it("says so when this browser won't let it read or remove what's stored", async () => {
    serve();
    localStorage.setItem(ANSWER, "Unsent");
    const removeItem = vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new DOMException("denied", "SecurityError"); });
    const first = renderApp("/settings/data", { signedIn: true });
    await first.user.click(await screen.findByRole("checkbox", { name: /Written answer, not sent/ }));
    await first.user.click(screen.getByRole("button", { name: "Review removal (1)" }));
    await first.user.click(screen.getByRole("button", { name: "Remove it from this device" }));
    expect(await screen.findByText(/1 couldn't be removed: this browser refused the change\./)).toBeInTheDocument();
    expect(screen.getByText(/Removed 0 items/)).toBeInTheDocument();
    removeItem.mockRestore();
    first.unmount();

    serve();
    vi.spyOn(Storage.prototype, "length", "get").mockImplementation(() => { throw new DOMException("denied", "SecurityError"); });
    renderApp("/settings/data", { signedIn: true });
    expect(await screen.findByText(/This browser isn't letting CodeCoach use its storage here/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Review removal/ })).not.toBeInTheDocument();
  });

  it("describes processing as it is: built in, or an outside provider whose retention isn't known", async () => {
    serve("offline");
    const first = renderApp("/settings/data", { signedIn: true });
    const where = await screen.findByRole("region", { name: "Where your words go when they're processed" });
    expect(await within(where).findByText(/nothing you write is sent to an AI provider/)).toBeInTheDocument();
    expect(where).toHaveTextContent("CodeCoach receives only the text you send, never audio.");
    expect(where).toHaveTextContent("This browser doesn't offer dictation here.");
    expect(where).toHaveTextContent("Read aloud is off on this device.");
    first.unmount();

    serve("anthropic");
    renderApp("/settings/data", { signedIn: true });
    const where2 = await screen.findByRole("region", { name: "Where your words go when they're processed" });
    expect(await within(where2).findByText(/How long Anthropic \(Claude\) keeps what it receives:/)).toHaveTextContent("not known to CodeCoach");
    expect(where2).toHaveTextContent("Deleting your account here can't erase the provider's copy.");
  });

  it("sends export and deletion to their own flows, which still ask for the password", async () => {
    serve();
    const { user, router } = renderApp("/settings/data", { signedIn: true });
    await user.click(await screen.findByRole("link", { name: "Delete my account" }));
    await waitFor(() => expect(router.state.location.hash).toBe("#danger"));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Danger zone" })).toHaveFocus());
    const danger = screen.getByRole("region", { name: "Danger zone" });
    expect(within(danger).getByRole("button", { name: "Delete my account" })).toBeDisabled();
    expect(within(danger).getByLabelText("Password")).toBeInTheDocument();
    router.navigate("/settings/data");
    await user.click(await screen.findByRole("link", { name: "Download my data" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Privacy & data" })).toHaveFocus());
    expect(screen.getByRole("button", { name: /Download my data/ })).toBeInTheDocument();
  });
});
