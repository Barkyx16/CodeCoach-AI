import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { storage } from "@/lib/storage";

import { applyDisplayPrefs, DEFAULT_DISPLAY, DISPLAY_KEY, DisplayContext, loadDisplayPrefs, type DisplayPrefs } from "./displayPrefs";

export function DisplayProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<DisplayPrefs>(loadDisplayPrefs);
  // Can this browser store them at all? (Private modes and blocked site data say no.)
  const [persisted, setPersisted] = useState(() => storage.set(`${DISPLAY_KEY}.probe`, "1") && storage.remove(`${DISPLAY_KEY}.probe`));

  useEffect(() => {
    applyDisplayPrefs(prefs);
    if (prefs.theme !== "system") return;
    // Follow the device when it switches between light and dark.
    let media: MediaQueryList | null = null;
    try { media = window.matchMedia("(prefers-color-scheme: light)"); } catch { media = null; }
    const onChange = () => applyDisplayPrefs(prefs);
    media?.addEventListener?.("change", onChange);
    return () => media?.removeEventListener?.("change", onChange);
  }, [prefs]);

  const save = useCallback((next: DisplayPrefs) => {
    setPrefs(next);
    const isDefault = JSON.stringify(next) === JSON.stringify(DEFAULT_DISPLAY);
    setPersisted(isDefault ? storage.remove(DISPLAY_KEY) : storage.set(DISPLAY_KEY, JSON.stringify(next)));
  }, []);

  const value = useMemo(() => ({
    prefs,
    persisted,
    update: (patch: Partial<DisplayPrefs>) => save({ ...prefs, ...patch }),
    reset: () => save(DEFAULT_DISPLAY),
  }), [prefs, persisted, save]);

  return <DisplayContext.Provider value={value}>{children}</DisplayContext.Provider>;
}
