import { storage } from "@/lib/storage";

/**
 * A sign-out the server never heard (the request failed or the device was offline). The refresh
 * cookie may still be valid there, so the next load would quietly sign the learner back in. The
 * device keeps one flag, no account data and no token, and until the sign-out reaches the server:
 * no refresh is attempted, and every load sends the sign-out again before anything else. A new
 * sign-in on this device clears it.
 */
export const PENDING_SIGN_OUT_KEY = "codecoach.sign-out-pending";

export function rememberPendingSignOut(): void {
  storage.set(PENDING_SIGN_OUT_KEY, "1");
}

export function signOutPending(): boolean {
  return storage.get(PENDING_SIGN_OUT_KEY) === "1";
}

export function forgetPendingSignOut(): void {
  storage.remove(PENDING_SIGN_OUT_KEY);
}
