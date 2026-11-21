/**
 * The served limits in tests (Volume 17, prompt 7): serve values unlike this build's, so a form that
 * states a copy of its own can't pass, or make the read fail. `reads()` counts the requests.
 */
import { http, HttpResponse } from "msw";

import type { LimitName } from "@/api/types";

import { API, SERVED_LIMITS, server } from "./server";

export function serveLimits(over: Partial<Record<LimitName, number>>) {
  const calls = { n: 0 };
  server.use(http.get(`${API}/api/v1/limits`, () => {
    calls.n += 1;
    return HttpResponse.json({ limits: SERVED_LIMITS.map((l) => ({ ...l, value: over[l.name] ?? l.value })) });
  }));
  return calls;
}

/** The read fails (it's tried once more, then the form states no number). */
export function failLimits() {
  const calls = { n: 0 };
  server.use(http.get(`${API}/api/v1/limits`, () => {
    calls.n += 1;
    return HttpResponse.json({ error: { code: "unavailable", message: "The service is busy.", details: null } }, { status: 503 });
  }));
  return calls;
}
