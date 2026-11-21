import { useSyncExternalStore } from "react";

import { snapshot, subscribe, type AppShellState } from "./appShell";

export function useAppShell(): AppShellState {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}
