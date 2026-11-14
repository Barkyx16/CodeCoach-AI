import { useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";

import { RELEASES, type ReleaseEntry } from "./releases";
import { BUILD_RELEASE, entryAccess, forThisCareer, markSeen, type WhatsNewContext } from "./whatsNew";
import { useSeenRelease, useShippedEntries, useWhatsNewContext } from "./useWhatsNew";

/**
 * What's new (Volume 11, prompt 10; docs/WHATS_NEW.md): the changes this build ships, written for
 * the learner, each with where to find it, what it doesn't do yet, and a link to the page when this
 * learner can use it there (or why not). Opening the page marks them seen for this account in this
 * browser; what was new when it opened stays marked for this visit.
 */
export function WhatsNewPage() {
  const entries = useShippedEntries();
  const { context, careerTitle, userId } = useWhatsNewContext();
  const { state, release: seen } = useSeenRelease(userId);

  // What was new on arrival, kept for this visit (and taken again if the account changes here).
  const [arrival, setArrival] = useState({ userId, seen });
  if (arrival.userId !== userId) setArrival({ userId, seen });

  useEffect(() => {
    if (!userId || state.kind === "unavailable") return;
    const already = state.kind === "seen" ? state.release : 0;
    if (already < BUILD_RELEASE) markSeen(userId, BUILD_RELEASE); // never lowered by an older build
  }, [userId, state]);

  const isNew = (e: ReleaseEntry) => arrival.seen !== null && e.release > arrival.seen && forThisCareer(e, context);
  const groups = RELEASES
    .map((r) => ({ ...r, entries: entries.filter((e) => e.release === r.release) }))
    .filter((g) => g.entries.length > 0);
  const newCount = entries.filter(isNew).length;

  return (
    <div className="page whats-new">
      <div className="page__header">
        <div>
          <h1 className="page__title">What&apos;s new</h1>
          <p className="page__subtitle">Changes in this version of CodeCoach that you can use now. Nothing here is a plan or a promise.</p>
        </div>
      </div>

      {groups.length === 0 ? (
        <p className="card">Nothing to show: this version doesn&apos;t list its changes.</p>
      ) : (
        <>
          {!userId && <p className="subtle">Sign in to see which of these are new to you and to open them.</p>}
          {userId && state.kind === "unavailable" && (
            <p className="banner banner--info">This browser isn&apos;t letting CodeCoach keep track of what you&apos;ve looked at here, so nothing is marked new. Everything is still listed.</p>
          )}
          {userId && state.kind !== "unavailable" && (
            <p className="subtle">
              {newCount > 0 ? `${newCount} new since you last looked, marked New. ` : "Nothing new since you last looked. "}
              Opening this page marks them as seen for your account in this browser; they stay listed here.
            </p>
          )}
          {groups.map((g) => (
            <ReleaseGroup key={g.release} title={g.release === BUILD_RELEASE ? `In this version: ${g.title}` : `Earlier: ${g.title}`}
              entries={g.entries} isNew={isNew} context={context} careerTitle={careerTitle} />
          ))}
        </>
      )}
    </div>
  );
}

function ReleaseGroup({ title, entries, isNew, context, careerTitle }: {
  title: string;
  entries: ReleaseEntry[];
  isNew: (e: ReleaseEntry) => boolean;
  context: WhatsNewContext;
  careerTitle?: string;
}) {
  const id = useId();
  return (
    <section className="stack-sm whats-new__group" aria-labelledby={id}>
      <h2 className="section-title" id={id}>{title}</h2>
      <ul className="whats-new__list">
        {entries.map((e) => <Entry key={e.id} entry={e} isNew={isNew(e)} context={context} careerTitle={careerTitle} />)}
      </ul>
    </section>
  );
}

function Entry({ entry, isNew, context, careerTitle }: { entry: ReleaseEntry; isNew: boolean; context: WhatsNewContext; careerTitle?: string }) {
  const access = entryAccess(entry, context, careerTitle);
  return (
    <li className="card stack-sm whats-new__entry">
      <h3 className="whats-new__title">
        {entry.title}
        {isNew && <>{" "}<span className="badge badge--success">New</span></>}
      </h3>
      <p>{entry.what}</p>
      <p className="subtle"><strong>Where:</strong> {entry.where}</p>
      {entry.limit && <p className="subtle"><strong>Limits:</strong> {entry.limit}</p>}
      {entry.audience === "coding" && access.to && <p className="subtle">For careers with coding practice.</p>}
      {access.note && <p className="subtle">{access.note}</p>}
      {access.to ? (
        <p>
          <Link className="btn btn--secondary btn--sm" to={access.to} state={{ from: "/whats-new", fromLabel: "Back to What's new" }}>
            Open {access.label}
          </Link>
        </p>
      ) : (
        <p className="subtle">{access.unavailable}</p>
      )}
    </li>
  );
}
