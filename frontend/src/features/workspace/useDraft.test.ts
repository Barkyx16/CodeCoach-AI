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
});
