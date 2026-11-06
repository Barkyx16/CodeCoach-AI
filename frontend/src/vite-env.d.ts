/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  /** "off": build without the service worker (./dev.sh does, for a local copy). */
  readonly VITE_SERVICE_WORKER?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Monaco internals we import directly (the package ships no typings for these paths).
declare module "monaco-editor/editor/contrib/toggleTabFocusMode/browser/toggleTabFocusMode";
declare module "monaco-editor/editor/browser/config/tabFocus" {
  /** Global "Tab moves focus" switch shared by every editor on the page (Ctrl+M / Ctrl+Shift+M toggles it). */
  export const TabFocus: {
    getTabFocusMode(): boolean;
    setTabFocusMode(on: boolean): void;
    onDidChangeTabFocus(listener: (on: boolean) => void): { dispose(): void };
  };
}
