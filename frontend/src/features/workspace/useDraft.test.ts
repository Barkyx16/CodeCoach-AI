import { act, renderHook } from "@testing-library/react";

import { useDraft } from "./useDraft";

describe("useDraft", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("autosaves after a pause and restores on remount", () => {
    const { result, unmount } = renderHook(() => useDraft("two-sum", "starter", "u1", 500));
    expect(result.current.code).toBe("starter");
    act(() => result.current.setCode("my code"));
    expect(result.current.saveState).toBe("unsaved");
    act(() => vi.advanceTimersByTime(500));
    expect(result.current.saveState).toBe("saved");
    unmount();
    const again = renderHook(() => useDraft("two-sum", "starter", "u1", 500));
    expect(again.result.current.code).toBe("my code");
    expect(again.result.current.isModified).toBe(true);
  });

  it("keeps drafts separate per user and problem", () => {
    const a = renderHook(() => useDraft("two-sum", "starter", "u1", 0));
    act(() => a.result.current.setCode("alice"));
    act(() => vi.advanceTimersByTime(1));
    expect(renderHook(() => useDraft("two-sum", "starter", "u2", 0)).result.current.code).toBe("starter");
    expect(renderHook(() => useDraft("binary-search", "s2", "u1", 0)).result.current.code).toBe("s2");
  });

  it("adopts starter code that arrives after mount, but never overwrites edits", () => {
    const { result, rerender } = renderHook(({ starter }) => useDraft("iv", starter, "u1", 0), { initialProps: { starter: "" } });
    expect(result.current.code).toBe("");
    rerender({ starter: "class Solution {}" });
    expect(result.current.code).toBe("class Solution {}");
    act(() => result.current.setCode("my edit"));
    rerender({ starter: "something else" });
    expect(result.current.code).toBe("my edit");
  });

  it("reset restores the starter code and clears storage", () => {
    const { result } = renderHook(() => useDraft("two-sum", "starter", "u1", 0));
    act(() => result.current.setCode("changed"));
    act(() => vi.advanceTimersByTime(1));
    act(() => result.current.reset());
    expect(result.current.code).toBe("starter");
    expect(window.localStorage.length).toBe(0);
  });

  it("flushes a pending edit when navigating away before the debounce", () => {
    const first = renderHook(() => useDraft("two-sum", "starter", "u1", 600));
    act(() => first.result.current.setCode("last keystroke"));
    first.unmount();
    const second = renderHook(() => useDraft("two-sum", "starter", "u1", 600));
    expect(second.result.current.code).toBe("last keystroke");
  });

  it("flushes before pagehide and keeps switched-user drafts isolated", () => {
    const draft = renderHook(({ scope }) => useDraft("two-sum", "starter", scope, 600), { initialProps: { scope: "u1" } });
    act(() => draft.result.current.setCode("alice"));
    act(() => window.dispatchEvent(new Event("pagehide")));
    draft.rerender({ scope: "u2" });
    expect(draft.result.current.code).toBe("starter");
    act(() => draft.result.current.setCode("bob"));
    draft.rerender({ scope: "u1" });
    expect(draft.result.current.code).toBe("alice");
    draft.rerender({ scope: "u2" });
    expect(draft.result.current.code).toBe("bob");
  });

  it("reports storage failure without pretending the draft is saved", () => {
    const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota"); });
    const draft = renderHook(() => useDraft("two-sum", "starter", "u1", 500));
    act(() => draft.result.current.setCode("keep this in the editor"));
    act(() => vi.advanceTimersByTime(500));
    expect(draft.result.current.saveState).toBe("error");
    expect(draft.result.current.code).toBe("keep this in the editor");
    draft.unmount();
    write.mockRestore();
  });
});
