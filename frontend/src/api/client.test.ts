import { http, HttpResponse } from "msw";

import { API, server } from "@/test/server";

import { apiRequest, ApiError, buildUrl, configureAuth } from "./client";
import { shouldRetry, submissionPollInterval } from "./queries";
import { queuedSubmission } from "@/test/fixtures";

describe("apiRequest", () => {
  afterEach(() => configureAuth(() => null, () => {}));

  it("drops empty query params", () => {
    expect(buildUrl("/api/v1/problems", { q: "", topic: "arrays", page: 2, difficulty: undefined }))
      .toBe(`${API}/api/v1/problems?topic=arrays&page=2`);
  });

  it("parses the error envelope into an ApiError with the stable code", async () => {
    server.use(http.get(`${API}/x`, () => HttpResponse.json(
      { error: { code: "hint_locked", message: "Unlock level 1 first", request_id: "abc12345", details: { next_unlockable_level: 1 } } },
      { status: 409 })));
    const err = await apiRequest("/x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 409, code: "hint_locked", requestId: "abc12345", details: { next_unlockable_level: 1 } });
  });

  it("handles non-JSON error bodies", async () => {
    server.use(http.get(`${API}/x`, () => new HttpResponse("Bad gateway", { status: 502 })));
    await expect(apiRequest("/x")).rejects.toMatchObject({ status: 502, code: "http_error" });
  });

  it("turns network failures into a network_error", async () => {
    server.use(http.get(`${API}/x`, () => HttpResponse.error()));
    await expect(apiRequest("/x")).rejects.toMatchObject({ status: 0, code: "network_error" });
  });

  it("sends the bearer token and reports 401s to the auth layer", async () => {
    const onUnauthorized = vi.fn();
    configureAuth(() => "tok", onUnauthorized);
    let seen: string | null = null;
    server.use(http.get(`${API}/x`, ({ request }) => {
      seen = request.headers.get("Authorization");
      return HttpResponse.json({ error: { code: "invalid_token", message: "revoked", request_id: null, details: null } }, { status: 401 });
    }));
    await expect(apiRequest("/x")).rejects.toMatchObject({ code: "invalid_token" });
    expect(seen).toBe("Bearer tok");
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("does not send the token when auth is false", async () => {
    configureAuth(() => "tok", () => {});
    let seen: string | null = "unset";
    server.use(http.post(`${API}/x`, ({ request }) => {
      seen = request.headers.get("Authorization");
      return HttpResponse.json({ ok: true });
    }));
    await apiRequest("/x", { method: "POST", body: {}, auth: false });
    expect(seen).toBeNull();
  });

  it("returns undefined for 204", async () => {
    server.use(http.post(`${API}/x`, () => new HttpResponse(null, { status: 204 })));
    await expect(apiRequest("/x", { method: "POST" })).resolves.toBeUndefined();
  });
});

describe("query policies", () => {
  it("never retries 4xx, retries network/5xx twice", () => {
    expect(shouldRetry(0, new ApiError(404, "not_found", "x"))).toBe(false);
    expect(shouldRetry(0, new ApiError(500, "internal_error", "x"))).toBe(true);
    expect(shouldRetry(2, new ApiError(0, "network_error", "x"))).toBe(false);
  });

  it("polls only while a job is running and execution is enabled", () => {
    expect(submissionPollInterval(undefined)).toBe(false);
    expect(submissionPollInterval(queuedSubmission)).toBe(false); // execution disabled
    const fresh = { ...queuedSubmission, execution_enabled: true, created_at: new Date().toISOString() };
    expect(submissionPollInterval(fresh)).toBe(1500);
    expect(submissionPollInterval(fresh, Date.now() + 2 * 60_000)).toBe(5000); // slower after a minute
    expect(submissionPollInterval(fresh, Date.now() + 16 * 60_000)).toBe(false); // bounded
    expect(submissionPollInterval({ ...queuedSubmission, execution_enabled: true, status: "PASSED", is_terminal: true })).toBe(false);
  });
});
