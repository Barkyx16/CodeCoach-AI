import { useEditorPreferences } from "./editorPreferences";

/** CSS preview avoids downloading Monaco just to visit settings. */
export function EditorAppearancePreview() {
  const { preferences } = useEditorPreferences();
  return <div className="editor-appearance" data-theme={preferences.theme} aria-label="Editor appearance preview">
    <div className="editor-appearance__title"><span>Solution.java</span><span>Preview</span></div>
    <pre tabIndex={0} role="region" aria-label="Editor code preview" style={{ fontSize: preferences.fontSize, whiteSpace: preferences.wordWrap === "on" ? "pre-wrap" : "pre" }}><code><span>1</span> <b>class</b>{` Solution {
`}<span>2</span>{" ".repeat(preferences.tabSize)}<i>{"// A workspace that feels like yours."}</i>{`
`}<span>3</span>{` }`}</code></pre>
  </div>;
}
