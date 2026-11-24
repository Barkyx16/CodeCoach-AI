/**
 * Bundle Monaco locally instead of loading it from a CDN (the @monaco-editor/react default):
 * no third-party script at runtime, works offline, and allows a strict Content-Security-Policy.
 * Only the core editor + Java syntax are imported to keep the chunk small, plus the
 * "Tab moves focus" toggle (Ctrl+M, or Ctrl+Shift+M on a Mac) so keyboard users can leave the
 * editor with Tab: without it, Tab only ever indents.
 */
import { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor/editor/editor.api";
import EditorWorker from "monaco-editor/editor/editor.worker?worker";
import "monaco-editor/languages/definitions/java/register";
import "monaco-editor/editor/contrib/toggleTabFocusMode/browser/toggleTabFocusMode";
import { TabFocus } from "monaco-editor/editor/browser/config/tabFocus";

self.MonacoEnvironment = { getWorker: () => new EditorWorker() };
loader.config({ monaco });

monaco.editor.defineTheme("codecoach-dark", {
  base: "vs-dark",
  inherit: true,
  // Warm charcoal with gold keywords, matching the site's dark surface; every token colour is
  // >= 4.5:1 on the background and on the current line.
  rules: [
    { token: "comment", foreground: "A69D8C" },
    { token: "keyword", foreground: "E2C07A" },
    { token: "number", foreground: "F2C6A0" },
    { token: "string", foreground: "A9D6A6" },
  ],
  colors: {
    "editor.background": "#1a1917",
    "editor.foreground": "#ece6da",
    "editor.lineHighlightBackground": "#24221f",
    "editorLineNumber.foreground": "#9c937f",
    "editorLineNumber.activeForeground": "#ece6da",
  },
});

export { monaco, TabFocus };
