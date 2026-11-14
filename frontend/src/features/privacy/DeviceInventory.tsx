import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/endpoints";
import { recentKey } from "@/app/commands";
import { deviceCopies, type DeviceCopy } from "./copyKinds";
import { Button } from "@/components/Button";
import { readCopy, removeCopies } from "@/lib/deviceCopies";
import { timeAgo } from "@/lib/format";
import { forgetIntents, listIntents, type IntentKind, type PendingIntent } from "@/lib/pendingIntents";

const INTENT_LABEL: Record<IntentKind, string> = {
  submission: "Code submission", run: "Code run", hint: "Hint request", review: "Code review request",
  story: "Story save", note_copy: "Note copy",
};
// Targets that are public problem names, safe to show; the others are record ids.
const NAMED_TARGET = new Set<IntentKind>(["submission", "run", "hint", "review"]);
const intentId = (i: PendingIntent) => `intent:${i.kind}:${i.target}`;

function readable(): boolean {
  try {
    void window.localStorage.length;
    return true;
  } catch {
    return false;
  }
}

function recentCount(userId: string): number {
  try {
    const v: unknown = JSON.parse(readCopy(recentKey(userId)) ?? "[]");
    return Array.isArray(v) ? v.length : 0;
  } catch {
    return 0;
  }
}

/**
 * Which of these interviews are this account's: interview drafts are keyed by the interview, not
 * the account, so only the ones this account owns are listed (summaries only, never transcripts).
 */
function useOwnedInterviews(ids: string[]) {
  const wanted = [...new Set(ids)].sort();
  return useQuery({
    queryKey: ["me", "interviews-owned", wanted],
    enabled: wanted.length > 0,
    queryFn: async () => {
      const owned = new Set<string>();
      for (let page = 1; page <= 10; page++) {
        const p = await api.interviews({ page, page_size: 100 });
        for (const iv of p.items) if (wanted.includes(iv.id)) owned.add(iv.id);
        if (wanted.every((id) => owned.has(id)) || page * p.page_size >= p.total) break;
      }
      return owned;
    },
  });
}

/** One choosable item: a checkbox with what it is, and a link to its page when there is one. */
function Item({ id, label, detail, open, checked, onPick }: {
  id: string; label: string; detail: string; open?: string | null; checked: boolean; onPick: (id: string, on: boolean) => void;
}) {
  return (
    <li className="yd-item">
      <label className="checkbox">
        <input type="checkbox" checked={checked} onChange={(e) => onPick(id, e.target.checked)} />
        <span><strong>{label}</strong> <span className="subtle">· {detail}</span></span>
      </label>
      {open && <Link to={open} className="yd-open" aria-label={`Open: ${label}`}>Open</Link>}
    </li>
  );
}

const sizeOf = (c: DeviceCopy) => (c.kind.code ? `${c.size} ${c.size === 1 ? "line" : "lines"}` : `${c.size} ${c.size === 1 ? "word" : "words"}`);

/** This account's copies on this browser, chosen and removed precisely; nothing else is touched. */
export function DeviceInventory({ userId }: { userId: string }) {
  const [version, setVersion] = useState(0);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [reviewing, setReviewing] = useState(false);
  const [outcome, setOutcome] = useState<{ text: string; tone: "success" | "warning" } | null>(null);
  const outcomeRef = useRef<HTMLParagraphElement>(null);
  const reviewRef = useRef<HTMLHeadingElement>(null);

  // Another tab keeping or removing a copy: list what's there now.
  useEffect(() => {
    const changed = () => setVersion((v) => v + 1);
    window.addEventListener("storage", changed);
    return () => window.removeEventListener("storage", changed);
  }, []);
  useEffect(() => { if (outcome) outcomeRef.current?.focus(); }, [outcome]);
  useEffect(() => { if (reviewing) reviewRef.current?.focus(); }, [reviewing]);

  const ok = readable();
  const all = ok ? deviceCopies(userId) : [];
  const ivIds = all.flatMap((c) => (c.interviewId ? [c.interviewId] : []));
  const owned = useOwnedInterviews(ivIds);
  const copies = all.filter((c) => !c.interviewId || owned.data?.has(c.interviewId));
  const checkingInterviews = ivIds.length > 0 && owned.isPending;
  const intents = ok ? listIntents(userId) : [];
  const recents = ok ? recentCount(userId) : 0;
  void version; // re-read on every change above

  if (!ok) {
    return (
      <p className="banner banner--warning" role="status">
        This browser isn't letting CodeCoach use its storage here (private browsing, or site data blocked), so nothing
        of yours is kept on this device and there's nothing to list or remove. Your account's saved work is unaffected.
      </p>
    );
  }

  const unsent = copies.filter((c) => c.kind.onAccount === "none");
  const edits = copies.filter((c) => c.kind.onAccount === "saved");
  const pick = (id: string, on: boolean) => {
    setOutcome(null);
    setChosen((s) => { const n = new Set(s); if (on) n.add(id); else n.delete(id); return n; });
  };
  const chosenCopies = copies.filter((c) => chosen.has(c.key));
  const chosenIntents = intents.filter((i) => chosen.has(intentId(i)));
  const chosenRecent = chosen.has("recent") && recents > 0;
  const count = chosenCopies.length + chosenIntents.length + (chosenRecent ? 1 : 0);

  function remove() {
    const keys = [...chosenCopies.map((c) => c.key), ...(chosenRecent ? [recentKey(userId)] : [])];
    const result = removeCopies(keys);
    const intentsOk = chosenIntents.length === 0 || forgetIntents(userId, chosenIntents);
    const failed = result.failed.length + (intentsOk ? 0 : chosenIntents.length);
    const done = result.removed.length + (intentsOk ? chosenIntents.length : 0);
    const parts = [`Removed ${done} ${done === 1 ? "item" : "items"} from this browser. Everything saved to your account is unchanged.`];
    if (failed) parts.push(`${failed} couldn't be removed: this browser refused the change.`);
    if (!result.guarded) parts.push("This browser couldn't record the removal, so a page still open in another tab could keep its copy again: close those pages, then check here.");
    setOutcome({ text: parts.join(" "), tone: failed || !result.guarded ? "warning" : "success" });
    setChosen(new Set());
    setReviewing(false);
    setVersion((v) => v + 1);
  }

  const copyRow = (c: DeviceCopy) => (
    <Item key={c.key} id={c.key} label={c.kind.label} open={c.open} checked={chosen.has(c.key)} onPick={pick}
      detail={`${sizeOf(c)}${c.keptAt ? `, kept ${timeAgo(c.keptAt)}` : ""}`} />
  );
  const nothing = copies.length === 0 && intents.length === 0 && recents === 0 && !checkingInterviews;

  return (
    <div className="stack-sm">
      {outcome && <p ref={outcomeRef} tabIndex={-1} className={`banner banner--${outcome.tone}`} role="status">{outcome.text}</p>}
      {nothing ? <p>Nothing of this account's is waiting on this device.</p> : (
        <fieldset className="yd-groups stack-sm">
          <legend className="visually-hidden">Choose what to remove from this device</legend>
          {unsent.length > 0 && (
            <div className="stack-sm">
              <h3 className="review-minor">Not sent yet: only on this device</h3>
              <ul className="yd-list">{unsent.map(copyRow)}</ul>
            </div>
          )}
          {edits.length > 0 && (
            <div className="stack-sm">
              <h3 className="review-minor">Unsaved changes: your account keeps the last saved version</h3>
              <ul className="yd-list">{edits.map(copyRow)}</ul>
            </div>
          )}
          {checkingInterviews && <p className="subtle" role="status">Checking which interview drafts are yours…</p>}
          {intents.length > 0 && (
            <div className="stack-sm">
              <h3 className="review-minor">Actions waiting for a reply</h3>
              <p className="subtle">A short record (what, and when) so that after a reload the page can ask whether it went through instead of sending it twice. No content. Each goes on its own within a day.</p>
              <ul className="yd-list">
                {intents.map((i) => (
                  <Item key={intentId(i)} id={intentId(i)} label={INTENT_LABEL[i.kind]} checked={chosen.has(intentId(i))} onPick={pick}
                    detail={`${NAMED_TARGET.has(i.kind) ? `${i.target}, ` : ""}sent ${timeAgo(new Date(i.sentAt).toISOString())}`} />
                ))}
              </ul>
            </div>
          )}
          {recents > 0 && (
            <div className="stack-sm">
              <h3 className="review-minor">Other</h3>
              <ul className="yd-list"><Item id="recent" label="Pages you opened recently, for Go to" checked={chosen.has("recent")} onPick={pick} detail={`${recents} ${recents === 1 ? "page" : "pages"} (names only)`} /></ul>
            </div>
          )}
        </fieldset>
      )}
      {!nothing && (
        <div className="row">
          <Button variant="secondary" disabled={count === 0} onClick={() => { setOutcome(null); setReviewing(true); }}>
            Review removal{count ? ` (${count})` : ""}
          </Button>
        </div>
      )}
      {reviewing && count > 0 && (
        <section className="card stack-sm yd-review" aria-labelledby="yd-review-title">
          <h3 className="section-title" id="yd-review-title" ref={reviewRef} tabIndex={-1}>Before you remove {count === 1 ? "this" : `these ${count}`}</h3>
          <ul className="mini-list">
            {chosenCopies.map((c) => <li key={c.key}><strong>{c.kind.label}</strong> ({sizeOf(c)}). What stays: {c.kind.keeps}</li>)}
            {chosenIntents.map((i) => (
              <li key={intentId(i)}><strong>{INTENT_LABEL[i.kind]}</strong>: if its reply was lost, the page can't check what happened after a reload, and sending again may save it twice.</li>
            ))}
            {chosenRecent && <li><strong>Recently opened pages</strong>: Go to starts again with none. The pages themselves stay.</li>}
          </ul>
          <p className="subtle">
            Only these go, from this browser only. Your account, your sign-in and everything else on this device stay. A page
            that's open in another tab won't keep its copy again; open it again to start a new one.
          </p>
          <div className="row">
            <Button variant="danger" onClick={remove}>Remove {count === 1 ? "it" : `these ${count}`} from this device</Button>
            <Button variant="ghost" onClick={() => setReviewing(false)}>Keep them</Button>
          </div>
        </section>
      )}
    </div>
  );
}
