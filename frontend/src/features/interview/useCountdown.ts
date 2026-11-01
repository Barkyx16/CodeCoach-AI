import { useEffect, useState } from "react";

/** Seconds left until `deadline` (ISO). Ticks every second; the server stays authoritative. */
export function useCountdown(deadline: string | null, active: boolean): number {
  const compute = () => (deadline ? Math.max(0, Math.round((new Date(deadline).getTime() - Date.now()) / 1000)) : 0);
  const [seconds, setSeconds] = useState(compute);
  useEffect(() => {
    if (!active || !deadline) return;
    const tick = () => setSeconds(Math.max(0, Math.round((new Date(deadline).getTime() - Date.now()) / 1000)));
    tick();
    const t = window.setInterval(tick, 1000);
    return () => window.clearInterval(t);
  }, [deadline, active]);
  return active ? seconds : 0;
}

export function formatClock(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
