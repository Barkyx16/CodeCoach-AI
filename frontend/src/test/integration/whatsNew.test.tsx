/**
 * What's new (Volume 11, prompt 10; docs/WHATS_NEW.md): a fresh account, changes already seen, a
 * newer release than the one seen, a change another career can't use, a server that doesn't run
 * code, storage that refuses, another account signing in on the same browser, and an answer in
 * progress that the header's dot doesn't interrupt.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { User } from "@/api/types";
import { ENTRIES } from "@/features/whatsnew/releases";
import { seenKey } from "@/features/whatsnew/whatsNew";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse: User = { ...baseUser, id: "u-nurse", career_track: "registered-nurse" };
const engineer: User = { ...baseUser, id: "u-eng", career_track: "software-engineer" };
const asUser = (u: User) => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: u }))));
const seen = (u: User, release: number) => window.localStorage.setItem(seenKey(u.id), JSON.stringify({ v: 1, seen: release }));
const stored = (u: User) => window.localStorage.getItem(seenKey(u.id));

const latest = ENTRIES.filter((e) => e.release === 2);
const nonCoding = ENTRIES.filter((e) => e.audience !== "coding");
/** The header's link: "What's new", plus ", N new" for screen readers when there's something new. */
const headerLink = (name: string | RegExp) => screen.findByRole("link", { name }, { timeout: 3000 });
const section = (name: RegExp) => screen.getByRole("region", { name });

afterEach(() => { vi.restoreAllMocks(); server.events.removeAllListeners(); });

describe("What's new", () => {
  it("a fresh account: this release's changes are new, opening the page marks them seen, and they stay listed", async () => {
    asUser(nurse);
    const { user } = renderApp("/help", { signedIn: true });
    await user.click(await headerLink(`What's new, ${latest.length} new`));
    expect(await screen.findByRole("heading", { level: 1, name: "What's new" })).toBeInTheDocument();
    const current = section(/^In this version: A more useful personal workspace/);
    expect(within(current).getAllByText("New")).toHaveLength(latest.length);
    expect(within(section(/^Earlier: Practice labs and career tools/)).queryAllByText("New")).toHaveLength(0);
    expect(screen.getByText(new RegExp(`^${latest.length} new since you last looked`))).toBeInTheDocument();
    expect(within(current).getByRole("link", { name: "Open Search your saved work" })).toHaveAttribute("href", "/search");
    // Seen now: the dot goes, the page keeps its marks for this visit, and the entries stay.
    expect(await headerLink("What's new")).toBeInTheDocument();
    expect(JSON.parse(stored(nurse)!)).toEqual({ v: 1, seen: 2 });
    expect(within(current).getAllByText("New")).toHaveLength(latest.length);
  });

  it("changes already seen: no dot, nothing marked new, everything still listed", async () => {
    asUser(nurse);
    seen(nurse, 2);
    renderApp("/whats-new", { signedIn: true });
    expect(await screen.findByText(/^Nothing new since you last looked/, undefined, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.queryAllByText("New")).toHaveLength(0);
    expect(screen.getByRole("link", { name: "What's new" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(ENTRIES.length);
  });

  it("a newer release than the one seen: only its changes are new; a value from a newer build isn't lowered", async () => {
    asUser(nurse);
    seen(nurse, 1);
    const first = renderApp("/help", { signedIn: true });
    expect(await headerLink(`What's new, ${latest.length} new`)).toBeInTheDocument();
    first.unmount();

    seen(nurse, 0); // seen before anything listed here: every change this career can use is new
    const second = renderApp("/help", { signedIn: true });
    expect(await headerLink(`What's new, ${nonCoding.length} new`)).toBeInTheDocument();
    second.unmount();

    seen(nurse, 7); // written by a newer build of the app in this browser
    renderApp("/whats-new", { signedIn: true });
    expect(await screen.findByText(/^Nothing new since you last looked/, undefined, { timeout: 3000 })).toBeInTheDocument();
    expect(JSON.parse(stored(nurse)!)).toEqual({ v: 1, seen: 7 });
  });

  it("the header asks for the careers list only when a coding-only change is among the unseen", async () => {
    const asked: string[] = [];
    server.events.on("request:start", ({ request }) => { asked.push(new URL(request.url).pathname); });
    asUser(nurse);
    seen(nurse, 1); // the unseen changes are this release's: none is coding-only
    const first = renderApp("/help", { signedIn: true });
    expect(await headerLink(`What's new, ${latest.length} new`)).toBeInTheDocument();
    expect(asked).not.toContain("/api/v1/careers");
    first.unmount();
    seen(nurse, 0); // now the earlier release's coding-only changes are unseen too
    renderApp("/help", { signedIn: true });
    expect(await headerLink(`What's new, ${nonCoding.length} new`)).toBeInTheDocument();
    expect(asked).toContain("/api/v1/careers");
  });

  it("a change for coding careers: a link for an engineer (with the server's note), the reason for a nurse", async () => {
    asUser(engineer);
    const eng = renderApp("/whats-new", { signedIn: true });
    const lab = (await screen.findByRole("heading", { level: 3, name: "Debugging lab" }, { timeout: 3000 })).closest("li")!;
    await waitFor(() => expect(within(lab).getByRole("link", { name: "Open Debugging lab" })).toHaveAttribute("href", "/problems?view=debugging"));
    expect(lab).toHaveTextContent("Code isn't run on this server right now: attempts are saved, not judged.");
    expect(lab).toHaveTextContent("For careers with coding practice.");
    eng.unmount();

    asUser(nurse);
    renderApp("/whats-new", { signedIn: true });
    const nurseLab = (await screen.findByRole("heading", { level: 3, name: "Debugging lab" }, { timeout: 3000 })).closest("li")!;
    await waitFor(() => expect(nurseLab).toHaveTextContent("For careers with coding practice: not part of Registered Nurse practice."));
    expect(within(nurseLab).queryByRole("link")).toBeNull(); // no Open for a page this career doesn't have
  });

  it("storage that refuses: no dot, nothing marked new, and the page says why", async () => {
    asUser(nurse);
    const getItem = Storage.prototype.getItem;
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(function (this: Storage, key: string) {
      if (key.startsWith("codecoach.whatsnew.")) throw new DOMException("denied", "SecurityError");
      return getItem.call(this, key);
    });
    renderApp("/whats-new", { signedIn: true });
    expect(await screen.findByText(/This browser isn't letting CodeCoach keep track of what you've looked at here/, undefined, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.queryAllByText("New")).toHaveLength(0);
    expect(screen.getByRole("link", { name: "What's new" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(ENTRIES.length);
  });

  it("another account signing in on this browser has its own: nothing carried over either way", async () => {
    asUser(nurse);
    seen(nurse, 2);
    const { user, router } = renderApp("/help", { signedIn: true });
    expect(await headerLink("What's new")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Sign out" })).toBeNull());
    await router.navigate("/login");
    await user.type(await screen.findByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "CorrectHorse42");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    // The default sign-in is another account (u-1, a software engineer) that hasn't looked yet.
    expect(await headerLink(`What's new, ${latest.length} new`)).toBeInTheDocument();
    expect(stored(baseUser)).toBeNull();
    expect(JSON.parse(stored(nurse)!)).toEqual({ v: 1, seen: 2 });
  });

  it("an answer in progress isn't interrupted: the dot takes no focus and says nothing, and the answer is there after a look", async () => {
    asUser(nurse);
    const { user, router } = renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    const box = await screen.findByLabelText("Your answer", undefined, { timeout: 3000 });
    await user.type(box, "I checked her airway first.");
    expect(await headerLink(`What's new, ${latest.length} new`)).toBeInTheDocument();
    expect(box).toHaveFocus();
    expect(screen.queryByRole("dialog")).toBeNull();
    for (const live of [...screen.queryAllByRole("status"), ...screen.queryAllByRole("alert")]) expect(live).not.toHaveTextContent(/What's new/);
    await user.click(screen.getByRole("link", { name: `What's new, ${latest.length} new` }));
    expect(await screen.findByRole("heading", { level: 1, name: "What's new" })).toBeInTheDocument();
    await router.navigate(-1);
    expect(await screen.findByLabelText("Your answer", undefined, { timeout: 3000 })).toHaveValue("I checked her airway first.");
  });

  it("a visitor sees the list, with sign-in for pages that need it, and no dot", async () => {
    renderApp("/whats-new");
    expect(await screen.findByText("Sign in to see which of these are new to you and to open them.", undefined, { timeout: 3000 })).toBeInTheDocument();
    const packet = screen.getByRole("heading", { level: 3, name: "Practice packet" }).closest("li")!;
    expect(packet).toHaveTextContent("Sign in to use it.");
    expect(within(packet).queryByRole("link")).toBeNull();
    expect(screen.getByRole("link", { name: "What's new" })).toBeInTheDocument();
    expect(screen.queryAllByText("New")).toHaveLength(0);
  });
});
