import { Link, useRouteError } from "react-router-dom";

import { Button } from "@/components/Button";
import { isChunkLoadError } from "@/lib/chunkError";

/**
 * Shown inside the layout when a page can't render. A page whose code couldn't be downloaded
 * (offline, or the app was updated and the old file is gone) gets a reload, not a stack trace.
 * Nothing the learner typed is lost by reloading: drafts are kept on the device.
 */
export function RouteError() {
  const error = useRouteError();
  const chunk = isChunkLoadError(error);
  const offline = typeof navigator !== "undefined" && !navigator.onLine;
  return (
    <div className="page">
      <div className="state state--error" role="alert">
        <strong>{chunk ? "This page couldn't load" : "Something went wrong on this page"}</strong>
        <p className="muted">
          {chunk && offline
            ? "You're offline, and this page isn't saved on this device."
            : chunk
              ? "Part of the app couldn't be downloaded, maybe because it was just updated. Reloading usually fixes it."
              : "Reloading the page usually fixes it. Drafts you were writing are kept on this device."}
        </p>
        {chunk && offline && <p className="muted"><a href="/offline">See what's saved for offline</a></p>}
        <span className="row">
          <Button variant="primary" onClick={() => window.location.reload()}>Reload the page</Button>
          <Link to="/dashboard">Go to your dashboard</Link>
        </span>
      </div>
    </div>
  );
}
