import { useRef, useState } from "react";

import type { ShareCreated } from "@/api/types";
import { Button } from "@/components/Button";
import { formatDateTime } from "@/lib/format";

/** The new link, shown once (only a hash of its secret is stored), with a copy button. */
export function LinkPanel({ created }: { created: ShareCreated }) {
  const url = `${window.location.origin}${created.path}`;
  const field = useRef<HTMLInputElement>(null);
  const [copied, setCopied] = useState<"yes" | "manual" | null>(null);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied("yes");
    } catch {
      // Clipboard blocked (permissions, insecure context): select it so Ctrl/⌘+C works.
      field.current?.select();
      setCopied("manual");
    }
  }

  return (
    <section className="card stack share-link" aria-labelledby="share-link-title">
      <h2 className="section-title" id="share-link-title">Your private link</h2>
      <div className="share-link__row">
        <label className="visually-hidden" htmlFor="share-link-url">Private link</label>
        <input id="share-link-url" ref={field} className="input share-link__url" readOnly value={url}
          onFocus={(e) => e.currentTarget.select()} aria-describedby="share-link-help" />
        <Button variant="primary" onClick={() => void copy()}>Copy link</Button>
      </div>
      <p className="subtle" role="status">
        {copied === "yes" ? "Copied. Paste it into a message to your reviewer." : copied === "manual" ? "Couldn't copy automatically: the link is selected, press Ctrl+C (⌘+C on a Mac)." : ""}
      </p>
      <ul className="mini-list" id="share-link-help">
        <li><strong>This is the only time the link is shown.</strong> CodeCoach keeps only a scrambled fingerprint of it. If you lose it, make a new link; the old one stops working.</li>
        <li>Anyone with the link can see what you selected until {formatDateTime(created.share.expires_at)}, or until you turn it off.</li>
        <li>Send it yourself, to someone you trust. CodeCoach never emails or messages anyone.</li>
      </ul>
    </section>
  );
}
