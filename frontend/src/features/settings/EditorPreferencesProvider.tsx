import { useState, type ReactNode } from "react";
import { storage } from "@/lib/storage";
import { EDITOR_KEY, EditorPreferencesContext, loadEditorPreferences, type EditorPreferences } from "./editorPreferences";

export function EditorPreferencesProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState(loadEditorPreferences);
  const [persisted, setPersisted] = useState(true);
  function update(patch: Partial<EditorPreferences>) {
    const next = { ...preferences, ...patch };
    setPersisted(storage.set(EDITOR_KEY, JSON.stringify(next)));
    setPreferences(next);
  }
  return <EditorPreferencesContext.Provider value={{ preferences, update, persisted }}>{children}</EditorPreferencesContext.Provider>;
}
