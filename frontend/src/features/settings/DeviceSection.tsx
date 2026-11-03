import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/Button";
import { useOfflineList } from "@/features/offline/useOfflineEntry";
import { install } from "@/pwa/appShell";
import { useAppShell } from "@/pwa/useAppShell";

/** Installing the app and using it offline on this device: only what this browser really supports. */
export function DeviceRows() {
  const shell = useAppShell();
  const saved = useOfflineList();
  const [outcome, setOutcome] = useState<string>("");
  return (
    <>
      <div className="setting" role="group" aria-labelledby="install-title">
        <div className="setting__intro">
          <h3 className="setting__title" id="install-title">Install the app</h3>
          <p className="setting__desc">Opens in its own window, from your home screen or dock. Same account, same data.</p>
        </div>
        <div className="setting__body">
          {shell.installed ? <p>Installed on this device.</p>
            : shell.canInstall ? (
              <div className="setting__actions">
                <Button onClick={() => void install().then((r) => setOutcome(r === "accepted" ? "Installing…" : r === "dismissed" ? "Not installed. You can install it later." : ""))}>Install CodeCoach</Button>
              </div>
            ) : (
              <ul className="mini-list">
                <li>This browser hasn't offered to install it here.</li>
                <li>iPhone and iPad (Safari): Share, then “Add to Home Screen”.</li>
                <li>Chrome or Edge on a computer or Android: “Install” in the address bar or the browser menu, once the site has loaded over HTTPS.</li>
                <li>Firefox on a computer doesn't install web apps.</li>
              </ul>
            )}
          <p className="subtle" role="status">{outcome}</p>
        </div>
      </div>
      <div className="setting" role="group" aria-labelledby="offline-title">
        <div className="setting__intro">
          <h3 className="setting__title" id="offline-title">Offline use</h3>
          <p className="setting__desc">What this device can do without a connection.</p>
        </div>
        <div className="setting__body">
          <p>{shell.offlineReady ? "Ready: CodeCoach opens on this device without a connection." : shell.unsupportedReason ?? "Not ready yet: it becomes available after the app has fully loaded once."}</p>
          <p>
            {saved.data ? `${saved.data.length} ${saved.data.length === 1 ? "item" : "items"} saved for offline reading. ` : ""}
            <Link to="/offline">Manage saved items</Link>
          </p>
          <p className="subtle">Feedback, judging, the coach, interviews and sign-in always need a connection. Signing out deletes your unsent drafts from this device; saved public pages and display settings stay.</p>
        </div>
      </div>
    </>
  );
}
