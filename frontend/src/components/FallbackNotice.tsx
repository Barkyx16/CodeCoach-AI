/**
 * Claude was asked but couldn't give a usable answer (it timed out, was busy, refused, or its reply
 * didn't check out), so the built-in coach answered instead (Volume 4 brief 06). Said plainly and
 * visibly, as a status, so an answer is never taken for Claude's when it isn't.
 */
export function FallbackNotice({ provider }: { provider: string | undefined }) {
  if (!provider?.includes("fallback")) return null;
  return (
    <p className="banner banner--info" role="status">
      Claude couldn't give a usable answer this time, so this one is from the built-in coach (curated hints and
      static analysis). You can ask again later.
    </p>
  );
}
