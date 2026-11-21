import { useState } from "react";

import { formatDateTime } from "@/lib/format";

import { Button } from "./Button";

/**
 * A browser copy of an unfinished form, offered back (Volume 9, prompt 2): its age and what it
 * is, and Restore or Discard. Nothing is replaced until the learner chooses. `newer` says when the
 * saved record changed after the copy was made.
 */
export function FormDraftOffer({ what, at, newer, onRestore, onDiscard }: {
  what: string;
  at: string;
  newer?: string | null;
  onRestore(): void;
  onDiscard(): void;
}) {
  return (
    <div className="banner banner--info stack-sm" role="region" aria-label="Unsaved changes found">
      <span>You have unsaved changes to {what} from {formatDateTime(at)}, kept on this device. They aren't saved to your account.</span>
      {newer && <span className="subtle">{newer}</span>}
      <span className="row">
        <Button size="sm" variant="primary" onClick={onRestore}>Restore them</Button>
        <Button size="sm" variant="ghost" onClick={onDiscard}>Discard them</Button>
      </span>
    </div>
  );
}

/**
 * Where unsaved changes are: kept on this device, or only on this page (the browser refused the
 * copy, or another tab has a newer one). Never "saved". Copy your work when they're on the page only.
 *
 * Always on the page, empty while nothing has changed (Volume 9, prompt 8): its line doesn't push
 * Save down when typing starts, and a screen reader hears each change of state. The mark beside
 * the words is decoration; the words say the state.
 */
export function FormDraftStatus({ changed, kept, competing, copyText }: {
  changed: boolean;
  kept: boolean;
  competing: boolean;
  copyText: () => string;
}) {
  const [copied, setCopied] = useState<"yes" | "no" | null>(null);
  const onPageOnly = !kept || competing;
  const tone = !changed ? "" : onPageOnly ? " form-state--page-only" : " form-state--local";
  return (
    <p className={`form-state${tone}`} role="status">
      {changed && (
        <>
          <span className="form-state__mark" aria-hidden="true" />
          <span>
            {competing
              ? "Another tab of this browser has a newer copy of this form, kept as it was. These changes are on this page only: save them, or copy your work."
              : onPageOnly
                ? "Unsaved changes, and this browser can't keep a copy: save them, or copy your work."
                : "Unsaved changes, kept on this device."}
          </span>
          {onPageOnly && (
            <span className="form-state__action">
              <Button size="sm" variant="ghost" onClick={async () => {
                try {
                  await navigator.clipboard.writeText(copyText());
                  setCopied("yes");
                } catch {
                  setCopied("no");
                }
              }}>Copy your work</Button>
              {copied === "yes" && " Copied."}
              {copied === "no" && " This browser didn't allow copying: select the text and copy it yourself."}
            </span>
          )}
        </>
      )}
    </p>
  );
}
