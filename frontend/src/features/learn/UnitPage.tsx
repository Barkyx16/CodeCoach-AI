import { useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useLearnMutation, useLearnUnit, useMyLearn, useUnitProgress } from "@/api/queries";
import type { CheckResult, UnitProgress } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { NoteCapture } from "@/features/notes/NoteCapture";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { timeAgo } from "@/lib/format";

import { statusLabel, useReadingProgress } from "./progress";
import { CheckSection, CodeBlock, ExerciseSection } from "./UnitParts";
import { SaveOffline } from "@/features/offline/SaveOffline";
import { useOnline } from "@/hooks/useOnline";

const SECTIONS = [
  ["objective", "Objective"],
  ["before", "Before you start"],
  ["explanation", "Explanation"],
  ["example", "Worked example"],
  ["mistakes", "Common mistakes"],
  ["exercise", "Try it"],
  ["check", "Check yourself"],
  ["practice", "Practice"],
  ["sources", "Sources and review"],
] as const;

const EVENT_LABEL: Record<UnitProgress["events"][number]["kind"], string> = {
  started: "Opened",
  read: "Marked read",
  check_attempted: "Check attempted",
  check_passed: "Check passed",
  practiced: "Practised",
};

/** One learning unit: read, try the exercise with as much help as you want, check, then practise. */
export function UnitPage() {
  const { unitId = "" } = useParams();
  const { user, isAuthenticated, offlineUser } = useAuth();
  const online = useOnline();
  const unit = useLearnUnit(unitId);
  const progress = useUnitProgress(unitId, isAuthenticated);
  const prereqStatus = useMyLearn(unit.data?.track ?? "", isAuthenticated && Boolean(unit.data));
  const version = unit.data?.version ?? 1;
  const event = useLearnMutation(unitId, (kind: "started" | "read") => api.learnEvent(unitId, kind, version), (p) => p);
  const check = useLearnMutation(unitId, (answers: Record<string, number>) => api.learnCheck(unitId, version, answers), (r: CheckResult) => r.progress);
  const reading = useReadingProgress(SECTIONS.map(([id]) => id), Boolean(unit.data));
  const startedFor = useRef<string | null>(null);
  const narrow = useMediaQuery("(max-width: 860px)");
  const outline = (
    <ol>
      {SECTIONS.map(([id, label], i) => (
        <li key={id}><a href={`#${id}`} aria-current={i === reading.current ? "location" : undefined}>{label}</a></li>
      ))}
    </ol>
  );

  // Opening the unit records "started" once per version (signed in only). Nothing else is implied.
  const p = progress.data;
  useEffect(() => {
    if (!unit.data || !p || p.started && p.versions_used.includes(unit.data.version)) return;
    const key = `${unit.data.id}:${unit.data.version}`;
    if (startedFor.current === key) return;
    startedFor.current = key;
    event.mutate("started");
  }, [unit.data, p]); // eslint-disable-line react-hooks/exhaustive-deps

  if (unit.isPending) return <LoadingState label="Loading the unit…" />;
  if (unit.isError) return <div className="page"><ErrorState error={unit.error} onRetry={() => void unit.refetch()} /></div>;
  const u = unit.data;
  const older = p ? p.versions_used.filter((v) => v < u.version) : [];
  const caughtUp = Boolean(p?.read || p?.check_passed);
  const changed = (event.error ?? check.error) as { code?: string } | null;

  return (
    <div className="page unit-page">
      <BackLink fallback={{ to: `/learn?career=${u.track}`, label: `${u.career_title} lessons` }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">LEARN · {u.career_title.toUpperCase()}</p>
          <h1 className="page__title">{u.title}</h1>
          <p className="row unit-page__meta">
            <span className="subtle"><Icon name="clock" size={13} /> {u.minutes} min</span>
            <span className="subtle">Version {u.version}</span>
            {u.skill && <span className="subtle">Skill: {u.skill}</span>}
            {u.review.status === "generated_draft"
              ? <Badge tone="warning">Generated draft: not reviewed yet</Badge>
              : <Badge tone="info">Reviewed by the project author</Badge>}
            {p && <Badge tone={statusLabel(p).tone}>{statusLabel(p).text}</Badge>}
          </p>
        </div>
      </div>

      {u.scope_note && (
        <p className="banner banner--warning unit-page__scope" role="note"><strong>Scope: </strong>{u.scope_note}</p>
      )}
      {older.length > 0 && !caughtUp && (
        <p className="banner banner--info">
          You last used version {Math.max(...older)}; this is version {u.version}. What changed: {u.changes.at(-1)} Your earlier progress is kept.
        </p>
      )}
      {changed?.code === "unit_changed" && (
        <p className="banner banner--warning" role="alert">
          This unit was updated while you had it open. <Button size="sm" onClick={() => window.location.reload()}>Reload the new version</Button>
        </p>
      )}

      {isAuthenticated && p && (
        <Card className="unit-next row" role="region" aria-label="Next step">
          <span><strong>Next:</strong> {p.next_action.label}</span>
          {p.next_action.kind === "read" && <a className="btn btn--secondary btn--sm" href="#finish-reading">Go to the end of the reading</a>}
          {p.next_action.kind === "check" && <a className="btn btn--secondary btn--sm" href="#check">Go to the check</a>}
          {p.next_action.kind === "practice" && <Link className="btn btn--primary btn--sm" to={u.practice.href}>{u.practice.label}</Link>}
        </Card>
      )}

      <SaveOffline kind="lesson" itemKey={u.id} label="lesson" />
      <div className="unit-page__layout">
        <nav className="unit-outline" aria-label="Sections of this unit">
          <p className="unit-outline__progress" aria-live="off">
            Section {reading.current + 1} of {SECTIONS.length}
            <progress aria-label="Reading progress through this unit" value={reading.furthest + 1} max={SECTIONS.length} />
          </p>
          {narrow ? (
            <details>
              <summary>On this page ({SECTIONS.length} sections)</summary>
              {outline}
            </details>
          ) : outline}
        </nav>

        <article className="unit-content stack">
          <section className="learn-section" id="objective" aria-labelledby="objective-title">
            <h2 className="section-title" id="objective-title">Objective</h2>
            <p>{u.objective}</p>
          </section>

          <section className="learn-section" id="before" aria-labelledby="before-title">
            <h2 className="section-title" id="before-title">Before you start</h2>
            {u.prerequisites.length === 0 ? <p>No other unit is needed first.</p> : (
              <ul className="mini-list">
                {u.prerequisites.map((pre) => {
                  const st = prereqStatus.data?.[pre.id];
                  return (
                    <li key={pre.id}>
                      <Link to={`/learn/${pre.id}`} state={{ from: `/learn/${u.id}`, fromLabel: `Back to ${u.title}` }}>{pre.title}</Link>
                      {isAuthenticated && <> · <span className="subtle">{statusLabel(st).text}</span></>}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="learn-section stack-sm" id="explanation" aria-labelledby="explanation-title">
            <h2 className="section-title" id="explanation-title">Explanation</h2>
            {u.explanation.map((para, i) => <p key={i}>{para}</p>)}
          </section>

          <section className="learn-section stack-sm" id="example" aria-labelledby="example-title">
            <h2 className="section-title" id="example-title">Worked example: {u.example.title}</h2>
            <p>{u.example.intro}</p>
            {u.example.code && <CodeBlock code={u.example.code} language={u.example.language ?? null} label={u.example.title} />}
            <ol className="learn-walkthrough">{u.example.walkthrough.map((w, i) => <li key={i}>{w}</li>)}</ol>
          </section>

          <section className="learn-section" id="mistakes" aria-labelledby="mistakes-title">
            <h2 className="section-title" id="mistakes-title">Common mistakes</h2>
            <ul className="mini-list">{u.mistakes.map((m) => <li key={m}>{m}</li>)}</ul>
          </section>

          <div className="unit-read" id="finish-reading">
            {isAuthenticated ? (
              p?.read ? <p className="subtle"><Icon name="check" size={14} /> Marked as read for version {u.version}. Reading on its own isn't mastery: the check and practice are.</p> : (
                <Button onClick={() => event.mutate("read")} loading={event.isPending && event.variables === "read"}>I've read this unit</Button>
              )
            ) : <p className="subtle">Sign in to keep your place and progress.</p>}
            {changed?.code !== "unit_changed" && <InlineError error={event.error} />}
          </div>

          <ExerciseSection unit={u} draftKey={`learn-draft:${user?.id ?? "anon"}:${u.id}`} />

          <CheckSection unit={u} signedIn={isAuthenticated || Boolean(offlineUser)} offline={!online} onSubmit={(a) => check.mutate(a)} pending={check.isPending}
            error={changed?.code === "unit_changed" ? null : check.error} result={check.data ?? null} />

          <section className="learn-section stack-sm" id="practice" aria-labelledby="practice-title">
            <h2 className="section-title" id="practice-title">Practice</h2>
            <p>Put it to work on a real {u.practice.kind === "problem" ? "coding problem" : "interview question"}.</p>
            <p><Link className="btn btn--primary btn--md" to={u.practice.href} state={{ from: `/learn/${u.id}`, fromLabel: `Back to ${u.title}` }}>{u.practice.label}</Link></p>
            {p && (p.practiced
              ? <p className="subtle"><Icon name="check" size={14} /> Practised since you started this unit: {p.practiced_evidence}.</p>
              : <p className="subtle">Not practised yet. It's recorded from your real {u.practice.kind === "problem" ? "submission" : "answer"}, not from reading.</p>)}
          </section>

          {isAuthenticated && <NoteCapture source={{ type: "lesson", id: u.id }} excerpt={u.objective} excerptLabel="the lesson's objective" />}

          <section className="learn-section stack-sm" id="sources" aria-labelledby="sources-title">
            <h2 className="section-title" id="sources-title">Sources and review</h2>
            <p className="subtle">{u.review.note} ({u.review.by}, {u.review.on})</p>
            {u.references.length === 0 ? <p>No references are recorded for this unit.</p> : (
              <ul className="learn-refs">
                {u.references.map((r) => (
                  <li key={r.title}>
                    {r.url ? <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a> : <span>{r.title}</span>}
                    <span className="subtle"> · {r.publisher}{r.published ? ` · ${r.published}` : ""}</span>
                    {r.kind === "repository" && <Badge>In this repository</Badge>}
                    {r.note && <span className="subtle learn-refs__note">{r.note}</span>}
                  </li>
                ))}
              </ul>
            )}
            {!u.references.some((r) => r.kind === "external") && <p className="subtle">No outside references: this unit is based on CodeCoach's own question bank and rubric.</p>}
            <details>
              <summary>Version history</summary>
              <ol>{u.changes.map((c, i) => <li key={i}>Version {i + 1}: {c}</li>)}</ol>
            </details>
          </section>

          {p && p.events.length > 0 && (
            <section className="learn-section" aria-labelledby="mine-title">
              <h2 className="section-title" id="mine-title">Your progress on this unit</h2>
              <ul className="learn-events">
                {p.events.map((e, i) => (
                  <li key={i}>{EVENT_LABEL[e.kind]}{e.detail ? `: ${e.detail}` : ""} <span className="subtle">· version {e.version} · {timeAgo(e.at)}</span></li>
                ))}
              </ul>
            </section>
          )}
        </article>
      </div>
    </div>
  );
}
