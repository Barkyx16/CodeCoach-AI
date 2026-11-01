import { useId } from "react";
import { Button } from "@/components/Button";
import { DEFAULT_EDITOR, FONT_SIZES, useEditorPreferences } from "./editorPreferences";

export function EditorPreferencesControls() {
  const id = useId();
  const { preferences, update, persisted } = useEditorPreferences();
  return (
    <div className="editor-preferences stack">
      <div className="editor-preferences__grid">
        <div className="field">
          <label className="field__label" htmlFor={`${id}-theme`}>Editor theme</label>
          <select id={`${id}-theme`} className="select" value={preferences.theme}
            onChange={(e) => update({ theme: e.target.value === "vs" ? "vs" : "codecoach-dark" })}>
            <option value="codecoach-dark">CodeCoach Dark</option><option value="vs">Light</option>
          </select>
        </div>
        <div className="field">
          <label className="field__label" htmlFor={`${id}-font`}>Font size</label>
          <select id={`${id}-font`} className="select" value={preferences.fontSize}
            onChange={(e) => update({ fontSize: Number(e.target.value) })}>
            {FONT_SIZES.map((size) => <option key={size} value={size}>{size} px</option>)}
          </select>
        </div>
        <div className="field">
          <label className="field__label" htmlFor={`${id}-tab`}>Indentation</label>
          <select id={`${id}-tab`} className="select" value={preferences.tabSize}
            onChange={(e) => update({ tabSize: Number(e.target.value) })}>
            <option value="2">2 spaces</option><option value="4">4 spaces</option>
          </select>
        </div>
      </div>
      <label className="row editor-preferences__wrap"><input type="checkbox" checked={preferences.wordWrap === "on"}
        onChange={(e) => update({ wordWrap: e.target.checked ? "on" : "off" })} />Wrap long lines</label>
      <div className="row">
        <Button size="sm" variant="ghost" onClick={() => update(DEFAULT_EDITOR)}>Restore editor defaults</Button>
        <p className="subtle" role={persisted ? "status" : "alert"}>{persisted
          ? "Saved in this browser. Applies to practice and interviews."
          : "Browser storage is unavailable. Settings apply for this visit only."}</p>
      </div>
    </div>
  );
}
