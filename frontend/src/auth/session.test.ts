import { tokenResponse } from "@/test/fixtures";

import { isExpired, loadSession, saveSession, sessionFromToken } from "./session";

describe("session storage", () => {
  it("round-trips a valid session", () => {
    const s = sessionFromToken(tokenResponse());
    saveSession(s);
    expect(loadSession()).toEqual(s);
  });

  it("discards expired or corrupt sessions", () => {
    saveSession(sessionFromToken(tokenResponse({ expires_at: new Date(Date.now() - 1000).toISOString() })));
    expect(loadSession()).toBeNull();
    window.localStorage.setItem("codecoach.session.v1", "{not json");
    expect(loadSession()).toBeNull();
  });

  it("treats tokens within 30s of expiry as expired", () => {
    const s = sessionFromToken(tokenResponse({ expires_at: new Date(Date.now() + 10_000).toISOString() }));
    expect(isExpired(s)).toBe(true);
  });
});
