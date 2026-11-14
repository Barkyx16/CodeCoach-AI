import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, vi } from "vitest";

import { clearFailures } from "@/lib/supportLog";

import { resetExploreStore } from "./explore";
import { resetLearnStore } from "./learn";
import { resetNoteStore } from "./notes";
import { resetScenarioStore } from "./scenarios";
import { cookieJar, server } from "./server";

// Monaco needs a real browser; in jsdom we swap it for a textarea with the same contract.
vi.mock("@monaco-editor/react", async () => {
  const { createElement } = await import("react");
  return {
    default: ({ value, onChange, options }: { value: string; onChange(v: string): void; options?: { ariaLabel?: string } }) =>
      createElement("textarea", {
        "aria-label": options?.ariaLabel ?? "code editor",
        value,
        onChange: (e: { target: { value: string } }) => onChange(e.target.value),
      }),
    loader: { config: () => undefined },
  };
});
vi.mock("@/features/workspace/monacoSetup", () => ({
  monaco: {},
  TabFocus: { getTabFocusMode: () => false, setTabFocusMode: () => undefined, onDidChangeTabFocus: () => ({ dispose: () => undefined }) },
}));

// jsdom lacks layout APIs that the resizable panel library relies on.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

// jsdom has <dialog> but not its modal methods. Open/close only: the browser's own focus handling,
// inert background and Escape are covered by the browser tests (e2e/command-palette.spec.ts).
if (!HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
}

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
  window.localStorage.clear();
  window.sessionStorage.clear(); // e.g. an unfinished refresh attempt key
  // Display preferences and focus mode live on <html>, which outlives each test's render.
  for (const name of ["data-theme", "data-text", "data-spacing", "data-motion", "data-contrast", "data-focus"]) document.documentElement.removeAttribute(name);
  cookieJar.hasSession = false;
  resetExploreStore();
  resetLearnStore();
  resetNoteStore();
  resetScenarioStore();
  clearFailures(); // a page load starts with an empty failed-request log; so does each test
});
afterAll(() => server.close());
