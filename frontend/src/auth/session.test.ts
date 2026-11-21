import { tokenResponse } from "@/test/fixtures";

import { forgetLegacySession, isExpired, LEGACY_SESSION_KEY, refreshDelay, sessionFromToken } from "./session";

describe("session", () => {
  it("treats tokens within 30s of expiry as expired", () => {
    const s = sessionFromToken(tokenResponse({ expires_at: new Date(Date.now() + 10_000).toISOString() }));
    expect(isExpired(s)).toBe(true);
    expect(isExpired(sessionFromToken(tokenResponse()))).toBe(false);
  });

  it("schedules the refresh a minute before expiry, never in the past", () => {
    const now = Date.now();
    const s = sessionFromToken(tokenResponse({ expires_at: new Date(now + 15 * 60_000).toISOString() }));
    expect(refreshDelay(s, now)).toBe(14 * 60_000);
    expect(refreshDelay(sessionFromToken(tokenResponse({ expires_at: new Date(now).toISOString() })), now)).toBe(0);
  });

  it("removes sessions saved by older versions, which kept the token in localStorage", () => {
    window.localStorage.setItem(LEGACY_SESSION_KEY, JSON.stringify(sessionFromToken(tokenResponse())));
    forgetLegacySession();
    expect(window.localStorage.getItem(LEGACY_SESSION_KEY)).toBeNull();
  });
});
