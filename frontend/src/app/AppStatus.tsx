import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/Button";
import { hasUnretainedWork } from "@/hooks/useLeaveWarning";
import { useOnline } from "@/hooks/useOnline";
import { updateNow } from "@/pwa/appShell";
import { useAppShell } from "@/pwa/useAppShell";

/** Connection and app-update status, shown under the header only when they apply. */
export function AppStatus() {
  const online = useOnline();
  const { updateWaiting } = useAppShell();
  const [later, setLater] = useState(false);
  return (
    <>
      {!online && (
        <div className="banner banner--warning app__banner app-status" role="status">
          <strong>You're offline.</strong> Drafts are kept on this device and <Link to="/offline">saved pages</Link> still open.
          Feedback, judging, interviews and sign-in need a connection.
        </div>
      )}
      {updateWaiting && !later && (
        <div className="banner banner--info app__banner app-status row" role="status">
          <span>A new version of CodeCoach is ready. Your drafts on this device are kept when you update.</span>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => {
              if (hasUnretainedWork() && !window.confirm("Something on this page couldn't be saved on this device and would be lost. Update anyway?")) return;
              updateNow();
            }}>Update now</Button>
            <Button size="sm" variant="ghost" onClick={() => setLater(true)}>Later</Button>
          </span>
        </div>
      )}
    </>
  );
}
