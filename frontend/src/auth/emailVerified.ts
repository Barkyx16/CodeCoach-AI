import { safeReturnPath } from "@/lib/links";
import { storage } from "@/lib/storage";

/**
 * Email verification across tabs, in this browser:
 * - where the learner was going when they were asked to confirm (a question, an interview), so a
 *   link opened in a new tab can continue there. Kept per account, and checked as an in-app path
 *   whenever it's read;
 * - a "verified" signal, so the tab still showing "Check your email" (or Settings) refreshes the
 *   account at once. Another device finds out when its tab is next focused.
 */
const NEXT_KEY = "codecoach:verify-next";
export const VERIFIED_KEY = "codecoach:email-verified";
const KEEP_MS = 7 * 24 * 60 * 60 * 1000;
/** After confirming, never back to the confirmation page itself. */
const NOT_NEXT = ["/verify-email"];

export function rememberVerifyNext(userId: string, path: string): void {
  const safe = safeReturnPath(path, "", NOT_NEXT);
  if (safe) storage.set(NEXT_KEY, JSON.stringify({ userId, path: safe, at: Date.now() }));
}

/** The remembered destination for this account, if any (and still an in-app path). */
export function verifyNextFor(userId: string | null | undefined): string | null {
  if (!userId) return null;
  try {
    const saved = JSON.parse(storage.get(NEXT_KEY) ?? "null") as { userId?: unknown; path?: unknown; at?: unknown } | null;
    if (!saved || saved.userId !== userId || typeof saved.at !== "number" || Date.now() - saved.at > KEEP_MS) return null;
    return safeReturnPath(saved.path, "", NOT_NEXT) || null;
  } catch {
    return null;
  }
}

export function forgetVerifyNext(): void {
  storage.remove(NEXT_KEY);
}

/** Tell this browser's other tabs that this account's email was just confirmed. */
export function announceVerified(userId: string): void {
  storage.set(VERIFIED_KEY, JSON.stringify({ userId, at: Date.now() }));
}

/** The account a "verified" signal from another tab is about, or null if it isn't one. */
export function verifiedElsewhere(event: StorageEvent): string | null {
  if (event.key !== VERIFIED_KEY || !event.newValue) return null;
  try {
    const { userId } = JSON.parse(event.newValue) as { userId?: unknown };
    return typeof userId === "string" ? userId : null;
  } catch {
    return null;
  }
}
