import { useEffect } from "react";

import { Button } from "@/components/Button";

import { useFocusMode } from "./focusContext";

/**
 * "Focus mode" on pages where you answer something: hides navigation and side panels until you
 * exit. A toggle button with a fixed name; its pressed state says whether it's on.
 */
export function FocusToggle() {
  const focus = useFocusMode();
  // Focus mode lasts only while the page offers it: when this toggle goes (an interview round
  // turns into its results at the same address, say), the navigation comes back.
  const { release } = focus;
  useEffect(() => release, [release]);
  return (
    <Button id="focus-toggle" size="sm" variant="ghost" className="focus-toggle" aria-pressed={focus.on}
      onClick={() => (focus.on ? focus.exit() : focus.enter())}
      title={focus.on ? "Show navigation and side panels again (Esc)" : "Hide navigation and side panels while you answer"}>
      <span className="focus-toggle__box" aria-hidden="true" />Focus mode
    </Button>
  );
}
