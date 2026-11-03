import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, vi } from "vitest";

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
vi.mock("@/features/workspace/monacoSetup", () => ({ monaco: {} }));

// jsdom lacks layout APIs that the resizable panel library relies on.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
  window.localStorage.clear();
  cookieJar.hasSession = false;
  resetExploreStore();
  resetLearnStore();
  resetNoteStore();
  resetScenarioStore();
});
afterAll(() => server.close());
