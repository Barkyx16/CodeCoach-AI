import { useEffect, useId, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useOnboarding, useUpdateOnboarding } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/States";

import { searchHelp, type HelpLink } from "./helpTopics";

/** Help for the core actions, organised by topic and searchable, plus the introduction controls. */
export function HelpPage() {
  const [query, setQuery] = useState("");
  // The count is announced once typing pauses, not on every keystroke.
  const [announced, setAnnounced] = useState("");
  const searchId = useId();
  const topics = searchHelp(query);
  const count = topics.reduce((n, t) => n + t.items.length, 0);

  const summary = count === 0 ? "No help topics match." : `${count} ${count === 1 ? "answer matches" : "answers match"}.`;
  useEffect(() => {
    const id = window.setTimeout(() => setAnnounced(summary), 600);
    return () => window.clearTimeout(id);
  }, [summary]);

  return (
    <div className="page help-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">HELP</p>
          <h1 className="page__title">How CodeCoach works</h1>
          <p className="page__subtitle">Short answers about the things you'll do most, with links to the real pages.</p>
        </div>
      </div>
      <div className="help-page__layout">
        <div className="stack">
          <form role="search" className="help-search" onSubmit={(e) => e.preventDefault()}>
            <label className="field__label" htmlFor={searchId}>Search help</label>
            <input id={searchId} type="search" className="input" value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="For example: drafts, voice, feedback" aria-describedby={`${searchId}-count`} />
            <p id={`${searchId}-count`} className="subtle">{query.trim() ? summary : ""}</p>
            <p className="visually-hidden" role="status">{query.trim() ? announced : ""}</p>
          </form>
          {topics.length === 0 && (
            <Card className="stack-sm">
              <p>Nothing matches “{query.trim()}”. Try a single word such as <em>draft</em>, <em>voice</em> or <em>history</em>.</p>
              <span><Button size="sm" variant="secondary" onClick={() => setQuery("")}>Clear the search</Button></span>
            </Card>
          )}
          {topics.map((t) => (
            <section key={t.id} className="card stack-sm help-topic" aria-labelledby={`help-${t.id}`}>
              <h2 className="section-title" id={`help-${t.id}`}>{t.title}</h2>
              {t.items.map((item) => (
                <details key={item.q} className="help-item" open={!!query.trim() || undefined}>
                  <summary>{item.q}</summary>
                  <p>{item.a}</p>
                  {item.links && <p className="help-item__links">{item.links.map((l) => <HelpAnchor key={l.to} link={l} />)}</p>}
                </details>
              ))}
            </section>
          ))}
        </div>
        <aside className="stack">
          <IntroductionCard />
          <Card className="stack-sm">
            <h2 className="section-title">Something not working?</h2>
            <p>A support report describes the problem without your answers, code or account details. You see all of it
              first, and it stays on this device until you copy or save it.</p>
            <p><Link to="/help/report" state={{ from: "/help", fromLabel: "Back to Help" }}>Get a support report</Link></p>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function HelpAnchor({ link }: { link: HelpLink }) {
  if (link.external) {
    return <a href={link.to} target="_blank" rel="noopener noreferrer">{link.label}<span className="visually-hidden"> (opens in a new tab)</span></a>;
  }
  return <Link to={link.to}>{link.label}</Link>;
}

const STATUS_TEXT = {
  not_started: "You haven't taken the introduction.",
  in_progress: "The introduction is open.",
  paused: "You left the introduction part-way.",
  completed: "You finished the introduction.",
  skipped: "You skipped the introduction.",
} as const;

/** Start, resume or replay the guided introduction; it opens on a real page from your career. */
function IntroductionCard() {
  const { isAuthenticated } = useAuth();
  const state = useOnboarding(isAuthenticated);
  const update = useUpdateOnboarding();
  const navigate = useNavigate();

  if (!isAuthenticated) {
    return (
      <Card className="stack-sm">
        <h2 className="section-title">The introduction</h2>
        <p>A short guided tour of the practice page for your job. It needs an account, or a guest session.</p>
        <p className="row"><Link to="/login" state={{ from: "/welcome" }}>Sign in</Link><Link to="/register">Create an account</Link></p>
      </Card>
    );
  }
  const o = state.data;
  if (!o) return null;
  const starter = o.starter;
  const resumable = (o.tour_status === "paused" || o.tour_status === "in_progress") && starter
    && ((starter.kind === "problem") === (o.tour_kind === "coding"));

  async function run(resume: boolean) {
    if (!starter) return;
    try {
      await update.mutateAsync(resume ? { tour: "step", tour_step: o!.tour_step } : { tour: "start", tour_kind: o!.format });
      navigate(starter.href);
    } catch {
      /* shown below */
    }
  }

  return (
    <Card className="stack-sm">
      <h2 className="section-title">The introduction</h2>
      <p>{STATUS_TEXT[o.tour_status]}{(o.tour_status === "paused" || o.tour_status === "in_progress") ? ` You were on step ${o.tour_step + 1} of ${o.tour_steps}.` : ""}</p>
      {starter ? (
        <>
          <p className="subtle">It opens on “{starter.title}”, a real {starter.kind === "problem" ? "problem" : "question"} for your job. Taking it again doesn't change any of your practice.</p>
          <span className="row">
            {resumable && <Button size="sm" variant="primary" loading={update.isPending} onClick={() => void run(true)}>Resume</Button>}
            <Button size="sm" variant={resumable ? "secondary" : "primary"} loading={update.isPending && !resumable}
              onClick={() => void run(false)}>
              {o.tour_status === "not_started" ? "Start the tour" : "Replay from the start"}
            </Button>
          </span>
        </>
      ) : <p className="subtle">There's no practice for your job on this server yet, so the tour can't open.</p>}
      <p><Link to="/welcome">See the ways to get started</Link></p>
      <InlineError error={update.error} />
    </Card>
  );
}
