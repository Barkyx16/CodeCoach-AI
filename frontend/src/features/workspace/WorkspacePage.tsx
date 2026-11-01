import { useId, useState, type ReactNode } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useProblem, useSubmission, useSubmit } from "@/api/queries";
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

const SAVE_LABEL: Record<SaveState, string> = { saved: "Draft saved", saving: "Saving…", unsaved: "Unsaved changes", error: "Draft not saved — browser storage unavailable" };

export default function WorkspacePage() {
  const { slug = "" } = useParams();
  const problem = useProblem(slug);

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
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const submission = useSubmission(submissionId);
  const [highlightLine, setHighlightLine] = useState<number | null>(null);
  const [mobileTab, setMobileTab] = useState<"problem" | "code" | "coach">("problem");
  const [showSettings, setShowSettings] = useState(false);
  const settingsId = useId();
  const judging = !!submission.data?.execution_enabled && !submission.data.is_terminal;

  const goSignIn = () => navigate("/login", { state: { from: `/problems/${problem.slug}` } });

  async function handleSubmit() {
    if (!isAuthenticated) return goSignIn();
    if (submit.isPending || judging) return;
    try {
      const created = await submit.mutateAsync({ problem_slug: problem.slug, language: "java", source_code: draft.code });
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
      <span className="editor-toolbar__lang">Java</span>
      <span className={`save-state save-state--${draft.saveState}`} aria-live="polite">{SAVE_LABEL[draft.saveState]}</span>
      <div className="editor-toolbar__actions">
        <Button size="sm" variant="ghost" aria-expanded={showSettings} aria-controls={settingsId}
          onClick={() => setShowSettings((value) => !value)}>Editor settings</Button>
        <Button size="sm" variant="ghost" disabled={!draft.isModified}
          onClick={() => { if (window.confirm("Reset to the starter code? Your draft will be lost.")) draft.reset(); }}>
          Reset
        </Button>
        <Button size="sm" variant="primary" loading={submit.isPending} disabled={judging} onClick={() => void handleSubmit()}
          title="Submit (Ctrl/⌘ + Enter)">
          Submit
        </Button>
      </div>
    </div>
  );

  const statement = <div className="panel-scroll"><ProblemStatement problem={problem} /></div>;
  const editor = (
    <div className="editor-pane">
      {toolbar}
      {showSettings && <div id={settingsId} className="editor-options"><EditorPreferencesControls /></div>}
      <CodeEditor value={draft.code} onChange={(v) => { draft.setCode(v); setHighlightLine(null); }}
        onSubmit={() => void handleSubmit()} highlightLine={highlightLine} />
    </div>
  );
  const results = (
    <div className="panel-scroll">
      <SubmissionPanel submission={submission.data} error={submit.error ?? submission.error} />
    </div>
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
      <div className="workspace workspace--stacked">
        <Tabs label="Workspace" tabs={tabs} value={mobileTab} onChange={setMobileTab}
          className="workspace__tab-system" listClassName="workspace__tabs" panelClassName="workspace__mobile-panel">
          {tabs.find((t) => t.id === mobileTab)?.content}
        </Tabs>
      </div>
    );
  }

  return (
    <div className="workspace">
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
    </div>
  );
}
