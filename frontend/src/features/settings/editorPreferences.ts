import { createContext, useContext } from "react";
import { storage } from "@/lib/storage";

export interface EditorPreferences {
  theme: "codecoach-dark" | "vs";
  fontSize: number;
  tabSize: number;
  wordWrap: "on" | "off";
}
export const EDITOR_KEY = "codecoach.editor.v1";
export const DEFAULT_EDITOR: EditorPreferences = { theme: "codecoach-dark", fontSize: 14, tabSize: 4, wordWrap: "off" };
export const FONT_SIZES = [12, 14, 16, 18, 20];
export function loadEditorPreferences(): EditorPreferences {
  try {
    const saved: unknown = JSON.parse(storage.get(EDITOR_KEY) ?? "null");
    if (typeof saved !== "object" || saved === null) return DEFAULT_EDITOR;
    const value = saved as Partial<EditorPreferences>;
    return {
      theme: value.theme === "vs" ? "vs" : DEFAULT_EDITOR.theme,
      fontSize: FONT_SIZES.includes(value.fontSize ?? 0) ? value.fontSize! : DEFAULT_EDITOR.fontSize,
      tabSize: value.tabSize === 2 ? 2 : 4,
      wordWrap: value.wordWrap === "on" ? "on" : "off",
    };
  } catch { return DEFAULT_EDITOR; }
}
export const EditorPreferencesContext = createContext<{
  preferences: EditorPreferences;
  update(patch: Partial<EditorPreferences>): void;
  persisted: boolean;
} | null>(null);
export function useEditorPreferences() {
  const value = useContext(EditorPreferencesContext);
  if (!value) throw new Error("EditorPreferencesProvider is required");
  return value;
}
