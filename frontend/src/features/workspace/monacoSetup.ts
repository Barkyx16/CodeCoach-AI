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
    "editor.background": "#0b1220",
    "editor.lineHighlightBackground": "#17243a",
    "editorLineNumber.foreground": "#99aac4",
    "editorLineNumber.activeForeground": "#f3f6fc",
  },
});

export { monaco };
