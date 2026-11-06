import type { Competency, Story, StoryContext, StoryCreate, StorySection } from "@/api/types";

/** What the editor holds. Tags are typed as one comma-separated line. */
export interface StoryForm {
  title: string;
  track: string;
  context: StoryContext | "";
  situation: string;
  task: string;
  action: string;
  result: string;
  reflection: string;
  notes: string;
  evidence: string;
  competencies: Competency[];
  tags: string;
  short_version: string;
  long_version: string;
  target_id: string;
}

export const emptyForm = (track: string): StoryForm => ({
  title: "", track, context: "", situation: "", task: "", action: "", result: "", reflection: "",
  notes: "", evidence: "", competencies: [], tags: "", short_version: "", long_version: "", target_id: "",
});

export function fromStory(s: Story): StoryForm {
  return {
    title: s.title, track: s.track ?? "", context: s.context ?? "", situation: s.situation, task: s.task,
    action: s.action, result: s.result, reflection: s.reflection, notes: s.notes, evidence: s.evidence,
    competencies: s.competencies, tags: s.tags.join(", "), short_version: s.short_version,
    long_version: s.long_version, target_id: s.target?.id ?? "",
  };
}

export function toBody(f: StoryForm): StoryCreate {
  return {
    title: f.title.trim(), track: f.track || null, context: f.context || null, situation: f.situation, task: f.task,
    action: f.action, result: f.result, reflection: f.reflection, notes: f.notes, evidence: f.evidence,
    competencies: f.competencies, tags: f.tags.split(",").map((t) => t.trim()).filter(Boolean),
    short_version: f.short_version, long_version: f.long_version, target_id: f.target_id || null,
  };
}

/** Only the fields that differ from the saved story (so a save never rewrites what you didn't touch). */
export function changes(base: StoryForm, now: StoryForm): Partial<StoryCreate> & { clear_target?: boolean } {
  const a = toBody(base);
  const b = toBody(now);
  const out: Record<string, unknown> = {};
  for (const k of Object.keys(b) as (keyof StoryCreate)[]) {
    if (JSON.stringify(a[k]) !== JSON.stringify(b[k])) out[k] = b[k];
  }
  if ("target_id" in out && !b.target_id) {
    delete out.target_id;
    out.clear_target = true;
  }
  return out;
}

export const sameForm = (a: StoryForm, b: StoryForm) => JSON.stringify(a) === JSON.stringify(b);

export const SECTION_FIELDS: StorySection[] = ["situation", "task", "action", "result", "reflection"];

export const storyDraftKey = (userId: string, storyId: string) => `story-draft:${userId}:${storyId}`;

/** A first draft from a story, in the order an answer is usually told. The learner edits it. */
export function draftFromStory(s: { situation: string; task: string; action: string; result: string; reflection: string }): string {
  return [[s.situation, s.task].filter((t) => t.trim()).join(" "), s.action, s.result, s.reflection]
    .map((t) => t.trim()).filter(Boolean).join("\n\n");
}
