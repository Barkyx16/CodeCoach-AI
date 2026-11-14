import { useEffect, useId, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import type { Impact, ImpactEffect, LifecycleOutcome } from "@/api/types";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";
import { useRequestKey } from "@/lib/requestKey";

/** In the order a learner weighs them: what goes first, what stays last. */
const GROUPS: { effect: ImpactEffect["effect"]; heading: string }[] = [
  { effect: "deleted", heading: "Deleted" },
  { effect: "archived", heading: "Archived (you can undo this)" },
  { effect: "unlinked", heading: "Unlinked (the other record stays)" },
  { effect: "unavailable", heading: "Kept, but no longer available" },
  { effect: "kept", heading: "Kept" },
];

const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/**
 * What an archive or a delete will do, before it's done (docs/LIFECYCLE.md): the server's plan,
 * every item by kind and title, grouped by what happens to it. The button names the action and its
 * reach in words, and sends back the plan it showed: if the scope changed meanwhile, nothing is
 * done and the new plan is shown instead. A retry after a lost reply uses the same request key, so
 * it's answered with what was done, not done twice.
 */
export function ImpactPreview({ load, run, danger = false, onDone, onCancel }: {
  load: () => Promise<Impact>;
  run: (fingerprint: string, requestKey: string) => Promise<LifecycleOutcome>;
  danger?: boolean;
  onDone: (outcome: LifecycleOutcome) => void;
  onCancel: () => void;
}) {
  const [impact, setImpact] = useState<Impact | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [runError, setRunError] = useState<unknown>(null);
  const [changed, setChanged] = useState(false);
  const [busy, setBusy] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const headingId = useId();
  const { keyFor, done } = useRequestKey();

  useEffect(() => {
    let live = true;
    load().then((i) => { if (live) setImpact(i); }, (e) => { if (live) setLoadError(e); });
    return () => { live = false; };
  }, [load]);
  // The list is what to read before choosing: focus goes to it when it arrives or changes.
  useEffect(() => { if (impact) heading.current?.focus(); }, [impact]);

  if (loadError) return <div className="impact stack-sm"><InlineError error={loadError} /><span className="row"><Button size="sm" variant="ghost" onClick={onCancel}>Close</Button></span></div>;
  if (!impact) return <p className="subtle" role="status">Working out what this affects…</p>;
  const actionable = impact.effects.some((e) => e.effect !== "kept");

  async function go(i: Impact) {
    setBusy(true);
    setRunError(null);
    try {
      const out = await run(i.fingerprint, keyFor(i.fingerprint));
      done();
      onDone(out);
    } catch (e) {
      const current = e instanceof ApiError && e.code === "impact_changed" ? (e.details as { current?: Impact } | null)?.current : null;
      if (current) {
        setChanged(true);
        setImpact(current);
      } else setRunError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="impact stack-sm" role="group" aria-labelledby={headingId}>
      <h3 id={headingId} className="impact__title" tabIndex={-1} ref={heading}>What this will do</h3>
      {changed && (
        <p className="banner banner--warning">What this affects changed since you looked. Nothing was done: check the list again.</p>
      )}
      {GROUPS.map((g) => {
        const items = impact.effects.filter((e) => e.effect === g.effect);
        if (items.length === 0) return null;
        return (
          <div key={g.effect} className="impact__group">
            <h4 className="impact__heading">{g.heading} ({items.length})</h4>
            <ul className="mini-list">
              {items.map((e) => (
                <li key={`${e.kind}:${e.id ?? e.title}`}>
                  <span className="subtle">{capital(e.kind)}:</span> {e.title}
                  {e.note && <>{" "}<span className="subtle impact__note">{e.note}</span></>}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      {!actionable && <p>{impact.summary}. Nothing would change.</p>}
      {(impact.notes ?? []).map((n) => <p key={n} className="subtle">{n}</p>)}
      <span className="row">
        {actionable && (
          <Button size="sm" variant={danger ? "danger" : "primary"} loading={busy} onClick={() => void go(impact)}>
            {impact.summary}
          </Button>
        )}
        <Button size="sm" variant="ghost" disabled={busy} onClick={onCancel}>{actionable ? "Cancel" : "Close"}</Button>
      </span>
      <InlineError error={runError} />
    </div>
  );
}
