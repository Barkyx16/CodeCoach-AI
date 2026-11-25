/**
 * One key per exact request for a form (Volume 8, prompt 2): a retry of the same content reuses
 * it, changed content gets a new one (the server refuses an old key with other content), and
 * after a success the next send is new even if it's identical.
 */
import { renderHook } from "@testing-library/react";

import { useRequestKey } from "./requestKey";

it("keeps the key for the same content, renews it for changed content and after a success", () => {
  const { result, rerender } = renderHook(() => useRequestKey());
  const first = result.current.keyFor({ employer: "Mercy", role: "RN" });
  rerender();
  expect(result.current.keyFor({ employer: "Mercy", role: "RN" })).toBe(first); // a retry
  const edited = result.current.keyFor({ employer: "St. Anne's", role: "RN" });
  expect(edited).not.toBe(first);
  expect(result.current.keyFor({ employer: "Mercy", role: "RN" })).not.toBe(first); // edited back: new again
  const sent = result.current.keyFor({ employer: "Mercy", role: "RN" });
  result.current.done();
  expect(result.current.keyFor({ employer: "Mercy", role: "RN" })).not.toBe(sent); // a second, identical one
  expect(first).toMatch(/^[0-9a-f-]{16,}$/);
});
