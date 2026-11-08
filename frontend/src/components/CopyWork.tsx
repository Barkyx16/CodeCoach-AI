import { useState } from "react";

import { Button } from "./Button";

/** When this browser can't keep a copy (private mode, storage full), the learner's text exists
 * only on this page: a way to copy it somewhere safe, said plainly. */
export function CopyWork({ text, label = "Copy your text" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button size="sm" variant="ghost" onClick={() => {
      void navigator.clipboard?.writeText(text).then(() => setCopied(true), () => setCopied(false));
    }}>
      {copied ? "Copied" : label}
    </Button>
  );
}
