import { useId, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Group, Panel, Separator } from "react-resizable-panels";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { queryKeys, useCapabilities, useContentMeta, useMySubmissions, useProblem, useSubmission, useSubmit } from "@/api/queries";
import type { SubmissionCreate, SubmissionMode } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { ActionError } from "@/components/ActionError";
import { JudgeRecovery } from "./JudgeRecovery";
import { judgeRetryHelps } from "./judgeRefusals";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { Tabs } from "@/components/Tabs";
import { EditorPreferencesControls } from "@/features/settings/EditorPreferencesControls";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { useRetryWait } from "@/hooks/useCountdown";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useOnline } from "@/hooks/useOnline";
import { SaveOffline } from "@/features/offline/SaveOffline";
import { ContentInfo } from "@/features/content/ContentInfo";
import { ReportIssue } from "@/features/content/ReportIssue";

import { CoachPanel } from "./CoachPanel";
import { GuidedTour } from "@/features/onboarding/GuidedTour";

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
import { EarlierActionNotice } from "@/features/recovery/EarlierActionNotice";
import { useEarlierAction } from "@/features/recovery/useEarlierAction";
import { fingerprint, forgetIntent, keyForIntent } from "@/lib/pendingIntents";


// Drafts live on this device until submitted: the labels say so (a draft is never "submitted").
// Kept short: the toolbar must fit on one line beside the buttons.
const SAVE_LABEL: Record<SaveState, string> = { saved: "Saved on device", saving: "Saving…", unsaved: "Unsaved changes", error: "Not saved: storage unavailable" };

export default function WorkspacePage() {
  const { slug = "" } = useParams();
  // Wait for the session to be restored: fetched anonymously, the open isn't recorded and the
  // cached anonymous copy would be reused once signed in.
  const { isRestoring } = useAuth();
  const problem = useProblem(slug, !isRestoring);

  if (problem.isPending) return <LoadingState label="Loading problem…" />;
  if (problem.isError) {
    if (problem.error instanceof ApiError && problem.error.status === 404) {
      // Not there (mistyped, or removed): a retry can't help, a way back can.
      return (
        <div className="page">
          <EmptyState pageTitle title="This problem isn't available"
            action={<Link className="btn btn--primary btn--md" to="/problems">Browse coding problems</Link>}>
            <p>The link may be mistyped, or the problem may have been removed from the library.</p>
          </EmptyState>
        </div>
      );
    }
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
  const { isAuthenticated, draftScope, user } = useAuth();
  const online = useOnline();
  const navigate = useNavigate();
  const isNarrow = useMediaQuery("(max-width: 900px)");
  const draft = useDraft(problem.slug, problem.starter_code, draftScope);
  useLeaveWarning(draft.saveState === "error");
  const submit = useSubmit();
  // The server asked for a wait (too many submissions, the judge busy): Run and Submit wait that
  // long; the editor, the coach and the rest of the page don't.
  const submitWait = useRetryWait(submit.error);
  const queryClient = useQueryClient();
  const execution = useCapabilities().data?.execution;
  const content = useContentMeta("problem", problem.slug);
  const retired = content.data?.status === "retired";
  const canRun = execution?.run_available === true;
  const savedOnly = execution?.submit_mode === "saved_only";
  const [pendingMode, setPendingMode] = useState<SubmissionMode>("submit");
  const [chosenId, setSubmissionId] = useState<string | null>(null);
  // Reload recovery: until you submit again, show a submission of this problem that's still queued or running.
  const latest = useMySubmissions({ problem_slug: problem.slug, page: 1, page_size: 1 }, isAuthenticated);
  const pendingLatest = latest.data?.items[0];
  const resumable = pendingLatest && (pendingLatest.status === "QUEUED" || pendingLatest.status === "RUNNING") ? pendingLatest.id : null;
  // A submission sent before a reload whose reply never came: the server says what it made (Volume 8, prompt 1).
  const earlier = useEarlierAction("submission", isAuthenticated ? problem.slug : null);
  const earlierId = earlier.status === "found" ? earlier.outcome.id : null;
  const submissionId = chosenId ?? earlierId ?? resumable;
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
      forgetIntent(user?.id, "submission", problem.slug, body.client_request_id ?? undefined);
      setUnconfirmed(null);
      setSubmissionId(created.id);
      if (isNarrow) setMobileTab("code");
    } catch (e) {
      // Only a lost connection leaves it unknown whether the server got the request. Any other
      // answer is definite: nothing is pending, so the record of it goes.
      const lost = e instanceof ApiError && e.code === "network_error";
      setUnconfirmed(lost ? body : null);
      if (!lost) forgetIntent(user?.id, "submission", problem.slug, body.client_request_id ?? undefined);
      // The judge said it's down or busy: the banner above the editor should say so now, not
      // whenever the page is next loaded.
      if (e instanceof ApiError && ["judge_unavailable", "judge_busy", "execution_disabled"].includes(e.code)) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.capabilities });
      }
    }
  }

  async function handleSubmit(mode: SubmissionMode = "submit") {
    if (!online || retired) return; // the judge is on the server: nothing is "run" or "graded" offline
    if (!isAuthenticated) return goSignIn();
    if (submit.isPending || judging || submitWait > 0) return; // (the keyboard shortcut, too)
    // Its outcome is unknown and the code hasn't changed: the same request again, with the same
    // key, so pressing Submit (not only "Try again") can't make a second submission.
    if (unconfirmed && unconfirmed.source_code === draft.code && (unconfirmed.mode ?? "submit") === mode) {
      return send(unconfirmed);
    }
    if (earlier.status !== "none") earlier.dismiss(); // a new action: the earlier one's notice has done its job
    // Written down before sending: the same code and mode reuses an unresolved key (from before a
    // reload, or another tab), so the server makes it once; changed code is a new submission.
    const { key } = keyForIntent(user!.id, "submission", problem.slug, fingerprint(problem.slug, mode, draft.code));
    await send({ problem_slug: problem.slug, language: "java", source_code: draft.code, mode, client_request_id: key });
  }

  /** The coach's review is the way on when code can't run: bring it into view. */
  function showCoach() {
    if (isNarrow) setMobileTab("coach");
    window.setTimeout(() => {
      const coach = document.querySelector<HTMLElement>('[data-tour="coach"]');
      coach?.scrollIntoView({ block: "start" });
      coach?.querySelector<HTMLElement>("button, a[href]")?.focus();
    }, 0);
  }

  function jumpToLine(line: number | null) {
    setHighlightLine(line);
    if (line && isNarrow) setMobileTab("code");
  }

  const toolbar = (
    <div className="editor-toolbar">
      <span className="editor-toolbar__lang"><Icon name="code" size={15} />Solution.java</span>
      {/* Not a live region: it changes with every keystroke. A failure is announced once. */}
      <span className={`save-state save-state--${draft.saveState}`} data-tour="save"
        title={draft.saveState === "saved" ? "Your draft is kept in this browser. It isn't submitted until you submit it." : undefined}>
        {SAVE_LABEL[draft.saveState]}
      </span>
      {draft.saveState === "error" && <span className="visually-hidden" role="alert">Your draft isn't being saved: this browser's storage is unavailable.</span>}
      <div className="editor-toolbar__actions" data-tour="submit">
        <Button size="sm" variant="ghost" aria-expanded={showSettings} aria-controls={settingsId}
          onClick={() => setShowSettings((value) => !value)}>Editor settings</Button>
        {/* "Reset" on screen (the toolbar has no room for more in a narrow panel); its name and the
            confirmation say what it resets and what it keeps. */}
        <Button size="sm" variant="ghost" disabled={!draft.isModified} aria-label="Reset code"
          title="Replace your code with the starter code (past submissions are kept)"
          onClick={() => {
            if (window.confirm("Replace your code with the starter code? Your unsent changes in the editor will be lost; your past submissions are kept.")) draft.reset();
          }}>
          Reset
        </Button>
        {canRun && (
          <Button size="sm" variant="secondary" loading={submit.isPending && pendingMode === "run"}
            disabled={!online || retired || judging || submitWait > 0 || (submit.isPending && pendingMode !== "run")} onClick={() => void handleSubmit("run")}
            title="Run the public tests only (Ctrl/⌘ + ')">
            Run
          </Button>
        )}
        <Button size="sm" variant="primary" loading={submit.isPending && pendingMode === "submit"}
          disabled={!online || retired || judging || submitWait > 0 || (submit.isPending && pendingMode !== "submit")} onClick={() => void handleSubmit()}
          title={savedOnly ? "Save this attempt without a verdict (Ctrl/⌘ + Enter)" : "Submit (Ctrl/⌘ + Enter)"}
          aria-label={savedOnly ? "Save attempt" : undefined}>
          {savedOnly ? "Save attempt" : "Submit"} <Icon name="arrow" size={14} />
        </Button>
      </div>
    </div>
  );

  const savedRef = { item_type: "problem" as const, track: "", ref_id: problem.slug };
  const statement = (
    <section className="panel-scroll" aria-label="Problem description" tabIndex={0} data-tour="statement">
      <ProblemStatement problem={problem}
        before={isAuthenticated ? <div className="focus-hide display-contents"><QueueBar item={savedRef} /></div> : undefined}
        after={<div className="focus-hide display-contents">
          <LearnLinks query={{ problem_slug: problem.slug }} from={{ from: `/problems/${problem.slug}`, fromLabel: "Back to the problem" }} />
          {isAuthenticated && <SaveControls item={savedRef} title={problem.title} />}
          {isAuthenticated && <NoteCapture source={{ type: "problem", id: problem.slug }} excerpt={draft.code} excerptKind="code" excerptLabel="your current code" />}
          <SaveOffline kind="problem" itemKey={problem.slug} label="problem" />
        </div>} />
      <div className="workspace-content-info stack-sm">
        <ContentInfo type="problem" id={problem.slug} />
        {content.data && <ReportIssue type="problem" id={problem.slug} version={content.data.version} />}
      </div>
    </section>
  );
  const editor = (
    <div className="editor-pane" data-tour="editor">
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
      {retired && (
        <div className="banner banner--warning" role="status">
          <strong>Retired problem.</strong> {content.data?.retired_reason} You can still read it and edit your code; it isn't judged any more.
        </div>
      )}
      {!online && (
        <div className="banner banner--warning" role="status">
          <strong>Offline.</strong> You can read the problem and edit your code; it's saved on this device.
          Running and judging need the server, so they're paused until you're back online.
        </div>
      )}
      {unconfirmed && (
        <div className="banner banner--warning row" role="alert">
          <span>We couldn't confirm your {unconfirmed.mode === "run" ? "run" : "submission"} because the connection dropped. Trying again won't create a duplicate.</span>
          <Button size="sm" loading={submit.isPending} onClick={() => void send(unconfirmed)}>Try again</Button>
        </div>
      )}
      {toolbar}
      <EarlierActionNotice earlier={earlier} noun={earlier.status === "found" && earlier.outcome.kind === "run" ? "run" : "submission"}
        found={<>{earlier.status === "found" && earlier.outcome.state === "pending" ? "It's saved; its status is below." : "Its result is below."}</>}
        changed={earlier.status !== "none"
          && ![fingerprint(problem.slug, "submit", draft.code), fingerprint(problem.slug, "run", draft.code)].includes(earlier.intent.fingerprint)
          ? "The code in the editor has changed since you sent it. Your current code is kept as your draft." : null} />
      {/* A definite failure (not a lost connection: that's the banner above), next to the buttons.
          The previous result stays in the results panel. */}
      {submit.error && !unconfirmed && !submit.isPending && (
        <ActionError error={submit.error} action={pendingMode === "run" ? "Your run" : "Your submission"}
          onRetry={judgeRetryHelps(submit.error) ? () => void handleSubmit(pendingMode) : undefined}
          extra={<JudgeRecovery error={submit.error} mode={pendingMode} problemSlug={problem.slug} code={draft.code}
            onShowSubmission={(id) => { submit.reset(); setSubmissionId(id); }}
            onSubmitInstead={() => void handleSubmit("submit")} onAskCoach={showCoach} />} />
      )}
      {showSettings && <div id={settingsId} className="editor-options"><EditorPreferencesControls /></div>}
      <CodeEditor value={draft.code} onChange={(v) => { draft.setCode(v); setHighlightLine(null); }}
        onSubmit={() => void handleSubmit()} onRun={canRun ? () => void handleSubmit("run") : undefined} highlightLine={highlightLine} />
    </div>
  );
  const results = (
    <section className="panel-scroll" aria-label="Submission results" tabIndex={0}>
      <SubmissionPanel submission={submission.data} error={submission.error} onHighlightLine={jumpToLine}
        editorCode={draft.code} onCheckAgain={() => void submission.refetch()} checking={submission.isFetching} />
    </section>
  );
  const coach = (
    <div className="panel-scroll" data-tour="coach">
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
        <GuidedTour kind="coding" />
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
      <GuidedTour kind="coding" />
    </div></WorkspaceFrame>
  );
}
