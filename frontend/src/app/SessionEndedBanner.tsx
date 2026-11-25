import { Link, useLocation } from "react-router-dom";

import { storage } from "@/lib/storage";

const PROBE = "codecoach.storage-probe";

function browserKeepsCopies(): boolean {
  const ok = storage.set(PROBE, "1");
  storage.remove(PROBE);
  return ok;
}

/** Pages where a sign-in link would point at itself. */
const AUTH_PAGES = ["/login", "/register", "/forgot-password", "/reset-password"];

/**
 * The session ended by itself (expired or revoked), not by signing out (Volume 8, prompt 8;
 * RECOVERY.md "When a session ends"). Says what that means for the work on screen, and offers a
 * sign-in that comes back to this page. It names nobody: whoever is at this browser now may not be
 * the person who was signed in.
 */
export function SessionEndedBanner({ reason }: { reason: string }) {
  const location = useLocation();
  const onAuthPage = AUTH_PAGES.includes(location.pathname);
  const kept = browserKeepsCopies();
  return (
    <div className="banner banner--warning app__banner session-ended" role="status">
      <strong>{reason}</strong>{" "}
      {kept
        ? "Until then nothing is saved to an account. Unsaved work this page keeps on this device stays with the account that was signed in, and is offered back when that account signs in again; another account signing in here isn't shown it."
        : "Until then nothing is saved to an account, and this browser can't keep a copy: copy anything you need before leaving this page."}
      {!onAuthPage && (
        <>
          {" "}
          <Link className="btn btn--secondary btn--sm" to="/login" state={{ from: location.pathname + location.search }}>Sign in again</Link>
        </>
      )}
    </div>
  );
}
