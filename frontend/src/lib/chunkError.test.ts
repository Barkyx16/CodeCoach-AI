import { isChunkLoadError } from "./chunkError";

describe("isChunkLoadError", () => {
  it.each([
    "Failed to fetch dynamically imported module: http://localhost/assets/SettingsPage-x.js", // Chromium
    "error loading dynamically imported module: http://localhost/assets/SettingsPage-x.js", // Firefox
    "Importing a module script failed.", // Safari
  ])("recognises %s", (message) => expect(isChunkLoadError(new Error(message))).toBe(true));

  it("doesn't treat other errors (or non-errors) as a failed download", () => {
    expect(isChunkLoadError(new Error("Cannot read properties of undefined"))).toBe(false);
    expect(isChunkLoadError("Failed to fetch dynamically imported module")).toBe(false);
  });
});
