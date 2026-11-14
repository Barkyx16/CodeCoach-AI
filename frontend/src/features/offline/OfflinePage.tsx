import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/Button";
import { EmptyState, InlineError, LoadingState } from "@/components/States";
import { useOnline } from "@/hooks/useOnline";
import { formatDateTime } from "@/lib/format";
import { useAppShell } from "@/pwa/useAppShell";

import { clearOffline, MAX_SAVED, offlineSupported, revalidateOffline, storageEstimate, type OfflineEntry } from "./offlineStore";
import { useOfflineList, useOfflineMutation } from "./useOfflineEntry";

const KIND: Record<OfflineEntry["kind"], string> = { lesson: "Lesson", question: "Question", problem: "Coding problem" };

function size(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Everything kept on this device for offline use, with sizes, dates and removal. */
export function OfflinePage() {
  const list = useOfflineList();
  const remove = useOfflineMutation();
  const online = useOnline();
  const shell = useAppShell();
  const qc = useQueryClient();
  const estimate = useQuery({ queryKey: ["offline", "estimate"], queryFn: storageEstimate, networkMode: "always" });
  const [notice, setNotice] = useState("");
  const refresh = useMutation({
    mutationFn: revalidateOffline,
    networkMode: "always",
    onSuccess: (r) => {
      setNotice(r.unreachable ? "Couldn't reach the server to check your saved items. Try again later."
        : r.removed.length ? `Removed ${r.removed.map((e) => `“${e.title}”`).join(", ")}: no longer available.`
        : `All ${r.refreshed.length} saved ${r.refreshed.length === 1 ? "item is" : "items are"} up to date.`);
      void qc.invalidateQueries({ queryKey: ["offline"] });
    },
  });
  const clearAll = useMutation({ mutationFn: clearOffline, networkMode: "always", onSuccess: () => void qc.invalidateQueries({ queryKey: ["offline"] }) });
  const items = list.data ?? [];
  const total = items.reduce((n, e) => n + e.bytes, 0);
  const { mutate: check } = refresh;
  const hasItems = items.length > 0;
  // Coming back here online: check that saved items still exist (retired content is removed).
  useEffect(() => {
    if (online && hasItems) check();
  }, [online, hasItems, check]);

  return (
    <div className="page offline-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">THIS DEVICE</p>
          <h1 className="page__title">Saved for offline</h1>
          <p className="page__subtitle">Public lessons, questions and coding problems you chose to keep on this device. Your answers and account data aren't stored here.</p>
        </div>
      </div>

      <section className="card stack-sm" aria-labelledby="offline-what">
        <h2 className="section-title" id="offline-what">What works without a connection</h2>
        <ul className="mini-list">
          <li>Opening the app {shell.offlineReady ? "(ready on this device)" : shell.unsupportedReason ? `(not available: ${shell.unsupportedReason})` : "(after it has loaded once online)"}.</li>
          <li>Reading the items below, writing answer drafts and editing code on this device.</li>
          <li>Notes you edit offline are kept on this device and sent when you're back online.</li>
        </ul>
        <p className="subtle">Needs a connection: feedback on answers, running and judging code, the coach, mock interviews, voice, signing in, and anything not saved here. Nothing is graded offline.</p>
      </section>

      {!offlineSupported() ? <p className="banner banner--info">This browser can't keep pages for offline use (it needs a secure connection and Cache Storage).</p>
        : list.isPending ? <LoadingState label="Reading this device…" />
        : items.length === 0 ? (
          <EmptyState title="Nothing saved yet" action={<Link className="btn btn--secondary btn--md" to="/learn">Browse lessons</Link>}>
            Use “Save for offline” on a lesson, a question or a coding problem.
          </EmptyState>
        ) : (
          <section className="stack" aria-labelledby="offline-items">
            <div className="row offline-page__summary">
              <h2 className="section-title" id="offline-items">{items.length} of up to {MAX_SAVED} items · {size(total)}</h2>
              {estimate.data && <span className="subtle">This site uses {size(estimate.data.usage)} of the {size(estimate.data.quota)} the browser allows.</span>}
            </div>
            <ul className="offline-list">
              {items.map((e) => (
                <li key={`${e.kind}:${e.key}`} className="card offline-list__item">
                  <Link to={e.href} className="offline-list__title">{e.title}</Link>
                  <span className="subtle">{KIND[e.kind]} · {e.subtitle.split(" · ").slice(1).join(" · ") || e.subtitle} · saved {formatDateTime(e.saved_at)}{e.version ? ` · version ${e.version}` : ""} · {size(e.bytes)}</span>
                  <span><Button size="sm" variant="ghost" aria-label={`Remove ${e.title} from this device`}
                    loading={remove.isPending && remove.variables?.key === e.key}
                    onClick={() => remove.mutate({ kind: e.kind, key: e.key, remove: true })}>Remove</Button></span>
                </li>
              ))}
            </ul>
            <span className="row">
              <Button size="sm" disabled={!online} loading={refresh.isPending} onClick={() => refresh.mutate()}>Check for updates</Button>
              <Button size="sm" variant="ghost" loading={clearAll.isPending}
                onClick={() => { if (window.confirm("Remove every saved item from this device?")) clearAll.mutate(); }}>Remove all</Button>
            </span>
          </section>
        )}
      <p role="status" className="subtle">{notice}</p>
      <InlineError error={remove.error ?? refresh.error ?? clearAll.error} />
    </div>
  );
}
