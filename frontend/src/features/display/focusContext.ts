import { createContext, useContext } from "react";

export interface FocusModeValue {
  on: boolean;
  enter(): void;
  /** Turn it off and put keyboard focus back on the toggle. */
  exit(): void;
  /** Turn it off without moving focus: the page stopped offering it (e.g. the round ended). Stable. */
  release(): void;
}

export const FocusModeContext = createContext<FocusModeValue>({ on: false, enter: () => undefined, exit: () => undefined, release: () => undefined });

export function useFocusMode(): FocusModeValue {
  return useContext(FocusModeContext);
}
