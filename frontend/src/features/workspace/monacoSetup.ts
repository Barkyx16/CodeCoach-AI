/**
 * Bundle Monaco locally instead of loading it from a CDN (the @monaco-editor/react default):
 * no third-party script at runtime, works offline, and allows a strict Content-Security-Policy.
 * Only the core editor + Java syntax are imported to keep the chunk small.
 */
import { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor/editor/editor.api";
import EditorWorker from "monaco-editor/editor/editor.worker?worker";
import "monaco-editor/languages/definitions/java/register";

self.MonacoEnvironment = { getWorker: () => new EditorWorker() };
loader.config({ monaco });

monaco.editor.defineTheme("codecoach-dark", {
  base: "vs-dark",
  inherit: true,
  rules: [],
  colors: {
    "editor.background": "#0a1222",
    "editor.lineHighlightBackground": "#13203a",
    "editorLineNumber.foreground": "#4b5d7e",
    "editorLineNumber.activeForeground": "#9aabc6",
  },
});

export { monaco };
