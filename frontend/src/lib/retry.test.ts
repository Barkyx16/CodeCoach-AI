import { ApiError, parseRetryAfter } from "@/api/client";
import { failureKind, formatWait } from "@/lib/errors";

describe("Retry-After", () => {
  const now = Date.parse("2026-11-08T12:00:00Z");
  it.each([
    ["120", 120],
    ["0", 0],
    [" 7 ", 7],
    ["Sun, 08 Nov 2026 12:01:30 GMT", 90], // an HTTP date, 90 s from now
    ["Sun, 08 Nov 2026 11:59:00 GMT", 0], // already past: no wait, never negative
    ["soon", null],
    ["-5", null],
    ["", null],
    [null, null],
  ] as const)("%j → %j", (value, seconds) => {
    expect(parseRetryAfter(value, now)).toBe(seconds);
  });

  it("an error prefers the body's figure, then the header's", () => {
    expect(new ApiError(429, "rate_limited", "x", { retry_after_seconds: 41.2 }, null, 60).retryAfterSeconds).toBe(42);
    expect(new ApiError(429, "rate_limited", "x", null, null, 60).retryAfterSeconds).toBe(60);
    expect(new ApiError(429, "rate_limited", "x").retryAfterSeconds).toBeNull();
    const e = new ApiError(503, "server_busy", "x", null, null, 5);
    expect(e.retryAt! - e.receivedAt).toBe(5000);
  });
});

describe("failure kinds and waits", () => {
  it.each([
    [new ApiError(0, "network_error", "x"), "offline"],
    [new ApiError(429, "rate_limited", "x"), "busy"],
    [new ApiError(503, "judge_unavailable", "x"), "unavailable"],
    [new ApiError(422, "validation_error", "x"), "invalid"],
    [new ApiError(401, "invalid_credentials", "x"), "invalid"], // a wrong password isn't a lost session
    [new ApiError(401, "invalid_token", "x"), "signed_out"],
    [new ApiError(403, "forbidden", "x"), "forbidden"],
    [new ApiError(404, "not_found", "x"), "not_found"],
    [new ApiError(409, "idempotency_key_reused", "x"), "conflict"],
    [new ApiError(500, "internal_error", "x"), "server"],
    [new Error("boom"), "other"],
  ] as const)("%o is %s", (error, kind) => {
    expect(failureKind(error)).toBe(kind);
  });

  it.each([
    [0, "0 s"], [42, "42 s"], [65, "1 min 05 s"], [599, "9 min 59 s"], [1500, "about 25 min"], [7200, "about 2 h"], [11_520, "about 3 h 12 min"],
  ])("%i s reads as %s", (seconds, text) => {
    expect(formatWait(seconds)).toBe(text);
  });
});
