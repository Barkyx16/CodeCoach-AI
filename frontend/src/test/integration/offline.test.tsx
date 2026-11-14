import { act, screen, waitFor, within } from "@testing-library/react";
import { MutationObserver, onlineManager } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { vi } from "vitest";

import { makeQueryClient } from "@/app/queryClient";
import { DEVICE_USER_KEY } from "@/auth/deviceUser";
import { clearLocalWork, countLocalWork } from "@/auth/localWork";
import { answerDraftKey } from "@/features/dashboard/savedWork";
import { listOffline, readOffline, removeOffline, revalidateOffline, saveOffline, withOfflineCopy } from "@/features/offline/offlineStore";
import { ApiError } from "@/api/client";
import { setAppShellState } from "@/pwa/appShell";

import { user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

vi.mock("@/pwa/appShell", async (original) => ({ ...(await original<typeof import("@/pwa/appShell")>()), updateNow: vi.fn() }));

/** A minimal Cache Storage (jsdom has none). */
function installCaches() {
  const stores = new Map<string, Map<string, string>>();
  const open = async (name: string) => {
    if (!stores.has(name)) stores.set(name, new Map());
    const store = stores.get(name)!;
    const key = (r: RequestInfo | URL) => new URL(typeof r === "string" ? r : r instanceof URL ? r.href : r.url, "http://localhost").pathname;
    return {
      put: async (r: RequestInfo | URL, res: Response) => void store.set(key(r), await res.text()),
      match: async (r: RequestInfo | URL) => (store.has(key(r)) ? new Response(store.get(key(r))) : undefined),
      delete: async (r: RequestInfo | URL) => store.delete(key(r)),
      keys: async () => [...store.keys()].map((k) => new Request(`http://localhost${k}`)),
    };
  };
  Object.defineProperty(globalThis, "caches", { configurable: true, value: { open, delete: async (n: string) => stores.delete(n), keys: async () => [...stores.keys()] } });
  Object.defineProperty(window, "isSecureContext", { configurable: true, value: true });
  return stores;
}

let online = true;
beforeEach(() => {
  online = true;
  Object.defineProperty(navigator, "onLine", { configurable: true, get: () => online });
  installCaches();
});
afterEach(() => {
  online = true;
  act(() => setAppShellState({ updateWaiting: false, offlineReady: false }));
});

function goOffline() {
  online = false;
  act(() => { window.dispatchEvent(new Event("offline")); });
}
function goOnline() {
  online = true;
  act(() => { window.dispatchEvent(new Event("online")); });
}

describe("saved for offline", () => {
  it("stores only public copies, fetched without credentials, and lists, reads and removes them", async () => {
    const auth: (string | null)[] = [];
    server.use(http.get(`${API}/api/v1/careers/:track/questions/:id`, ({ request, params }) => {
      auth.push(request.headers.get("authorization"));
      return HttpResponse.json({ id: params.id, title: "Patient assessment under pressure", prompt: "Tell me…", difficulty: "medium", kind: "behavioral", best_score: null, track: params.track, career_title: "Registered Nurse", tips: [], rubric_labels: [] });
    }));
    const saved = await saveOffline("question", "registered-nurse/m-pressure-0");
    expect(auth).toEqual([null]); // never the learner's token
    expect(saved).toMatchObject({ kind: "question", title: "Patient assessment under pressure", href: "/careers/registered-nurse/questions/m-pressure-0" });
    await saveOffline("problem", "two-sum");
    expect((await listOffline()).map((e) => e.kind).sort()).toEqual(["problem", "question"]);
    expect((await readOffline<{ title: string }>("problem", "two-sum"))?.data.title).toBe("Two Sum");
    await removeOffline("problem", "two-sum");
    expect((await listOffline()).map((e) => e.kind)).toEqual(["question"]);
  });

  it("serves the saved copy only when the network fails, and drops retired items on reconnect", async () => {
    await saveOffline("question", "registered-nurse/m-pressure-0");
    await saveOffline("problem", "two-sum");
    const networkError = () => Promise.reject(new ApiError(0, "network_error", "offline"));
    expect(await withOfflineCopy("problem", "two-sum", networkError)).toMatchObject({ slug: "two-sum" });
    await expect(withOfflineCopy("problem", "missing", networkError)).rejects.toThrow("offline");
    await expect(withOfflineCopy("problem", "two-sum", () => Promise.reject(new ApiError(500, "boom", "x")))).rejects.toThrow("x");

    server.use(http.get(`${API}/api/v1/problems/two-sum`, () => HttpResponse.json({ error: { code: "not_found", message: "gone", request_id: "r", details: null } }, { status: 404 })));
    const result = await revalidateOffline();
    expect(result.removed.map((e) => e.key)).toEqual(["two-sum"]);
    expect(result.refreshed.map((e) => e.key)).toEqual(["registered-nurse/m-pressure-0"]);
    expect((await listOffline()).map((e) => e.key)).toEqual(["registered-nurse/m-pressure-0"]);
  });

  it("the offline page lists saved items with sizes and removes them", async () => {
    await saveOffline("question", "registered-nurse/m-pressure-0");
    const { user } = renderApp("/offline");
    expect(await screen.findByRole("link", { name: "Patient assessment under pressure" })).toHaveAttribute("href", "/careers/registered-nurse/questions/m-pressure-0");
    expect(await screen.findByText(/1 of up to 50 items/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove Patient assessment under pressure from this device" }));
    expect(await screen.findByText("Nothing saved yet")).toBeInTheDocument();
  });
});

describe("offline drafts and sessions", () => {
  const nurse = { ...baseUser, id: "u-nurse", career_track: "registered-nurse" };

  it("offline at launch: the last account's draft stays, feedback waits, and reconnecting restores the session", async () => {
    localStorage.setItem(DEVICE_USER_KEY, JSON.stringify({ id: nurse.id, display_name: "Ada", career_track: "registered-nurse", is_guest: false }));
    localStorage.setItem(answerDraftKey(nurse.id, "registered-nurse", "m-pressure-0"), "My unsent answer.");
    await saveOffline("question", "registered-nurse/m-pressure-0");
    let refreshes = 0;
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => { refreshes += 1; return HttpResponse.error(); }),
      http.get(`${API}/api/v1/careers/:track/questions/:id`, () => HttpResponse.error()),
    );
    online = false;
    renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "Patient assessment under pressure" })).toBeInTheDocument();
    expect(refreshes).toBe(0); // known offline: no doomed refresh
    expect(screen.getByLabelText("Your answer")).toHaveValue("My unsent answer.");
    expect(screen.getByRole("button", { name: "Get feedback" })).toBeDisabled();
    expect(screen.getByText(/You're offline\. Feedback needs a connection/)).toBeInTheDocument();
    expect(screen.getAllByText("Offline").length).toBeGreaterThan(0); // the header names the offline account
    expect(screen.getByText(/Drafts are kept on this device/)).toBeInTheDocument(); // the offline banner
  });

  it("an account page offline explains it needs a connection instead of asking to sign in", async () => {
    localStorage.setItem(DEVICE_USER_KEY, JSON.stringify({ id: nurse.id, display_name: "Ada", career_track: null, is_guest: false }));
    online = false;
    const { router } = renderApp("/history", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: "This page needs a connection" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/history");
  });

  it("losing the network doesn't sign anyone out; mutations are never paused to replay later", async () => {
    const qc = makeQueryClient();
    expect(qc.getDefaultOptions().mutations?.networkMode).toBe("always");
    onlineManager.setOnline(false);
    try {
      const fn = vi.fn().mockRejectedValue(new ApiError(0, "network_error", "offline"));
      const observer = new MutationObserver<unknown, Error, void>(qc, { mutationFn: fn });
      await expect(observer.mutate(undefined)).rejects.toThrow("offline");
      expect(fn).toHaveBeenCalledTimes(1); // ran (and failed) now, instead of waiting to resend
      onlineManager.setOnline(true);
      await new Promise((r) => setTimeout(r, 20));
      expect(fn).toHaveBeenCalledTimes(1); // and nothing was replayed on reconnect
    } finally {
      onlineManager.setOnline(true);
    }
  });
});

describe("signing out on a shared device", () => {
  it("deletes this account's private drafts and keeps device preferences and other accounts' work", () => {
    const keep = { "codecoach.display.v1": "{}", "codecoach.editor.v1": "{}", "codecoach.answer.other.registered-nurse.q": "theirs" };
    const mine = {
      "codecoach.answer.me.registered-nurse.q": "a", "codecoach.draft.v1.me.two-sum": "code", "note-draft:me:new": "{}",
      "note-capture:me:question:q": "{}", "learn-draft:me:u": "x", "codecoach.round.iv1.0": "round",
      "story-draft:me:new": "{}", "whiteboard-draft:me:p1": "{}", "reflection-draft:me:e1": "{}",
      "drill-draft:me:d1": "words", "codecoach.interview-message.iv2": "hi", "codecoach.retry.r1.0": "again",
    };
    for (const [k, v] of Object.entries({ ...keep, ...mine })) localStorage.setItem(k, v);
    expect(countLocalWork("me")).toBe(12);
    clearLocalWork("me");
    expect(Object.keys(localStorage).sort()).toEqual(Object.keys(keep).sort());
  });

  it("covers every key the app's source uses for unsent text", async () => {
    // Every storage key in the source that looks like private work (draft, round, retry, message,
    // answer, capture), as the literal text before its first ${...}. A new one that sign-out
    // doesn't clear would outlive the account on a shared device.
    const { localWorkKeys } = await import("@/auth/localWork");
    const sources = import.meta.glob(["/src/**/*.{ts,tsx}", "!/src/**/*.test.{ts,tsx}", "!/src/test/**"], {
      query: "?raw", import: "default", eager: true,
    }) as Record<string, string>;
    const prefixes = new Set<string>();
    for (const text of Object.values(sources)) {
      for (const m of text.matchAll(/`([a-z][\w.-]*(?:draft|round|retry|message|answer|capture|notes)[\w.-]*[:.])\$\{/g)) {
        if (m[1]) prefixes.add(m[1]);
      }
    }
    expect(prefixes.size).toBeGreaterThanOrEqual(10); // the scan finds the known ones
    for (const prefix of prefixes) {
      const sample = `${prefix}me${prefix.endsWith(":") ? ":" : "."}x`;
      localStorage.clear();
      localStorage.setItem(sample, "unsent");
      expect(localWorkKeys("me"), `${prefix} isn't cleared on sign-out`).toContain(sample);
    }
  });

  it("warns before signing out when unsent drafts would be deleted", async () => {
    localStorage.setItem(answerDraftKey(baseUser.id, "registered-nurse", "m-pressure-0"), "unsent");
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { user } = renderApp("/dashboard", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("1 unsent draft on this device"));
    expect(localStorage.getItem(answerDraftKey(baseUser.id, "registered-nurse", "m-pressure-0"))).toBe("unsent"); // stayed
    confirm.mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(localStorage.getItem(answerDraftKey(baseUser.id, "registered-nurse", "m-pressure-0"))).toBeNull());
  });
});

describe("app updates", () => {
  it("an update waits for the learner; updating with a draft that couldn't be kept asks first", async () => {
    const { updateNow } = await import("@/pwa/appShell");
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation((key: string) => {
      if (key.startsWith("codecoach.answer.")) throw new DOMException("full", "QuotaExceededError");
    });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { user } = renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Typed but not kept");
    expect(screen.getByRole("alert")).toHaveTextContent("couldn't be saved on this device");
    act(() => setAppShellState({ updateWaiting: true }));
    const banner = (await screen.findByText(/A new version of CodeCoach is ready/)).closest(".banner") as HTMLElement;
    await user.click(within(banner).getByRole("button", { name: "Update now" }));
    expect(confirm).toHaveBeenCalled();
    expect(updateNow).not.toHaveBeenCalled(); // the learner said "not yet"
    confirm.mockReturnValue(true);
    await user.click(within(banner).getByRole("button", { name: "Update now" }));
    expect(updateNow).toHaveBeenCalledTimes(1);
    await user.click(within(banner).getByRole("button", { name: "Later" }));
    expect(screen.queryByText(/A new version of CodeCoach is ready/)).toBeNull();
    setItem.mockRestore();
  });
});

describe("notes offline", () => {
  it("an edit made offline is 'sync pending' and is sent once when the connection returns", async () => {
    const { user } = renderApp("/notes/new", { signedIn: true });
    await user.type(await screen.findByLabelText("Title"), "Escalation");
    await waitFor(() => expect(screen.getByText("Saved", { selector: ".note-status" })).toBeInTheDocument(), { timeout: 3000 });
    goOffline();
    await user.type(screen.getByLabelText("Note"), " Call early.");
    expect(await screen.findByText(/Sync pending/, {}, { timeout: 3000 })).toBeInTheDocument();
    goOnline();
    await waitFor(() => expect(screen.getByText("Saved", { selector: ".note-status" })).toBeInTheDocument(), { timeout: 3000 });
  });
});
