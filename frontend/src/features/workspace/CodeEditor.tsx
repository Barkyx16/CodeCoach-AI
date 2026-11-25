import Editor, { type OnMount } from "@monaco-editor/react";
import { useEffect, useRef, useState } from "react";

import { LoadingState } from "@/components/States";
import { useEditorPreferences } from "@/features/settings/editorPreferences";

import { TabFocus, type monaco } from "./monacoSetup";

interface CodeEditorProps {
  value: string;
  onChange(value: string): void;
  onSubmit?(): void;
  /** Ctrl/Cmd + ' runs the public tests (when the deployment supports running code). */
  onRun?(): void;
  /** 1-based line to reveal and highlight (e.g. from an AI review issue). */
  highlightLine?: number | null;
}

export function CodeEditor({ value, onChange, onSubmit, onRun, highlightLine }: CodeEditorProps) {
  const { preferences } = useEditorPreferences();
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const decorations = useRef<monaco.editor.IEditorDecorationsCollection | null>(null);
  const submitRef = useRef(onSubmit);
  const runRef = useRef(onRun);
  const [focused, setFocused] = useState(false);
  const [tabMovesFocus, setTabMovesFocus] = useState(false);
  useEffect(() => {
    submitRef.current = onSubmit;
    runRef.current = onRun;
  }, [onSubmit, onRun]);

  const handleMount: OnMount = (editor, monacoApi) => {
    editorRef.current = editor;
    decorations.current = editor.createDecorationsCollection();
    // Ctrl/Cmd + Enter submits, matching most online judges.
    editor.addCommand(monacoApi.KeyMod.CtrlCmd | monacoApi.KeyCode.Enter, () => submitRef.current?.());
    editor.addCommand(monacoApi.KeyMod.CtrlCmd | monacoApi.KeyCode.Quote, () => runRef.current?.());
    // Tab indents inside the editor. Monaco's own "tab moves focus" toggle is the way out; say so while it has focus.
    editor.onDidFocusEditorWidget(() => {
      setFocused(true);
      setTabMovesFocus(TabFocus.getTabFocusMode());
    });
    editor.onDidBlurEditorWidget(() => setFocused(false));
    const tabFocus = TabFocus.onDidChangeTabFocus(setTabMovesFocus);
    editor.onDidDispose(() => tabFocus.dispose());
  };

  useEffect(() => {
    const editor = editorRef.current;
    if (!editor || !decorations.current) return;
    if (!highlightLine) {
      decorations.current.clear();
      return;
    }
    editor.revealLineInCenter(highlightLine);
    decorations.current.set([{
      range: { startLineNumber: highlightLine, startColumn: 1, endLineNumber: highlightLine, endColumn: 1 },
      options: { isWholeLine: true, className: "editor-line--flagged", glyphMarginClassName: "editor-glyph--flagged" },
    }]);
  }, [highlightLine]);

  return (
    <div className="code-editor" data-testid="code-editor">
      <Editor
        language="java"
        theme={preferences.theme}
        value={value}
        onChange={(v) => onChange(v ?? "")}
        onMount={handleMount}
        loading={<LoadingState label="Starting editor…" />}
        options={{
          fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace",
          fontSize: preferences.fontSize,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          tabSize: preferences.tabSize,
          wordWrap: preferences.wordWrap,
          automaticLayout: true,
          glyphMargin: true,
          ariaLabel: "Java code editor. Press Control or Command plus Enter to submit. Tab indents; to move focus out of the editor with Tab, first press Control plus M (on a Mac, Control plus Shift plus M).",
          padding: { top: 12 },
        }}
      />
      {focused && (
        <p className="code-editor__hint" aria-hidden="true">
          {tabMovesFocus ? "Tab moves focus out of the editor. To indent with Tab again, press " : "Tab indents. To leave with Tab, press "}
          <kbd>Ctrl</kbd>+<kbd>M</kbd> (Mac: <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>M</kbd>){tabMovesFocus ? "." : " first."}
        </p>
      )}
    </div>
  );
}
