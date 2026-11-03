/**
 * Lost refresh responses, reloads, races and sign-out, through the real AuthProvider and API
 * client against a fake server that applies the backend's rules (app/services/refresh.py):
 * a cookie rotates once; presenting a used cookie again with the key of the attempt that rotated
 * it returns the same successor (while it is unused); anything else is a race.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api/client";
import { makeQueryClient } from "@/app/queryClient";
import { API, server } from "@/test/server";
import { tokenResponse } from "@/test/fixtures";

import { AuthProvider } from "./AuthProvider";
import { beginAttempt, pendingAttemptKey, RACE_RETRY_MS, resetRefreshAttemptsForTests, settleAttempt, withRefreshLock } from "./refreshAttempt";
import { useAuth } from "./useAuth";

interface Rotation { key: string | null; successor: string }

/** The server's view of the refresh cookie, and the browser's cookie jar. */
class FakeSessionServer {
  jar: string | null = "C1";
  used = new Map<string, Rotation>();
  revoked = new Set<string>();
  calls: { cookie: string | null; key: string | null }[] = [];
  /** Lose the next response after the server has processed it (reload, dropped connection). */
  loseNext = false;
  /** Hold every refresh until released (a slow network). */
  hold: Promise<void> | null = null;
  private seq = 1;

  handler = http.post(`${API}/api/v1/auth/refresh`, async ({ request }) => {
    const presented = this.jar;
    const key = request.headers.get("X-Refresh-Attempt");
    this.calls.push({ cookie: presented, key });
    const fail = (code: string) => HttpResponse.json({ error: { code, message: code, request_id: "r", details: null } }, { status: 401 });
    if (!presented || this.revoked.has(presented)) return fail("invalid_refresh");
    const rotation = this.used.get(presented);
    let successor: string;
    if (rotation) {
      const successorUsed = this.used.has(rotation.successor) || this.revoked.has(rotation.successor);
      if (!key || key !== rotation.key || successorUsed) return fail("refresh_race");
      successor = rotation.successor; // recovery: the same successor, nothing new issued
    } else {
      successor = `C${++this.seq}`;
      this.used.set(presented, { key, successor });
    }
    if (this.hold) await this.hold; // processed; the answer is slow to arrive
    if (this.loseNext) {
      this.loseNext = false;
      return HttpResponse.error(); // processed, but the browser never sees the answer
    }
    this.jar = successor;
    return HttpResponse.json(tokenResponse({ access_token: `token-${successor}` }));
  });

  logout = http.post(`${API}/api/v1/auth/logout`, () => {
    for (const token of [this.jar, ...this.used.keys(), ...[...this.used.values()].map((r) => r.successor)]) {
      if (token) this.revoked.add(token);
    }
    this.jar = null;
    return new HttpResponse(null, { status: 204 });
  });
}

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <p>{auth.isRestoring ? "restoring" : auth.isAuthenticated ? `signed in as ${auth.user?.email}` : "signed out"}</p>
      <p>{auth.signedOutReason ?? "no reason"}</p>
      <p>{auth.signedOutDeliberately ? "deliberate" : "not deliberate"}</p>
      <button onClick={() => void auth.logout()}>Sign out</button>
    </div>
  );
}

function mount() {
  const queryClient = makeQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider><Probe /></AuthProvider>
    </QueryClientProvider>,
  );
}

let fake: FakeSessionServer;
beforeEach(() => {
  resetRefreshAttemptsForTests();
  fake = new FakeSessionServer();
  server.use(fake.handler, fake.logout);
});
afterEach(() => {
  resetRefreshAttemptsForTests();
  window.sessionStorage.clear();
});

describe("a lost refresh response", () => {
  it("is recovered after a reload: the same attempt key brings back the same new session", async () => {
    fake.loseNext = true;
    const first = mount();
    await waitFor(() => expect(screen.queryByText("restoring")).toBeNull());
    expect(fake.used.size).toBe(1); // the server rotated C1 -> C2...
    expect(fake.jar).toBe("C1"); // ...but the browser still holds C1
    first.unmount(); // reload

    mount();
    await screen.findByText(/signed in as/);
    expect(fake.calls).toHaveLength(2);
    expect(fake.calls[1]).toEqual({ cookie: "C1", key: fake.calls[0]!.key });
    expect(fake.calls[0]!.key).toMatch(/^[A-Za-z0-9_-]{22,64}$/);
    expect(fake.jar).toBe("C2"); // the successor the lost response carried
    expect(window.sessionStorage.getItem("codecoach.refresh-attempt")).toBeNull(); // settled
  });

  it("is recovered by the 401 retry in the same page, without a reload", async () => {
    mount();
    await screen.findByText(/signed in as/);
    const seen: string[] = [];
    server.use(http.get(`${API}/api/v1/thing`, ({ request }) => {
      const auth = request.headers.get("Authorization") ?? "";
      seen.push(auth);
      return auth === "Bearer token-C3"
        ? HttpResponse.json({ ok: true })
        : HttpResponse.json({ error: { code: "unauthorized", message: "expired", request_id: "r", details: null } }, { status: 401 });
    }));
    fake.loseNext = true; // the refresh this 401 triggers is lost: a network error, not a sign-out...
    await expect(apiRequest("/api/v1/thing")).rejects.toMatchObject({ code: "network_error" });
    expect(screen.getByText(/signed in as/)).toBeInTheDocument();
    // ...and the next 401 recovers the session with the same key.
    await expect(apiRequest("/api/v1/thing")).resolves.toEqual({ ok: true });
    const keys = fake.calls.slice(1).map((c) => c.key);
    expect(keys[0]).toBe(keys[1]);
    expect(fake.calls.slice(1).map((c) => c.cookie)).toEqual(["C2", "C2"]);
    expect(screen.getByText(/signed in as/)).toBeInTheDocument();
  });
});

describe("races and retries", () => {
  it("retries a race a bounded number of times, then signs out instead of looping", async () => {
    fake.used.set("C1", { key: "someone-elses-attempt-key-000", successor: "C9" });
    mount();
    await screen.findByText("signed out", {}, { timeout: 6000 });
    expect(fake.calls).toHaveLength(1 + RACE_RETRY_MS.length);
    const settled = fake.calls.length;
    await act(() => new Promise((r) => setTimeout(r, 400)));
    expect(fake.calls).toHaveLength(settled); // nothing more
  });

  it("recovers when another tab's refresh finishes while this one waits", async () => {
    // Another tab rotated C1 -> C2 a moment ago; its response reaches the shared cookie jar
    // while this tab is backing off.
    fake.used.set("C1", { key: "another-tabs-attempt-key-0000", successor: "C2" });
    setTimeout(() => { fake.jar = "C2"; }, 100);
    mount();
    await screen.findByText(/signed in as/);
    expect(fake.calls.map((c) => c.cookie)).toEqual(["C1", "C2"]);
  });

  it("shares one refresh between concurrent 401s", async () => {
    mount();
    await screen.findByText(/signed in as/);
    let release!: () => void;
    fake.hold = new Promise<void>((resolve) => { release = resolve; });
    let rejected = 0;
    server.use(http.get(`${API}/api/v1/thing`, ({ request }) => {
      if (request.headers.get("Authorization") === "Bearer token-C3") return HttpResponse.json({ ok: true });
      rejected += 1;
      return HttpResponse.json({ error: { code: "unauthorized", message: "expired", request_id: "r", details: null } }, { status: 401 });
    }));
    const all = Promise.all([apiRequest("/api/v1/thing"), apiRequest("/api/v1/thing"), apiRequest("/api/v1/thing")]);
    await waitFor(() => expect(rejected).toBe(3)); // all three hit 401 while the refresh is held
    release();
    await expect(all).resolves.toEqual([{ ok: true }, { ok: true }, { ok: true }]);
    expect(fake.calls).toHaveLength(2); // the restore, then one shared refresh
  });
});

describe("signing out", () => {
  it("a refresh that answers after a deliberate sign-out doesn't sign the user back in", async () => {
    mount();
    await screen.findByText(/signed in as/);
    let release!: () => void;
    fake.hold = new Promise<void>((resolve) => { release = resolve; });
    server.use(http.get(`${API}/api/v1/thing`, () =>
      HttpResponse.json({ error: { code: "unauthorized", message: "expired", request_id: "r", details: null } }, { status: 401 })));
    const pending = apiRequest("/api/v1/thing").catch(() => undefined); // starts a refresh, which waits
    await waitFor(() => expect(fake.calls).toHaveLength(2));
    screen.getByRole("button", { name: "Sign out" }).click();
    await screen.findByText("signed out");
    fake.hold = null;
    release(); // the refresh's answer arrives after the sign-out
    await pending;
    expect(fake.jar).toBe("C3"); // the late answer even set its (revoked) cookie
    expect(screen.getByText("signed out")).toBeInTheDocument();
    expect(screen.getByText("deliberate")).toBeInTheDocument(); // not "your session ended"
    expect(screen.getByText("no reason")).toBeInTheDocument();
    expect(window.sessionStorage.getItem("codecoach.refresh-attempt")).toBeNull();
  });

  it("a reload after signing out stays signed out", async () => {
    const page = mount();
    await screen.findByText(/signed in as/);
    screen.getByRole("button", { name: "Sign out" }).click();
    await screen.findByText("signed out");
    page.unmount();
    mount();
    await screen.findByText("signed out");
  });
});

describe("attempt keys", () => {
  it("keeps this tab's unfinished key, and forgets it once settled", () => {
    const key = beginAttempt();
    expect(beginAttempt()).toBe(key);
    settleAttempt(key);
    expect(beginAttempt()).not.toBe(key);
  });

  it("stops reusing a key after the recovery window", () => {
    const old = beginAttempt(Date.now() - 200_000);
    expect(beginAttempt()).not.toBe(old);
  });

  it("picks up another tab's unfinished attempt, and drops it when that tab settles", async () => {
    const otherTab = new BroadcastChannel("codecoach-auth");
    expect(pendingAttemptKey()).toBeNull(); // also opens this tab's channel
    const theirs = "another-tabs-attempt-key-0001";
    otherTab.postMessage({ type: "attempt", attempt: { key: theirs, at: Date.now() } });
    await waitFor(() => expect(pendingAttemptKey()).toBe(theirs));
    expect(beginAttempt()).toBe(theirs); // this tab's refresh finishes theirs
    otherTab.postMessage({ type: "settled", key: theirs }); // they got their answer after all
    await waitFor(() => expect(pendingAttemptKey()).toBeNull());
    expect(beginAttempt()).not.toBe(theirs);
    otherTab.close();
  });
});

describe("the cross-tab refresh lock", () => {
  it("goes ahead without the lock when another tab's refresh is stuck", async () => {
    // A lock that is never granted (another tab's request hangs): the refresh still runs.
    const request = vi.fn((_name: string, options: { signal: AbortSignal }) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(options.signal.reason));
    }));
    vi.stubGlobal("navigator", { ...navigator, locks: { request } });
    try {
      await expect(withRefreshLock(async () => "refreshed", 50)).resolves.toBe("refreshed");
      expect(request).toHaveBeenCalledOnce();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("runs inside the lock when it is granted, and passes errors through", async () => {
    const request = vi.fn((_name: string, _options: unknown, fn: () => Promise<unknown>) => fn());
    vi.stubGlobal("navigator", { ...navigator, locks: { request } });
    try {
      await expect(withRefreshLock(async () => "refreshed")).resolves.toBe("refreshed");
      await expect(withRefreshLock(async () => { throw new Error("refused"); })).rejects.toThrow("refused");
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
