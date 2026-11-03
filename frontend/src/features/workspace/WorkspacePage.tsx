import { useId, useState, type ReactNode } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { useCapabilities, useProblem, useSubmission, useSubmit } from "@/api/queries";
import type { SubmissionMode } from "@/api/types";
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
import { QueueBar } from "@/features/saved/QueueBar";
import { SaveControls } from "@/features/saved/SaveControls";

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
  const canRun = useCapabilities().data?.execution_enabled === true;
  const [pendingMode, setPendingMode] = useState<SubmissionMode>("submit");
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const submission = useSubmission(submissionId);
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

  async function handleSubmit(mode: SubmissionMode = "submit") {
    if (!isAuthenticated) return goSignIn();
    if (submit.isPending || judging) return;
    setPendingMode(mode);
    try {
      const created = await submit.mutateAsync({ problem_slug: problem.slug, language: "java", source_code: draft.code, mode });
      setSubmissionId(created.id);
      if (isNarrow) setMobileTab("code");
    } catch {
      /* error rendered by SubmissionPanel */
    }
  }

  function jumpToLine(line: number | null) {
    setHighlightLine(line);
    if (line && isNarrow) setMobileTab("code");
  }

  const toolbar = (
    <div className="editor-toolbar">
      <span className="editor-toolbar__lang"><Icon name="code" size={15} />Solution.java</span>
      <span className={`save-state save-state--${draft.saveState}`} aria-live="polite">{SAVE_LABEL[draft.saveState]}</span>
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
          title="Submit (Ctrl/⌘ + Enter)">
          Submit <Icon name="arrow" size={14} />
        </Button>
      </div>
    </div>
  );

  const savedRef = { item_type: "problem" as const, track: "", ref_id: problem.slug };
  const statement = (
    <section className="panel-scroll" aria-label="Problem description" tabIndex={0}>
      <ProblemStatement problem={problem}
        before={isAuthenticated ? <QueueBar item={savedRef} /> : undefined}
        after={<>
          <LearnLinks query={{ problem_slug: problem.slug }} from={{ from: `/problems/${problem.slug}`, fromLabel: "Back to the problem" }} />
          {isAuthenticated && <SaveControls item={savedRef} title={problem.title} />}
        </>} />
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
