import { useCallback, useRef } from "react";

/** A random key for one logical create, so sending it again (a lost response, a retry) is
 * recognised by the server and makes nothing twice. */
export function newRequestKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * One key per exact request, for a form on this page (Volume 8, prompt 2). Sending the same
 * content again (a retry after a lost reply) reuses the key, so the server makes it once;
 * changed content is a new request with a new key, because the server refuses an old key with
 * different content (409 `idempotency_key_reused`). `done()` after a success: the next send is
 * new even if it's identical.
 */
export function useRequestKey(): { keyFor: (content: unknown) => string; done: () => void } {
  const last = useRef<{ content: string; key: string } | null>(null);
  const keyFor = useCallback((content: unknown) => {
    const text = JSON.stringify(content) ?? "";
    if (last.current?.content !== text) last.current = { content: text, key: newRequestKey() };
    return last.current.key;
  }, []);
  const done = useCallback(() => { last.current = null; }, []);
  return { keyFor, done };
}
