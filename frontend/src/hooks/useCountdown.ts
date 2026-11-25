import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";

/**
 * Seconds left until `until` (a time in ms since the epoch), ticking once a second; 0 once it has
 * passed or when there's nothing to wait for (null).
 */
export function useCountdown(until: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (until === null) return;
    const tick = () => setNow(Date.now());
    const timer = window.setInterval(tick, 1000);
    const first = window.setTimeout(tick, 0); // count from now, not from when the hook first ran
    return () => {
      window.clearInterval(timer);
      window.clearTimeout(first);
    };
  }, [until]);
  return until === null ? 0 : Math.max(0, Math.ceil((until - now) / 1000));
}

/** The server's wait for a failed request, counting down to 0 (and 0 when it asked for none). */
export function useRetryWait(error: unknown): number {
  return useCountdown(error instanceof ApiError ? error.retryAt : null);
}
