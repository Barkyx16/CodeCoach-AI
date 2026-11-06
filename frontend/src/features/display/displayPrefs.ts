import { createContext, useContext } from "react";

import { storage } from "@/lib/storage";

/** Presentation preferences: kept in this browser, never sent to the server or mixed with career data. */
export interface DisplayPrefs {
  theme: "system" | "light" | "dark";
  text: "default" | "large" | "larger";
  spacing: "default" | "spacious";
  motion: "system" | "reduce";
  contrast: "standard" | "high";
}

export const DISPLAY_KEY = "codecoach.display.v1";
export const DEFAULT_DISPLAY: DisplayPrefs = { theme: "system", text: "default", spacing: "default", motion: "system", contrast: "standard" };

const ALLOWED: { [K in keyof DisplayPrefs]: readonly DisplayPrefs[K][] } = {
  theme: ["system", "light", "dark"],
  text: ["default", "large", "larger"],
  spacing: ["default", "spacious"],
  motion: ["system", "reduce"],
  contrast: ["standard", "high"],
};

/** Saved values are validated field by field; anything unknown falls back to the default. */
export function parseDisplayPrefs(raw: string | null): DisplayPrefs {
  let saved: Record<string, unknown> = {};
  try {
    const value: unknown = JSON.parse(raw ?? "null");
    if (value && typeof value === "object") saved = value as Record<string, unknown>;
  } catch {
    saved = {};
  }
  const out = { ...DEFAULT_DISPLAY };
  for (const key of Object.keys(ALLOWED) as (keyof DisplayPrefs)[]) {
    const v = saved[key];
    if ((ALLOWED[key] as readonly unknown[]).includes(v)) (out as Record<string, unknown>)[key] = v;
  }
  return out;
}

export function loadDisplayPrefs(): DisplayPrefs {
  return parseDisplayPrefs(storage.get(DISPLAY_KEY));
}

export function resolvedTheme(prefs: DisplayPrefs): "light" | "dark" {
  if (prefs.theme !== "system") return prefs.theme;
  try {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  } catch {
    return "dark";
  }
}

/** Put the preferences on <html> as data attributes; tokens.css does the rest. */
export function applyDisplayPrefs(prefs: DisplayPrefs, root: HTMLElement = document.documentElement): void {
  const set = (name: string, value: string | null) => (value ? root.setAttribute(name, value) : root.removeAttribute(name));
  const theme = resolvedTheme(prefs);
  set("data-theme", theme);
  set("data-text", prefs.text === "default" ? null : prefs.text);
  set("data-spacing", prefs.spacing === "spacious" ? "spacious" : null);
  set("data-motion", prefs.motion === "reduce" ? "reduce" : null);
  set("data-contrast", prefs.contrast === "high" ? "high" : null);
  document.querySelector('meta[name="color-scheme"]')?.setAttribute("content", theme);
}

export interface DisplayContextValue {
  prefs: DisplayPrefs;
  update(patch: Partial<DisplayPrefs>): void;
  reset(): void;
  /** False when this browser won't store them: they apply for this visit only. */
  persisted: boolean;
}

export const DisplayContext = createContext<DisplayContextValue | null>(null);

export function useDisplayPrefs(): DisplayContextValue {
  const value = useContext(DisplayContext);
  if (!value) throw new Error("DisplayProvider is required");
  return value;
}
