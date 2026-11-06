import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import type { PrepEntry } from "@/api/types";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";

import { describeWhen } from "./dates";

const when = (t: PrepEntry["current"]) => (t.all_day ? `${describeWhen({ ...t, local_time: null })}, all day` : describeWhen(t));

/**
 * The interview's preparation times and what a reschedule would do to them. Fixed times stay;
 * times the learner chose to keep relative to the interview get a proposed new time. Nothing
 * moves until the learner ticks entries and confirms; the server re-checks that what's moved is
 * what was previewed.
 */
export function PrepPanel({ appId, eventId }: { appId: string; eventId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <details className="prep-panel" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>Preparation times</summary>
      {open && <PrepList appId={appId} eventId={eventId} />}
    </details>
  );
}

function PrepList({ appId, eventId }: { appId: string; eventId: string }) {
  const qc = useQueryClient();
  const key = ["me", "prep", appId, eventId];
  const prep = useQuery({ queryKey: key, queryFn: () => api.prepPreview(appId, eventId), staleTime: 0 });
  const [chosen, setChosen] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState("");
  if (prep.isPending) return <p className="subtle">Loading…</p>;
  if (prep.isError) return <InlineError error={prep.error} />;
  const p = prep.data;
  if (p.entries.length === 0) {
    return <p className="subtle">No preparation scheduled for this interview. <Link to="/schedule">Your schedule</Link></p>;
  }
  async function move() {
    setBusy(true);
    setError(null);
    setResult("");
    try {
      const entries = p.entries.filter((x) => chosen.includes(x.id)).map((x) => ({ id: x.id, sequence: x.sequence }));
      const r = await api.prepShift(appId, eventId, p.event_starts_at ?? null, entries);
      setResult(`Moved ${r.moved.length}.${r.already_aligned.length ? ` ${r.already_aligned.length} already matched.` : ""}`);
      setChosen([]);
      qc.setQueryData(key, r.preview);
      void qc.invalidateQueries({ queryKey: ["me", "schedule"] });
    } catch (e) {
      setError(e);
      if (e instanceof ApiError && (e.code === "interview_changed" || e.code === "prep_not_movable")) {
        setChosen([]);
        void prep.refetch(); // show what's true now; nothing was moved
      }
    } finally {
      setBusy(false);
    }
  }
  const movable = p.entries.filter((x) => x.status === "can_move");
  return (
    <div className="stack-sm">
      <ul className="prep-list">
        {p.entries.map((x) => (
          <li key={x.id}>
            {x.status === "can_move" && x.proposal ? (
              <label className="checkbox">
                <input type="checkbox" checked={chosen.includes(x.id)}
                  onChange={(e) => setChosen((c) => (e.target.checked ? [...c, x.id] : c.filter((id) => id !== x.id)))} />
                <span>{x.title}: {when(x.current)} → <strong>{when(x.proposal)}</strong></span>
              </label>
            ) : (
              <span>{x.title}: {when(x.current)}</span>
            )}
            <span className="subtle"> {x.note}</span>
          </li>
        ))}
      </ul>
      {movable.length > 0 && (
        <span className="row">
          <Button size="sm" loading={busy} disabled={chosen.length === 0} onClick={() => void move()}>
            Move selected ({chosen.length})
          </Button>
          <span className="subtle">Only ticked times move. Calendar files you downloaded before don't change by themselves.</span>
        </span>
      )}
      {result && <p className="subtle" role="status">{result}</p>}
      <InlineError error={error} />
      <p className="subtle">Choose which times follow the interview in <Link to="/schedule">your schedule</Link>.</p>
    </div>
  );
}
