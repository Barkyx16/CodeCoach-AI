import { Link } from "react-router-dom";

import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";
import { useOnline } from "@/hooks/useOnline";
import { formatDateTime } from "@/lib/format";

import { offlineSupported, type OfflineKind } from "./offlineStore";
import { useOfflineEntry, useOfflineMutation } from "./useOfflineEntry";

const NEEDS_SERVER: Record<OfflineKind, string> = {
  lesson: "Offline you can read it; the check needs a connection.",
  question: "Offline you can read it and write a draft on this device; feedback needs a connection.",
  problem: "Offline you can read it and edit code on this device; running and judging need a connection.",
};

/** "Save for offline" for public content, with what will and won't work without a connection. */
export function SaveOffline({ kind, itemKey, label }: { kind: OfflineKind; itemKey: string; label: string }) {
  const entry = useOfflineEntry(kind, itemKey);
  const mutation = useOfflineMutation();
  const online = useOnline();
  if (!offlineSupported()) return null;
  const saved = entry.data;
  return (
    <section className="card stack-sm save-offline" aria-labelledby={`offline-${kind}`}>
      <h2 className="section-title" id={`offline-${kind}`}>Offline</h2>
      {saved ? (
        <>
          <p>Saved on this device {formatDateTime(saved.saved_at)}{saved.version ? ` (version ${saved.version})` : ""}. {NEEDS_SERVER[kind]}</p>
          <span className="row">
            {online && <Button size="sm" loading={mutation.isPending && !mutation.variables?.remove}
              onClick={() => mutation.mutate({ kind, key: itemKey })}>Update copy</Button>}
            <Button size="sm" variant="ghost" loading={mutation.isPending && Boolean(mutation.variables?.remove)}
              onClick={() => mutation.mutate({ kind, key: itemKey, remove: true })}>Remove from device</Button>
            <Link to="/offline">All saved items</Link>
          </span>
        </>
      ) : (
        <>
          <p className="subtle">Keep this {label} on this device to read it without a connection. {NEEDS_SERVER[kind]}</p>
          <span><Button size="sm" disabled={!online} loading={mutation.isPending}
            onClick={() => mutation.mutate({ kind, key: itemKey })}>Save for offline</Button></span>
          {!online && <p className="subtle">Connect to save it.</p>}
        </>
      )}
      <p className="visually-hidden" role="status">{mutation.isSuccess ? (mutation.data ? "Saved for offline." : "Removed from this device.") : ""}</p>
      <InlineError error={mutation.error} />
    </section>
  );
}
