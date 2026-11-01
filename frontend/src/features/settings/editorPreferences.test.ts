import { DEFAULT_EDITOR, EDITOR_KEY, loadEditorPreferences } from "./editorPreferences";

it("recovers from corrupt and out-of-range saved editor settings", () => {
  localStorage.setItem(EDITOR_KEY, "{broken");
  expect(loadEditorPreferences()).toEqual(DEFAULT_EDITOR);
  localStorage.setItem(EDITOR_KEY, JSON.stringify({ theme: "unknown", fontSize: 400, tabSize: -4, wordWrap: "sometimes" }));
  expect(loadEditorPreferences()).toEqual(DEFAULT_EDITOR);
});
