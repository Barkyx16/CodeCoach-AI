import { useId, useState, type ReactNode } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { useCapabilities, useMySubmissions, useProblem, useSubmission, useSubmit } from "@/api/queries";
import type { SubmissionCreate, SubmissionMode } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { ErrorState, LoadingState } from "@/components/States";
import { Tabs } from "@/components/Tabs";
import { EditorPreferencesControls } from "@/features/settings/EditorPreferencesControls";
import { useMediaQuery } from "@/hooks/useMediaQuery";

import { CoachPanel } from "./CoachPanel";
import { CodeEditor } from "./CodeEditor";
import { ProblemStatement } from "./ProblemStatement";
import { SubmissionPanel } from "./SubmissionPanel";
import { useDraft, type SaveState } from "./useDraft";
import { WorkspaceFrame } from "./WorkspaceFrame";
import { Icon } from "@/components/Icon";
import { LearnLinks } from "@/features/learn/LearnLinks";
import { NoteCapture } from "@/features/notes/NoteCapture";
import { QueueBar } from "@/features/saved/QueueBar";
import { SaveControls } from "@/features/saved/SaveControls";

function newRequestId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
  }
}

const SAVE_LABEL: Record<SaveState, string> = { saved: "Draft saved", saving: "Saving…", unsaved: "Unsaved changes", error: "Draft not saved — browser storage unavailable" };

export default function WorkspacePage() {
  const { slug = "" } = useParams();
  // Wait for the session to be restored: fetched anonymously, the open isn't recorded and the
  // cached anonymous copy would be reused once signed in.
  const { isRestoring } = useAuth();
  const problem = useProblem(slug, !isRestoring);

  if (problem.isPending) return <LoadingState label="Loading problem…" />;
  if (problem.isError) {
    return (
      <div className="page">
        <ErrorState error={problem.error} onRetry={() => problem.refetch()} />
        <p className="subtle" style={{ textAlign: "center" }}><Link to="/problems">Back to all problems</Link></p>
      </div>
    );
  }
  return <Workspace key={slug} problem={problem.data} />;
}

function Workspace({ problem }: { problem: NonNullable<ReturnType<typeof useProblem>["data"]> }) {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const isNarrow = useMediaQuery("(max-width: 900px)");
  const draft = useDraft(problem.slug, problem.starter_code, user?.id ?? "anon");
  const submit = useSubmit();
  const execution = useCapabilities().data?.execution;
  const canRun = execution?.run_available === true;
  const savedOnly = execution?.submit_mode === "saved_only";
  const [pendingMode, setPendingMode] = useState<SubmissionMode>("submit");
  const [chosenId, setSubmissionId] = useState<string | null>(null);
  // Reload recovery: until you submit again, show a submission of this problem that's still queued or running.
  const latest = useMySubmissions({ problem_slug: problem.slug, page: 1, page_size: 1 }, isAuthenticated);
  const pendingLatest = latest.data?.items[0];
  const resumable = pendingLatest && (pendingLatest.status === "QUEUED" || pendingLatest.status === "RUNNING") ? pendingLatest.id : null;
  const submissionId = chosenId ?? resumable;
  const submission = useSubmission(submissionId);
  // A request that failed in the network keeps its id, so "Try again" can't create a duplicate.
  const [unconfirmed, setUnconfirmed] = useState<SubmissionCreate | null>(null);
  const [highlightLine, setHighlightLine] = useState<number | null>(null);
  const [mobileTab, setMobileTab] = useState<"problem" | "code" | "coach">("problem");
  const [showSettings, setShowSettings] = useState(false);
  const settingsId = useId();
  const judging = !!submission.data?.execution_enabled && !submission.data.is_terminal;

  const goSignIn = () => navigate("/login", { state: { from: `/problems/${problem.slug}` } });

  // Code offered from a past submission (History): never replaces the draft without a choice.
  const location = useLocation();
  const offer = location.state as { loadCode?: string; loadFrom?: string } | null;
  const offeredCode = offer?.loadCode && offer.loadCode !== draft.code ? offer.loadCode : null;
  const settleOffer = (replace: boolean) => {
    if (replace && offeredCode) draft.setCode(offeredCode);
    navigate(location.pathname + location.search, { replace: true, state: null });
  };

  async function send(body: SubmissionCreate) {
    setPendingMode(body.mode ?? "submit");
    try {
      const created = await submit.mutateAsync(body);
      setUnconfirmed(null);
      setSubmissionId(created.id);
      if (isNarrow) setMobileTab("code");
    } catch (e) {
      // Only a lost connection leaves it unknown whether the server got the request.
      setUnconfirmed(e instanceof ApiError && e.code === "network_error" ? body : null);
    }
  }

  async function handleSubmit(mode: SubmissionMode = "submit") {
    if (!isAuthenticated) return goSignIn();
    if (submit.isPending || judging) return;
    await send({ problem_slug: problem.slug, language: "java", source_code: draft.code, mode, client_request_id: newRequestId() });
  }

  function jumpToLine(line: number | null) {
    setHighlightLine(line);
    if (line && isNarrow) setMobileTab("code");
  }

  const toolbar = (
    <div className="editor-toolbar">
      <span className="editor-toolbar__lang"><Icon name="code" size={15} />Solution.java</span>
      {/* Not a live region: it changes with every keystroke. A failure is announced once. */}
      <span className={`save-state save-state--${draft.saveState}`}>{SAVE_LABEL[draft.saveState]}</span>
      {draft.saveState === "error" && <span className="visually-hidden" role="alert">Your draft isn't being saved: this browser's storage is unavailable.</span>}
      <div className="editor-toolbar__actions">
        <Button size="sm" variant="ghost" aria-expanded={showSettings} aria-controls={settingsId}
          onClick={() => setShowSettings((value) => !value)}>Editor settings</Button>
        <Button size="sm" variant="ghost" disabled={!draft.isModified}
          onClick={() => { if (window.confirm("Reset to the starter code? Your draft will be lost.")) draft.reset(); }}>
          Reset
        </Button>
        {canRun && (
          <Button size="sm" variant="secondary" loading={submit.isPending && pendingMode === "run"}
            disabled={judging || (submit.isPending && pendingMode !== "run")} onClick={() => void handleSubmit("run")}
            title="Run the public tests only (Ctrl/⌘ + ')">
            Run
          </Button>
        )}
        <Button size="sm" variant="primary" loading={submit.isPending && pendingMode === "submit"}
          disabled={judging || (submit.isPending && pendingMode !== "submit")} onClick={() => void handleSubmit()}
          title={savedOnly ? "Save this attempt without a verdict (Ctrl/⌘ + Enter)" : "Submit (Ctrl/⌘ + Enter)"}
          aria-label={savedOnly ? "Save attempt" : undefined}>
          {savedOnly ? "Save attempt" : "Submit"} <Icon name="arrow" size={14} />
        </Button>
      </div>
    </div>
  );

  const savedRef = { item_type: "problem" as const, track: "", ref_id: problem.slug };
  const statement = (
    <section className="panel-scroll" aria-label="Problem description" tabIndex={0}>
      <ProblemStatement problem={problem}
        before={isAuthenticated ? <div className="focus-hide display-contents"><QueueBar item={savedRef} /></div> : undefined}
        after={<div className="focus-hide display-contents">
          <LearnLinks query={{ problem_slug: problem.slug }} from={{ from: `/problems/${problem.slug}`, fromLabel: "Back to the problem" }} />
          {isAuthenticated && <SaveControls item={savedRef} title={problem.title} />}
          {isAuthenticated && <NoteCapture source={{ type: "problem", id: problem.slug }} excerpt={draft.code} excerptKind="code" excerptLabel="your current code" />}
        </div>} />
    </section>
  );
  const editor = (
    <div className="editor-pane">
      {offeredCode && (
        <div className="banner banner--info load-offer" role="region" aria-label="Open past code">
          <span>Open the code you submitted{offer?.loadFrom ? ` on ${offer.loadFrom}` : ""}? It replaces what's in the editor now{draft.isModified ? " (your current draft)" : ""}.</span>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => settleOffer(true)}>Replace my draft</Button>
            <Button size="sm" variant="ghost" onClick={() => settleOffer(false)}>Keep my draft</Button>
          </span>
        </div>
      )}
      {execution && execution.state !== "ready" && (
        <div className={`banner ${execution.state === "not_configured" ? "banner--info" : "banner--warning"} judge-status`} role="status">
          <strong>{execution.state === "not_configured" ? "Code can't run on this server." : "The code judge is temporarily unavailable."}</strong>{" "}
          {execution.message}
          {savedOnly && <> <button type="button" className="link-button" onClick={() => setMobileTab("coach")}>Ask the coach for a code review</button> instead.</>}
          {execution.setup_help && (
            <details className="judge-status__help"><summary>Developer setup</summary><p>{execution.setup_help}</p></details>
          )}
        </div>
      )}
      {unconfirmed && (
        <div className="banner banner--warning row" role="alert">
          <span>We couldn't confirm your {unconfirmed.mode === "run" ? "run" : "submission"} because the connection dropped. Trying again won't create a duplicate.</span>
          <Button size="sm" loading={submit.isPending} onClick={() => void send(unconfirmed)}>Try again</Button>
        </div>
      )}
      {toolbar}
      {showSettings && <div id={settingsId} className="editor-options"><EditorPreferencesControls /></div>}
      <CodeEditor value={draft.code} onChange={(v) => { draft.setCode(v); setHighlightLine(null); }}
        onSubmit={() => void handleSubmit()} onRun={canRun ? () => void handleSubmit("run") : undefined} highlightLine={highlightLine} />
    </div>
  );
  const results = (
    <section className="panel-scroll" aria-label="Submission results" tabIndex={0}>
      <SubmissionPanel submission={submission.data} error={submit.error ?? submission.error} onHighlightLine={jumpToLine} />
    </section>
  );
  const coach = (
    <div className="panel-scroll">
      <CoachPanel problemSlug={problem.slug} maxLevel={problem.hint_levels} code={draft.code}
        submissionId={submissionId} enabled={isAuthenticated} onSignInRequired={goSignIn} onHighlightLine={jumpToLine} />
    </div>
  );

  if (isNarrow) {
    const tabs: { id: typeof mobileTab; label: string; content: ReactNode }[] = [
      { id: "problem", label: "Problem", content: statement },
      { id: "code", label: "Code", content: <div className="mobile-code">{editor}{results}</div> },
      { id: "coach", label: "Coach", content: coach },
    ];
    return (
      <WorkspaceFrame title={problem.title}><div className="workspace workspace--stacked">
        <Tabs label="Workspace" tabs={tabs} value={mobileTab} onChange={setMobileTab}
          className="workspace__tab-system" listClassName="workspace__tabs" panelClassName="workspace__mobile-panel">
          {tabs.find((t) => t.id === mobileTab)?.content}
        </Tabs>
      </div></WorkspaceFrame>
    );
  }

  return (
    <WorkspaceFrame title={problem.title}><div className="workspace">
      <Group orientation="horizontal" className="workspace__group">
        <Panel id="statement" defaultSize="30" minSize="18" className="workspace__panel">{statement}</Panel>
        <Separator className="resize-handle" />
        <Panel id="center" defaultSize="44" minSize="28" className="workspace__panel">
          <Group orientation="vertical">
            <Panel id="editor" defaultSize="68" minSize="25">{editor}</Panel>
            <Separator className="resize-handle resize-handle--horizontal" />
            <Panel id="results" defaultSize="32" minSize="12">{results}</Panel>
          </Group>
        </Panel>
        <Separator className="resize-handle" />
        <Panel id="coach" defaultSize="26" minSize="18" className="workspace__panel">{coach}</Panel>
      </Group>
    </div></WorkspaceFrame>
  );
}
