import Editor, { type OnMount } from "@monaco-editor/react";
import { useEffect, useRef } from "react";

import { LoadingState } from "@/components/States";

import "./monacoSetup";
import type { monaco } from "./monacoSetup";

interface CodeEditorProps {
  value: string;
  onChange(value: string): void;
  onSubmit?(): void;
  /** 1-based line to reveal and highlight (e.g. from an AI review issue). */
  highlightLine?: number | null;
}

export function CodeEditor({ value, onChange, onSubmit, highlightLine }: CodeEditorProps) {
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const decorations = useRef<monaco.editor.IEditorDecorationsCollection | null>(null);
  const submitRef = useRef(onSubmit);
  useEffect(() => {
    submitRef.current = onSubmit;
  }, [onSubmit]);

  const handleMount: OnMount = (editor, monacoApi) => {
    editorRef.current = editor;
    decorations.current = editor.createDecorationsCollection();
    // Ctrl/Cmd + Enter submits, matching most online judges.
    editor.addCommand(monacoApi.KeyMod.CtrlCmd | monacoApi.KeyCode.Enter, () => submitRef.current?.());
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
        theme="codecoach-dark"
        value={value}
        onChange={(v) => onChange(v ?? "")}
        onMount={handleMount}
        loading={<LoadingState label="Starting editor…" />}
        options={{
          fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace",
          fontSize: 14,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          tabSize: 4,
          automaticLayout: true,
          glyphMargin: true,
          ariaLabel: "Java code editor. Press Control or Command plus Enter to submit.",
          padding: { top: 12 },
        }}
      />
    </div>
  );
}
