import type { Kit } from "@/api/types";

/**
 * The examples as this kit prepared them (docs/STORY_FRESHNESS.md): a story that changed since in a
 * way that matters prints as prepared, with a note; one deleted since prints from what was kept.
 */
export function preparedExamples(kit: Kit): { id: string; title: string; short_version: string; note: string | null }[] {
  const out = kit.stories.map((s) => {
    const state = s.freshness?.state;
    if (s.prepared && (state === "needs_review" || state === "kept")) {
      const note = state === "needs_review" ? `version ${s.prepared.revision}; the story has changed since` : `version ${s.prepared.revision}, kept as prepared`;
      return { id: s.id, title: s.prepared.title, short_version: s.prepared.short_version, note };
    }
    return { id: s.id, title: s.title, short_version: s.short_version, note: null };
  });
  for (const k of kit.kept_stories ?? []) {
    out.push({ id: k.id, title: k.title, short_version: k.short_version, note: "no longer in your story bank" });
  }
  return out;
}
